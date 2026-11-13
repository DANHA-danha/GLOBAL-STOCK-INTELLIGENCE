"""주식랩 — 실행: streamlit run app.py"""
import streamlit as st

from lib import ui

st.set_page_config(page_title="주식랩", page_icon=":material/monitoring:", layout="wide")

home = st.Page("views/home.py", title="홈", icon=":material/home:", default=True)
pages = {
    "": [home],
    # 이 앱의 중심 흐름: 세계 경제 → 산업과 회사 → 주가 → 내가 샀다면
    "따라가기": [
        st.Page("views/economy.py", title="1 세계 경제", icon=":material/public:"),
        st.Page("views/industry.py", title="2 산업과 회사", icon=":material/hub:"),
        st.Page("views/company.py", title="3 회사와 주가", icon=":material/show_chart:"),
        st.Page("views/simulator.py", title="4 내가 샀다면", icon=":material/savings:"),
    ],
    "더 알아보기": [
        st.Page("views/events.py", title="금리 결정 전후", icon=":material/timeline:"),
        st.Page("views/calendar.py", title="일정 캘린더", icon=":material/calendar_month:"),
        st.Page("views/tutor.py", title="용어 튜터", icon=":material/school:"),
    ],
}

nav = st.navigation(pages, position="top")
ui.style()
nav.run()
