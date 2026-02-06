import flet as ft
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import parsedate_to_datetime
from deep_translator import GoogleTranslator
import concurrent.futures
import traceback # 에러 추적용

# -------------------------------------------------------------------
# 1. 데이터 처리 로직 (에러 핸들링 강화)
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
        # 타임아웃 추가 (무한 로딩 방지)
        response = requests.get(rss_url, headers=headers, timeout=10)
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
        # 에러를 던져서 UI가 알게 함
        raise Exception(f"크롤링 에러: {str(e)}")

def translate_text(text):
    try:
        if not any('\u3131' <= char <= '\u3163' or '\uac00' <= char <= '\ud7a3' for char in text):
            translator = GoogleTranslator(source='auto', target='ko')
            translated = translator.translate(text)
            if translated: return translated
    except: pass
    return text

# -------------------------------------------------------------------
# 2. 메인 앱 (UI)
# -------------------------------------------------------------------
def main(page: ft.Page):
    # [설정]
    page.title = "ODM"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window_width = 400
    page.window_height = 800
    page.bgcolor = "white"
    
    ODM_RED = "#ca0000"
    ODM_BLACK = "#1a1a1a"
    ODM_GREY = "#9e9e9e"

    scrapped_items = []

    # ----------------------------------------------------------------
    # UI 컴포넌트
    # ----------------------------------------------------------------
    
    # 에러 메시지 보여주는 공간 (디버깅용)
    error_text = ft.Text("", color="red", size=14, selectable=True)
    
    app_bar = ft.AppBar(
        title=ft.Text("ODM", size=24, weight=ft.FontWeight.W_900, color=ODM_BLACK, font_family="Serif"),
        center_title=False,
        bgcolor="white",
        elevation=0,
        actions=[
            ft.IconButton(ft.icons.REFRESH_ROUNDED, icon_color=ODM_BLACK, on_click=lambda e: load_news(e)),
            ft.Container(width=10)
        ]
    )

    news_list_view = ft.Column(scroll="auto", expand=True, spacing=0)
    scrap_list_view = ft.Column(scroll="auto", expand=True, spacing=0)
    loading_spinner = ft.ProgressBar(color=ODM_RED, bgcolor="transparent", visible=False, height=2)
    
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
        border_color="transparent", 
        focused_border_color="transparent",
        icon_enabled=False,
        content_padding=15,
        on_change=lambda e: load_news(e)
    )

    # ----------------------------------------------------------------
    # 기능 함수들
    # ----------------------------------------------------------------

    def show_message(text):
        page.show_snack_bar(
            ft.SnackBar(content=ft.Text(text, color="white"), bgcolor=ODM_BLACK)
        )

    def create_list_item(news, is_scrap_mode=False):
        # 액션 버튼 (아이콘만 심플하게)
        if is_scrap_mode:
            action_icon = ft.icons.CLOSE
            action_func = lambda e: delete_scrap(news)
        else:
            action_icon = ft.icons.BOOKMARK_BORDER
            action_func = lambda e: add_scrap(news)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(news['date_str'], size=11, color=ODM_GREY, weight="bold"),
                    ft.IconButton(icon=action_icon, icon_color=ODM_BLACK, icon_size=20, on_click=action_func, style=ft.ButtonStyle(padding=0))
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text(news['title'], size=16, weight="bold", color=ODM_BLACK, height=1.4),
                ft.Container(height=10),
                ft.Row([
                    ft.ElevatedButton(
                        "READ ARTICLE", url=news['link'], bgcolor=ODM_BLACK, color="white",
                        style=ft.ButtonStyle(shape=ft.RectangleBorder(), elevation=0),
                        height=40, expand=True
                    )
                ])
            ]),
            padding=ft.padding.symmetric(vertical=20, horizontal=20),
            border=ft.border.only(bottom=ft.BorderSide(1, "#f0f0f0")),
            bgcolor="white"
        )

    # 스크랩 관련 함수
    def add_scrap(news_data):
        if any(item['title'] == news_data['title'] for item in scrapped_items):
            show_message("이미 저장됨")
        else:
            scrapped_items.append(news_data)
            show_message("저장됨")
            render_scraps()

    def delete_scrap(news_data):
        if news_data in scrapped_items:
            scrapped_items.remove(news_data)
            render_scraps()
            page.update()
            
    def render_scraps():
        scrap_list_view.controls.clear()
        if not scrapped_items:
            scrap_list_view.controls.append(ft.Text("보관함이 비었습니다.", color="grey"))
        else:
            for news in scrapped_items:
                scrap_list_view.controls.append(create_list_item(news, True))

    # [핵심] 뉴스 로드 함수 (철저한 에러 핸들링)
    def load_news(e):
        try:
            loading_spinner.visible = True
            error_text.value = "" # 에러 메시지 초기화
            news_list_view.controls.clear()
            page.update()

            selected_site = site_dropdown.value
            
            # 데이터 가져오기 (여기서 실패하면 except로 감)
            raw_data = get_news_data(selected_site)
            
            if not raw_data:
                error_text.value = "뉴스를 가져오지 못했습니다. (데이터 없음)"
                loading_spinner.visible = False
                page.update()
                return

            # 번역 시도 (번역이 실패해도 앱은 죽지 않게 함)
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    titles = [news['title'] for news in raw_data]
                    translated_titles = list(executor.map(translate_text, titles))
                    
                for i, news in enumerate(raw_data):
                    news['title'] = translated_titles[i]
            except Exception as trans_e:
                error_text.value = f"번역 중 오류 (무시하고 진행): {str(trans_e)}"
                # 번역 실패해도 원본으로 진행

            for news in raw_data:
                item = create_list_item(news, False)
                news_list_view.controls.append(item)

        except Exception as e:
            # 치명적인 에러 발생 시 화면에 출력
            error_msg = traceback.format_exc()
            error_text.value = f"오류 발생:\n{str(e)}\n\n{error_msg}"
            print(error_msg) # 로그용
            
        finally:
            loading_spinner.visible = False
            page.update()

    # ----------------------------------------------------------------
    # 탭 및 실행
    # ----------------------------------------------------------------
    
    tab_1 = ft.Container(content=ft.Column([
        ft.Container(content=site_dropdown, border=ft.border.only(bottom=ft.BorderSide(1, ODM_BLACK))),
        loading_spinner,
        ft.Container(content=error_text, padding=10), # 에러 메시지 표시 영역 추가
        news_list_view
    ], spacing=0))
    
    tab_2 = ft.Container(content=ft.Column([
        ft.Container(content=ft.Text("ARCHIVE", size=20, weight="bold", color=ODM_RED), padding=20),
        scrap_list_view
    ]), visible=False)

    def nav_change(e):
        if e.control.selected_index == 0:
            tab_1.visible = True
            tab_2.visible = False
        else:
            tab_1.visible = False
            tab_2.visible = True
            render_scraps()
        page.update()

    nav_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationDestination(icon=ft.icons.GRID_VIEW, label="NEWS"),
            ft.NavigationDestination(icon=ft.icons.BOOKMARK_BORDER, label="ARCHIVE"),
        ],
        on_change=nav_change,
        bgcolor="white",
        indicator_color="transparent",
        elevation=0
    )

    page.add(app_bar, ft.Column([tab_1, tab_2], expand=True), nav_bar)
    
    # 시작하자마자 로드하지 않고, 화면이 다 그려진 후 0.1초 뒤에 로드 (안정성 확보)
    # load_news(None) -> 자동 로딩 잠시 끔. 사용자가 새로고침 눌러보게 유도할 수도 있고, 
    # 혹은 안전하게 호출:
    load_news(None)

ft.app(target=main)
