import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from html import escape

from lib import flow, industry, stocks, ui
from lib.glossary import ask, term

flow.bar(3)
st.title("이 회사는 돈을 얼마나 벌고, 주가는 어땠나")
st.caption("앞 단계에서 고른 회사를 자세히 봐요. 돈을 얼마나 잘 버는지, 주가가 어떻게 움직였는지 확인하고 다음 단계에서 그때 샀다면 어땠을지 계산해요.")

uni = stocks.universe()["stocks"]
if not stocks.has_any():
    st.info(
        "아직 종목 데이터를 받지 않았어요. `.env`에 `DART_API_KEY`를 넣고 "
        "`python3 scripts/collect_stocks.py`를 실행하면 채워져요. 주가는 키 없이도 받아요.",
        icon=":material/database:",
    )

labels = {s["code"]: f"{s['name']} ({s['code']}) · {s['industry']}" for s in uni}
# 앞 단계에서 고른 회사를 기본으로. 위젯 키는 페이지를 떠나면 지워져서 flow에 따로 담아 둬요
fc = flow.get("company") or st.session_state.get("company_code")
if fc in labels and st.session_state.get("company_code") != fc and "company_code" not in st.session_state:
    st.session_state["company_code"] = fc
code = st.selectbox("종목", list(labels), format_func=labels.get, key="company_code")
if code != flow.get("company"):
    flow.put(company=code)
s = stocks.stock(code)
us = s["market"] == "US"
cur = "달러" if us else "원"
m = stocks.metrics(code)
inf = stocks.info(code)

d = industry.driver(flow.get("driver")) if flow.get("driver") else None
if d and flow.get("industry"):
    eff = next((e for e in d["effects"] if e["industry"] == flow.get("industry")), None)
    if eff and s["industry"] in eff.get("universe", []):
        word = "유리" if eff["sign"] == "up" else "불리"
        ui.reading(f"<b>{escape(d['name'])}</b> 때 <b>{escape(ui.josa(eff['industry'], '은', '는'))}</b> {word}해질 수 있다고 봤어요. "
                   f"{escape(eff['why'])}", label="이 회사를 보는 이유")

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

if m.price and m.high_52w and m.low_52w and m.high_52w > m.low_52w:
    pos = (m.price - m.low_52w) / (m.high_52w - m.low_52w) * 100
    from_low = (m.price / m.low_52w - 1) * 100
    from_high = (m.price / m.high_52w - 1) * 100
    st.markdown(
        f'<div class="sl-range"><div class="sl-range-cap">지난 1년 가격 범위에서 지금 위치</div>'
        f'<div class="sl-range-bar"><span style="left:{pos:.1f}%"></span></div>'
        f'<div class="sl-range-ends"><span>최저 {pfmt(m.low_52w)}</span><span>최고 {pfmt(m.high_52w)}</span></div></div>',
        unsafe_allow_html=True,
    )
    ui.reading(f"지금 주가는 1년 중 가장 쌌을 때보다 <b class=\"up\">{from_low:+.0f}%</b>, "
               f"가장 비쌌을 때보다 <b class=\"down\">{from_high:+.0f}%</b>예요. "
               f"1년 범위의 <b>{pos:.0f}%</b> 지점이라 "
               + ("고점 가까이에 있어요." if pos >= 70 else ("저점 가까이에 있어요." if pos <= 30 else "중간쯤에 있어요.")))

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

def easy(v, f):
    """값이 있을 때만 쉬운 말 풀이를 만들어요."""
    return None if v is None else f(v)


items = [
    ("PER", times(m.per), "PER",
     easy(m.per, lambda x: f"지금 이익이 그대로면 시가총액만큼 버는 데 약 {x:.0f}년 걸려요" if x > 0 else "이익이 적자라 계산이 어려워요")),
    ("PBR", times(m.pbr), "PBR",
     easy(m.pbr, lambda x: f"장부상 순자산보다 {x:.1f}배 비싸게 거래돼요" if x >= 1 else f"장부상 순자산보다 싸게({x:.1f}배) 거래돼요")),
    ("ROE", pct(m.roe), "ROE", easy(m.roe, lambda x: f"주주 돈 100원으로 1년에 {x:.1f}원을 벌었어요")),
    ("영업이익률", pct(m.op_margin), "영업이익률", easy(m.op_margin, lambda x: f"1,000원어치 팔아 본업으로 {x * 10:.0f}원을 남겼어요")),
    ("부채비율", pct(m.debt_ratio), "부채비율", easy(m.debt_ratio, lambda x: f"자기 돈 100원당 빚이 {x:.0f}원이에요")),
    ("배당수익률", pct(m.div_yield), "배당수익률", easy(m.div_yield, lambda x: f"100만원어치 사면 1년 배당은 약 {x * 10_000:,.0f}원이에요")),
]
for row in (items[:3], items[3:]):
    cols = st.columns(3)
    for col, (lab, val, t, hint) in zip(cols, row):
        with col:
            ui.hint_metric(lab, val, hint, t, key=f"co_{t}")

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
                                 line=dict(color=ui.PALETTE[2], width=1.6)))
        fig.update_yaxes(title="시작=100")
    else:
        fig.add_trace(go.Scatter(x=v["date"], y=v["close"], name="종가", line=dict(color=ui.ACCENT, width=2.2),
                                 hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f}<extra></extra>"))
        mdd, pk, tr = stocks.max_drawdown(v.set_index("date")["close"])
        if pk is not None and tr is not None and mdd < -5:
            fig.add_vrect(x0=pk, x1=tr, fillcolor=ui.DOWN, opacity=0.06, line_width=0)
            fig.add_annotation(x=tr, y=float(v.set_index("date").loc[tr, "close"]), text=f"고점 대비 {mdd:.0f}%",
                               showarrow=True, arrowhead=0, ay=30, arrowcolor=ui.DOWN,
                               font=dict(color=ui.DOWN, family=ui.MONO, size=12))
    fig.update_layout(height=360, margin=dict(l=8, r=8, t=10, b=8), hovermode="x unified",
                      legend=dict(orientation="h", y=-0.15))
    ui.chart(fig)

    p0, p1 = float(v["close"].iloc[0]), float(v["close"].iloc[-1])
    chg = (p1 / p0 - 1) * 100
    mdd_all, _, _ = stocks.max_drawdown(v.set_index("date")["close"])
    msg = (f"{yrs}년 전 {pfmt(p0)}이던 주가가 지금 {pfmt(p1)}이에요 "
           f'(<b class="{"up" if chg >= 0 else "down"}">{chg:+.0f}%</b>, 배당 제외). ')
    if mdd_all < -5:
        msg += f"그 사이 고점에서 최대 <b>{mdd_all:.0f}%</b> 떨어졌던 구간(파란 음영)도 있었어요."
    if compare and bpx is not None:
        msg += f" 두 선이 같은 100에서 출발하니, 위에 있는 쪽이 이 기간에 더 많이 오른 거예요."
    ui.reading(msg)
    term("MDD", "최대 낙폭(MDD)이란?")

    ar = stocks.annual_returns(code)
    if ar is not None and not ar.empty:
        st.markdown("**연도별 수익률** (배당 포함)")
        bar = go.Figure(go.Bar(
            x=[f"{y}{'*' if p else ''}" for y, p in zip(ar["year"], ar["partial"])], y=ar["return"],
            marker_color=[ui.UP if r >= 0 else ui.DOWN for r in ar["return"]],
            text=[f"{r:+.0f}%" for r in ar["return"]], textposition="outside", cliponaxis=False,
            textfont=dict(family=ui.MONO, size=12, color=ui.TEXT2),
        ))
        lo, hi = min(0, ar["return"].min()), max(0, ar["return"].max())
        pad = (hi - lo) * 0.15 or 5
        bar.update_yaxes(range=[lo - pad, hi + pad])
        bar.update_layout(height=300, margin=dict(l=8, r=8, t=24, b=8), bargap=0.4,
                          yaxis=dict(ticksuffix="%"), xaxis=dict(type="category"))
        ui.chart(bar)
        full = ar[~ar["partial"]]
        if len(full) >= 2:
            best, worst = full.loc[full["return"].idxmax()], full.loc[full["return"].idxmin()]
            ups_n = int((full["return"] > 0).sum())
            ui.reading(f"지난 {len(full)}년 중 <b>{ups_n}년</b>은 오르고 <b>{len(full) - ups_n}년</b>은 내렸어요. "
                       f'가장 좋았던 해는 {int(best["year"])}년 <b class="up">{best["return"]:+.0f}%</b>, '
                       f'가장 나빴던 해는 {int(worst["year"])}년 <b class="down">{worst["return"]:+.0f}%</b>예요.')
        st.caption("빨강은 오른 해, 파랑은 내린 해예요. * 올해는 1월 1일부터 지금까지예요.")

# ---------- 재무 ----------
fin = stocks.financials(code)
if fin is not None and not fin.empty:
    st.subheader("실적 추이")
    big = fin["revenue"].abs().max() >= 1e13  # 매출이 10조 원 넘으면 조 단위로
    unit, div = ("조 원", 1e12) if big else ("억 원", 1e8)
    st.caption(f"{fin['basis'].iloc[-1]} 재무제표 기준, 차트 단위 {unit}")
    f = fin.copy()
    for col in ["revenue", "operating_income", "net_income", "assets", "liabilities", "equity"]:
        f[col] = f[col] / div
    g = go.Figure()
    f["year"] = f["year"].astype(str)
    hov = "%{x}<br>%{y:,.1f}" + unit + "<extra>%{fullData.name}</extra>"
    g.add_trace(go.Bar(x=f["year"], y=f["revenue"], name="매출", marker_color="#cdd5dc", hovertemplate=hov))
    g.add_trace(go.Bar(x=f["year"], y=f["operating_income"], name="영업이익", marker_color=ui.ACCENT, hovertemplate=hov))
    g.add_trace(go.Bar(x=f["year"], y=f["net_income"], name="당기순이익", marker_color=ui.PALETTE[1], hovertemplate=hov))
    g.update_layout(barmode="group", height=320, margin=dict(l=8, r=8, t=10, b=8), legend=dict(orientation="h", y=-0.15),
                    bargap=0.25)
    g.update_yaxes(tickformat=",", ticksuffix=unit[0])
    g.update_xaxes(type="category")
    ui.chart(g)

    if len(fin) >= 2:
        a, b = fin.iloc[-1], fin.iloc[-2]
        def yoy(cur, prev):
            if not prev or prev <= 0:
                return ""
            c = (cur / prev - 1) * 100
            return f' (전년보다 <b class="{"up" if c >= 0 else "down"}">{c:+.0f}%</b>)'
        margin = a["operating_income"] / a["revenue"] * 100 if a["revenue"] else None
        msg = (f"{a['year']}년 매출은 <b>{stocks.won(a['revenue'])}</b>{yoy(a['revenue'], b['revenue'])}, "
               f"영업이익은 <b>{stocks.won(a['operating_income'])}</b>{yoy(a['operating_income'], b['operating_income'])}이에요.")
        if margin is not None:
            msg += f" 매출 100원 중 본업으로 <b>{margin:.0f}원</b>을 남긴 셈이에요."
        ui.reading(msg)

    t = pd.DataFrame({
        "연도": f["year"].astype(str),
        "매출(억)": f["revenue"].round(0),
        "영업이익(억)": f["operating_income"].round(0),
        "당기순이익(억)": f["net_income"].round(0),
        "영업이익률(%)": (fin["operating_income"] / fin["revenue"] * 100).round(1),
        "ROE(%)": (fin["net_income"] / fin["equity"] * 100).round(1),
        "부채비율(%)": (fin["liabilities"] / fin["equity"] * 100).round(1),
    })
    ui.table(t, hide_index=True,
                 column_config={k: st.column_config.NumberColumn(format="localized") for k in ["매출(억)", "영업이익(억)", "당기순이익(억)"]})
    tc = st.columns(4)
    for col, name in zip(tc, ["영업이익", "당기순이익", "ROE", "부채비율"]):
        with col:
            term(name, ask(name))
    st.caption("출처: 금융감독원 Open DART 사업보고서 주요계정")

st.divider()
st.markdown("#### 다음 단계")
st.caption("이 회사 주식을 예전에 샀다면 지금 얼마가 됐을지, 같은 돈을 코스피에 넣었을 때와 비교해요.")
flow.next_button(4, f"{ui.josa(s['name'], '을', '를')} 3년 전에 샀다면?",
                 key="co_next", company=code)
st.divider()
ui.disclaimer()
