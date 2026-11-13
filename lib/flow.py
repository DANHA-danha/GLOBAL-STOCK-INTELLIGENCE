"""세계 경제 → 산업과 회사 → 주가 → 내가 샀다면, 네 단계를 잇는 흐름.

페이지를 옮겨 다녀도 고른 것이 이어지도록 위젯이 아닌 session_state 키에 따로 담아 둬요.
(위젯 키는 그 위젯이 없는 페이지로 가면 Streamlit이 지워요.)
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

import pandas as pd
import streamlit as st

from lib import data, industry, stocks

PAGES = {
    1: "views/economy.py",
    2: "views/industry.py",
    3: "views/company.py",
    4: "views/simulator.py",
}
STEPS = [
    (1, "세계 경제", "무엇이 변했나"),
    (2, "산업과 회사", "어디가 유리하고, 누가 잘 버나"),
    (3, "회사와 주가", "그 회사 주가는 어땠나"),
    (4, "내가 샀다면", "그때 샀으면 지금 얼마일까"),
]


def get(key: str, default=None):
    return st.session_state.get(f"flow_{key}", default)


def put(**kw) -> None:
    for k, v in kw.items():
        st.session_state[f"flow_{k}"] = v


def _values() -> dict[int, str]:
    out: dict[int, str] = {}
    d = industry.driver(get("driver")) if get("driver") else None
    if d:
        out[1] = d["name"]
    bits = [b for b in (get("industry"), _name(get("company"))) if b]
    if bits:
        out[2] = " · ".join(bits)
    if get("company"):
        out[3] = _name(get("company"))
    return out


def _name(code: str | None) -> str | None:
    if not code:
        return None
    s = stocks.stock(code)
    return s["name"] if s else code


def bar(current: int) -> None:
    """페이지 맨 위의 단계 표시줄. 지금까지 고른 것을 이어서 보여줘요."""
    vals = _values()
    items = []
    for n, label, q in STEPS:
        state = "is-now" if n == current else ("is-done" if n < current else "")
        val = vals.get(n)
        sub = escape(val) if val and n != current else escape(q)
        items.append(
            f'<li class="{state}"><span class="sl-step-num">{n}</span>'
            f'<span class="sl-step-body"><span class="sl-step-label">{escape(label)}</span>'
            f'<span class="sl-step-sub">{sub}</span></span></li>'
        )
    st.markdown(f'<ol class="sl-flow">{"".join(items)}</ol>', unsafe_allow_html=True)


def next_button(step: int, label: str, key: str, **state) -> None:
    """다음 단계로 가는 버튼. 누르면 고른 것을 저장하고 그 페이지로 가요."""
    if st.button(label, key=key, type="primary", icon=":material/arrow_forward:"):
        put(**state)
        st.switch_page(PAGES[step])


# ---------- 홈 첫 화면 예시 ----------
@dataclass
class Example:
    detected: bool
    driver: dict
    why: str
    effect: dict
    code: str
    name: str
    margin: float | None
    roe: float | None
    price_ret: float | None
    years: int
    invested: float
    final: float | None


def _related(effect: dict) -> list[dict]:
    return industry.stocks_in(effect.get("universe", []))


def example(years: int = 3, amount: float = 10_000_000) -> Example | None:
    """오늘 지표로 보이는 변화 하나를 골라 네 단계를 끝까지 계산해 봐요."""
    now = industry.detect_now()
    drivers = industry.drivers()
    order = [d for d in drivers if d["id"] in now] + [d for d in drivers if d["id"] not in now]
    for d in order:
        for e in [x for x in d["effects"] if x["sign"] == "up"]:
            cands = []
            for s in _related(e):
                m = stocks.metrics(s["code"])
                if m.price is None:
                    continue
                cands.append((m.op_margin if m.op_margin is not None else -999, s, m))
            if not cands:
                continue
            _, s, m = max(cands, key=lambda c: c[0])
            px = stocks.prices(s["code"])
            start = px["date"].max() - pd.DateOffset(years=years)
            v = px[px["date"] >= start]
            price_ret = (v["close"].iloc[-1] / v["close"].iloc[0] - 1) * 100 if len(v) > 1 else None
            is_us = s["market"] == "US"
            krw = is_us and data.series("kr_usdkrw") is not None
            amt = amount if (not is_us or krw) else amount / 1400
            r = stocks.simulate(s["code"], s["name"], start, amt, False, with_div=True, krw=krw)
            return Example(
                detected=d["id"] in now, driver=d, why=now.get(d["id"], d["summary"]), effect=e,
                code=s["code"], name=s["name"], margin=m.op_margin, roe=m.roe,
                price_ret=price_ret, years=years, invested=amt,
                final=r.final if r else None,
            )
    return None
