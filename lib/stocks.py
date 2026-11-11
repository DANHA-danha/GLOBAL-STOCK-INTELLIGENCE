"""종목 데이터 읽기와 계산: 투자 지표, 연도별 수익률, 모의투자."""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
import streamlit as st
import yaml

from lib.data import DATA, ROOT, series

STOCKS = DATA / "stocks"


def folder(code: str):
    return STOCKS / code.replace("^", "IDX_")


@st.cache_data(ttl=600)
def universe() -> dict:
    return yaml.safe_load((ROOT / "config" / "universe.yaml").read_text(encoding="utf-8"))


def stock(code: str) -> dict | None:
    for s in universe()["stocks"]:
        if s["code"] == code:
            return s
    return None


def benchmark_for(code: str) -> tuple[str, str]:
    s = stock(code)
    return ("^GSPC", "S&P 500") if s and s["market"] == "US" else ("^KS11", "코스피")


@st.cache_data(ttl=600)
def prices(code: str) -> pd.DataFrame | None:
    p = folder(code) / "prices.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"]).sort_values("date")
    return df if not df.empty else None


@st.cache_data(ttl=600)
def financials(code: str) -> pd.DataFrame | None:
    p = folder(code) / "financials.csv"
    return pd.read_csv(p) if p.exists() else None


@st.cache_data(ttl=600)
def info(code: str) -> dict:
    p = folder(code) / "info.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def has_any() -> bool:
    return STOCKS.exists() and any(STOCKS.glob("*/prices.csv"))


def meta() -> dict:
    p = DATA / "stocks_meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# ---------- 투자 지표 ----------
@dataclass
class Metrics:
    price: float | None = None
    price_date: pd.Timestamp | None = None
    market_cap: float | None = None   # 원
    per: float | None = None
    pbr: float | None = None
    roe: float | None = None          # %
    op_margin: float | None = None    # %
    debt_ratio: float | None = None   # %
    div_yield: float | None = None    # %
    high_52w: float | None = None
    low_52w: float | None = None
    fin_year: int | None = None


def metrics(code: str) -> Metrics:
    m = Metrics()
    px = prices(code)
    if px is not None:
        last = px.iloc[-1]
        m.price, m.price_date = float(last["close"]), last["date"]
        y1 = px[px["date"] >= last["date"] - pd.DateOffset(years=1)]
        m.high_52w, m.low_52w = float(y1["close"].max()), float(y1["close"].min())
        divs = y1["dividend"].sum() if "dividend" in y1 else 0
        if divs > 0 and m.price:
            m.div_yield = divs / m.price * 100

    fin = financials(code)
    if fin is not None and not fin.empty:
        f = fin.sort_values("year").iloc[-1]
        m.fin_year = int(f["year"])
        if pd.notna(f.get("equity")) and f["equity"] and pd.notna(f.get("net_income")):
            m.roe = f["net_income"] / f["equity"] * 100
        if pd.notna(f.get("revenue")) and f["revenue"] and pd.notna(f.get("operating_income")):
            m.op_margin = f["operating_income"] / f["revenue"] * 100
        if pd.notna(f.get("equity")) and f["equity"] and pd.notna(f.get("liabilities")):
            m.debt_ratio = f["liabilities"] / f["equity"] * 100
        shares = info(code).get("shares", {}).get("common")
        if shares and m.price:
            m.market_cap = m.price * shares  # 보통주 기준 근사치
            if pd.notna(f.get("net_income")) and f["net_income"] > 0:
                m.per = m.market_cap / f["net_income"]
            if pd.notna(f.get("equity")) and f["equity"] > 0:
                m.pbr = m.market_cap / f["equity"]
    return m


def annual_returns(code: str) -> pd.DataFrame | None:
    """연도별 수익률(배당 포함 수정주가 기준). 올해는 연초부터 지금까지."""
    px = prices(code)
    if px is None:
        return None
    s = px.set_index("date")["adj_close"]
    ye = s.groupby(s.index.year).last()
    rows = []
    for y, v in ye.items():
        prev = ye.get(y - 1)
        if prev is None:  # 첫해는 비교할 전년 말 값이 없어요
            continue
        rows.append({"year": int(y), "return": (v / prev - 1) * 100, "partial": y == s.index[-1].year})
    return pd.DataFrame(rows)


def max_drawdown(s: pd.Series) -> tuple[float, pd.Timestamp | None, pd.Timestamp | None]:
    peak = s.cummax()
    dd = s / peak - 1
    if dd.empty:
        return 0.0, None, None
    trough = dd.idxmin()
    peak_date = s.loc[:trough].idxmax()
    return float(dd.min() * 100), peak_date, trough


# ---------- 모의투자 ----------
@dataclass
class SimResult:
    name: str
    code: str
    invested: float
    final: float
    profit: float
    total_return: float      # %
    cagr: float | None       # % (적립식은 연환산 수익률 = IRR)
    mdd: float               # % (기간 중 가격 최대 낙폭)
    curve: pd.DataFrame      # date, value, invested
    start: pd.Timestamp
    end: pd.Timestamp


def _price_series(code: str, with_div: bool, krw: bool) -> pd.Series | None:
    px = prices(code)
    if px is None:
        return None
    s = px.set_index("date")["adj_close" if with_div else "close"].astype(float)
    if krw:
        fx = series("kr_usdkrw")
        if fx is not None:
            f = fx.set_index("date")["value"].reindex(s.index.union(fx["date"])).ffill().reindex(s.index)
            s = (s * f).dropna()
    return s


def _xirr(flows: list[tuple[pd.Timestamp, float]]) -> float | None:
    t0 = flows[0][0]

    def npv(r: float) -> float:
        return sum(cf / (1 + r) ** ((d - t0).days / 365.25) for d, cf in flows)

    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2 * 100


def simulate(code: str, name: str, start: pd.Timestamp, amount: float, monthly: bool,
             with_div: bool = True, krw: bool = False) -> SimResult | None:
    s = _price_series(code, with_div, krw)
    if s is None:
        return None
    s = s[s.index >= start]
    if len(s) < 2:
        return None
    if monthly:
        buy_days = s.groupby([s.index.year, s.index.month]).head(1).index
        units = pd.Series(0.0, index=s.index)
        inv = pd.Series(0.0, index=s.index)
        units.loc[buy_days] = amount / s.loc[buy_days]
        inv.loc[buy_days] = amount
        units, inv = units.cumsum(), inv.cumsum()
        value = units * s
        flows = [(d, -amount) for d in buy_days] + [(s.index[-1], float(value.iloc[-1]))]
        cagr = _xirr(flows)
    else:
        units = amount / s.iloc[0]
        value = units * s
        inv = pd.Series(amount, index=s.index)
        years = (s.index[-1] - s.index[0]).days / 365.25
        cagr = ((value.iloc[-1] / amount) ** (1 / years) - 1) * 100 if years >= 0.5 else None
    invested, final = float(inv.iloc[-1]), float(value.iloc[-1])
    mdd, _, _ = max_drawdown(s)
    return SimResult(
        name=name, code=code, invested=invested, final=final, profit=final - invested,
        total_return=(final / invested - 1) * 100, cagr=cagr, mdd=mdd,
        curve=pd.DataFrame({"date": s.index, "value": value.values, "invested": inv.values}),
        start=s.index[0], end=s.index[-1],
    )


def won(v: float | None) -> str:
    """원 단위 금액을 억·만으로."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    neg = v < 0
    v = abs(v)
    if v >= 1e12:
        s = f"{v / 1e12:,.1f}조"
    elif v >= 1e8:
        s = f"{v / 1e8:,.1f}억"
    elif v >= 1e4:
        s = f"{v / 1e4:,.0f}만"
    else:
        s = f"{v:,.0f}"
    return ("−" if neg else "") + s + "원"
