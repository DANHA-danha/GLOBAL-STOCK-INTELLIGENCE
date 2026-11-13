from html import escape

import streamlit as st

from lib import data, flow, industry, insights, ui
from lib.glossary import term

flow.bar(1)
st.title("세계 경제가 어떻게 변했나")
st.caption("금리·환율·유가 같은 큰 숫자가 어떻게 바뀌었는지 보고, 그 변화가 어떤 산업으로 이어지는지 다음 단계에서 따라가요.")
ui.collected_caption()

if not data.has_any_series():
    ui.no_data_notice()

# ---------- 지금 보이는 변화 → 다음 단계 ----------
st.subheader("지금 지표로 보이는 변화")
now = industry.detect_now()
if not now:
    st.caption("금리·환율·유가에서 최근 뚜렷한 변화가 보이지 않아요. 다음 단계에서 궁금한 변화를 직접 골라 볼 수 있어요.")
    flow.next_button(2, "산업과 회사에서 변화 직접 고르기", key="eco_pick")
cols = st.columns(min(len(now), 3) or 1)
for i, (did, why) in enumerate(now.items()):
    d = industry.driver(did)
    if not d:
        continue
    ups = [e["industry"] for e in d["effects"] if e["sign"] == "up"]
    downs = [e["industry"] for e in d["effects"] if e["sign"] == "down"]
    with cols[i % len(cols)], st.container(border=True, key=f"eco_now_{did}"):
        st.markdown(
            f'<div class="sl-now-card"><div class="sl-insight-title">{escape(d["name"])}</div>'
            f'<div class="sl-hint">{escape(why)}</div>'
            f'<div class="sl-now-eff"><span class="is-up"><b>▲</b> {escape(", ".join(ups) or "—")}</span>'
            f'<span class="is-down"><b>▼</b> {escape(", ".join(downs) or "—")}</span></div></div>',
            unsafe_allow_html=True,
        )
        flow.next_button(2, "어떤 산업에 영향을 줄까", key=f"eco_go_{did}", driver=did, industry=None, company=None)

# ---------- 연결 고리 ----------
st.subheader("숫자가 말하는 것")
st.caption("지표를 정해진 규칙으로 읽은 결과예요. 경제지표 하나로 주가가 정해지지 않으니 '가능성'으로 봐 주세요.")
items = insights.build()
if not items:
    st.caption("지표가 쌓이면 여기에 설명이 나와요.")
cols = st.columns(2)
for i, it in enumerate(items):
    with cols[i % 2], st.container(border=True):
        ui.insight_card(it, border=False)
        if it.watch:
            st.caption(f"다음에 볼 것: {it.watch}")
        tcols = st.columns(len(it.terms) or 1)
        for tc, t in zip(tcols, it.terms):
            with tc:
                term(t)

# ---------- 비교 ----------
st.subheader("한국 vs 미국 기준금리")
term("한미 금리차")
ui.line_chart(["kr_base_rate", "us_fed_upper"], years=10, height=340)
_kr, _us = data.latest("kr_base_rate"), data.latest("us_fed_upper")
if _kr and _us:
    gap = _kr.value - _us.value
    ui.reading(
        f"지금 한국 <b>{_kr.value:.2f}%</b>, 미국 <b>{_us.value:.2f}%</b>(상단)로 "
        + (f"미국이 <b>{-gap:.2f}%p</b> 높아요. 달러 예금·채권이 더 매력적이라 원화가 약해지는 쪽으로 압력이 생길 수 있어요."
           if gap < 0 else f"한국이 <b>{gap:.2f}%p</b> 높거나 같아요. 원화 자산의 매력이 커지는 쪽이에요.")
    )

st.subheader("미국 장단기 금리")
term("장단기 금리차")
ui.line_chart(["us_10y", "us_2y"], years=10, height=340)
_l, _s = data.latest("us_10y"), data.latest("us_2y")
if _l and _s:
    sp = _l.value - _s.value
    ui.reading(
        f"10년 <b>{_l.value:.2f}%</b> − 2년 <b>{_s.value:.2f}%</b> = <b>{sp:+.2f}%p</b>. "
        + ("10년 금리가 더 높은 보통 상태예요. 두 선이 뒤집히면(2년이 위로) 경기 둔화 신호로 읽어요."
           if sp >= 0 else "2년 금리가 더 높은 역전 상태예요. 시장이 앞으로 경기 둔화와 금리 인하를 예상한다는 신호로 읽어요.")
    )

# ---------- 나라별 (자세히) ----------
with st.expander("나라별 지표 자세히 보기 (한국·미국·유로존·일본·중국·원자재)"):
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


st.divider()
ui.disclaimer()
