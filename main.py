import flet as ft
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import parsedate_to_datetime
from deep_translator import GoogleTranslator
import concurrent.futures

# -------------------------------------------------------------------
# 1. 데이터 처리 로직 (변동 없음)
# -------------------------------------------------------------------
def get_news_data(site_name, days_limit=7, limit_count=20):
    site_list = {
        "Hypebeast KR": "https://news.google.com/rss/search?q=site:hypebeast.kr/fashion&hl=ko&gl=KR&ceid=KR:ko",
        "Dazed Digital": "https://news.google.com/rss/search?q=site:dazeddigital.com/fashion&hl=en-US&gl=US&ceid=US:en",
        "Vogue US": "https://news.google.com/rss/search?q=site:vogue.com/fashion&hl=en-US&gl=US&ceid=US:en",
        "Highsnobiety": "https://news.google.com/rss/search?q=site:highsnobiety.com&hl=en-US&gl=US&ceid=US:en"
    }
    
    try:
        rss_url = site_list[site_name]
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(rss_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.find_all('item')
        
        raw_news = []
        for item in items:
            title_text = item.find('title').text
            if "Page " in title_text or "Category" in title_text: continue
            date_tag = item.find('pubdate')
            article_date_obj = datetime.now()
            display_date = ""
            is_recent = False
            
            if date_tag:
                try:
                    article_date_obj = parsedate_to_datetime(date_tag.text)
                    now = datetime.now(article_date_obj.tzinfo)
                    if (now - article_date_obj).days <= days_limit:
                        is_recent = True
                        display_date = article_date_obj.strftime("%Y-%m-%d")
                except: is_recent = True 
            else: is_recent = True

            if is_recent:
                if item.find('link').next_sibling: link = item.find('link').next_sibling.strip()
                else: link = item.find('link').text
                if "/page/" in link: continue
                raw_news.append({'title': title_text, 'link': link, 'date_str': display_date, 'real_date': article_date_obj})

        raw_news.sort(key=lambda x: x['real_date'], reverse=True)
        return raw_news[:limit_count]
    except Exception as e:
        print(f"Error: {e}")
        return []

def translate_text(text):
    try:
        if not any('\u3131' <= char <= '\u3163' or '\uac00' <= char <= '\ud7a3' for char in text):
            translator = GoogleTranslator(source='auto', target='ko')
            translated = translator.translate(text)
            if translated: return translated
    except: pass
    return text

# -------------------------------------------------------------------
# 2. 메인 앱 (UI) - 세련된 디자인 적용
# -------------------------------------------------------------------
def main(page: ft.Page):
    # [설정] 앱 기본 디자인: 매거진 스타일
    page.title = "ODM"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window_width = 400
    page.window_height = 800
    page.bgcolor = "white" # 완전한 화이트 배경
    
    # [Color Palette]
    ODM_RED = "#ca0000"
    ODM_BLACK = "#1a1a1a" # 완전 블랙보다 살짝 부드러운 블랙
    ODM_GREY = "#9e9e9e"

    # [데이터 저장소]
    scrapped_items = []

    # ----------------------------------------------------------------
    # UI 컴포넌트들
    # ----------------------------------------------------------------
    
    # 1. 상단 앱바 (화이트 배경 + 블랙 텍스트로 모던하게 변경)
    app_bar = ft.AppBar(
        title=ft.Text("ODM", size=24, weight=ft.FontWeight.W_900, color=ODM_BLACK, font_family="Serif"),
        center_title=False, # 왼쪽 정렬이 더 매거진 같음
        bgcolor="white",
        elevation=0, # 그림자 제거 (Flat Design)
        actions=[
            ft.IconButton(ft.icons.REFRESH_ROUNDED, icon_color=ODM_BLACK, tooltip="새로고침", on_click=lambda e: load_news(e)),
            ft.Container(width=10)
        ]
    )

    # 2. 리스트 컨테이너
    news_list_view = ft.Column(scroll="auto", expand=True, spacing=0) # 간격 0 (Divider로 구분)
    scrap_list_view = ft.Column(scroll="auto", expand=True, spacing=0)
    
    # 3. 로딩 바 (상단에 얇게)
    loading_spinner = ft.ProgressBar(color=ODM_RED, bgcolor="transparent", visible=False, height=2)
    
    # 4. 채널 선택 드롭다운 (심플하게)
    site_dropdown = ft.Dropdown(
        options=[
            ft.dropdown.Option("Hypebeast KR"),
            ft.dropdown.Option("Dazed Digital"),
            ft.dropdown.Option("Vogue US"),
            ft.dropdown.Option("Highsnobiety"),
        ],
        value="Hypebeast KR",
        text_size=15,
        text_style=ft.TextStyle(weight="bold", color=ODM_BLACK),
        border_color="transparent", # 테두리 없애고 텍스트만 보이게
        focused_border_color="transparent",
        icon_enabled=False, # 화살표 아이콘 제거 (텍스트 클릭 느낌)
        content_padding=15,
        on_change=lambda e: load_news(e)
    )

    # ----------------------------------------------------------------
    # 기능 함수들
    # ----------------------------------------------------------------

    def show_message(text):
        # 이모지 없는 깔끔한 스낵바
        page.show_snack_bar(
            ft.SnackBar(
                content=ft.Text(text, color="white", weight="bold"),
                bgcolor=ODM_BLACK,
                action="OK",
                action_color=ODM_RED
            )
        )

    def add_scrap(news_data):
        if any(item['title'] == news_data['title'] for item in scrapped_items):
            show_message("이미 저장된 기사입니다.")
        else:
            scrapped_items.append(news_data)
            show_message("저장되었습니다.")
            render_scraps()

    def delete_scrap(news_data):
        if news_data in scrapped_items:
            scrapped_items.remove(news_data)
            render_scraps()
            page.update()

    # [디자인 핵심] 매거진 스타일 리스트 아이템
    def create_list_item(news, is_scrap_mode=False):
        # 액션 버튼 (아이콘만 심플하게)
        if is_scrap_mode:
            action_icon = ft.icons.CLOSE # X 표시가 휴지통보다 세련됨
            action_tooltip = "삭제"
            action_func = lambda e: delete_scrap(news)
        else:
            action_icon = ft.icons.BOOKMARK_BORDER # 외곽선 아이콘이 더 깔끔함
            action_tooltip = "저장"
            action_func = lambda e: add_scrap(news)

        return ft.Container(
            content=ft.Column([
                # 1. 상단: 날짜 + 액션 버튼
                ft.Row([
                    ft.Text(news['date_str'], size=11, color=ODM_GREY, weight="bold"),
                    ft.IconButton(
                        icon=action_icon, 
                        icon_color=ODM_BLACK, 
                        icon_size=20,
                        tooltip=action_tooltip,
                        on_click=action_func,
                        style=ft.ButtonStyle(padding=0) # 패딩 줄임
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                
                # 2. 제목 (크고 진하게)
                ft.Text(news['title'], size=16, weight="bold", color=ODM_BLACK, height=1.4),
                
                ft.Container(height=10), # 여백
                
                # 3. READ 버튼 (직각 형태의 모던한 버튼)
                ft.Row([
                    ft.ElevatedButton(
                        "READ ARTICLE", # 영어 표기가 더 디자인적으로 보일 때가 있음
                        url=news['link'], 
                        bgcolor=ODM_BLACK, # 블랙 버튼
                        color="white",
                        style=ft.ButtonStyle(
                            shape=ft.RectangleBorder(), # 완전 직각
                            elevation=0, # 그림자 제거
                        ),
                        height=40,
                        expand=True # 가로 꽉 차게
                    )
                ])
            ]),
            padding=ft.padding.symmetric(vertical=20, horizontal=20),
            border=ft.border.only(bottom=ft.BorderSide(1, "#f0f0f0")), # 하단에만 아주 연한 줄
            bgcolor="white"
        )

    def load_news(e):
        loading_spinner.visible = True
        news_list_view.controls.clear()
        page.update()

        selected_site = site_dropdown.value
        raw_data = get_news_data(selected_site)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            titles = [news['title'] for news in raw_data]
            translated_titles = list(executor.map(translate_text, titles))

        for i, news in enumerate(raw_data):
            news['title'] = translated_titles[i] 
            item = create_list_item(news, is_scrap_mode=False)
            news_list_view.controls.append(item)

        loading_spinner.visible = False
        page.update()

    def render_scraps():
        scrap_list_view.controls.clear()
        if not scrapped_items:
            scrap_list_view.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.BOOKMARK_BORDER, size=40, color="#eeeeee"),
                        ft.Text("ARCHIVE IS EMPTY", color="#cccccc", weight="bold")
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.alignment.center,
                    padding=ft.padding.only(top=100)
                )
            )
        else:
            for news in scrapped_items:
                item = create_list_item(news, is_scrap_mode=True)
                scrap_list_view.controls.append(item)

    # ----------------------------------------------------------------
    # 탭 네비게이션
    # ----------------------------------------------------------------
    
    tab_1 = ft.Container(
        content=ft.Column([
            ft.Container(content=site_dropdown, border=ft.border.only(bottom=ft.BorderSide(1, ODM_BLACK))), # 드롭다운 밑에 진한 줄
            loading_spinner,
            news_list_view
        ], spacing=0),
    )
    
    tab_2 = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Text("ARCHIVE", size=20, weight="bold", color=ODM_RED), 
                padding=20,
                alignment=ft.alignment.center_left
            ),
            scrap_list_view
        ]),
        visible=False
    )

    def nav_change(e):
        index = e.control.selected_index
        if index == 0:
            tab_1.visible = True
            tab_2.visible = False
        else:
            tab_1.visible = False
            tab_2.visible = True
            render_scraps()
        page.update()

    # 하단 네비게이션 (심플 & 아이콘 위주)
    nav_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationDestination(
                icon=ft.icons.GRID_VIEW, # 일반적인 뉴스 아이콘보다 더 모던함
                selected_icon=ft.icons.GRID_VIEW_ROUNDED,
                label="NEWS"
            ),
            ft.NavigationDestination(
                icon=ft.icons.BOOKMARK_BORDER, 
                selected_icon=ft.icons.BOOKMARK,
                label="ARCHIVE"
            ),
        ],
        selected_index=0,
        on_change=nav_change,
        bgcolor="white",
        indicator_color="transparent", # 선택된 배경색 제거 (아이콘 색만 변하게)
        icon_color={
            ft.MaterialState.SELECTED: ODM_RED, # 선택되면 레드
            ft.MaterialState.DEFAULT: ODM_GREY  # 아니면 그레이
        },
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        elevation=0,
        border=ft.border.only(top=ft.BorderSide(1, "#f0f0f0")) # 상단에 연한 줄
    )

    # 앱 실행
    page.add(app_bar, ft.Column([tab_1, tab_2], expand=True), nav_bar)
    load_news(None)

ft.app(target=main)