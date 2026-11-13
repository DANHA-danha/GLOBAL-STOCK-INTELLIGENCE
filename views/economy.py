import streamlit as st

from lib import data, insights, ui
from lib.glossary import term

st.title("경제 상황판")
st.caption("주요 나라의 금리·물가·환율을 한눈에 보고, 그 숫자가 한국 증시에 어떻게 이어지는지 봐요.")
ui.collected_caption()

if not data.has_any_series():
    ui.no_data_notice()

# ---------- 연결 고리 ----------
st.subheader("연결 고리")
st.caption("지표를 정해진 규칙으로 읽은 결과예요. 경제지표 하나로 주가가 정해지지 않으니 '가능성'으로 봐 주세요.")
items = insights.build()
if not items:
    st.caption("지표가 쌓이면 여기에 설명이 나와요.")
cols = st.columns(2)
for i, it in enumerate(items):
    with cols[i % 2], st.container(border=True):
        st.markdown(f"**{it.title}**")
        st.caption(it.fact)
        for j, step in enumerate(it.chain):
            st.markdown(f"{'↳ ' if j else '• '}{step}")
        if it.watch:
            st.caption(f"다음에 볼 것: {it.watch}")
        tcols = st.columns(len(it.terms) or 1)
        for tc, t in zip(tcols, it.terms):
            with tc:
                term(t)

# ---------- 나라별 ----------
st.subheader("나라별 지표")
cfg = data.config()
months = st.segmented_control("변화 비교 기간", options=[1, 3, 12], default=1,
                              format_func=lambda m: {1: "1개월", 3: "3개월", 12: "1년"}[m])
tabs = st.tabs([c["name"] for c in cfg["countries"]])
for tab, c in zip(tabs, cfg["countries"]):
    with tab:
        st.caption(c.get("note", ""))
        keys = [s["key"] for s in c["series"]]
        for row in range(0, len(keys), 4):
            cs = st.columns(4)
            for col, k in zip(cs, keys[row:row + 4]):
                with col:
                    ui.metric(k, months=months or 1)

        rates = [s["key"] for s in c["series"] if s.get("unit") == "%"]
        others = [s["key"] for s in c["series"] if s.get("unit") != "%"]
        if rates:
            ui.line_chart(rates, years=5, title=f"{c['name']} 금리·물가 (%) 최근 5년")
        for k in others:
            s = data.series_def(k)
            ui.line_chart([k], years=5, title=f"{s['label']} 최근 5년", height=260)

        if c["code"] == "KR":
            ks = data.key_stats()
            if ks is not None and not ks.empty:
                st.markdown("**한국은행 주요 통계 (최신값)**")
                ui.table(
                    ks.rename(columns={"group": "분류", "name": "지표", "value": "값", "unit": "단위", "period": "기준"}),
                    hide_index=True,
                )
        if c["code"] == "CN":
            st.caption("중국 제조업 PMI는 무료 API가 없어 다음 단계에서 추가할 예정이에요.")

# ---------- 비교 ----------
st.subheader("한국 vs 미국 기준금리")
term("한미 금리차")
ui.line_chart(["kr_base_rate", "us_fed_upper"], years=10, height=340)

st.subheader("미국 장단기 금리")
term("장단기 금리차")
ui.line_chart(["us_10y", "us_2y"], years=10, height=340)

st.divider()
ui.disclaimer()
