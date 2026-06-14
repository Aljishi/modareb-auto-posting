#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DAILY_FILE = DATA_DIR / "daily.json"

API_URL = os.getenv("API_URL", "https://app.sahmk.sa/api/v1").rstrip("/")
API_KEY = os.getenv("API_KEY") or os.getenv("SAHMK_API_KEY")
TIMEOUT = int(os.getenv("SAHMK_TIMEOUT", "20"))

DEFAULT_SYMBOLS = [
    "1120", "1180", "2010", "2222", "2200", "2286", "4030", "4031",
    "4001", "4002", "4003", "4004", "4005", "4007", "4010", "4011",
    "4164", "4190", "4191", "4192", "4194", "4260", "4261", "4262",
    "4321", "4349", "6004", "6010", "7030", "7203", "7204", "8010",
    "8060", "8311", "1211", "1212", "1301", "1302", "1303", "1322",
    "1810", "1832", "2082", "2083", "2084", "2085", "2086", "2087",
    "2380", "2381", "2382"
]

# قاموس احتياطي للقطاعات — يُستخدم فقط عندما لا يُرجع Sahmk قطاع السهم
# (مطلوب لتفعيل sector_strength_score في generate_signal.py)
SECTOR_MAP = {
    "1120": "البنوك", "1180": "البنوك", "1150": "البنوك", "1060": "البنوك",
    "1020": "البنوك", "1050": "البنوك", "1140": "البنوك", "1010": "البنوك",
    "1080": "البنوك", "1182": "البنوك",
    "2010": "البتروكيماويات", "2350": "البتروكيماويات", "2380": "البتروكيماويات",
    "2381": "البتروكيماويات", "2382": "البتروكيماويات", "2090": "البتروكيماويات",
    "2330": "البتروكيماويات", "2310": "البتروكيماويات",
    "2222": "الطاقة", "5110": "الطاقة",
    "1211": "التأمين", "1212": "التأمين", "8010": "التأمين", "8060": "التأمين",
    "8311": "التأمين", "8210": "التأمين",
    "2050": "الأغذية والمشروبات", "4002": "الأغذية والمشروبات",
    "2270": "الأغذية والمشروبات", "2280": "الأغذية والمشروبات",
    "6001": "الأغذية والمشروبات",
    "4030": "النقل", "4031": "النقل",
    "1301": "المواد الأساسية", "1302": "المواد الأساسية", "1303": "المواد الأساسية",
    "1304": "المواد الأساسية", "1320": "المواد الأساسية", "1321": "المواد الأساسية",
    "1322": "المواد الأساسية",
    "4001": "العقارات", "4003": "التجزئة", "4004": "العقارات", "4005": "العقارات",
    "4007": "العقارات", "4010": "العقارات", "4011": "العقارات", "4020": "العقارات",
    "4164": "التجزئة", "4190": "التجزئة", "4191": "التجزئة", "4192": "التجزئة",
    "4194": "التجزئة", "4240": "التجزئة", "4250": "العقارات",
    "4260": "الإعلام والترفيه", "4261": "الإعلام والترفيه", "4262": "الإعلام والترفيه",
    "4321": "العقارات", "4349": "العقارات",
    "6004": "الإعلام والترفيه", "6010": "الإعلام والترفيه",
    "6015": "الإعلام والترفيه", "6017": "التقنية", "6018": "الإعلام والترفيه",
    "7030": "الاتصالات", "7010": "الاتصالات", "7020": "الاتصالات",
    "7202": "التقنية", "7203": "التقنية", "7204": "التقنية", "7205": "الخدمات",
    "1810": "الموارد البشرية", "1831": "الموارد البشرية", "1832": "الموارد البشرية",
    "1834": "الموارد البشرية", "1820": "الاستثمار الصناعي",
    "2082": "الطاقة", "2083": "الطاقة", "2084": "الطاقة", "2085": "الطاقة",
    "2086": "الطاقة", "2087": "الطاقة",
    "2030": "الصناعات", "2020": "الصناعات", "2060": "الصناعات",
    "2001": "الصناعات", "2002": "الصناعات", "2003": "الصناعات", "2004": "الصناعات",
    "2200": "الصناعات", "2230": "الكيماويات",
    "4061": "الاستثمار الصناعي", "4110": "النقل", "4130": "العقارات",
    "4280": "الاستثمار الصناعي", "3008": "المواد الأساسية",
}


def sector_for(symbol: str, api_sector: str = "") -> str:
    """القطاع من الـ API أولاً، وإلا من القاموس المحلي، وإلا (متعدد)"""
    api_sector = (api_sector or "").strip()
    if api_sector:
        return api_sector
    return SECTOR_MAP.get(str(symbol).strip(), "متعدد")


def headers():
    if not API_KEY:
        raise RuntimeError("API_KEY / SAHMK_API_KEY غير موجود في GitHub Secrets")
    return {
        "X-API-Key": API_KEY,
        "Accept": "application/json",
        "User-Agent": "Rased-Auto-Posting/1.0"
    }


def fnum(x, default=0.0):
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace(",", "").replace("%", "").strip()
        return float(x)
    except Exception:
        return default


def get_symbols():
    raw = os.getenv("TASI_SYMBOLS", "").strip()
    if raw:
        symbols = [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]
        return list(dict.fromkeys(symbols))
    return DEFAULT_SYMBOLS


def sahmk_get(path, params=None):
    url = f"{API_URL}/{path.lstrip('/')}"
    r = requests.get(url, headers=headers(), params=params or {}, timeout=TIMEOUT)

    if r.status_code >= 400:
        raise RuntimeError(f"SAHMK {r.status_code}: {r.text[:250]}")

    return r.json()


def normalize_quote(q):
    symbol = str(q.get("symbol") or "").strip()
    price = fnum(q.get("price") or q.get("current_price"))
    volume = fnum(q.get("volume"))
    value = fnum(q.get("value") or q.get("turnover"))

    if value <= 0 and price > 0 and volume > 0:
        value = price * volume

    if not symbol or price <= 0:
        return None

    return {
        "symbol": symbol,
        "name": q.get("name") or q.get("name_ar") or q.get("company_name") or symbol,
        "name_en": q.get("name_en") or "",
        "sector": sector_for(symbol, q.get("sector") or ""),
        "current_price": price,
        "price": price,
        "change": fnum(q.get("change")),
        "change_percent": fnum(q.get("change_percent")),
        "open": fnum(q.get("open")),
        "high": fnum(q.get("high")),
        "low": fnum(q.get("low")),
        "previous_close": fnum(q.get("previous_close")),
        "volume": volume,
        "value": value,
        "turnover": value,
        "bid": fnum(q.get("bid")),
        "ask": fnum(q.get("ask")),
        "updated_at": q.get("updated_at") or datetime.now().isoformat(),
        "is_delayed": bool(q.get("is_delayed", False)),
        "provider": "sahmk",
        "data_source": "api"
    }


def fetch_quotes_batch(symbols):
    try:
        payload = sahmk_get("quotes/", {"symbols": ",".join(symbols)})
        rows = payload.get("quotes") or payload.get("data") or []
        stocks = []

        for q in rows:
            nq = normalize_quote(q)
            if nq:
                stocks.append(nq)

        if stocks:
            return stocks

    except Exception as exc:
        print(f"⚠️ Batch quotes failed: {exc}")

    return []


def fetch_quotes_single(symbols):
    stocks = []

    for sym in symbols:
        try:
            payload = sahmk_get(f"quote/{sym}/")
            nq = normalize_quote(payload)
            if nq:
                stocks.append(nq)
                print(f"✅ {sym}: {nq['current_price']} | {nq['change_percent']}%")
            else:
                print(f"⚠️ {sym}: invalid quote")
        except Exception as exc:
            print(f"⚠️ {sym}: quote failed: {exc}")

        time.sleep(0.12)

    return stocks


def fetch_market_summary():
    try:
        return sahmk_get("market/summary/", {"index": "TASI"})
    except Exception as exc:
        print(f"⚠️ market summary failed: {exc}")
        return {}


def main():
    print("=" * 60)
    print("راصد — Fetch Sahmk Daily Quotes")
    print("=" * 60)

    if not API_KEY:
        print("❌ API_KEY غير موجود")
        return 1

    symbols = get_symbols()
    print(f"📊 Symbols: {len(symbols)}")

    stocks = fetch_quotes_batch(symbols)

    if not stocks:
        print("ℹ️ Using single quote endpoint...")
        stocks = fetch_quotes_single(symbols)

    if not stocks:
        print("❌ لم يتم جلب أي بيانات من Sahmk")
        return 1

    market_summary = fetch_market_summary()

    out = {
        "provider": "sahmk",
        "data_source": "api",
        "engine": "rased_market_intelligence_sahmk",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "api_url": API_URL,
        "market_summary": market_summary,
        "stocks": stocks,
        "count": len(stocks),
        "note": "Real Sahmk API quotes. No fallback/mock data."
    }

    DAILY_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Saved {len(stocks)} stocks to {DAILY_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
