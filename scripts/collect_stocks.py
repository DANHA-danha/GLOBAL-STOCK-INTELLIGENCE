"""종목 데이터 수집 스크립트

config/universe.yaml 의 종목마다
  - 주가(10년, 일별 종가·수정종가·거래량·배당): Yahoo Finance(yfinance)
  - 한국 종목만: 기업 개요, 연간 재무제표(최근 6년), 발행주식수: Open DART
를 받아 data/stocks/<코드>/ 에 저장해요.

실행:
    python3 scripts/collect_stocks.py
    python3 scripts/collect_stocks.py --only 005930   # 한 종목만

필요한 키(.env 또는 환경변수): DART_API_KEY  (주가는 키 없이 받아요)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from collect import load_env  # noqa: E402  같은 .env 읽기 함수를 써요

DATA = Path(os.environ.get("DATA_DIR", ROOT / "data"))
STOCKS = DATA / "stocks"
DART = "https://opendart.fss.or.kr/api"
TIMEOUT = 30
KST = timezone(timedelta(hours=9))

# DART "단일회사 주요계정"에서 찾을 계정 이름 (회사마다 표기가 조금씩 달라요)
ACCOUNTS = {
    "revenue": ["매출액", "수익(매출액)", "영업수익", "매출"],
    "operating_income": ["영업이익", "영업이익(손실)"],
    "net_income": ["당기순이익", "당기순이익(손실)"],
    "assets": ["자산총계"],
    "liabilities": ["부채총계"],
    "equity": ["자본총계"],
}


def yahoo_symbol(s: dict) -> str:
    if s["market"] == "KOSPI":
        return f"{s['code']}.KS"
    if s["market"] == "KOSDAQ":
        return f"{s['code']}.KQ"
    return s["code"]


# ---------- 주가 ----------
def fetch_prices(symbol: str) -> pd.DataFrame:
    import yfinance as yf

    h = yf.Ticker(symbol).history(period="10y", auto_adjust=False, actions=True)
    if h is None or h.empty:
        raise RuntimeError("주가를 받지 못했어요")
    h = h.reset_index()
    d = pd.to_datetime(h["Date"])
    if d.dt.tz is not None:
        d = d.dt.tz_localize(None)
    zero = pd.Series(0.0, index=h.index)
    out = pd.DataFrame(
        {
            "date": d.dt.normalize(),
            "close": h["Close"].round(4),
            "adj_close": (h["Adj Close"] if "Adj Close" in h else h["Close"]).round(4),
            "volume": h["Volume"].fillna(0).astype("int64") if "Volume" in h else zero.astype("int64"),
            "dividend": (h["Dividends"] if "Dividends" in h else zero).fillna(0).round(4),
        }
    )
    return out.dropna(subset=["close"])


# ---------- Open DART ----------
def dart_get(path: str, key: str, **params) -> dict:
    r = requests.get(f"{DART}/{path}", params={"crtfc_key": key, **params}, timeout=TIMEOUT)
    r.raise_for_status()
    js = r.json()
    status = js.get("status")
    if status not in ("000", "013"):  # 013 = 조회된 데이터 없음
        raise RuntimeError(f"DART {path}: {js.get('message', status)}")
    return js


def corp_codes(key: str) -> dict[str, str]:
    """종목코드 → DART 고유번호. 한 번 받으면 data/dart_corp_codes.csv 에 저장해 다시 써요."""
    cache = DATA / "dart_corp_codes.csv"
    if cache.exists() and (time.time() - cache.stat().st_mtime) < 30 * 86400:
        df = pd.read_csv(cache, dtype=str)
        return dict(zip(df["stock_code"], df["corp_code"]))
    r = requests.get(f"{DART}/corpCode.xml", params={"crtfc_key": key}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml = z.read(z.namelist()[0])
    rows = []
    for el in ET.fromstring(xml).iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        if sc:
            rows.append({"stock_code": sc, "corp_code": el.findtext("corp_code"), "corp_name": el.findtext("corp_name")})
    df = pd.DataFrame(rows)
    df.to_csv(cache, index=False)
    return dict(zip(df["stock_code"], df["corp_code"]))


def to_num(x) -> float | None:
    try:
        return float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def pick(rows: list[dict], names: list[str], fs_div: str, col: str) -> float | None:
    for n in names:
        for r in rows:
            if r.get("fs_div") == fs_div and r.get("account_nm", "").replace(" ", "") == n.replace(" ", ""):
                v = to_num(r.get(col))
                if v is not None:
                    return v
    return None


def fetch_financials(corp: str, key: str) -> pd.DataFrame:
    """사업보고서 기준 연간 주요계정. 한 번 조회하면 3개 연도가 와서 두 번 조회해 최근 6년을 만들어요."""
    last_year = date.today().year - 1
    if date.today().month < 4:  # 사업보고서는 3월 말까지 나와요
        last_year -= 1
    years: dict[int, dict] = {}
    for base in (last_year, last_year - 3):
        js = dart_get("fnlttSinglAcnt.json", key, corp_code=corp, bsns_year=str(base), reprt_code="11011")
        rows = js.get("list", [])
        if not rows:
            continue
        fs = "CFS" if any(r.get("fs_div") == "CFS" for r in rows) else "OFS"  # 연결 우선
        for offset, col in ((0, "thstrm_amount"), (1, "frmtrm_amount"), (2, "bfefrmtrm_amount")):
            y = base - offset
            if y in years:
                continue
            rec = {k: pick(rows, names, fs, col) for k, names in ACCOUNTS.items()}
            if any(v is not None for v in rec.values()):
                years[y] = {"year": y, "basis": "연결" if fs == "CFS" else "별도", **rec}
    if not years:
        raise RuntimeError("재무제표가 없어요")
    return pd.DataFrame(sorted(years.values(), key=lambda r: r["year"]))


def fetch_overview(corp: str, key: str) -> dict:
    js = dart_get("company.json", key, corp_code=corp)
    keep = ["corp_name", "corp_name_eng", "stock_code", "ceo_nm", "est_dt", "induty_code", "hm_url", "adres", "acc_mt"]
    return {k: js.get(k, "") for k in keep}


def fetch_shares(corp: str, key: str, year: int) -> dict:
    """보통주·우선주 발행주식수(사업보고서 기준)."""
    for y in (year, year - 1):
        js = dart_get("stockTotqySttus.json", key, corp_code=corp, bsns_year=str(y), reprt_code="11011")
        out = {"year": y}
        for r in js.get("list", []):
            se = r.get("se", "")
            n = to_num(r.get("istc_totqy"))
            if "보통" in se:
                out["common"] = n
            elif "우선" in se:
                out["preferred"] = n
        if out.get("common"):
            return out
    return {}


# ---------- 실행 ----------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="종목코드 하나만 (예: 005930, NVDA)")
    args = ap.parse_args()

    load_env()
    key = os.environ.get("DART_API_KEY", "")
    cfg = yaml.safe_load((ROOT / "config" / "universe.yaml").read_text(encoding="utf-8"))
    STOCKS.mkdir(parents=True, exist_ok=True)
    ok, failed, skipped = [], [], []

    codes = {}
    if key:
        try:
            codes = corp_codes(key)
        except Exception as e:
            failed.append(f"DART 고유번호 목록: {e}")
    else:
        skipped.append("한국 종목 재무제표 (DART 키 없음)")

    items = [dict(s, kind="stock") for s in cfg["stocks"]] + [dict(b, market="INDEX", kind="index") for b in cfg["benchmarks"]]
    for s in items:
        if args.only and s["code"] != args.only:
            continue
        folder = STOCKS / s["code"].replace("^", "IDX_")
        folder.mkdir(parents=True, exist_ok=True)
        label = f"{s['name']}({s['code']})"

        try:
            px = fetch_prices(yahoo_symbol(s) if s["kind"] == "stock" else s["code"])
            px.to_csv(folder / "prices.csv", index=False, date_format="%Y-%m-%d")
            ok.append(f"{label} 주가 {len(px)}일, 최신 {px['date'].iloc[-1]:%Y-%m-%d}")
        except Exception as e:
            failed.append(f"{label} 주가: {e}")

        if s["kind"] != "stock" or s["market"] not in ("KOSPI", "KOSDAQ") or not key or not codes:
            continue
        corp = codes.get(s["code"])
        if not corp:
            failed.append(f"{label}: DART 고유번호를 못 찾았어요")
            continue
        try:
            fin = fetch_financials(corp, key)
            fin.to_csv(folder / "financials.csv", index=False)
            info = fetch_overview(corp, key)
            info["shares"] = fetch_shares(corp, key, int(fin["year"].max()))
            (folder / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
            ok.append(f"{label} 재무 {fin['year'].min()}~{fin['year'].max()}년")
        except Exception as e:
            failed.append(f"{label} 재무: {e}")
        time.sleep(0.3)  # DART에 너무 빨리 요청하지 않게

    meta = {"collected_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "ok": ok, "failed": failed, "skipped": skipped}
    (DATA / "stocks_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"성공 {len(ok)}개")
    for x in ok:
        print("  ✓", x)
    for x in skipped:
        print("  - 건너뜀:", x)
    if failed:
        print(f"실패 {len(failed)}개")
        for x in failed:
            print("  ✗", x)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
