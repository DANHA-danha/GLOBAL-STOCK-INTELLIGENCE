"""이벤트 스터디: 금리 결정 같은 사건 전후로 주가가 평균적으로 어떻게 움직였는지 계산해요."""
from __future__ import annotations

import pandas as pd

from lib import stocks
from lib.data import series

US_CODES = {"^GSPC", "^IXIC"}


def is_us(code: str) -> bool:
    s = stocks.stock(code)
    return code in US_CODES or (s is not None and s["market"] == "US")


def fed_events() -> pd.DataFrame:
    """미국 기준금리(상단)가 바뀐 날을 모두 찾아요.

    FRED의 기준금리 값은 발표 다음 날부터 바뀌어 있어서, 바뀐 날(effective) 하루 전을 발표일로 봐요.
    """
    df = series("us_fed_upper")
    if df is None or len(df) < 2:
        return pd.DataFrame()
    df = df.sort_values("date").reset_index(drop=True)
    df["prev"] = df["value"].shift(1)
    ch = df[(df["value"] != df["prev"]) & df["prev"].notna()].copy()
    if ch.empty:
        return pd.DataFrame()
    ch["change"] = (ch["value"] - ch["prev"]).round(2)
    ch["direction"] = ch["change"].apply(lambda x: "인하" if x < 0 else "인상")
    ch["effective"] = ch["date"]
    ch["announced"] = ch["date"] - pd.Timedelta(days=1)
    # 사이클의 첫 결정: 직전 변경과 방향이 다르거나, 직전 변경 후 180일 넘게 쉬었을 때
    ch = ch.reset_index(drop=True)
    firsts = []
    for i, r in ch.iterrows():
        if i == 0:
            firsts.append(True)
            continue
        p = ch.iloc[i - 1]
        firsts.append(p["direction"] != r["direction"] or (r["effective"] - p["effective"]).days > 180)
    ch["first"] = firsts
    return ch[["announced", "effective", "direction", "change", "value", "first"]].rename(columns={"value": "level"})


def window(code: str, effective: pd.Timestamp, before: int, after: int) -> pd.Series | None:
    """한 사건 전후 주가를 '반응 전날 = 100'으로 맞춘 값. 인덱스는 거래일 기준 위치(0 = 반응한 날)."""
    px = stocks.prices(code)
    if px is None:
        return None
    s = px.set_index("date")["adj_close"].astype(float)
    idx = s.index
    if is_us(code):
        # 미국은 발표 당일(오후 2시) 종가에 반응이 들어가요 → 바뀐 날 직전 거래일
        pos = idx.searchsorted(effective, side="left") - 1
    else:
        # 한국은 다음 날 아침 장에서 반응 → 바뀐 날 이후 첫 거래일
        pos = idx.searchsorted(effective, side="left")
    if pos - 1 < 0 or pos >= len(idx):
        return None
    base = s.iloc[pos - 1]
    lo, hi = max(0, pos - before), min(len(idx) - 1, pos + after)
    seg = s.iloc[lo:hi + 1] / base * 100
    seg.index = range(lo - pos, hi - pos + 1)
    if seg.index.min() > -min(before, 5):  # 발표 전 데이터가 거의 없으면 버려요
        return None
    return seg


def study(code: str, events: pd.DataFrame, before: int, after: int) -> tuple[pd.DataFrame, pd.Series]:
    """사건별 경로(열 = 사건)와 평균 경로."""
    paths = {}
    for _, e in events.iterrows():
        w = window(code, e["effective"], before, after)
        if w is not None:
            paths[e["announced"]] = w
    if not paths:
        return pd.DataFrame(), pd.Series(dtype=float)
    m = pd.DataFrame(paths)
    return m, m.mean(axis=1)


def ret(path: pd.Series, a: int, b: int) -> float | None:
    """경로에서 위치 a → b 사이 수익률(%)."""
    if a not in path.index or b not in path.index:
        return None
    va, vb = path.loc[a], path.loc[b]
    if pd.isna(va) or pd.isna(vb):
        return None
    return (vb / va - 1) * 100
