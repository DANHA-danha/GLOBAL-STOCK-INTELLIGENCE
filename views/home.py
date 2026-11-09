import streamlit as st

from lib import data, glossary, insights, ui

st.title("주식랩")
st.markdown("##### 뉴스 속 숫자가 내 투자에 무슨 뜻인지, 하나씩 연결해 봐요.")
ui.collected_caption()

if not data.has_any_series():
    ui.no_data_notice()

st.subheader("오늘의 숫자")
cols = st.columns(4)
for col, key in zip(cols, ["kr_base_rate", "us_fed_upper", "kr_usdkrw", "us_10y"]):
    with col:
        ui.metric(key, with_country=True)

left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader("지금 숫자가 말하는 것")
    items = insights.build()
    if not items:
        st.caption("지표가 쌓이면 여기에 연결 고리 설명이 나와요.")
    for it in items[:3]:
        with st.container(border=True):
            st.markdown(f"**{it.title}**")
            st.caption(it.fact)
            st.write(" → ".join(it.chain))
    if items:
        st.page_link("views/economy.py", label="연결 고리 전체 보기", icon=":material/arrow_forward:")

with right:
    st.subheader("다가오는 일정")
    ev, types = data.events()
    upcoming = ev[ev["d_day"] >= 0].head(5) if not ev.empty else ev
    if upcoming.empty:
        st.caption("등록된 일정이 없어요.")
    for _, e in upcoming.iterrows():
        ui.event_row(e, types, compact=True)
    st.page_link("views/calendar.py", label="일정 전체 보기", icon=":material/arrow_forward:")

    st.subheader("오늘의 용어")
    with st.container(border=True):
        glossary.card(glossary.today_term())
    st.page_link("views/tutor.py", label="용어 튜터에서 퀴즈 풀기", icon=":material/arrow_forward:")

st.divider()
ui.disclaimer()
