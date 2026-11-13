from html import escape

import streamlit as st

from lib import data, flow, glossary, stocks, ui

with st.container(key="masthead"):
    st.title("주식랩")
    st.markdown(
        '<p class="sl-lede">세계 경제 뉴스에서 출발해, 영향받는 산업과 회사, 그 회사의 주가, '
        '내가 샀다면 얼마가 됐을지까지 한 줄로 따라가 봐요</p>',
        unsafe_allow_html=True,
    )
    ui.collected_caption()

if not data.has_any_series():
    ui.no_data_notice()

# ---------- 오늘의 예시: 네 단계를 끝까지 ----------
ex = flow.example()
if ex is not None:
    st.subheader("오늘 지표로 따라가 본 예시" if ex.detected else "이렇게 따라가 봐요")
    is_us = stocks.stock(ex.code)["market"] == "US"
    usd = is_us and ex.invested < 1_000_000  # 원화 환산이 안 되면 달러로 계산해요

    def money(v: float) -> str:
        return f"${v:,.0f}" if usd else stocks.won(v)

    why = ex.why.split(". ")[0].rstrip(".")
    margin = f"영업이익률 {ex.margin:.1f}%" if ex.margin is not None else None
    roe = f"ROE {ex.roe:.1f}%" if ex.roe is not None else None
    earn = " · ".join(b for b in (margin, roe) if b) or "재무 데이터 준비 중"
    pr = ex.price_ret
    pr_cls = "" if pr is None else ("up" if pr >= 0 else "down")
    mult = ex.final / ex.invested if ex.final else None

    cells = [
        (1, "세계 경제가 어떻게 변했나", escape(ex.driver["name"]), "", escape(why)),
        (2, "어떤 산업, 어떤 회사가", f"{escape(ex.effect['industry'])}<br>{escape(ex.name)}", "",
         "유리해질 수 있다고 보는 산업이에요. "
         + (f"관심 종목 중 본업 이익률이 가장 높아요 ({escape(earn)})." if ex.margin is not None
            else f"관심 종목 중 이 산업에 속한 회사예요 ({escape(earn)}).")),
        (3, f"그 회사 주가는 {ex.years}년 동안", "—" if pr is None else f"{pr:+.0f}%", pr_cls,
         f"{ex.years}년 전과 지금 종가를 비교했어요 (배당 제외)."),
        (4, "그때 샀다면", "—" if ex.final is None else money(ex.final), pr_cls,
         f"{ex.years}년 전에 {escape(ui.josa(money(ex.invested), '을', '를'))} 넣었다면"
         + ("" if mult is None else f" 지금 넣은 돈의 {mult:.1f}배예요 (배당 재투자).")),
    ]
    html = "".join(
        f'<div><div class="sl-story-q"><b>{n}</b>{q}</div>'
        f'<div class="sl-story-v {cls}">{v}</div><div class="sl-story-t">{t}</div></div>'
        for n, q, v, cls, t in cells
    )
    st.markdown(f'<div class="sl-story">{html}</div>', unsafe_allow_html=True)
    if not ex.detected:
        st.caption("지금 지표에서 뚜렷한 변화가 보이지 않아, 예시로 하나를 골랐어요.")
    st.caption("과거 결과는 흐름을 이해하기 위한 예시예요. 같은 일이 반복된다는 뜻이 아니에요.")
    flow.next_button(1, "이 흐름 직접 따라가 보기", key="home_start",
                     driver=ex.driver["id"], industry=ex.effect["industry"], company=ex.code)

# ---------- 오늘의 숫자 ----------
st.subheader("오늘의 숫자")
cols = st.columns(4)
for col, key in zip(cols, ["kr_base_rate", "us_fed_upper", "kr_usdkrw", "us_10y"]):
    with col:
        ui.metric(key, with_country=True)

left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader("다가오는 일정")
    ev, types = data.events()
    upcoming = ev[ev["d_day"] >= 0].head(5) if not ev.empty else ev
    if upcoming.empty:
        st.caption("등록된 일정이 없어요.")
    else:
        ui.event_list(upcoming)
    st.page_link("views/calendar.py", label="일정 전체 보기", icon=":material/arrow_forward:")

with right:
    st.subheader("오늘의 용어")
    with st.container(border=True):
        glossary.card(glossary.today_term())
    st.page_link("views/tutor.py", label="용어 튜터에서 퀴즈 풀기", icon=":material/arrow_forward:")

st.divider()
ui.disclaimer()
