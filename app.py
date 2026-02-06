import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import parsedate_to_datetime
from deep_translator import GoogleTranslator
import concurrent.futures
import base64
import os

# -------------------------------------------------------------------
# 1. 페이지 설정
# -------------------------------------------------------------------
st.set_page_config(
    page_title="ODM",       
    page_icon="logo.png",   
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# -------------------------------------------------------------------
# [핵심] 홈 화면 추가 시 아이콘/이름 강제 적용 함수
# -------------------------------------------------------------------
def setup_app_icon():
    """
    logo.png 파일을 읽어서 아이폰/안드로이드 홈 화면 아이콘으로 강제 등록하는 HTML 코드를 주입합니다.
    """
    logo_path = "logo.png"
    
    # 1. 로고 파일이 있으면 Base64 코드로 변환 (이미지를 글자로 바꿈)
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            data = f.read()
            encoded_image = base64.b64encode(data).decode()
        
        # 2. HTML 헤더에 아이콘 정보 강제 주입
        # apple-touch-icon: 아이폰용
        # apple-mobile-web-app-title: 앱 이름 설정
        st.markdown(
            f"""
            <style>
            </style>
            <link rel="apple-touch-icon" sizes="180x180" href="data:image/png;base64,{encoded_image}">
            <link rel="icon" type="image/png" sizes="32x32" href="data:image/png;base64,{encoded_image}">
            <link rel="icon" type="image/png" sizes="16x16" href="data:image/png;base64,{encoded_image}">
            <meta name="apple-mobile-web-app-title" content="ODM">
            <meta name="application-name" content="ODM">
            """,
            unsafe_allow_html=True
        )

# 함수 실행 (화면 그리기 전에 설정)
setup_app_icon()

# -------------------------------------------------------------------
# [메모리] 세션 상태 초기화
# -------------------------------------------------------------------
if 'scrapped_news' not in st.session_state:
    st.session_state.scrapped_news = []

if 'current_news' not in st.session_state:
    st.session_state.current_news = []

# -------------------------------------------------------------------
# [디자인] CSS 스타일 (#ca0000 테마 + 모바일 최적화)
# -------------------------------------------------------------------
st.markdown("""
    <style>
    /* 상단 여백 확보 */
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* 전체 배경 및 폰트 */
    .stApp {
        background-color: #ffffff;
        color: #000000;
        font-family: sans-serif;
    }
    
    /* 사이드바 스타일 (#ca0000) */
    section[data-testid="stSidebar"] {
        background-color: #ca0000;
    }
    section[data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    button[kind="header"] {
        color: #000000 !important;
    }

    /* 메인 타이틀 */
    h1 {
        font-size: 1.6rem !important;
        font-weight: 800 !important;
        color: #ca0000 !important;
        margin-bottom: 0rem !important;
    }
    
    /* 뉴스 카드 스타일 */
    div[data-testid="stContainer"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    h3 {
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        color: #000000 !important;
        margin-bottom: 0.3rem !important;
    }
    .stCaption {
        font-size: 0.8rem !important;
        color: #666666 !important;
    }
    
    /* 버튼 스타일 (Red) */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #ca0000 !important;
        color: #ffffff !important;
        border: none;
        font-weight: bold;
        font-size: 0.9rem !important;
    }
    .stButton>button:hover {
        background-color: #a00000 !important;
    }
    
    /* 링크 스타일 */
    a {
        text-decoration: none;
        color: #ca0000 !important;
        font-weight: 600;
        font-size: 0.85rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------------
# 사이트 목록
# -------------------------------------------------------------------
site_list = {
    "Hypebeast KR": "https://news.google.com/rss/search?q=site:hypebeast.kr/fashion&hl=ko&gl=KR&ceid=KR:ko",
    "Dazed Digital": "https://news.google.com/rss/search?q=site:dazeddigital.com/fashion&hl=en-US&gl=US&ceid=US:en",
    "Vogue US": "https://news.google.com/rss/search?q=site:vogue.com/fashion&hl=en-US&gl=US&ceid=US:en",
    "Highsnobiety": "https://news.google.com/rss/search?q=site:highsnobiety.com&hl=en-US&gl=US&ceid=US:en"
}

# -------------------------------------------------------------------
# 사이드바
# -------------------------------------------------------------------
with st.sidebar:
    st.header("ODM MENU")
    
    menu = st.radio("이동", ["실시간 뉴스", "나의 스크랩"])
    st.write("---")

    if menu == "실시간 뉴스":
        st.subheader("뉴스 필터")
        selected_site_name = st.radio("채널 선택", list(site_list.keys()))
        enable_translation = st.toggle("한국어 번역", value=True)
        limit_option = st.slider("기사 개수", 10, 50, 20)
        days_option = st.slider("기간 (일)", 1, 30, 7)
    
    st.caption("닫으면 화면이 넓어집니다.")

# -------------------------------------------------------------------
# 함수
# -------------------------------------------------------------------
def process_single_news(news_item):
    title = news_item['title']
    if " - " in title:
        title = title.rsplit(" - ", 1)[0]
    
    if enable_translation:
        try:
            if not any('\u3131' <= char <= '\u3163' or '\uac00' <= char <= '\ud7a3' for char in title):
                translator = GoogleTranslator(source='auto', target='ko')
                translated = translator.translate(title)
                if translated:
                    title = translated
        except:
            pass 
    news_item['title'] = title
    return news_item

def add_to_scrap(item):
    if item not in st.session_state.scrapped_news:
        st.session_state.scrapped_news.append(item)
        st.toast(f"저장 완료: {item['title'][:10]}...")
    else:
        st.toast("이미 저장된 기사입니다.")

def remove_from_scrap(item):
    st.session_state.scrapped_news.remove(item)
    st.rerun()

# -------------------------------------------------------------------
# 메인 화면 로직
# -------------------------------------------------------------------

# 1. 실시간 뉴스 화면
if menu == "실시간 뉴스":
    st.title(selected_site_name)

    if st.button("뉴스 새로고침", type="primary"):
        status_area = st.empty()
        status_area.caption('데이터 로딩 중...')
        
        try:
            rss_url = site_list[selected_site_name]
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(rss_url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.find_all('item')
            
            raw_news_list = []
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
                        if (now - article_date_obj).days <= days_option:
                            is_recent = True
                            display_date = article_date_obj.strftime("%Y-%m-%d")
                    except:
                        is_recent = True 
                else:
                    is_recent = True

                if is_recent:
                    if item.find('link').next_sibling:
                        link = item.find('link').next_sibling.strip()
                    else:
                        link = item.find('link').text
                    if "/page/" in link: continue

                    raw_news_list.append({
                        'title': title_text,
                        'link': link,
                        'date_str': display_date,
                        'real_date': article_date_obj 
                    })

            raw_news_list.sort(key=lambda x: x['real_date'], reverse=True)
            target_news = raw_news_list[:limit_option]

            if target_news:
                final_news_list = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    results = executor.map(process_single_news, target_news)
                    for result in results:
                        final_news_list.append(result)
                
                st.session_state.current_news = final_news_list
                status_area.empty()
            else:
                status_area.warning("새로운 소식이 없습니다.")
                st.session_state.current_news = []
                
        except Exception as e:
            st.error(f"오류: {e}")

    # 목록 표시
    if st.session_state.current_news:
        for i, news in enumerate(st.session_state.current_news):
            with st.container(border=True):
                st.subheader(news['title'])
                st.caption(f"{news['date_str']}")
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.link_button("기사 읽기", news['link'], use_container_width=True)
                with col2:
                    if st.button("스크랩", key=f"scrap_{i}"):
                        add_to_scrap(news)

# 2. 나의 스크랩 화면
elif menu == "나의 스크랩":
    st.title("나의 스크랩")
    st.caption("저장한 기사를 확인하세요. (브라우저를 닫으면 초기화됩니다)")
    
    if st.session_state.scrapped_news:
        for i, news in enumerate(st.session_state.scrapped_news):
            with st.container(border=True):
                st.subheader(news['title'])
                st.caption(f"저장일: {news['date_str']}")
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.link_button("기사 읽기", news['link'], use_container_width=True)
                with col2:
                    if st.button("삭제", key=f"del_{i}"):
                        remove_from_scrap(news)
    else:
        st.info("저장된 기사가 없습니다.")