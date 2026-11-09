"""data/ 폴더의 파일을 읽어 화면에서 쓰기 좋은 형태로 돌려줘요."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("DATA_DIR", ROOT / "data"))


@st.cache_data(ttl=600)
def config() -> dict:
    return yaml.safe_load((ROOT / "config" / "series.yaml").read_text(encoding="utf-8"))


def series_def(key: str) -> dict | None:
    for c in config()["countries"]:
        for s in c["series"]:
            if s["key"] == key:
                return {**s, "country": c["name"]}
    return None


@st.cache_data(ttl=600)
def series(key: str) -> pd.DataFrame | None:
    p = DATA / "series" / f"{key}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"]).dropna().sort_values("date")
    return df if not df.empty else None


@dataclass
class Latest:
    value: float
    date: pd.Timestamp
    change: float | None  # 비교 시점 대비 변화(같은 단위)
    change_label: str


def latest(key: str, months: int = 1) -> Latest | None:
    """가장 최근 값과 약 n개월 전 대비 변화."""
    df = series(key)
    if df is None:
        return None
    last = df.iloc[-1]
    ref_date = last["date"] - pd.DateOffset(months=months)
    past = df[df["date"] <= ref_date]
    change = float(last["value"] - past.iloc[-1]["value"]) if not past.empty else None
    label = f"{months}개월 전 대비" if months != 12 else "1년 전 대비"
    return Latest(float(last["value"]), last["date"], change, label)


def change_over(key: str, months: int) -> float | None:
    lt = latest(key, months)
    return lt.change if lt else None


@st.cache_data(ttl=600)
def meta() -> dict:
    p = DATA / "meta.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@st.cache_data(ttl=600)
def key_stats() -> pd.DataFrame | None:
    p = DATA / "kr_key_stats.csv"
    return pd.read_csv(p) if p.exists() else None


@st.cache_data(ttl=600)
def events() -> tuple[pd.DataFrame, dict]:
    """직접 적은 일정(events.yaml) + 자동 수집 일정(events_auto.csv)을 날짜순으로 합쳐요."""
    y = yaml.safe_load((DATA / "events.yaml").read_text(encoding="utf-8"))
    types = y.get("types", {})
    rows = []
    for e in y.get("events", []):
        t = types.get(e["type"], {})
        rows.append({**e, "date": pd.Timestamp(e["date"]), "term": e.get("term") or t.get("term", "")})
    auto = DATA / "events_auto.csv"
    if auto.exists():
        a = pd.read_csv(auto, parse_dates=["date"])
        rows += a.to_dict("records")
    df = pd.DataFrame(rows)
    if df.empty:
        return df, types
    df = df.drop_duplicates(subset=["date", "title"]).sort_values("date").reset_index(drop=True)
    df["d_day"] = (df["date"].dt.normalize() - pd.Timestamp(date.today())).dt.days
    return df, types


def has_any_series() -> bool:
    d = DATA / "series"
    return d.exists() and any(d.glob("*.csv"))
