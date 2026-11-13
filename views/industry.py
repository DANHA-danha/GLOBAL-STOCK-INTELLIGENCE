import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import industry, ui
from lib.glossary import ask, term

UP, DOWN = "#2d7a4b", "#b5452c"

st.title("산업 지도")
st.caption("경제가 이렇게 바뀌면 어떤 산업이 유리하거나 불리해질 수 있는지, 그리고 관심 종목 중 어디가 해당되는지 이어서 봐요.")

drivers = industry.drivers()
now = industry.detect_now()

# ---------- 지금 해당되는 변화 ----------
st.subheader("지금 지표로 보이는 변화")
if now:
    for did, why in now.items():
        d = industry.driver(did)
        if d:
            st.success(f"**{d['name']}** · {why}", icon=":material/trending_flat:")
else:
    st.caption("금리·환율·유가에서 최근 뚜렷한 변화가 보이지 않아요. 아래에서 궁금한 변화를 골라 보세요.")
st.caption("AI 투자, 중국 경기, 관세, 방위비, 친환경 정책은 숫자 하나로 판단하기 어려워 직접 골라 보는 항목이에요.")

# ---------- 변화 고르기 ----------
labels = {d["id"]: ("● " if d["id"] in now else "") + d["name"] for d in drivers}
default = next(iter(now), drivers[0]["id"])
did = st.pills("경제 변화 고르기", list(labels), default=default, format_func=labels.get, key="ind_driver") or default
d = industry.driver(did)

st.markdown(f"### {d['name']}")
st.write(d["summary"])
term(d["term"], ask(d["term"]))

ups = [e for e in d["effects"] if e["sign"] == "up"]
downs = [e for e in d["effects"] if e["sign"] == "down"]

# ---------- 흐름도 ----------
labels_n, colors_n = [d["name"]], ["#5d6b75"]
src, dst, val, lcol = [], [], [], []
for e in d["effects"]:
    labels_n.append(e["industry"])
    colors_n.append(UP if e["sign"] == "up" else DOWN)
    i_ind = len(labels_n) - 1
    src.append(0); dst.append(i_ind); val.append(2)
    lcol.append("rgba(45,122,75,0.35)" if e["sign"] == "up" else "rgba(181,69,44,0.35)")
    for s in industry.stocks_in(e.get("universe", [])):
        name = s["name"]
        if name not in labels_n:
            labels_n.append(name)
            colors_n.append("#a9b7bf")
        src.append(i_ind); dst.append(labels_n.index(name)); val.append(1)
        lcol.append("rgba(169,183,191,0.45)")
fig = go.Figure(go.Sankey(
    arrangement="snap",
    node=dict(label=labels_n, color=colors_n, pad=18, thickness=14, line=dict(width=0)),
    link=dict(source=src, target=dst, value=val, color=lcol, hovertemplate="%{source.label} → %{target.label}<extra></extra>"),
))
fig.update_layout(height=max(260, 46 * (len(labels_n) - 1)), margin=dict(l=8, r=8, t=10, b=10),
                  font=dict(size=13), paper_bgcolor="rgba(0,0,0,0)")
ui.chart(fig)
st.caption("초록은 유리해질 수 있는 산업, 빨강은 불리해질 수 있는 산업, 회색은 관심 종목 목록에 있는 해당 종목이에요.")


def stock_row(s: dict) -> None:
    r = industry.recent_return(s["code"])
    c1, c2 = st.columns([3, 2])
    with c1:
        if st.button(f"{s['name']}", key=f"go_{did}_{s['code']}", icon=":material/apartment:", help="기업 페이지로 이동"):
            st.session_state["company_code"] = s["code"]
            st.switch_page("views/company.py")
    with c2:
        if r is not None:
            st.markdown(f"<span style='color:{UP if r >= 0 else DOWN}'>최근 3개월 {r:+.1f}%</span>", unsafe_allow_html=True)


left, right = st.columns(2, gap="large")
for col, title, items, color in ((left, "유리해질 수 있는 산업", ups, UP), (right, "불리해질 수 있는 산업", downs, DOWN)):
    with col:
        st.markdown(f"<h4 style='color:{color}'>{title}</h4>", unsafe_allow_html=True)
        if not items:
            st.caption("뚜렷하게 정리된 산업이 없어요.")
        for e in items:
            with st.container(border=True):
                st.markdown(f"**{e['industry']}**")
                st.write(e["why"])
                ss = industry.stocks_in(e.get("universe", []))
                if ss:
                    for s in ss:
                        stock_row(s)
                else:
                    st.caption("관심 종목 목록에 해당 종목이 없어요. config/universe.yaml에 추가할 수 있어요.")

st.warning(d["caution"], icon=":material/lightbulb:")
if d["id"] in ("rate_cut", "rate_hike"):
    st.page_link("views/events.py", label="과거 금리 결정 때 실제로 어땠는지 데이터로 확인하기", icon=":material/arrow_forward:")

# ---------- 전체 표 ----------
st.subheader("전체 한눈에 보기")
inds: list[str] = []
for dd in drivers:
    for e in dd["effects"]:
        if e["industry"] not in inds:
            inds.append(e["industry"])
grid = pd.DataFrame("", index=inds, columns=[dd["name"] for dd in drivers])
for dd in drivers:
    for e in dd["effects"]:
        grid.loc[e["industry"], dd["name"]] = "▲" if e["sign"] == "up" else "▼"
grid.index.name = "산업"
ui.table(grid.reset_index(), hide_index=True)
st.caption("▲ 유리해질 수 있음 · ▼ 불리해질 수 있음. 일반적으로 알려진 경로를 정리한 것이고, 실제 주가는 기업 실적과 이미 반영된 기대에 따라 달라요. "
           "연결은 config/industry_map.yaml에서 고치거나 늘릴 수 있어요.")
st.divider()
ui.disclaimer()
