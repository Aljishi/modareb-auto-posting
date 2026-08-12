#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RASED Market Intelligence — Sahmk Daily Quotes v2.1
===================================================

المهام:
- جلب quotes لعينة راصد من Sahmk API.
- جلب ملخص TASI الرسمي.
- توحيد أسماء القطاعات وتصحيح الأخطاء المعروفة عبر sector_master.py.
- منع حفظ بيانات فارغة أو أسعار غير صالحة.
- الاحتفاظ بآخر daily.json صالح عند فشل API بدل إنشاء بيانات وهمية.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

try:
    from sector_master import normalize_stock_sector
except ImportError:
    # Allows running as module from repository root in some environments.
    from scripts.sector_master import normalize_stock_sector


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DAILY_FILE = DATA_DIR / "daily.json"

API_URL = os.getenv(
    "API_URL",
    "https://app.sahmk.sa/api/v1",
).rstrip("/")

API_KEY = (
    os.getenv("API_KEY")
    or os.getenv("SAHMK_API_KEY")
)

TIMEOUT = int(
    os.getenv("SAHMK_TIMEOUT", "20")
)

MAX_RETRIES = int(
    os.getenv("SAHMK_MAX_RETRIES", "4")
)

RETRY_DELAY = float(
    os.getenv("SAHMK_RETRY_DELAY", "3")
)

MAX_RETRY_DELAY = float(
    os.getenv("SAHMK_MAX_RETRY_DELAY", "60")
)

REQUEST_GAP = float(
    os.getenv("SAHMK_REQUEST_GAP", "1.25")
)

BATCH_SIZE = int(
    os.getenv("SAHMK_BATCH_SIZE", "15")
)

MIN_ACCEPTED_STOCKS = int(
    os.getenv("SAHMK_MIN_ACCEPTED_STOCKS", "15")
)


DEFAULT_SYMBOLS = [
    "1120", "1180", "2010", "2222", "2200", "2286",
    "4030", "4031", "4001", "4002", "4003", "4004",
    "4005", "4007", "4010", "4011", "4164", "4190",
    "4191", "4192", "4194", "4260", "4261", "4262",
    "4321", "4349", "6004", "6010", "7030", "7203",
    "7204", "8010", "8060", "8311", "1211", "1212",
    "1301", "1302", "1303", "1322", "1810", "1832",
    "2082", "2083", "2084", "2085", "2086", "2087",
    "2380", "2381", "2382",
]


def fnum(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default

        if isinstance(value, str):
            value = (
                value
                .replace(",", "")
                .replace("%", "")
                .strip()
            )

        return float(value)

    except Exception:
        return default


def fint(value: Any, default: int = 0) -> int:
    try:
        return int(round(fnum(value, default)))
    except Exception:
        return default


def headers() -> Dict[str, str]:
    if not API_KEY:
        raise RuntimeError(
            "API_KEY / SAHMK_API_KEY غير موجود في GitHub Secrets"
        )

    return {
        "X-API-Key": API_KEY,
        "Accept": "application/json",
        "User-Agent": "Rased-Auto-Posting/2.1",
    }


def get_symbols() -> List[str]:
    raw = os.getenv("TASI_SYMBOLS", "").strip()

    if raw:
        symbols = [
            item.strip()
            for item in raw.replace("\n", ",").split(",")
            if item.strip()
        ]
        return list(dict.fromkeys(symbols))

    return list(DEFAULT_SYMBOLS)


def sahmk_get(
    path: str,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    url = f"{API_URL}/{path.lstrip('/')}"

    delay = RETRY_DELAY
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                headers=headers(),
                params=params or {},
                timeout=TIMEOUT,
            )

            if response.status_code < 400:
                return response.json()

            # 429 / 5xx can be temporary.
            if response.status_code == 429 or response.status_code >= 500:
                raise RuntimeError(
                    f"SAHMK temporary HTTP {response.status_code}: "
                    f"{response.text[:250]}"
                )

            raise RuntimeError(
                f"SAHMK HTTP {response.status_code}: "
                f"{response.text[:250]}"
            )

        except Exception as exc:
            last_error = exc

            if attempt >= MAX_RETRIES:
                break

            print(
                f"⚠️ {path}: attempt {attempt}/{MAX_RETRIES} failed: {exc}"
            )

            time.sleep(delay)
            delay = min(delay * 2, MAX_RETRY_DELAY)

    raise RuntimeError(
        f"SAHMK request failed after {MAX_RETRIES} attempts: "
        f"{last_error}"
    )


def normalize_quote(quote: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    symbol = str(
        quote.get("symbol")
        or quote.get("ticker")
        or ""
    ).strip()

    price = fnum(
        quote.get("price")
        or quote.get("current_price")
        or quote.get("last_price")
    )

    if not symbol or price <= 0:
        return None

    volume = fnum(
        quote.get("volume")
        or quote.get("traded_volume")
    )

    value = fnum(
        quote.get("value")
        or quote.get("turnover")
        or quote.get("traded_value")
    )

    if value <= 0 and price > 0 and volume > 0:
        value = price * volume

    stock = {
        "symbol": symbol,
        "name": (
            quote.get("name")
            or quote.get("name_ar")
            or quote.get("company_name")
            or symbol
        ),
        "name_en": quote.get("name_en") or "",
        "sector": (
            quote.get("sector")
            or quote.get("sector_name")
            or ""
        ),
        "current_price": price,
        "price": price,
        "change": fnum(
            quote.get("change")
            or quote.get("price_change")
        ),
        "change_percent": fnum(
            quote.get("change_percent")
            or quote.get("change_percentage")
            or quote.get("percent_change")
        ),
        "open": fnum(
            quote.get("open")
            or quote.get("open_price")
        ),
        "high": fnum(
            quote.get("high")
            or quote.get("high_price")
        ),
        "low": fnum(
            quote.get("low")
            or quote.get("low_price")
        ),
        "previous_close": fnum(
            quote.get("previous_close")
            or quote.get("prev_close")
        ),
        "volume": volume,
        "value": value,
        "turnover": value,
        "bid": fnum(quote.get("bid")),
        "ask": fnum(quote.get("ask")),
        "updated_at": (
            quote.get("updated_at")
            or datetime.now().isoformat(timespec="seconds")
        ),
        "is_delayed": bool(
            quote.get("is_delayed", False)
        ),
        "provider": "sahmk",
        "data_source": "api",
    }

    return normalize_stock_sector(stock)


def extract_quote_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [
            row
            for row in payload
            if isinstance(row, dict)
        ]

    if not isinstance(payload, dict):
        return []

    candidates = (
        payload.get("quotes")
        or payload.get("data")
        or payload.get("stocks")
        or []
    )

    if isinstance(candidates, list):
        return [
            row
            for row in candidates
            if isinstance(row, dict)
        ]

    return []


def fetch_quotes_batch(
    symbols: List[str],
) -> List[Dict[str, Any]]:
    stocks: List[Dict[str, Any]] = []

    for start in range(0, len(symbols), max(1, BATCH_SIZE)):
        batch = symbols[start:start + max(1, BATCH_SIZE)]

        try:
            payload = sahmk_get(
                "quotes/",
                {"symbols": ",".join(batch)},
            )

            rows = extract_quote_rows(payload)

            for row in rows:
                normalized = normalize_quote(row)
                if normalized:
                    stocks.append(normalized)

        except Exception as exc:
            print(
                f"⚠️ Batch quotes failed "
                f"({batch[0]}..{batch[-1]}): {exc}"
            )

        if start + BATCH_SIZE < len(symbols):
            time.sleep(REQUEST_GAP)

    return stocks


def fetch_quote_single(
    symbol: str,
) -> Optional[Dict[str, Any]]:
    payload = sahmk_get(
        f"quote/{symbol}/"
    )

    if isinstance(payload, dict):
        # Some APIs nest the result under "data".
        nested = payload.get("data")
        if isinstance(nested, dict):
            payload = nested

        normalized = normalize_quote(payload)
        if normalized:
            return normalized

    return None


def fetch_missing_single(
    requested_symbols: List[str],
    existing: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_symbol = {
        str(stock.get("symbol") or ""): stock
        for stock in existing
        if stock.get("symbol")
    }

    missing = [
        symbol
        for symbol in requested_symbols
        if symbol not in by_symbol
    ]

    if not missing:
        return list(by_symbol.values())

    print(
        f"ℹ️ Missing from batch endpoint: {len(missing)} symbols"
    )

    for symbol in missing:
        try:
            stock = fetch_quote_single(symbol)

            if stock:
                by_symbol[symbol] = stock
                print(
                    f"✅ {symbol}: "
                    f"{stock['current_price']:.2f} | "
                    f"{stock['change_percent']:+.2f}% | "
                    f"{stock['sector']}"
                )
            else:
                print(
                    f"⚠️ {symbol}: invalid quote"
                )

        except Exception as exc:
            print(
                f"⚠️ {symbol}: quote failed: {exc}"
            )

        time.sleep(REQUEST_GAP)

    return [
        by_symbol[symbol]
        for symbol in requested_symbols
        if symbol in by_symbol
    ]


def fetch_market_summary() -> Dict[str, Any]:
    try:
        payload = sahmk_get(
            "market/summary/",
            {"index": "TASI"},
        )

        if isinstance(payload, dict):
            nested = payload.get("data")
            if isinstance(nested, dict):
                payload = nested

            return payload

    except Exception as exc:
        print(
            f"⚠️ market summary failed: {exc}"
        )

    return {}


def preserve_previous_market_summary(
    current: Dict[str, Any],
) -> Dict[str, Any]:
    """
    If the summary endpoint temporarily fails, preserve the previous
    market_summary but clearly mark it stale instead of inventing data.
    """
    if current:
        return current

    try:
        if DAILY_FILE.exists():
            previous = json.loads(
                DAILY_FILE.read_text(encoding="utf-8")
            )

            old_summary = previous.get("market_summary", {})

            if isinstance(old_summary, dict) and old_summary:
                old_summary = dict(old_summary)
                old_summary["is_delayed"] = True
                old_summary["stale_reason"] = (
                    "market_summary endpoint unavailable"
                )
                return old_summary

    except Exception as exc:
        print(
            f"⚠️ Previous market summary unavailable: {exc}"
        )

    return {}


def save_daily(
    stocks: List[Dict[str, Any]],
    requested_symbols: List[str],
    market_summary: Dict[str, Any],
) -> None:
    generated_at = datetime.now().isoformat(timespec="seconds")

    output = {
        "provider": "sahmk",
        "data_source": "api",
        "engine": "rased_market_intelligence_sahmk_v2_1",
        "generated_at": generated_at,
        "api_url": API_URL,
        "requested_symbols": len(requested_symbols),
        "market_summary": market_summary,
        "stocks": stocks,
        "count": len(stocks),
        "sector_normalization": {
            "enabled": True,
            "overrides": sum(
                1
                for stock in stocks
                if stock.get("sector_source") == "symbol_override"
            ),
        },
        "note": (
            "Real Sahmk API quotes. No fallback/mock stock prices. "
            "Sector names normalized by RASED Sector Master."
        ),
    }

    DAILY_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"✅ Saved {len(stocks)}/{len(requested_symbols)} "
        f"stocks to {DAILY_FILE}"
    )


def main() -> int:
    print("=" * 68)
    print("راصد — Market Intelligence v2.1")
    print("=" * 68)

    if not API_KEY:
        print(
            "❌ API_KEY / SAHMK_API_KEY غير موجود"
        )
        return 1

    symbols = get_symbols()

    print(
        f"📋 Requested symbols: {len(symbols)}"
    )

    stocks = fetch_quotes_batch(symbols)
    stocks = fetch_missing_single(symbols, stocks)

    # Deduplicate one final time.
    dedup: Dict[str, Dict[str, Any]] = {}

    for stock in stocks:
        symbol = str(
            stock.get("symbol")
            or ""
        ).strip()

        if symbol:
            dedup[symbol] = stock

    stocks = [
        dedup[symbol]
        for symbol in symbols
        if symbol in dedup
    ]

    if len(stocks) < MIN_ACCEPTED_STOCKS:
        print(
            f"❌ Data quality stop: only {len(stocks)} "
            f"stocks received; minimum={MIN_ACCEPTED_STOCKS}"
        )
        print(
            "ℹ️ Existing daily.json is left untouched."
        )
        return 1

    market_summary = preserve_previous_market_summary(
        fetch_market_summary()
    )

    save_daily(
        stocks=stocks,
        requested_symbols=symbols,
        market_summary=market_summary,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
