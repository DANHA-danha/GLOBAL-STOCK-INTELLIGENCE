"""경제 지표 수집 스크립트

한국은행 ECOS와 미국 FRED에서 config/series.yaml에 적힌 지표를 받아
data/series/<key>.csv 로 저장해요. 앱은 이 CSV만 읽기 때문에 API가 잠깐 막혀도 화면은 그대로 떠요.

실행:
    python scripts/collect.py            # 전체 수집
    python scripts/collect.py --only US  # 한 나라만

API 키는 환경변수 또는 프로젝트 폴더의 .env 파일에 넣어요.
    ECOS_API_KEY=...
    FRED_API_KEY=...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("DATA_DIR", ROOT / "data"))
SERIES_DIR = DATA / "series"
START = date(2015, 1, 1)
TIMEOUT = 20
KST = timezone(timedelta(hours=9))


def load_env() -> None:
    """프로젝트 폴더의 .env 를 읽어 환경변수로 넣어요(이미 있는 값은 그대로 둬요)."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---------- 한국은행 ECOS ----------
def ecos_period(d: date, cycle: str) -> str:
    if cycle == "D":
        return d.strftime("%Y%m%d")
    if cycle == "M":
        return d.strftime("%Y%m")
    if cycle == "Q":
        return f"{d.year}Q{(d.month - 1) // 3 + 1}"
    return str(d.year)


def parse_ecos_time(t: str, cycle: str) -> pd.Timestamp:
    if cycle == "D":
        return pd.to_datetime(t, format="%Y%m%d")
    if cycle == "M":
        return pd.to_datetime(t, format="%Y%m")
    if cycle == "Q":
        y, q = t.split("Q")
        return pd.Timestamp(int(y), (int(q) - 1) * 3 + 1, 1)
    return pd.Timestamp(int(t), 1, 1)


def fetch_ecos(s: dict, key: str) -> pd.DataFrame:
    cycle = s.get("cycle", "M")
    start = START - timedelta(days=400) if s.get("transform") == "yoy" else START
    url = (
        f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/100000/"
        f"{s['stat']}/{cycle}/{ecos_period(start, cycle)}/{ecos_period(date.today(), cycle)}/{s['item']}"
    )
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    js = r.json()
    if "StatisticSearch" not in js:
        msg = js.get("RESULT", {}).get("MESSAGE", str(js)[:200])
        raise RuntimeError(f"ECOS 응답 오류: {msg}")
    rows = js["StatisticSearch"]["row"]
    df = pd.DataFrame(
        {
            "date": [parse_ecos_time(x["TIME"], cycle) for x in rows],
            "value": pd.to_numeric([x["DATA_VALUE"] for x in rows], errors="coerce"),
        }
    )
    return df


def fetch_ecos_key_stats(names: list[str], key: str) -> pd.DataFrame:
    url = f"https://ecos.bok.or.kr/api/KeyStatisticList/{key}/json/kr/1/200"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    rows = r.json().get("KeyStatisticList", {}).get("row", [])
    picked = []
    for name in names:
        for x in rows:
            if name in x.get("KEYSTAT_NAME", ""):
                picked.append(
                    {
                        "group": x.get("CLASS_NAME", ""),
                        "name": x.get("KEYSTAT_NAME", ""),
                        "value": x.get("DATA_VALUE", ""),
                        "unit": x.get("UNIT_NAME", ""),
                        "period": x.get("CYCLE", ""),
                    }
                )
    return pd.DataFrame(picked).drop_duplicates(subset=["name"]) if picked else pd.DataFrame()


# ---------- 미국 FRED ----------
def fetch_fred(s: dict, key: str) -> pd.DataFrame:
    start = START - timedelta(days=400) if s.get("transform") == "yoy" else START
    r = requests.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": s["id"],
            "api_key": key,
            "file_type": "json",
            "observation_start": start.isoformat(),
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    obs = r.json().get("observations", [])
    df = pd.DataFrame(
        {
            "date": pd.to_datetime([o["date"] for o in obs]),
            "value": pd.to_numeric([o["value"] for o in obs], errors="coerce"),  # "." = 값 없음
        }
    )
    return df


def fetch_fred_release_dates(rel: dict, key: str) -> list[dict]:
    today = date.today().isoformat()
    r = requests.get(
        "https://api.stlouisfed.org/fred/release/dates",
        params={
            "release_id": rel["id"],
            "api_key": key,
            "file_type": "json",
            "realtime_start": today,
            "include_release_dates_with_no_data": "true",
            "sort_order": "asc",
            "limit": 24,
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    out = []
    for x in r.json().get("release_dates", []):
        if x["date"] >= today:
            out.append(
                {
                    "date": x["date"],
                    "type": "미국 지표",
                    "title": rel["name"],
                    "term": rel.get("term", ""),
                    "source": "FRED 발표 일정",
                    "url": f"https://fred.stlouisfed.org/releases/calendar?rid={rel['id']}",
                }
            )
    return out


# ---------- 공통 ----------
def apply_transform(df: pd.DataFrame, s: dict) -> pd.DataFrame:
    df = df.dropna().sort_values("date").reset_index(drop=True)
    if s.get("transform") == "yoy":
        df = df.set_index("date")["value"]
        df = (df / df.shift(12) - 1) * 100  # 월별 지수 → 전년 같은 달 대비 %
        df = df.dropna().reset_index()
        df.columns = ["date", "value"]
    df = df[df["date"] >= pd.Timestamp(START)]
    df["value"] = df["value"].round(4)
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="나라 코드 하나만 수집 (예: KR, US)")
    args = ap.parse_args()

    load_env()
    ecos_key = os.environ.get("ECOS_API_KEY", "")
    fred_key = os.environ.get("FRED_API_KEY", "")
    cfg = yaml.safe_load((ROOT / "config" / "series.yaml").read_text(encoding="utf-8"))
    SERIES_DIR.mkdir(parents=True, exist_ok=True)

    ok, failed, skipped = [], [], []
    for c in cfg["countries"]:
        if args.only and c["code"] != args.only:
            continue
        for s in c["series"]:
            key = ecos_key if s["source"] == "ecos" else fred_key
            if not key:
                skipped.append(f"{s['key']} ({s['source'].upper()} 키 없음)")
                continue
            try:
                raw = fetch_ecos(s, key) if s["source"] == "ecos" else fetch_fred(s, key)
                df = apply_transform(raw, s)
                if df.empty:
                    raise RuntimeError("받은 값이 없어요")
                df.to_csv(SERIES_DIR / f"{s['key']}.csv", index=False, date_format="%Y-%m-%d")
                ok.append(f"{s['key']} ({len(df)}개, 최신 {df['date'].iloc[-1]:%Y-%m-%d})")
            except Exception as e:  # 한 지표가 실패해도 나머지는 계속 받아요
                failed.append(f"{s['key']}: {e}")

    if ecos_key and not args.only:
        try:
            ks = fetch_ecos_key_stats(cfg.get("ecos_key_stats", []), ecos_key)
            if not ks.empty:
                ks.to_csv(DATA / "kr_key_stats.csv", index=False)
                ok.append(f"kr_key_stats ({len(ks)}개)")
        except Exception as e:
            failed.append(f"kr_key_stats: {e}")

    if fred_key and not args.only:
        events = []
        for rel in cfg.get("fred_releases", []):
            try:
                events += fetch_fred_release_dates(rel, fred_key)
            except Exception as e:
                failed.append(f"release {rel['id']}: {e}")
        if events:
            pd.DataFrame(events).to_csv(DATA / "events_auto.csv", index=False)
            ok.append(f"events_auto ({len(events)}개)")

    meta = {
        "collected_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "ok": ok,
        "failed": failed,
        "skipped": skipped,
    }
    (DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"성공 {len(ok)}개")
    for x in ok:
        print("  ✓", x)
    if skipped:
        print(f"건너뜀 {len(skipped)}개")
        for x in skipped:
            print("  -", x)
    if failed:
        print(f"실패 {len(failed)}개")
        for x in failed:
            print("  ✗", x)
    return 0 if ok or not failed else 1


if __name__ == "__main__":
    sys.exit(main())
