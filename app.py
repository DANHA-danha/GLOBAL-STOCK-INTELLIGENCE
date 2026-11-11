"""주식랩 — 실행: streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="주식랩", page_icon=":material/monitoring:", layout="wide")

pages = [
    st.Page("views/home.py", title="홈", icon=":material/home:", default=True),
    st.Page("views/economy.py", title="경제 상황판", icon=":material/public:"),
    st.Page("views/company.py", title="기업 페이지", icon=":material/apartment:"),
    st.Page("views/simulator.py", title="모의투자", icon=":material/savings:"),
    st.Page("views/calendar.py", title="일정 캘린더", icon=":material/calendar_month:"),
    st.Page("views/tutor.py", title="용어 튜터", icon=":material/school:"),
]

nav = st.navigation(pages, position="top")
nav.run()
