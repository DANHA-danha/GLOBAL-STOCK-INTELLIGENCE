from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import data, stocks, ui
from lib.glossary import ask, term

st.title("모의투자")
st.caption("실제 돈 없이, 과거 특정 날짜에 샀다면 지금 얼마가 됐을지 계산해요.")

uni = stocks.universe()["stocks"]
labels = {s["code"]: f"{s['name']} ({s['code']})" for s in uni}
default = [st.session_state.get("company_code", uni[0]["code"])]

with st.container(border=True):
    c1, c2 = st.columns([3, 2])
    with c1:
        picks = st.multiselect("종목 (최대 3개)", list(labels), default=default, format_func=labels.get,
                               max_selections=3, key="sim_picks")
    with c2:
        start = st.date_input("매수 시작일", value=date(date.today().year - 3, date.today().month, 1),
                              min_value=date(2016, 1, 1), max_value=date.today(), key="sim_start")
    c3, c4, c5 = st.columns([2, 2, 3])
    with c3:
        mode = st.radio("방식", ["한 번에 투자", "매달 적립"], horizontal=True, key="sim_mode")
    with c4:
        if mode == "한 번에 투자":
            amount = st.number_input("투자금 (만원)", min_value=10, value=1000, step=100, key="sim_amt") * 10_000
        else:
            amount = st.number_input("매달 (만원)", min_value=1, value=50, step=10, key="sim_mon") * 10_000
    with c5:
        with_div = st.toggle("배당금 다시 투자", value=True, key="sim_div", help="끄면 실제 종가만으로 계산해요")
        has_fx = data.series("kr_usdkrw") is not None
        krw = st.toggle("미국 종목은 원화로 환산", value=has_fx, disabled=not has_fx, key="sim_fx",
                        help="원/달러 환율 변화까지 반영해요. 경제 상황판 데이터를 쓰기 때문에 collect.py를 먼저 실행해야 해요.")

if not picks:
    st.info("종목을 하나 이상 골라 주세요.")
    st.stop()
if not stocks.has_any():
    st.info("아직 주가 데이터가 없어요. `python3 scripts/collect_stocks.py`를 실행해 주세요.", icon=":material/database:")
    st.stop()

markets = {stocks.stock(c)["market"] == "US" for c in picks}
if len(markets) == 2 and not krw:
    st.info("한국 종목과 미국 종목을 같이 비교하려면 '미국 종목은 원화로 환산'을 켜 주세요.")
    st.stop()

ts = pd.Timestamp(start)
monthly = mode == "매달 적립"
results = []
for code in picks:
    s = stocks.stock(code)
    is_us = s["market"] == "US"
    conv = is_us and krw
    amt = amount if (not is_us or conv) else amount / 1400  # 원화 환산을 끄면 대략 1달러=1400원으로 달러 투자금 계산
    r = stocks.simulate(code, s["name"], ts, amt, monthly, with_div=with_div, krw=conv)
    if r is None:
        st.warning(f"{s['name']}: 이 기간 주가 데이터가 없어요.")
        continue
    results.append((r, is_us and not conv))

if not results:
    st.stop()

# 비교 지수: 고른 종목이 모두 미국이면 S&P 500, 아니면 코스피
all_us = all(stocks.stock(c)["market"] == "US" for c in picks)
bcode, bname = ("^GSPC", "S&P 500") if all_us else ("^KS11", "코스피")
bres = stocks.simulate(bcode, bname, ts, amount if (not all_us or krw) else amount / 1400, monthly,
                       with_div=False, krw=all_us and krw)

def money(v: float, usd: bool) -> str:
    return f"${v:,.0f}" if usd else stocks.won(v)

# ---------- 결과 카드 ----------
st.subheader("결과")
cols = st.columns(len(results))
for col, (r, usd) in zip(cols, results):
    with col, st.container(border=True):
        st.markdown(f"**{r.name}**")
        st.caption(f"{r.start:%Y-%m-%d} ~ {r.end:%Y-%m-%d}")
        st.metric("지금 평가금액", money(r.final, usd), delta=f"{r.total_return:+.1f}%")
        a, b = st.columns(2)
        a.metric("넣은 돈", money(r.invested, usd))
        b.metric("손익", money(r.profit, usd))
        a.metric("연평균 수익률" if not monthly else "연환산 수익률", "—" if r.cagr is None else f"{r.cagr:.1f}%")
        b.metric("최대 낙폭", f"{r.mdd:.0f}%")
        if bres is not None:
            diff = r.total_return - bres.total_return
            st.caption(f"같은 방식으로 {bname}에 넣었다면 {bres.total_return:+.1f}% → {'초과' if diff >= 0 else '미달'} {diff:+.1f}%p")

tc = st.columns(4)
for col, t in zip(tc, ["CAGR", "MDD", "적립식 투자", "수정주가"]):
    with col:
        term(t, ask(t))

# ---------- 차트 ----------
st.subheader("평가금액 변화")
fig = go.Figure()
palette = [ui.ACCENT, "#c2603c", "#6b7f2a"]
for i, (r, usd) in enumerate(results):
    fig.add_trace(go.Scatter(x=r.curve["date"], y=r.curve["value"] / (1 if usd else 10_000), name=r.name,
                             line=dict(color=palette[i % 3], width=2.2)))
if bres is not None:
    busd = results[0][1]
    fig.add_trace(go.Scatter(x=bres.curve["date"], y=bres.curve["value"] / (1 if busd else 10_000), name=bname,
                             line=dict(color="#888", width=1.6, dash="dot")))
inv = results[0][0].curve
fig.add_trace(go.Scatter(x=inv["date"], y=inv["invested"] / (1 if results[0][1] else 10_000), name="넣은 돈",
                         line=dict(color="#bbb", width=1.4, shape="hv")))
fig.update_layout(height=380, margin=dict(l=8, r=8, t=10, b=8), hovermode="x unified", legend=dict(orientation="h", y=-0.15),
                  plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
fig.update_yaxes(title="만원" if not results[0][1] else "달러", gridcolor="rgba(128,128,128,0.2)", tickformat=",")
ui.chart(fig)

notes = ["최대 낙폭은 기간 중 주가가 고점에서 가장 많이 떨어진 비율이에요. 그 기간을 버텨야 위 결과를 얻을 수 있었다는 뜻이에요."]
if monthly:
    notes.append("매달 적립은 매달 첫 거래일에 산다고 가정했어요. 연환산 수익률은 돈이 들어간 시점을 반영한 값(IRR)이에요.")
notes.append("세금, 거래 수수료는 빼지 않았어요. 과거 수익률이 미래 수익을 보장하지 않아요.")
for n in notes:
    st.caption(n)
st.divider()
ui.disclaimer()
