"""화면 공통 요소: 지표 카드, 차트, 안내 문구."""
from __future__ import annotations

import inspect

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import data
from lib.glossary import term

ACCENT = "#1d5c73"

# st.metric의 delta_arrow는 최신 Streamlit에만 있어서, 지원할 때만 넘긴다
_HAS_DELTA_ARROW = "delta_arrow" in inspect.signature(st.metric).parameters


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
    """지표 하나: 최신값, 변화, 1년 추이 미니 차트."""
    s = data.series_def(key)
    if not s:
        return
    label = f"{s['country']} {s['label']}" if with_country else s["label"]
    lt = data.latest(key, months)
    if lt is None:
        st.metric(label, "—", help="아직 수집된 값이 없어요. README의 '데이터 받기'를 따라 해 주세요.")
        return
    df = data.series(key)
    recent = df[df["date"] >= lt.date - pd.DateOffset(years=1)]["value"].tolist()

    # 변화가 사실상 0이면 화살표 대신 "변동 없음"
    unchanged = lt.change is not None and abs(lt.change) < 0.005
    delta = "변동 없음" if unchanged else fmt_change(lt.change, s.get("unit", ""))
    color = "off" if unchanged else ("inverse" if s.get("up_is_bad") else "normal")

    # 마지막 값이 너무 오래됐으면(발표 중단 등) 날짜를 눈에 띄게 표시
    age = (pd.Timestamp.today().normalize() - lt.date).days
    stale = age > 200
    extra = {"delta_arrow": "off" if unchanged else "auto"} if _HAS_DELTA_ARROW else {}
    st.metric(
        label + (f" · {lt.date:%Y-%m} 이후 갱신 없음" if stale else ""),
        fmt(lt.value, s.get("unit", "")),
        delta=delta,
        delta_color=color,
        **extra,
        help=f"{lt.date:%Y-%m-%d} 기준 · {lt.change_label}",
        chart_data=recent if len(recent) > 2 else None,
        chart_type="line",
        border=True,
    )
    if show_term and s.get("term"):
        term(s["term"], f"{s['term']}란?")


def line_chart(keys: list[str], years: int = 5, title: str | None = None, height: int = 320) -> None:
    """여러 지표를 한 차트에. 단위가 같은 것끼리만 묶어요."""
    fig = go.Figure()
    palette = [ACCENT, "#c2603c", "#6b7f2a", "#7a5aa6"]
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
                mode="lines", line=dict(width=2.2, color=palette[i % len(palette)]),
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f}<extra>%{fullData.name}</extra>",
            )
        )
        any_data = True
    if not any_data:
        st.caption("차트에 쓸 데이터가 아직 없어요.")
        return
    fig.update_layout(
        title=title, height=height, margin=dict(l=8, r=8, t=40 if title else 10, b=8),
        legend=dict(orientation="h", y=-0.15), hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)", zeroline=False)
    fig.update_xaxes(showgrid=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


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
                    term(e["term"], f"{e['term']}란?")
