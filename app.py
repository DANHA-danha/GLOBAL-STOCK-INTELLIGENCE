"""주식랩 — 실행: streamlit run app.py"""
import streamlit as st

from lib import ui

st.set_page_config(page_title="주식랩", page_icon=":material/monitoring:", layout="wide")

# 상단 메뉴에 전부 펼쳐 보여요. 앞의 다섯 개가 중심 흐름, 뒤의 세 개는 더 알아보기
pages = [
    st.Page("views/home.py", title="홈", icon=":material/home:", default=True),
    st.Page("views/economy.py", title="글로벌 경제", icon=":material/public:"),
    st.Page("views/industry.py", title="산업·기업 분석", icon=":material/hub:"),
    st.Page("views/company.py", title="종목 분석", icon=":material/show_chart:"),
    st.Page("views/simulator.py", title="투자 시뮬레이션", icon=":material/savings:"),
    st.Page("views/events.py", title="금리·시장 영향", icon=":material/timeline:"),
    st.Page("views/calendar.py", title="경제 이벤트", icon=":material/calendar_month:"),
    st.Page("views/tutor.py", title="금융 용어 사전", icon=":material/school:"),
]

nav = st.navigation(pages, position="top")
ui.style()
nav.run()
