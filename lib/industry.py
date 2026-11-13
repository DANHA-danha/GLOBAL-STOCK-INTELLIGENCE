"""산업 지도 데이터와 '지금 해당되는 변화' 판단."""
from __future__ import annotations

import pandas as pd
import streamlit as st
import yaml

from lib import data, events, stocks
from lib.data import ROOT


@st.cache_data(ttl=600)
def drivers() -> list[dict]:
    return yaml.safe_load((ROOT / "config" / "industry_map.yaml").read_text(encoding="utf-8"))["drivers"]


def driver(did: str) -> dict | None:
    return next((d for d in drivers() if d["id"] == did), None)


def detect_now() -> dict[str, str]:
    """지금 지표로 판단되는 변화와 그 근거."""
    out: dict[str, str] = {}

    ev = events.fed_events()
    if not ev.empty:
        last = ev.iloc[-1]
        days = (pd.Timestamp.today() - last["effective"]).days
        if days <= 180:
            key = "rate_cut" if last["direction"] == "인하" else "rate_hike"
            out[key] = f"미국이 {last['announced']:%Y-%m-%d}에 기준금리를 {abs(last['change']):.2f}%p {last['direction']}했어요 (상단 {last['level']:.2f}%)."

    kr = data.series("kr_base_rate")
    if kr is not None and len(kr) > 7:
        k = kr.set_index("date")["value"]
        d6 = k.iloc[-1] - k[k.index <= k.index[-1] - pd.DateOffset(months=6)].iloc[-1]
        if abs(d6) >= 0.25:
            key = "rate_cut" if d6 < 0 else "rate_hike"
            msg = f"한국은행 기준금리가 6개월 동안 {d6:+.2f}%p 바뀌었어요 (지금 {k.iloc[-1]:.2f}%)."
            out[key] = (out[key] + " " + msg) if key in out else msg

    fx = data.change_over("kr_usdkrw", 3)
    if fx is not None:
        if fx >= 30:
            out["krw_weak"] = f"원/달러 환율이 3개월 동안 {fx:+,.0f}원 올랐어요."
        elif fx <= -30:
            out["krw_strong"] = f"원/달러 환율이 3개월 동안 {fx:+,.0f}원 내렸어요."

    oil = data.series("cm_wti")
    if oil is not None and len(oil) > 70:
        o = oil.set_index("date")["value"]
        past = o[o.index <= o.index[-1] - pd.DateOffset(months=3)]
        if not past.empty:
            pct = (o.iloc[-1] / past.iloc[-1] - 1) * 100
            if pct >= 10:
                out["oil_up"] = f"WTI 유가가 3개월 동안 {pct:+.0f}% 올랐어요 (배럴당 {o.iloc[-1]:.1f}달러)."
            elif pct <= -10:
                out["oil_down"] = f"WTI 유가가 3개월 동안 {pct:+.0f}% 내렸어요 (배럴당 {o.iloc[-1]:.1f}달러)."
    return out


def stocks_in(industries: list[str]) -> list[dict]:
    return [s for s in stocks.universe()["stocks"] if s["industry"] in industries]


def recent_return(code: str, months: int = 3) -> float | None:
    px = stocks.prices(code)
    if px is None or len(px) < 30:
        return None
    s = px.set_index("date")["adj_close"]
    past = s[s.index <= s.index[-1] - pd.DateOffset(months=months)]
    return None if past.empty else (s.iloc[-1] / past.iloc[-1] - 1) * 100
