import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import stocks, ui
from lib.glossary import ask, term

st.title("기업 페이지")
st.caption("종목 하나를 골라 무슨 회사인지, 돈을 얼마나 버는지, 주가가 어떻게 움직였는지 봐요.")

uni = stocks.universe()["stocks"]
if not stocks.has_any():
    st.info(
        "아직 종목 데이터를 받지 않았어요. `.env`에 `DART_API_KEY`를 넣고 "
        "`python3 scripts/collect_stocks.py`를 실행하면 채워져요. 주가는 키 없이도 받아요.",
        icon=":material/database:",
    )

labels = {s["code"]: f"{s['name']} ({s['code']}) · {s['industry']}" for s in uni}
code = st.selectbox("종목", list(labels), format_func=labels.get, key="company_code")
s = stocks.stock(code)
us = s["market"] == "US"
cur = "달러" if us else "원"
m = stocks.metrics(code)
inf = stocks.info(code)

# ---------- 개요 ----------
st.subheader(s["name"])
bits = [s["market"], s["industry"]]
if inf.get("ceo_nm"):
    bits.append(f"대표 {inf['ceo_nm']}")
if inf.get("est_dt"):
    e = inf["est_dt"]
    bits.append(f"설립 {e[:4]}.{e[4:6]}")
st.caption(" · ".join(bits))
if inf.get("hm_url"):
    url = inf["hm_url"] if inf["hm_url"].startswith("http") else "https://" + inf["hm_url"]
    st.caption(f"[회사 홈페이지]({url})")

def pfmt(v):
    if v is None:
        return "—"
    return f"${v:,.2f}" if us else f"{v:,.0f}원"

c = st.columns(4)
c[0].metric("현재 주가", pfmt(m.price), help=f"{m.price_date:%Y-%m-%d} 종가" if m.price_date is not None else None, border=True)
c[1].metric("52주 최고", pfmt(m.high_52w), border=True)
c[2].metric("52주 최저", pfmt(m.low_52w), border=True)
c[3].metric("시가총액", stocks.won(m.market_cap) if m.market_cap else "—",
            help="보통주 발행주식수 × 현재 주가로 계산한 근사치예요", border=True)

# ---------- 투자 지표 ----------
st.subheader("투자 지표")
if m.fin_year:
    st.caption(f"{m.fin_year}년 사업보고서(연간) 재무와 현재 주가로 계산했어요. 증권사 앱 숫자와 조금 다를 수 있어요.")
elif us:
    st.caption("미국 종목의 재무제표는 다음 단계에서 추가해요. 지금은 주가와 배당만 보여줘요.")

def pct(v):
    return "—" if v is None else f"{v:.1f}%"

def times(v):
    return "—" if v is None else f"{v:.1f}배"

items = [
    ("PER", times(m.per), "PER"),
    ("PBR", times(m.pbr), "PBR"),
    ("ROE", pct(m.roe), "ROE"),
    ("영업이익률", pct(m.op_margin), "영업이익률"),
    ("부채비율", pct(m.debt_ratio), "부채비율"),
    ("배당수익률", pct(m.div_yield), "배당수익률"),
]
cols = st.columns(6)
for col, (lab, val, t) in zip(cols, items):
    with col:
        st.metric(lab, val, border=True)
        term(t, ask(t))

# ---------- 주가 ----------
st.subheader("주가 흐름")
px = stocks.prices(code)
if px is None:
    st.caption("주가 데이터가 아직 없어요.")
else:
    period = st.segmented_control("기간", ["1년", "3년", "5년", "10년"], default="3년", key="px_period")
    yrs = int((period or "3년").rstrip("년"))
    v = px[px["date"] >= px["date"].max() - pd.DateOffset(years=yrs)]
    bcode, bname = stocks.benchmark_for(code)
    bpx = stocks.prices(bcode)
    compare = st.toggle(f"{bname}와 비교 (시작점을 100으로 맞춰서)", value=False, key="px_compare")

    fig = go.Figure()
    if compare and bpx is not None:
        b = bpx[bpx["date"] >= v["date"].iloc[0]]
        fig.add_trace(go.Scatter(x=v["date"], y=v["adj_close"] / v["adj_close"].iloc[0] * 100, name=s["name"],
                                 line=dict(color=ui.ACCENT, width=2.2)))
        fig.add_trace(go.Scatter(x=b["date"], y=b["close"] / b["close"].iloc[0] * 100, name=bname,
                                 line=dict(color="#888", width=1.6)))
        fig.update_yaxes(title="시작=100")
    else:
        fig.add_trace(go.Scatter(x=v["date"], y=v["close"], name="종가", line=dict(color=ui.ACCENT, width=2.2),
                                 hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f}<extra></extra>"))
        mdd, pk, tr = stocks.max_drawdown(v.set_index("date")["close"])
        if pk is not None and tr is not None and mdd < -5:
            fig.add_vrect(x0=pk, x1=tr, fillcolor="#c2603c", opacity=0.08, line_width=0)
            fig.add_annotation(x=tr, y=float(v.set_index("date").loc[tr, "close"]), text=f"최대 낙폭 {mdd:.0f}%",
                               showarrow=True, arrowhead=0, ay=30, font=dict(color="#c2603c"))
    fig.update_layout(height=360, margin=dict(l=8, r=8, t=10, b=8), hovermode="x unified",
                      legend=dict(orientation="h", y=-0.15), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    term("MDD", "최대 낙폭(MDD)이란?")

    ar = stocks.annual_returns(code)
    if ar is not None and not ar.empty:
        st.markdown("**연도별 수익률** (배당 포함)")
        bar = go.Figure(go.Bar(
            x=[f"{y}{'*' if p else ''}" for y, p in zip(ar["year"], ar["partial"])], y=ar["return"],
            marker_color=["#2d7a4b" if r >= 0 else "#b5452c" for r in ar["return"]],
            text=[f"{r:+.0f}%" for r in ar["return"]], textposition="outside",
        ))
        bar.update_layout(height=280, margin=dict(l=8, r=8, t=10, b=8), plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)", yaxis=dict(ticksuffix="%", gridcolor="rgba(128,128,128,0.2)"),
                          xaxis=dict(type="category"))
        st.plotly_chart(bar, width="stretch", config={"displayModeBar": False})
        st.caption("* 올해는 1월 1일부터 지금까지예요.")

# ---------- 재무 ----------
fin = stocks.financials(code)
if fin is not None and not fin.empty:
    st.subheader("실적 추이")
    st.caption(f"{fin['basis'].iloc[-1]} 재무제표 기준, 단위 억 원")
    f = fin.copy()
    for col in ["revenue", "operating_income", "net_income", "assets", "liabilities", "equity"]:
        f[col] = f[col] / 1e8
    g = go.Figure()
    f["year"] = f["year"].astype(str)
    g.add_trace(go.Bar(x=f["year"], y=f["revenue"], name="매출", marker_color="#a9c4cf"))
    g.add_trace(go.Bar(x=f["year"], y=f["operating_income"], name="영업이익", marker_color=ui.ACCENT))
    g.add_trace(go.Bar(x=f["year"], y=f["net_income"], name="당기순이익", marker_color="#c2603c"))
    g.update_layout(barmode="group", height=320, margin=dict(l=8, r=8, t=10, b=8), legend=dict(orientation="h", y=-0.15),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    g.update_yaxes(gridcolor="rgba(128,128,128,0.2)", tickformat=",")
    g.update_xaxes(type="category")
    st.plotly_chart(g, width="stretch", config={"displayModeBar": False})

    t = pd.DataFrame({
        "연도": f["year"].astype(str),
        "매출(억)": f["revenue"].round(0),
        "영업이익(억)": f["operating_income"].round(0),
        "당기순이익(억)": f["net_income"].round(0),
        "영업이익률(%)": (fin["operating_income"] / fin["revenue"] * 100).round(1),
        "ROE(%)": (fin["net_income"] / fin["equity"] * 100).round(1),
        "부채비율(%)": (fin["liabilities"] / fin["equity"] * 100).round(1),
    })
    st.dataframe(t, hide_index=True, width="stretch",
                 column_config={k: st.column_config.NumberColumn(format="localized") for k in ["매출(억)", "영업이익(억)", "당기순이익(억)"]})
    tc = st.columns(4)
    for col, name in zip(tc, ["영업이익", "당기순이익", "ROE", "부채비율"]):
        with col:
            term(name, ask(name))
    st.caption("출처: 금융감독원 Open DART 사업보고서 주요계정")

st.page_link("views/simulator.py", label="이 종목으로 모의투자 해보기", icon=":material/arrow_forward:")
st.divider()
ui.disclaimer()
