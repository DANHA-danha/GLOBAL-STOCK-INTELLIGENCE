"""화면 공통 요소: 지표 카드, 차트, 안내 문구."""
from __future__ import annotations

import inspect
from html import escape

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from lib import data
from lib.glossary import ask, term

ACCENT = "#1d5c73"
# 차트 색: 잉크(주 계열) 하나가 이끌고, 나머지는 차분한 보조색
PALETTE = [ACCENT, "#b8843b", "#7d8894", "#6f5a80"]
# 한국식 등락 색: 상승 빨강, 하락 파랑
UP, DOWN = "#d0392b", "#1f5fbf"

TEXT, TEXT2, MUTED = "#16191f", "#4a515c", "#6b7480"
LINE, GRID = "#e3e6ea", "#eef0f3"
SANS = "'IBM Plex Sans KR', 'Apple SD Gothic Neo', sans-serif"
MONO = "'IBM Plex Mono', ui-monospace, monospace"

pio.templates["stocklab"] = go.layout.Template(layout=dict(
    font=dict(family=SANS, size=12, color=TEXT2),
    colorway=PALETTE,
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    title=dict(font=dict(size=14, color=TEXT), x=0, xanchor="left", pad=dict(l=4)),
    xaxis=dict(showgrid=False, linecolor=LINE, ticks="outside", tickcolor=LINE, ticklen=4,
               tickfont=dict(family=MONO, size=11, color=MUTED), zeroline=False),
    yaxis=dict(gridcolor=GRID, zeroline=False, linecolor=LINE,
               tickfont=dict(family=MONO, size=11, color=MUTED)),
    legend=dict(font=dict(size=12, color=TEXT2), bgcolor="rgba(0,0,0,0)"),
    hoverlabel=dict(bgcolor="#ffffff", bordercolor=LINE, font=dict(family=SANS, size=12, color=TEXT)),
))
pio.templates.default = "plotly_white+stocklab"

# st.metric의 delta_arrow는 최신 Streamlit에만 있어서, 지원할 때만 넘긴다
_HAS_DELTA_ARROW = "delta_arrow" in inspect.signature(st.metric).parameters
# 차트·표의 가로 꽉 채우기 옵션도 버전마다 이름이 달라요 (width="stretch" ↔ use_container_width=True)
_CHART_WIDTH = "width" in inspect.signature(st.plotly_chart).parameters
_TABLE_WIDTH = "width" in inspect.signature(st.dataframe).parameters


def chart(fig) -> None:
    """plotly 차트를 가로로 꽉 채워 보여줘요. Streamlit 버전에 맞춰 옵션을 골라요."""
    opts = {"width": "stretch"} if _CHART_WIDTH else {"use_container_width": True}
    # Streamlit이 plotly 기본 템플릿을 바꿔 두기 때문에, 그릴 때마다 stocklab 템플릿을 직접 지정해요
    fig.update_layout(template="plotly_white+stocklab")
    # 배경을 비워 두면 Streamlit이 회색을 채워서, 투명으로 직접 적어 줘요
    if fig.layout.plot_bgcolor is None:
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    if fig.layout.paper_bgcolor is None:
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)")
    # theme=None: Streamlit 기본 차트 테마 대신 위의 stocklab 템플릿을 써요
    st.plotly_chart(fig, config={"displayModeBar": False}, theme=None, **opts)


def table(df, **kwargs):
    """표를 가로로 꽉 채워 보여줘요. on_select를 넘기면 선택 결과를 돌려줘요."""
    opts = {"width": "stretch"} if _TABLE_WIDTH else {"use_container_width": True}
    return st.dataframe(df, **kwargs, **opts)


def fmt(v: float, unit: str) -> str:
    if unit == "원":
        return f"{v:,.1f}원"
    if unit in ("엔", "위안", "달러"):
        return f"{v:,.2f}{unit}"
    if unit == "%":
        return f"{v:.2f}%"
    return f"{v:,.2f}"


def fmt_change(c: float | None, unit: str) -> str | None:
    if c is None:
        return None
    if unit == "%":
        return f"{c:+.2f}%p"
    if unit == "원":
        return f"{c:+,.1f}원"
    return f"{c:+,.2f}"


def metric(key: str, months: int = 1, show_term: bool = True, with_country: bool = False) -> None:
    """지표 하나: 최신값, 변화, 1년 추이 미니 차트. 용어 버튼까지 한 카드에 담아요."""
    s = data.series_def(key)
    if not s:
        return
    label = f"{s['country']} {s['label']}" if with_country else s["label"]
    lt = data.latest(key, months)
    if lt is None:
        with st.container(border=True, key=f"kpi_none_{key}"):
            st.metric(label, "—", help="아직 수집된 값이 없어요. README의 '데이터 받기'를 따라 해 주세요.")
        return
    df = data.series(key)
    recent = df[df["date"] >= lt.date - pd.DateOffset(years=1)]["value"].tolist()

    # 변화가 사실상 0이면 화살표 대신 "변동 없음"
    unchanged = lt.change is not None and abs(lt.change) < 0.005
    delta = "변동 없음" if unchanged else fmt_change(lt.change, s.get("unit", ""))
    # 색은 한국식(상승 빨강·하락 파랑)으로 CSS가 칠해요. 컨테이너 key에 방향을 담아 둬요
    direction = "flat" if unchanged or lt.change is None else ("up" if lt.change > 0 else "down")
    color = "off" if unchanged else "normal"

    # 마지막 값이 너무 오래됐으면(발표 중단 등) 날짜를 눈에 띄게 표시
    age = (pd.Timestamp.today().normalize() - lt.date).days
    stale = age > 200
    extra = {"delta_arrow": "off" if unchanged else "auto"} if _HAS_DELTA_ARROW else {}
    with st.container(border=True, key=f"kpi_{direction}_{key}"):
        st.metric(
            label + (f" · {lt.date:%Y-%m} 이후 갱신 없음" if stale else ""),
            fmt(lt.value, s.get("unit", "")),
            delta=delta,
            delta_color=color,
            **extra,
            help=f"{lt.date:%Y-%m-%d} 기준 · {lt.change_label}",
            chart_data=recent if len(recent) > 2 else None,
            chart_type="line",
        )
        if show_term and s.get("term"):
            term(s["term"], ask(s["term"]))


def line_chart(keys: list[str], years: int = 5, title: str | None = None, height: int = 320) -> None:
    """여러 지표를 한 차트에. 단위가 같은 것끼리만 묶어요."""
    fig = go.Figure()
    any_data = False
    for i, k in enumerate(keys):
        df = data.series(k)
        s = data.series_def(k)
        if df is None or not s:
            continue
        df = df[df["date"] >= df["date"].max() - pd.DateOffset(years=years)]
        fig.add_trace(
            go.Scatter(
                x=df["date"], y=df["value"], name=f"{s['country']} {s['label']}",
                mode="lines", line=dict(width=2 if i == 0 else 1.6, color=PALETTE[i % len(PALETTE)]),
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f}<extra>%{fullData.name}</extra>",
            )
        )
        any_data = True
    if not any_data:
        st.caption("차트에 쓸 데이터가 아직 없어요.")
        return
    fig.update_layout(
        title=title, height=height, margin=dict(l=8, r=8, t=40 if title else 12, b=8),
        legend=dict(orientation="h", y=-0.15), hovermode="x unified",
    )
    chart(fig)


def no_data_notice() -> None:
    st.info(
        "아직 경제 지표를 받아오지 않았어요. 무료 API 키 두 개를 받아 `.env`에 넣고 "
        "`python3 scripts/collect.py`를 한 번 실행하면 채워져요. 자세한 방법은 README의 '데이터 받기'에 있어요.",
        icon=":material/database:",
    )


def disclaimer() -> None:
    st.caption("분석과 설명은 공부를 위한 참고 자료예요. 특정 종목이나 상품의 투자를 권유하지 않아요.")


def collected_caption() -> None:
    m = data.meta()
    if m.get("collected_at"):
        txt = f"데이터 수집: {m['collected_at']} (한국 시간)"
        if m.get("failed"):
            txt += f" · 실패 {len(m['failed'])}개"
        st.caption(txt)


WEEKDAY = "월화수목금토일"


def d_label(d: int) -> str:
    return "오늘" if d == 0 else (f"D-{d}" if d > 0 else f"{-d}일 전")


def event_row(e: pd.Series, types: dict, compact: bool = False) -> None:
    with st.container(border=True):
        c1, c2 = st.columns([1, 4] if compact else [1, 6])
        with c1:
            st.markdown(f"**{d_label(int(e['d_day']))}**")
            st.caption(f"{e['date']:%m/%d}({WEEKDAY[e['date'].weekday()]})")
        with c2:
            st.markdown(f"**{e['title']}**")
            if not compact:
                why = types.get(e.get("type", ""), {}).get("why", "")
                if why:
                    st.caption(why)
                links = []
                if isinstance(e.get("url"), str) and e["url"]:
                    links.append(f"[{e.get('source', '출처')}]({e['url']})")
                if links:
                    st.caption(" · ".join(links))
                if isinstance(e.get("term"), str) and e["term"]:
                    term(e["term"], ask(e["term"]))


def insight_card(it, border: bool = True) -> None:
    """연결 고리 하나: 제목, 숫자로 확인되는 사실, 번호 붙은 경로."""
    steps = "".join(
        f'<li><span class="sl-step-n">{i}</span><span class="sl-step-t">{escape(step)}</span></li>'
        for i, step in enumerate(it.chain, 1)
    )
    cls = "sl-insight sl-card" if border else "sl-insight sl-plain"
    st.markdown(
        f'<div class="{cls}"><div class="sl-insight-title">{escape(it.title)}</div>'
        f'<div class="sl-insight-fact">{escape(it.fact)}</div>'
        f'<ol class="sl-chain">{steps}</ol></div>',
        unsafe_allow_html=True,
    )


def event_list(rows: pd.DataFrame) -> None:
    """다가오는 일정을 시세표처럼 한 줄씩: D-day · 일정 · 날짜."""
    if rows.empty:
        return
    out = []
    for _, e in rows.iterrows():
        d = int(e["d_day"])
        out.append(
            f'<div class="sl-evt{" is-soon" if d <= 7 else ""}">'
            f'<span class="sl-evt-d">{d_label(d)}</span>'
            f'<span class="sl-evt-t">{escape(str(e["title"]))}</span>'
            f'<span class="sl-evt-date">{e["date"]:%m/%d}({WEEKDAY[e["date"].weekday()]})</span></div>'
        )
    st.markdown(f'<div class="sl-card sl-evts">{"".join(out)}</div>', unsafe_allow_html=True)


def josa(word: str, with_final: str, without_final: str) -> str:
    """받침에 맞춰 조사를 붙여요. josa("코스피", "은", "는") → "코스피는"."""
    c = word.strip()[-1] if word.strip() else ""
    if "가" <= c <= "힣":
        has = (ord(c) - 0xAC00) % 28 != 0
    else:
        has = c.upper() in "LMNR013678"
    return word + (with_final if has else without_final)


def reading(html: str, label: str = "한 줄 해석") -> None:
    """화면의 숫자를 한 문장으로 풀어 주는 상자. html은 이미 escape된 문장이어야 해요."""
    st.markdown(f'<div class="sl-read"><span class="sl-read-label">{label}</span>'
                f'<p>{html}</p></div>', unsafe_allow_html=True)


def ret_color(v: float | None) -> str:
    """표에 쓰는 한국식 등락 색."""
    if v is None or pd.isna(v) or v == 0:
        return ""
    return f"color: {UP}" if v > 0 else f"color: {DOWN}"


def hint_metric(label: str, value: str, hint: str | None, term_name: str | None = None, key: str = "") -> None:
    """지표 카드: 값 아래에 '쉽게 말하면' 한 줄과 용어 버튼을 같이 담아요."""
    with st.container(border=True, key=f"kpi_flat_hint_{key or label}"):
        st.metric(label, value)
        if hint:
            st.markdown(f'<div class="sl-hint">{escape(hint)}</div>', unsafe_allow_html=True)
        if term_name:
            term(term_name, ask(term_name))


_CSS = """
<style>
:root {
  --sl-text: #16191f; --sl-text2: #4a515c; --sl-muted: #6b7480;
  --sl-line: #e3e6ea; --sl-raised: #f3f5f7; --sl-accent: #1d5c73;
  --sl-up: #d0392b; --sl-up-bg: #fbecea; --sl-down: #1f5fbf; --sl-down-bg: #e9f0fb;
  --sl-ochre: #9a6b16;
  --sl-mono: 'IBM Plex Mono', ui-monospace, monospace;
  --sl-ease: cubic-bezier(0.22, 1, 0.36, 1);
}

/* 상단 메뉴: 흰 바탕에 아래 괘선 하나 */
[data-testid="stHeader"] { background: #ffffff; border-bottom: 1px solid var(--sl-line); }
[data-testid="stMainBlockContainer"] { padding-top: 88px; padding-bottom: 64px; max-width: 1360px; }

/* 제목: 굵기 대신 크기로 위계 */
h1 { letter-spacing: -0.02em; }
h3 { padding-top: 24px; }
[data-testid="stHeadingWithActionElements"] a[href^="#"] { display: none; }

/* 숫자는 자릿수가 맞게 */
[data-testid="stMetricValue"], [data-testid="stMetricDelta"], .sl-insight-fact,
[data-testid="stDataFrame"], .sl-evt { font-variant-numeric: tabular-nums; }

/* 지표 카드 */
[class*="st-key-kpi_"] { gap: 8px; }
[data-testid="stMetricLabel"] p { color: var(--sl-text2); font-size: 14px; }
[data-testid="stMetricValue"] { font-size: 30px; font-weight: 500; line-height: 1.15; color: var(--sl-text); }
[data-testid="stMetricDelta"] { font-family: var(--sl-mono); font-size: 12px; }
[data-testid="stMetricDelta"]:has([data-testid="stMetricDeltaIcon-Up"]) { color: var(--sl-up) !important; background-color: var(--sl-up-bg) !important; }
[data-testid="stMetricDelta"]:has([data-testid="stMetricDeltaIcon-Down"]) { color: var(--sl-down) !important; background-color: var(--sl-down-bg) !important; }
[class*="st-key-kpi_flat_"] [data-testid="stMetricDelta"] { color: var(--sl-muted) !important; background-color: var(--sl-raised) !important; font-family: inherit; }
[class*="st-key-kpi_flat_"] [data-testid="stMetricDelta"] svg { display: none; }
[data-testid="stMetricChart"] svg.marks { background-color: transparent !important; }
[data-testid="stMetricChart"] path[aria-roledescription="line mark"] { stroke: var(--sl-accent) !important; stroke-width: 1.5px; }

/* 카드 안의 용어 버튼은 조용한 텍스트 링크처럼 */
[class*="st-key-kpi_"] [data-testid="stPopoverButton"] {
  border: none; background: transparent; padding: 4px 0; min-height: 0;
  color: var(--sl-muted); font-size: 13px; transition: color 150ms var(--sl-ease);
}
[class*="st-key-kpi_"] [data-testid="stPopoverButton"] p { font-size: 13px; }
[class*="st-key-kpi_"] [data-testid="stPopoverButton"]:hover { color: var(--sl-accent); }

/* 페이지 이동 링크: 잉크색 텍스트 */
[data-testid="stPageLink-NavLink"] { padding-left: 0; transition: background-color 150ms var(--sl-ease); }
[data-testid="stPageLink-NavLink"] p { color: var(--sl-accent); font-size: 14px; font-weight: 500; }
[data-testid="stPageLink-NavLink"] [data-testid="stIconMaterial"] { color: var(--sl-accent) !important; font-size: 18px; }

/* 공통 카드 */
.sl-card { border: 1px solid var(--sl-line); border-radius: 12px; background: #ffffff; }
[data-testid="stMarkdownContainer"]:has(> .sl-card) { margin-bottom: 0 !important; }

/* 연결 고리: 사실 → 번호 붙은 경로 */
.sl-insight { padding: 20px 24px; }
.sl-insight.sl-plain { padding: 0; }
.sl-insight-title { font-size: 16px; font-weight: 600; color: var(--sl-text); line-height: 1.4; }
.sl-insight-fact { margin-top: 4px; font-family: var(--sl-mono); font-size: 12px; color: var(--sl-muted); }
.sl-chain { list-style: none; margin: 16px 0 0; padding: 0; }
.sl-chain li { position: relative; display: flex; gap: 12px; align-items: flex-start; margin: 0; padding: 0 0 12px; font-size: 14px; line-height: 20px; color: var(--sl-text2); }
.sl-chain li:last-child { padding-bottom: 0; color: var(--sl-text); }
.sl-chain li:not(:last-child)::before { content: ""; position: absolute; left: 9.5px; top: 22px; bottom: 2px; width: 1px; background: var(--sl-line); }
.sl-step-n { flex: none; width: 20px; height: 20px; border-radius: 10px; border: 1px solid var(--sl-line); background: #ffffff;
  font-family: var(--sl-mono); font-size: 11px; line-height: 18px; text-align: center; color: var(--sl-muted); }
.sl-chain li:last-child .sl-step-n { border-color: var(--sl-accent); background: var(--sl-accent); color: #ffffff; }

/* 일정: 한 줄짜리 표 */
.sl-evts { padding: 4px 16px; }
.sl-evt { display: grid; grid-template-columns: 52px 1fr auto; gap: 12px; align-items: center; min-height: 44px; font-size: 14px; }
.sl-evt + .sl-evt { border-top: 1px solid var(--sl-line); }
.sl-evt-d { font-family: var(--sl-mono); font-size: 12px; color: var(--sl-muted); }
.sl-evt.is-soon .sl-evt-d { color: var(--sl-accent); font-weight: 500; }
.sl-evt-t { color: var(--sl-text); }
.sl-evt-date { font-family: var(--sl-mono); font-size: 12px; color: var(--sl-muted); text-align: right; }

/* 첫 화면 머리 */
.sl-lede { margin: -8px 0 0; font-size: 17px; line-height: 1.6; color: var(--sl-text2); }
.st-key-masthead [data-testid="stCaptionContainer"] { font-family: var(--sl-mono); font-size: 12px; }

/* 단계 표시줄: 지금 몇 번째 단계인지, 무엇을 골랐는지 */
.sl-flow { list-style: none; display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; margin: 0 0 8px; padding: 0;
  border: 1px solid var(--sl-line); border-radius: 12px; overflow: hidden; }
.sl-flow li { position: relative; display: flex; gap: 10px; align-items: flex-start; margin: 0; padding: 12px 16px; background: #ffffff; }
.sl-flow li + li { border-left: 1px solid var(--sl-line); }
.sl-step-num { flex: none; width: 22px; height: 22px; border-radius: 11px; border: 1px solid var(--sl-line);
  font-family: var(--sl-mono); font-size: 12px; line-height: 20px; text-align: center; color: var(--sl-muted); }
.sl-step-body { display: flex; flex-direction: column; min-width: 0; }
.sl-step-label { font-size: 14px; font-weight: 500; color: var(--sl-text2); }
.sl-step-sub { font-size: 12px; color: var(--sl-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sl-flow li.is-done .sl-step-num { border-color: var(--sl-text2); color: var(--sl-text2); }
.sl-flow li.is-done .sl-step-sub { color: var(--sl-text); }
.sl-flow li.is-now { background: var(--sl-raised); box-shadow: inset 0 -2px 0 var(--sl-accent); }
.sl-flow li.is-now .sl-step-num { border-color: var(--sl-accent); background: var(--sl-accent); color: #ffffff; }
.sl-flow li.is-now .sl-step-label { color: var(--sl-text); font-weight: 600; }
.sl-flow li.is-now .sl-step-sub { color: var(--sl-text2); }

/* 홈: 오늘의 예시 흐름 */
.sl-story { display: grid; grid-template-columns: repeat(4, 1fr); border: 1px solid var(--sl-line); border-radius: 16px; overflow: hidden; background: #ffffff; }
.sl-story > div { position: relative; padding: 20px 20px 24px; }
.sl-story > div + div { border-left: 1px solid var(--sl-line); }
.sl-story > div + div::before { content: "→"; position: absolute; left: -9px; top: 22px; width: 16px; height: 16px; line-height: 16px;
  text-align: center; font-size: 12px; color: var(--sl-muted); background: #ffffff; }
.sl-story-q { font-size: 12px; color: var(--sl-muted); }
.sl-story-q b { font-family: var(--sl-mono); font-weight: 500; color: var(--sl-accent); margin-right: 6px; }
.sl-story-v { margin-top: 12px; font-size: 22px; font-weight: 600; line-height: 1.25; color: var(--sl-text); font-variant-numeric: tabular-nums; }
.sl-story-v.up { color: var(--sl-up); } .sl-story-v.down { color: var(--sl-down); }
.sl-story-t { margin-top: 8px; font-size: 13px; line-height: 1.55; color: var(--sl-text2); }
.sl-story > div:last-child { background: var(--sl-raised); }

/* 경제: 지금 보이는 변화 카드 */
.sl-now-card .sl-hint { margin-top: 4px; }
.sl-now-eff { display: flex; flex-direction: column; gap: 4px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--sl-line); font-size: 13px; color: var(--sl-text); }
.sl-now-eff b { font-size: 10px; font-weight: 400; margin-right: 4px; }
[data-testid="stMarkdownContainer"]:has(> .sl-now-card) { margin-bottom: 0 !important; }

/* 한 줄 해석 */
.sl-read { margin: 4px 0; padding: 14px 16px 14px 18px; border-left: 2px solid var(--sl-accent); background: var(--sl-raised); border-radius: 0 8px 8px 0; }
.sl-read-label { display: block; margin-bottom: 4px; font-size: 12px; color: var(--sl-muted); }
.sl-read p { margin: 0; font-size: 15px; line-height: 1.65; color: var(--sl-text); }
.sl-read b { font-weight: 600; font-variant-numeric: tabular-nums; }
.sl-read .up { color: var(--sl-up); } .sl-read .down { color: var(--sl-down); }
[data-testid="stMarkdownContainer"]:has(> .sl-read), [data-testid="stMarkdownContainer"]:has(> .sl-hint) { margin-bottom: 0 !important; }
.sl-hint { font-size: 13px; line-height: 1.5; color: var(--sl-text2); }

/* 52주 범위 */
.sl-range { padding: 4px 0 0; }
.sl-range-cap { font-size: 13px; color: var(--sl-text2); margin-bottom: 8px; }
.sl-range-bar { position: relative; height: 6px; border-radius: 3px; background: #e6e9ed; }
.sl-range-bar span { position: absolute; top: -5px; width: 4px; height: 16px; margin-left: -2px; border-radius: 2px; background: var(--sl-text); }
.sl-range-ends { display: flex; justify-content: space-between; margin-top: 6px; font-family: var(--sl-mono); font-size: 12px; color: var(--sl-muted); }

/* 산업 지도 */
.sl-now { display: flex; gap: 12px; align-items: baseline; padding: 12px 16px; font-size: 14px; }
.sl-now-name { flex: none; font-weight: 600; color: var(--sl-text); }
.sl-now-name::before { content: ""; display: inline-block; width: 6px; height: 6px; margin: 0 8px 2px 0; border-radius: 3px; background: var(--sl-accent); }
.sl-now-why { color: var(--sl-text2); font-variant-numeric: tabular-nums; }
.sl-path { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 0 4px; font-size: 14px; }
.sl-path-from { font-weight: 600; color: var(--sl-text); }
.sl-path-arrow { color: var(--sl-muted); }
.sl-path-ind { display: inline-flex; gap: 6px; align-items: center; padding: 4px 10px; border: 1px solid var(--sl-line); border-radius: 6px; color: var(--sl-text); }
.sl-path-ind b, .sl-side b { font-size: 10px; font-weight: 400; }
.is-up > b { color: var(--sl-accent); }
.is-down > b { color: var(--sl-ochre); }
.sl-side { display: flex; gap: 8px; align-items: center; padding: 16px 0 4px; font-size: 16px; font-weight: 600; color: var(--sl-text); }
.sl-side span { margin-left: auto; font-family: var(--sl-mono); font-size: 12px; font-weight: 400; color: var(--sl-muted); }
[class*="st-key-indcard_"] { gap: 8px; }
[class*="st-key-indcard_"] [data-testid="stHorizontalBlock"] { border-top: 1px solid var(--sl-line); padding-top: 4px; }
[class*="st-key-indcard_"] button[kind="tertiary"] p { font-size: 14px; color: var(--sl-text); }
[class*="st-key-indcard_"] button[kind="tertiary"]:hover p { color: var(--sl-accent); }
[class*="st-key-indcard_"] button[kind="tertiary"] [data-testid="stIconMaterial"] { color: var(--sl-muted); font-size: 16px; }
[data-testid="stMarkdownContainer"]:has(> .sl-ret) { margin-bottom: 0 !important; }
.sl-ret { text-align: right; font-family: var(--sl-mono); font-size: 13px; color: var(--sl-text2); font-variant-numeric: tabular-nums; }
.sl-ret span { margin-right: 8px; font-family: inherit; color: var(--sl-muted); font-size: 12px; }
.sl-ret.is-up { color: var(--sl-up); }
.sl-ret.is-down { color: var(--sl-down); }

.sl-ind { padding: 16px 20px; margin-bottom: 12px; }
.sl-ind-why { margin-top: 4px; font-size: 14px; line-height: 1.6; color: var(--sl-text2); }
.sl-ind-stocks { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.sl-ind-stocks span { padding: 2px 8px; border-radius: 4px; background: var(--sl-raised); font-size: 13px; color: var(--sl-text); }
.sl-ind-stocks em { font-style: normal; font-size: 13px; color: var(--sl-muted); }
[data-testid="stMarkdownContainer"]:has(> .sl-ind) { margin-bottom: 0 !important; }

/* 키보드 포커스 */
a:focus-visible, button:focus-visible { outline: 2px solid var(--sl-accent); outline-offset: 2px; }

@media (max-width: 900px) {
  .sl-flow, .sl-story { grid-template-columns: 1fr 1fr; }
  .sl-flow li:nth-child(3), .sl-story > div:nth-child(3) { border-left: none; }
  .sl-flow li:nth-child(n+3), .sl-story > div:nth-child(n+3) { border-top: 1px solid var(--sl-line); }
  .sl-story > div:nth-child(3)::before { display: none; }
}
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding-top: 72px; }
  .sl-insight { padding: 16px; }
  .sl-evt { grid-template-columns: 44px 1fr auto; }
}
</style>
"""


def style() -> None:
    """모든 페이지에 공통 스타일을 넣어요. app.py에서 한 번 불러요."""
    st.markdown(_CSS, unsafe_allow_html=True)
