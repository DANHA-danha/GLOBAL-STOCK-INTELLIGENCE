import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import data, events, stocks, ui
from lib.glossary import ask, term

st.title("금리 결정 전후")
st.caption("미국이 기준금리를 바꿨던 날들을 모아, 그 전후로 주가가 평균적으로 어떻게 움직였는지 봐요.")

ev = events.fed_events()
if ev.empty:
    ui.no_data_notice()
    st.stop()
if not stocks.has_any():
    st.info("주가 데이터가 없어요. `python3 scripts/collect_stocks.py`를 먼저 실행해 주세요.", icon=":material/database:")
    st.stop()

# 다음 FOMC
up, _ = data.events()
nxt = up[(up["d_day"] >= 0) & (up["type"] == "미국 금리 결정")].head(1) if not up.empty else up
if not nxt.empty:
    n = nxt.iloc[0]
    st.info(f"다음 FOMC 금리 결정: {n['date']:%Y-%m-%d} (D-{int(n['d_day'])}). 과거에 비슷한 결정이 나왔을 때를 미리 살펴봐요.",
            icon=":material/event:")

# ---------- 조건 ----------
uni = stocks.universe()
names = {b["code"]: b["name"] for b in uni["benchmarks"]} | {s["code"]: s["name"] for s in uni["stocks"]}
with st.container(border=True):
    c1, c2 = st.columns([2, 3])
    with c1:
        direction = st.segmented_control("어떤 결정", ["인하", "인상"], default="인하", key="ev_dir") or "인하"
        only_first = st.toggle("사이클의 첫 결정만", value=False, key="ev_first",
                               help="인상·인하가 처음 시작된 날만 봐요. 연달아 내린 날은 앞 결정의 영향이 섞여 있어서요.")
    with c2:
        picks = st.multiselect("볼 종목·지수 (최대 4개)", list(names), default=["^KS11", "005930", "105560"],
                               format_func=lambda c: f"{names[c]} ({c})", max_selections=4, key="ev_picks")
    c3, c4 = st.columns(2)
    with c3:
        before = st.slider("발표 전 (거래일)", 5, 60, 20, step=5, key="ev_before")
    with c4:
        after = st.slider("발표 후 (거래일)", 5, 120, 60, step=5, key="ev_after")

sel = ev[ev["direction"] == direction]
if only_first:
    sel = sel[sel["first"]]
first_date = min((stocks.prices(c)["date"].min() for c in picks if stocks.prices(c) is not None), default=None)
if first_date is not None:
    sel = sel[sel["effective"] > pd.Timestamp(first_date) + pd.Timedelta(days=40)]

if sel.empty or not picks:
    st.warning("조건에 맞는 금리 결정이 없어요. 조건을 바꿔 보세요.")
    st.stop()

st.markdown(f"**{len(sel)}번의 금리 {direction}** "
            f"({sel['announced'].min():%Y-%m} ~ {sel['announced'].max():%Y-%m}) 전후 평균이에요. 반응 전날 주가를 100으로 맞췄어요.")

# ---------- 평균 경로 차트 ----------
palette = [ui.ACCENT, "#c2603c", "#6b7f2a", "#7a5aa6"]
fig = go.Figure()
results = {}
for i, code in enumerate(picks):
    paths, avg = events.study(code, sel, before, after)
    results[code] = (paths, avg)
    if avg.empty:
        continue
    if i == 0 and st.session_state.get("ev_each", False):
        for col in paths.columns:
            fig.add_trace(go.Scatter(x=paths.index, y=paths[col], mode="lines", showlegend=False,
                                     line=dict(color=palette[0], width=0.8), opacity=0.25,
                                     hovertemplate=f"{pd.Timestamp(col):%Y-%m-%d}<br>%{{y:.1f}}<extra></extra>"))
    fig.add_trace(go.Scatter(x=avg.index, y=avg.values, name=names[code], mode="lines",
                             line=dict(color=palette[i % 4], width=2.6),
                             hovertemplate="%{x}일<br>%{y:.1f}<extra>" + names[code] + "</extra>"))
fig.add_vline(x=0, line_dash="dot", line_color="#999")
fig.add_hline(y=100, line_color="rgba(128,128,128,0.4)")
fig.add_annotation(x=0, y=1, yref="paper", text="반응한 날", showarrow=False, xanchor="left", yanchor="top",
                   font=dict(color="#888"))
fig.update_layout(height=420, margin=dict(l=8, r=8, t=10, b=8), hovermode="x unified",
                  legend=dict(orientation="h", y=-0.18), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
fig.update_xaxes(title="발표 기준 거래일 (음수 = 발표 전)", zeroline=False)
fig.update_yaxes(title="반응 전날 = 100", gridcolor="rgba(128,128,128,0.2)")
ui.chart(fig)
st.toggle(f"{names[picks[0]]}의 사건별 경로도 흐리게 보기", key="ev_each")

# ---------- 요약 표 ----------
st.subheader("한눈에 보기")
rows = []
for code in picks:
    paths, avg = results[code]
    if avg.empty:
        continue
    after20 = [events.ret(paths[c].dropna(), -1, 20) for c in paths.columns]
    after20 = [x for x in after20 if x is not None]
    rows.append({
        "종목·지수": names[code],
        f"발표 전 {before}일": events.ret(avg, -before, -1),
        "반응한 날": events.ret(avg, -1, 0),
        "20일 후": events.ret(avg, -1, 20),
        f"{after}일 후": events.ret(avg, -1, after),
        "20일 후 오른 비율": (sum(x > 0 for x in after20) / len(after20) * 100) if after20 else None,
        "사건 수": paths.shape[1],
    })
tbl = pd.DataFrame(rows)
fmt = {c: st.column_config.NumberColumn(format="%+.1f%%") for c in tbl.columns if c not in ("종목·지수", "사건 수", "20일 후 오른 비율")}
fmt["20일 후 오른 비율"] = st.column_config.NumberColumn(format="%.0f%%")
ui.table(tbl, hide_index=True, column_config=fmt)
st.caption("모두 평균 경로 기준 수익률이에요. '20일 후 오른 비율'은 사건별로 20거래일 뒤 주가가 반응 전날보다 높았던 비율이에요.")

# ---------- 사건 목록 ----------
with st.expander(f"금리 {direction} 목록 {len(sel)}건"):
    lst = []
    for _, e in sel.sort_values("announced", ascending=False).iterrows():
        r = {"발표일": e["announced"].strftime("%Y-%m-%d"), "변화": f"{e['change']:+.2f}%p",
             "결정 후 금리(상단)": f"{e['level']:.2f}%", "첫 결정": "예" if e["first"] else ""}
        for code in picks:
            paths, _ = results[code]
            col = e["announced"]
            r[f"{names[code]} 20일 후"] = events.ret(paths[col].dropna(), -1, 20) if col in paths.columns else None
        lst.append(r)
    lt = pd.DataFrame(lst)
    ui.table(lt, hide_index=True,
             column_config={c: st.column_config.NumberColumn(format="%+.1f%%") for c in lt.columns if c.endswith("20일 후")})

tc = st.columns(3)
for col, t in zip(tc, ["FOMC", "기준금리", "이벤트 스터디"]):
    with col:
        term(t, ask(t))

st.caption(
    "읽을 때 주의할 점: 사건 수가 적어서(대개 10건 안팎) 우연이 크게 섞여요. 연달아 내린 경우 앞뒤 결정의 효과가 겹쳐요. "
    "2020년 3월처럼 위기 때 급히 내린 인하는 주가 급락과 함께 나타나서 평균을 크게 끌어내려요. "
    "금리 결정만이 주가를 움직인 원인이라고 볼 수는 없어요."
)
st.divider()
ui.disclaimer()
