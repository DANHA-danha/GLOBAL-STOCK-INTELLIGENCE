import streamlit as st

from lib import data, ui

st.title("일정 캘린더")
st.caption("시장을 크게 움직이는 금리 결정과 경제지표 발표 일정이에요.")

ev, types = data.events()
if ev.empty:
    st.info("등록된 일정이 없어요. data/events.yaml에 추가할 수 있어요.")
    st.stop()

kinds = sorted(ev["type"].dropna().unique().tolist())
picked = st.pills("종류", kinds, selection_mode="multi", default=kinds)
view = ev[ev["type"].isin(picked or kinds)]

up = view[view["d_day"] >= 0]
st.subheader(f"다가오는 일정 {len(up)}개")
month = None
for _, e in up.iterrows():
    m = f"{e['date']:%Y년 %m월}"
    if m != month:
        st.markdown(f"#### {m}")
        month = m
    ui.event_row(e, types)

past = view[view["d_day"] < 0]
if not past.empty:
    with st.expander(f"지난 일정 {len(past)}개"):
        for _, e in past.iloc[::-1].iterrows():
            ui.event_row(e, types, compact=True)

st.divider()
st.caption("FOMC·금통위 일정은 data/events.yaml, 미국 지표 발표일은 FRED에서 자동으로 받아요. "
           "FOMC 결과는 미국 동부 오후 2시, 한국 시간으로 다음 날 새벽 3~4시에 나와요.")
ui.disclaimer()
