from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import flow, industry, stocks, ui
from lib.glossary import ask, term

# 유리/불리는 등락(빨강·파랑)과 헷갈리지 않게 기호와 잉크·황토로 표시해요
MARK = {"up": "▲", "down": "▼"}

flow.bar(2)
st.title("어떤 산업이 유리하고, 누가 돈을 잘 버나")
st.caption("경제 변화 하나를 고르면 유리하거나 불리해질 수 있는 산업이 나오고, 그 산업의 관심 종목 중 누가 돈을 잘 버는지 비교해요.")

drivers = industry.drivers()
now = industry.detect_now()

# ---------- 변화 고르기 ----------
labels = {d["id"]: ("● " if d["id"] in now else "") + d["name"] for d in drivers}
fd = flow.get("driver")
default = fd if fd in labels else next(iter(now), drivers[0]["id"])
did = st.pills("경제 변화 고르기 (● 지금 지표로 보이는 변화)", list(labels), default=default,
               format_func=labels.get, key="ind_driver") or default
if did != fd:
    flow.put(driver=did, industry=None, company=None)
d = industry.driver(did)

st.markdown(f"### {d['name']}")
st.write(d["summary"])
if did in now:
    ui.reading(escape(now[did]), label="지금 지표에서 보이는 근거")
else:
    st.caption("지금 지표에서 뚜렷하게 보이는 변화는 아니에요. 이런 일이 생긴다면 어떨지 가정해서 봐요. "
               "AI 투자, 중국 경기, 관세, 방위비, 친환경 정책은 숫자 하나로 판단하기 어려워 직접 골라 보는 항목이에요.")
term(d["term"], ask(d["term"]))

ups = [e for e in d["effects"] if e["sign"] == "up"]
downs = [e for e in d["effects"] if e["sign"] == "down"]

# ---------- 경로 요약 ----------
parts = "".join(
    f'<span class="sl-path-ind is-{e["sign"]}"><b>{MARK[e["sign"]]}</b>{escape(e["industry"])}</span>'
    for e in ups + downs
)
st.markdown(
    f'<div class="sl-path"><span class="sl-path-from">{escape(d["name"])}</span>'
    f'<span class="sl-path-arrow">→</span>{parts}</div>',
    unsafe_allow_html=True,
)

left, right = st.columns(2, gap="large")
for col, sign, title, items in ((left, "up", "유리해질 수 있는 산업", ups), (right, "down", "불리해질 수 있는 산업", downs)):
    with col:
        st.markdown(f'<div class="sl-side is-{sign}"><b>{MARK[sign]}</b>{title}'
                    f'<span>{len(items)}개</span></div>', unsafe_allow_html=True)
        if not items:
            st.caption("뚜렷하게 정리된 산업이 없어요.")
        for e in items:
            ss = industry.stocks_in(e.get("universe", []))
            names = "".join(f"<span>{escape(x['name'])}</span>" for x in ss) or \
                "<em>관심 종목 목록에 해당 종목이 없어요</em>"
            st.markdown(
                f'<div class="sl-card sl-ind"><div class="sl-insight-title">{escape(e["industry"])}</div>'
                f'<div class="sl-ind-why">{escape(e["why"])}</div>'
                f'<div class="sl-ind-stocks">{names}</div></div>',
                unsafe_allow_html=True,
            )

# ---------- 누가 돈을 잘 버나 ----------
st.subheader("이 산업들에서 누가 돈을 잘 버나")


@st.cache_data(ttl=600)
def company_rows(effects: tuple) -> pd.DataFrame:
    rows, seen = [], set()
    for sign, ind, universe in effects:
        for s in industry.stocks_in(list(universe)):
            if s["code"] in seen:
                continue
            seen.add(s["code"])
            m = stocks.metrics(s["code"])
            growth = None
            fin = stocks.financials(s["code"])
            if fin is not None and len(fin) >= 2:
                f = fin.sort_values("year")
                a, b = f["revenue"].iloc[-1], f["revenue"].iloc[-2]
                if pd.notna(a) and pd.notna(b) and b > 0:
                    growth = (a / b - 1) * 100
            rows.append({
                "code": s["code"], "예상": f"{MARK[sign]} {'유리' if sign == 'up' else '불리'}", "sign": sign,
                "산업": ind, "회사": s["name"], "영업이익률": m.op_margin, "ROE": m.roe,
                "매출 성장": growth, "부채비율": m.debt_ratio, "PER": m.per,
                "3개월 주가": industry.recent_return(s["code"]),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for c in ("영업이익률", "ROE", "매출 성장", "부채비율", "PER", "3개월 주가"):
        df[c] = pd.to_numeric(df[c], errors="coerce")  # None → NaN이라 표에서 빈칸으로 보여요
    df["_o"] = df["sign"].map({"up": 0, "down": 1})
    return df.sort_values(["_o", "영업이익률"], ascending=[True, False], na_position="last").drop(columns="_o").reset_index(drop=True)


cmp = company_rows(tuple((e["sign"], e["industry"], tuple(e.get("universe", []))) for e in ups + downs))
if cmp.empty:
    st.caption("이 변화와 연결된 관심 종목이 없어요. config/universe.yaml에 종목을 추가할 수 있어요.")
else:
    hi = max(5.0, float(cmp["영업이익률"].max(skipna=True) or 0))
    sel = ui.table(
        cmp.drop(columns=["code", "sign"]),
        hide_index=True, on_select="rerun", selection_mode="single-row", key="ind_pick",
        column_config={
            "영업이익률": st.column_config.ProgressColumn(
                "영업이익률", help="매출 중 본업으로 남긴 비율", format="%.1f%%", min_value=0, max_value=hi),
            "ROE": st.column_config.NumberColumn("ROE", help="주주 돈으로 1년에 번 비율", format="%.1f%%"),
            "매출 성장": st.column_config.NumberColumn("매출 성장", help="전년 대비", format="%+.1f%%"),
            "부채비율": st.column_config.NumberColumn("부채비율", format="%.0f%%"),
            "PER": st.column_config.NumberColumn("PER", format="%.1f배"),
            "3개월 주가": st.column_config.NumberColumn("3개월 주가", format="%+.1f%%"),
        },
    )
    fin_ok = cmp.dropna(subset=["영업이익률"])
    bits = []
    if not fin_ok.empty:
        b1 = fin_ok.loc[fin_ok["영업이익률"].idxmax()]
        bits.append(f"본업 이익률이 가장 높은 곳은 <b>{escape(b1['회사'])}</b>(영업이익률 <b>{b1['영업이익률']:.1f}%</b>)")
    roe_ok = cmp.dropna(subset=["ROE"])
    if not roe_ok.empty:
        b2 = roe_ok.loc[roe_ok["ROE"].idxmax()]
        bits.append(f"주주 돈으로 가장 잘 버는 곳은 <b>{escape(b2['회사'])}</b>(ROE <b>{b2['ROE']:.1f}%</b>)")
    if bits:
        ui.reading("이 중 " + ", ".join(bits) + "예요. 이익률이 높아도 이미 주가에 반영돼 있을 수 있으니 다음 단계에서 주가를 같이 봐요.")
    if cmp["영업이익률"].isna().any():
        st.caption("빈칸은 재무 데이터가 없는 경우예요. 미국 종목과 은행처럼 매출 구조가 다른 회사는 영업이익률을 계산하지 않아요.")

    rows_sel = sel.selection.rows if sel is not None and hasattr(sel, "selection") else []
    if rows_sel:
        pick = cmp.iloc[rows_sel[0]]
    else:
        fc = flow.get("company")
        pick = cmp[cmp["code"] == fc].iloc[0] if fc in set(cmp["code"]) else cmp.iloc[0]
    st.caption("표에서 행을 누르면 다음 단계에서 볼 회사가 바뀌어요.")
    flow.next_button(3, f"{pick['회사']}의 주가는 어땠을까", key="ind_next",
                     driver=did, industry=pick["산업"], company=pick["code"])

# ---------- 예상과 실제 ----------
st.subheader("예상은 실제 주가와 맞았을까")
rows = []
for sign, items in (("up", ups), ("down", downs)):
    seen = set()
    for e in items:
        for s in industry.stocks_in(e.get("universe", [])):
            r = industry.recent_return(s["code"])
            if r is None or s["code"] in seen:
                continue
            seen.add(s["code"])
            rows.append({"sign": sign, "name": s["name"], "industry": e["industry"], "ret": r})
rt = pd.DataFrame(rows)
if rt.empty:
    st.caption("이 변화와 연결된 관심 종목의 주가 데이터가 없어요.")
else:
    side_label = {"up": "▲ 유리 예상", "down": "▼ 불리 예상"}
    rt = rt.sort_values(["sign", "ret"], ascending=[True, True])  # 아래부터 그려져요: down(불리)이 먼저라 유리가 위로
    fig = go.Figure(go.Bar(
        orientation="h",
        y=[[side_label[x] for x in rt["sign"]], rt["name"].tolist()],
        x=rt["ret"],
        marker_color=[ui.UP if v > 0 else ui.DOWN for v in rt["ret"]],
        text=[f"{v:+.1f}%" for v in rt["ret"]], textposition="outside", cliponaxis=False,
        textfont=dict(family=ui.MONO, size=12, color=ui.TEXT2),
        customdata=rt["industry"],
        hovertemplate="%{y}<br>%{customdata}<br>최근 3개월 %{x:+.1f}%<extra></extra>",
    ))
    span = max(5.0, rt["ret"].abs().max() * 1.25)
    fig.add_vline(x=0, line_color=ui.LINE, line_width=1)
    fig.update_layout(height=max(200, 44 * len(rt) + 40), margin=dict(l=8, r=24, t=8, b=8), bargap=0.45,
                      showlegend=False)
    fig.update_xaxes(range=[-span, span], ticksuffix="%", showgrid=True, gridcolor=ui.GRID)
    fig.update_yaxes(autorange=True, tickfont=dict(family=ui.SANS, size=13, color=ui.TEXT))
    ui.chart(fig)

    up_avg = rt.loc[rt["sign"] == "up", "ret"].mean()
    dn_avg = rt.loc[rt["sign"] == "down", "ret"].mean()
    def p(v):
        return f'<b class="{"up" if v > 0 else "down"}">{v:+.1f}%</b>'
    if pd.notna(up_avg) and pd.notna(dn_avg):
        gap = up_avg - dn_avg
        msg = (f"최근 3개월 동안 유리할 거라 본 종목은 평균 {p(up_avg)}, 불리할 거라 본 종목은 평균 {p(dn_avg)} 움직였어요. ")
        if gap > 0:
            msg += f"유리 쪽이 <b>{gap:.1f}%p</b> 더 나아서, 예상과 같은 방향이었어요."
        else:
            msg += (f"오히려 불리 쪽이 <b>{-gap:.1f}%p</b> 더 나았어요. "
                    "이 변화보다 실적이나 업황 같은 다른 이유가 더 크게 작용했을 수 있어요.")
    else:
        v = up_avg if pd.notna(up_avg) else dn_avg
        msg = f"관련 종목은 최근 3개월 평균 {p(v)} 움직였어요. 비교할 반대쪽 종목이 없어서 방향을 판단하긴 어려워요."
    if did not in now:
        msg = "지금 지표에서 보이는 변화는 아니에요. 그래서 위 결과는 이 변화와 상관없이 움직였을 수 있어요. " + msg
    ui.reading(msg)
    st.caption("막대는 종목별 최근 3개월 수익률이에요. 빨강은 상승, 파랑은 하락이에요. "
               "종목 수가 적어서 평균은 한두 종목에 크게 흔들려요.")

st.warning(d["caution"], icon=":material/lightbulb:")
if d["id"] in ("rate_cut", "rate_hike"):
    st.page_link("views/events.py", label="과거 금리 결정 때 실제로 어땠는지 데이터로 확인하기", icon=":material/arrow_forward:")

# ---------- 전체 표 ----------
exp = st.expander("모든 변화와 산업을 한눈에 보기")
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
with exp:
    ui.table(
        grid.reset_index().style.map(
            lambda v: f"color: {ui.ACCENT}" if v == "▲" else ("color: #9a6b16" if v == "▼" else "")
        ),
        hide_index=True,
    )
    st.caption("▲ 유리해질 수 있음 · ▼ 불리해질 수 있음. 일반적으로 알려진 경로를 정리한 것이고, 실제 주가는 기업 실적과 이미 반영된 기대에 따라 달라요. "
               "연결은 config/industry_map.yaml에서 고치거나 늘릴 수 있어요.")
st.divider()
ui.disclaimer()
