#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — جلب بيانات السوق من Sahmk

التحسينات:
1. معالجة HTTP 429 واحترام Retry-After.
2. استخدام انتظار تصاعدي Exponential Backoff.
3. تقسيم طلبات Batch إلى مجموعات صغيرة.
4. منع الانتقال إلى عشرات الطلبات الفردية بعد ظهور 429.
5. إضافة فاصل زمني آمن بين الطلبات.
6. عدم استخدام بيانات وهمية أو أسعار عشوائية.
7. كتابة تقرير واضح عن حالة الجلب.
8. الاحتفاظ بملف daily.json السابق دون استبداله ببيانات ناقصة.
"""

import json
import os
import sys
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests


# =========================================================
# المسارات
# =========================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DAILY_FILE = DATA_DIR / "daily.json"
FETCH_STATUS_FILE = DATA_DIR / "market_fetch_status.json"


# =========================================================
# إعدادات Sahmk
# =========================================================

API_URL = os.getenv(
    "API_URL",
    "https://app.sahmk.sa/api/v1",
).rstrip("/")

API_KEY = (
    os.getenv("API_KEY")
    or os.getenv("SAHMK_API_KEY")
    or ""
).strip()

TIMEOUT = max(
    10,
    int(os.getenv("SAHMK_TIMEOUT", "25")),
)

MAX_RETRIES = max(
    1,
    int(os.getenv("SAHMK_MAX_RETRIES", "4")),
)

BASE_RETRY_DELAY = max(
    1.0,
    float(os.getenv("SAHMK_RETRY_DELAY", "3")),
)

MAX_RETRY_DELAY = max(
    10.0,
    float(os.getenv("SAHMK_MAX_RETRY_DELAY", "60")),
)

REQUEST_GAP = max(
    0.5,
    float(os.getenv("SAHMK_REQUEST_GAP", "1.25")),
)

BATCH_SIZE = max(
    5,
    min(25, int(os.getenv("SAHMK_BATCH_SIZE", "15"))),
)

MIN_ACCEPTED_STOCKS = max(
    1,
    int(os.getenv("SAHMK_MIN_ACCEPTED_STOCKS", "15")),
)


# =========================================================
# قائمة الأسهم
# =========================================================

DEFAULT_SYMBOLS = [
    "1120",
    "1180",
    "2010",
    "2222",
    "2200",
    "2286",
    "4030",
    "4031",
    "4001",
    "4002",
    "4003",
    "4004",
    "4005",
    "4007",
    "4010",
    "4011",
    "4164",
    "4190",
    "4191",
    "4192",
    "4194",
    "4260",
    "4261",
    "4262",
    "4321",
    "4349",
    "6004",
    "6010",
    "7030",
    "7203",
    "7204",
    "8010",
    "8060",
    "8311",
    "1211",
    "1212",
    "1301",
    "1302",
    "1303",
    "1322",
    "1810",
    "1832",
    "2082",
    "2083",
    "2084",
    "2085",
    "2086",
    "2087",
    "2380",
    "2381",
    "2382",
]


# =========================================================
# خريطة قطاعات احتياطية
# تستخدم فقط إذا لم يُرجع Sahmk القطاع
# =========================================================

SECTOR_MAP = {
    # البنوك
    "1010": "البنوك",
    "1020": "البنوك",
    "1050": "البنوك",
    "1060": "البنوك",
    "1080": "البنوك",
    "1120": "البنوك",
    "1140": "البنوك",
    "1150": "البنوك",
    "1180": "البنوك",
    "1182": "البنوك",

    # الطاقة والمرافق
    "2082": "المرافق العامة",
    "2083": "الطاقة",
    "2084": "الطاقة",
    "2085": "الطاقة",
    "2086": "الطاقة",
    "2087": "الطاقة",
    "2222": "الطاقة",
    "5110": "المرافق العامة",

    # المواد الأساسية والبتروكيماويات
    "1211": "المواد الأساسية",
    "1212": "السلع الرأسمالية",
    "1301": "المواد الأساسية",
    "1302": "المواد الأساسية",
    "1303": "المواد الأساسية",
    "1304": "المواد الأساسية",
    "1320": "المواد الأساسية",
    "1321": "المواد الأساسية",
    "1322": "المواد الأساسية",
    "2010": "المواد الأساسية",
    "2090": "المواد الأساسية",
    "2310": "المواد الأساسية",
    "2330": "المواد الأساسية",
    "2350": "المواد الأساسية",
    "2380": "المواد الأساسية",
    "2381": "المواد الأساسية",
    "2382": "المواد الأساسية",
    "3008": "المواد الأساسية",

    # النقل
    "4030": "النقل",
    "4031": "النقل",
    "4110": "النقل",

    # التأمين
    "8010": "التأمين",
    "8060": "التأمين",
    "8210": "التأمين",
    "8311": "التأمين",

    # الاتصالات والتقنية
    "7010": "الاتصالات",
    "7020": "الاتصالات",
    "7030": "الاتصالات",
    "7202": "التطبيقات وخدمات التقنية",
    "7203": "التطبيقات وخدمات التقنية",
    "7204": "التطبيقات وخدمات التقنية",
    "7205": "التطبيقات وخدمات التقنية",

    # الرعاية الصحية
    "4002": "الرعاية الصحية",
    "4004": "الرعاية الصحية",
    "4005": "الرعاية الصحية",
    "4007": "الرعاية الصحية",
    "4010": "الرعاية الصحية",
    "4011": "الرعاية الصحية",

    # التجزئة والخدمات الاستهلاكية
    "4001": "تجزئة وتوزيع السلع الاستهلاكية",
    "4003": "تجزئة السلع الكمالية",
    "4164": "تجزئة السلع الكمالية",
    "4190": "تجزئة السلع الكمالية",
    "4191": "تجزئة السلع الكمالية",
    "4192": "تجزئة السلع الكمالية",
    "4194": "تجزئة السلع الكمالية",
    "4240": "تجزئة السلع الكمالية",

    # الإعلام والترفيه
    "4260": "الخدمات الاستهلاكية",
    "4261": "الخدمات الاستهلاكية",
    "4262": "الخدمات الاستهلاكية",
    "6004": "الإعلام والترفيه",
    "6010": "الإعلام والترفيه",
    "6015": "الخدمات الاستهلاكية",
    "6018": "الخدمات الاستهلاكية",

    # العقارات
    "4020": "إدارة وتطوير العقارات",
    "4130": "إدارة وتطوير العقارات",
    "4250": "إدارة وتطوير العقارات",
    "4321": "الصناديق العقارية المتداولة",
    "4349": "الصناديق العقارية المتداولة",

    # الخدمات التجارية والمهنية
    "1810": "الخدمات التجارية والمهنية",
    "1820": "الخدمات التجارية والمهنية",
    "1831": "الخدمات التجارية والمهنية",
    "1832": "الخدمات التجارية والمهنية",
    "1834": "الخدمات التجارية والمهنية",

    # السلع الرأسمالية والصناعات
    "2001": "السلع الرأسمالية",
    "2002": "السلع الرأسمالية",
    "2003": "السلع الرأسمالية",
    "2004": "السلع الرأسمالية",
    "2020": "السلع الرأسمالية",
    "2030": "السلع الرأسمالية",
    "2060": "السلع الرأسمالية",
    "2200": "السلع الرأسمالية",
    "2230": "المواد الأساسية",
    "4061": "السلع الرأسمالية",
    "4280": "الخدمات التجارية والمهنية",

    # الأغذية والمشروبات
    "2050": "إنتاج الأغذية",
    "2270": "إنتاج الأغذية",
    "2280": "إنتاج الأغذية",
    "6001": "إنتاج الأغذية",
}


# =========================================================
# الاستثناءات
# =========================================================

class SahmkError(RuntimeError):
    """خطأ عام صادر من Sahmk."""


class SahmkRateLimitError(SahmkError):
    """تم تجاوز حد طلبات Sahmk."""


class SahmkRequestError(SahmkError):
    """تعذر تنفيذ طلب Sahmk."""


# =========================================================
# جلسة HTTP
# =========================================================

SESSION = requests.Session()


# =========================================================
# أدوات عامة
# =========================================================

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def fnum(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default

        if isinstance(value, str):
            value = (
                value.replace(",", "")
                .replace("%", "")
                .strip()
            )

        return float(value)

    except (TypeError, ValueError):
        return default


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def sector_for(symbol: str, api_sector: str = "") -> str:
    api_sector = safe_text(api_sector)

    if api_sector:
        return api_sector

    return SECTOR_MAP.get(
        safe_text(symbol),
        "غير محدد",
    )


def unique_symbols(symbols: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()

    for symbol in symbols:
        symbol = safe_text(symbol)

        if not symbol or symbol in seen:
            continue

        seen.add(symbol)
        result.append(symbol)

    return result


def get_symbols() -> List[str]:
    raw = os.getenv("TASI_SYMBOLS", "").strip()

    if not raw:
        return unique_symbols(DEFAULT_SYMBOLS)

    prepared = raw.replace("\n", ",").replace(";", ",")

    return unique_symbols(
        item.strip()
        for item in prepared.split(",")
    )


def chunked(
    values: List[str],
    size: int,
) -> Iterable[List[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def request_headers() -> Dict[str, str]:
    if not API_KEY:
        raise RuntimeError(
            "API_KEY أو SAHMK_API_KEY غير موجود في GitHub Secrets"
        )

    return {
        "X-API-Key": API_KEY,
        "Accept": "application/json",
        "User-Agent": "Rased-Auto-Posting/2.0",
    }


def parse_retry_after(
    header_value: Optional[str],
) -> Optional[float]:
    if not header_value:
        return None

    value = header_value.strip()

    try:
        seconds = float(value)
        return max(1.0, seconds)
    except ValueError:
        pass

    try:
        retry_date = parsedate_to_datetime(value)

        if retry_date.tzinfo is None:
            return None

        current = datetime.now(retry_date.tzinfo)
        seconds = (retry_date - current).total_seconds()

        return max(1.0, seconds)

    except Exception:
        return None


def response_preview(response: requests.Response) -> str:
    try:
        text = response.text
    except Exception:
        return ""

    return text.replace("\n", " ")[:350]


def write_fetch_status(
    *,
    status: str,
    reason: str,
    requested_symbols: int,
    fetched_stocks: int,
    rate_limited: bool = False,
    errors: Optional[List[str]] = None,
) -> None:
    payload = {
        "status": status,
        "provider": "sahmk",
        "api_url": API_URL,
        "requested_symbols": requested_symbols,
        "fetched_stocks": fetched_stocks,
        "rate_limited": rate_limited,
        "reason": reason,
        "errors": (errors or [])[:30],
        "generated_at": now_iso(),
    }

    FETCH_STATUS_FILE.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# =========================================================
# طلب Sahmk مع Retry وBackoff
# =========================================================

def sahmk_get(
    path: str,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    url = f"{API_URL}/{path.lstrip('/')}"

    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = SESSION.get(
                url,
                headers=request_headers(),
                params=params or {},
                timeout=TIMEOUT,
            )

        except requests.RequestException as exc:
            last_error = exc

            if attempt >= MAX_RETRIES:
                raise SahmkRequestError(
                    f"تعذر الاتصال بـ Sahmk بعد "
                    f"{MAX_RETRIES} محاولات: {exc}"
                ) from exc

            wait_seconds = min(
                MAX_RETRY_DELAY,
                BASE_RETRY_DELAY * (2 ** (attempt - 1)),
            )

            print(
                f"⚠️ Sahmk connection error "
                f"({attempt}/{MAX_RETRIES}): {exc}"
            )
            print(
                f"⏳ إعادة المحاولة بعد "
                f"{wait_seconds:.1f} ثانية"
            )

            time.sleep(wait_seconds)
            continue

        if response.status_code == 429:
            retry_after = parse_retry_after(
                response.headers.get("Retry-After")
            )

            calculated_delay = min(
                MAX_RETRY_DELAY,
                BASE_RETRY_DELAY * (2 ** (attempt - 1)),
            )

            wait_seconds = min(
                MAX_RETRY_DELAY,
                retry_after or calculated_delay,
            )

            message = (
                f"SAHMK 429: تم تجاوز حد الطلبات. "
                f"{response_preview(response)}"
            )

            last_error = SahmkRateLimitError(message)

            if attempt >= MAX_RETRIES:
                raise last_error

            print(
                f"⚠️ Sahmk rate limit 429 "
                f"({attempt}/{MAX_RETRIES})"
            )
            print(
                f"⏳ انتظار {wait_seconds:.1f} ثانية "
                f"قبل إعادة المحاولة"
            )

            time.sleep(wait_seconds)
            continue

        if 500 <= response.status_code <= 599:
            message = (
                f"SAHMK {response.status_code}: "
                f"{response_preview(response)}"
            )

            last_error = SahmkRequestError(message)

            if attempt >= MAX_RETRIES:
                raise last_error

            wait_seconds = min(
                MAX_RETRY_DELAY,
                BASE_RETRY_DELAY * (2 ** (attempt - 1)),
            )

            print(
                f"⚠️ Sahmk server error "
                f"{response.status_code} "
                f"({attempt}/{MAX_RETRIES})"
            )
            print(
                f"⏳ إعادة المحاولة بعد "
                f"{wait_seconds:.1f} ثانية"
            )

            time.sleep(wait_seconds)
            continue

        if response.status_code >= 400:
            raise SahmkRequestError(
                f"SAHMK {response.status_code}: "
                f"{response_preview(response)}"
            )

        try:
            return response.json()

        except ValueError as exc:
            raise SahmkRequestError(
                "Sahmk أعاد استجابة ليست JSON صالحًا: "
                f"{response_preview(response)}"
            ) from exc

    raise SahmkRequestError(
        f"فشل طلب Sahmk: {last_error}"
    )


# =========================================================
# تطبيع البيانات
# =========================================================

def extract_quote_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [
            row
            for row in payload
            if isinstance(row, dict)
        ]

    if not isinstance(payload, dict):
        return []

    candidates = [
        payload.get("quotes"),
        payload.get("stocks"),
        payload.get("results"),
        payload.get("data"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return [
                row
                for row in candidate
                if isinstance(row, dict)
            ]

        if isinstance(candidate, dict):
            nested_candidates = [
                candidate.get("quotes"),
                candidate.get("stocks"),
                candidate.get("results"),
                candidate.get("items"),
            ]

            for nested in nested_candidates:
                if isinstance(nested, list):
                    return [
                        row
                        for row in nested
                        if isinstance(row, dict)
                    ]

    if payload.get("symbol"):
        return [payload]

    return []


def normalize_quote(
    quote: Dict[str, Any],
    fallback_symbol: str = "",
) -> Optional[Dict[str, Any]]:
    symbol = safe_text(
        quote.get("symbol")
        or quote.get("ticker")
        or quote.get("code")
        or fallback_symbol
    )

    price = fnum(
        quote.get("price")
        or quote.get("current_price")
        or quote.get("last_price")
        or quote.get("last")
        or quote.get("close")
    )

    volume = fnum(
        quote.get("volume")
        or quote.get("traded_volume")
        or quote.get("total_volume")
    )

    value = fnum(
        quote.get("value")
        or quote.get("turnover")
        or quote.get("traded_value")
        or quote.get("total_value")
    )

    if value <= 0 and price > 0 and volume > 0:
        value = price * volume

    if not symbol or price <= 0:
        return None

    api_sector = (
        quote.get("sector")
        or quote.get("sector_name")
        or quote.get("sector_name_ar")
        or ""
    )

    return {
        "symbol": symbol,
        "name": (
            quote.get("name")
            or quote.get("name_ar")
            or quote.get("company_name")
            or quote.get("company_name_ar")
            or symbol
        ),
        "name_en": (
            quote.get("name_en")
            or quote.get("company_name_en")
            or ""
        ),
        "sector": sector_for(
            symbol,
            safe_text(api_sector),
        ),
        "current_price": price,
        "price": price,
        "change": fnum(
            quote.get("change")
            or quote.get("price_change")
        ),
        "change_percent": fnum(
            quote.get("change_percent")
            or quote.get("change_pct")
            or quote.get("percent_change")
        ),
        "open": fnum(quote.get("open")),
        "high": fnum(quote.get("high")),
        "low": fnum(quote.get("low")),
        "previous_close": fnum(
            quote.get("previous_close")
            or quote.get("prev_close")
        ),
        "volume": volume,
        "value": value,
        "turnover": value,
        "bid": fnum(
            quote.get("bid")
            or quote.get("best_bid")
        ),
        "ask": fnum(
            quote.get("ask")
            or quote.get("best_ask")
        ),
        "updated_at": (
            quote.get("updated_at")
            or quote.get("timestamp")
            or now_iso()
        ),
        "is_delayed": bool(
            quote.get("is_delayed", False)
        ),
        "provider": "sahmk",
        "data_source": "api",
    }


def deduplicate_stocks(
    stocks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_symbol: Dict[str, Dict[str, Any]] = {}

    for stock in stocks:
        symbol = safe_text(stock.get("symbol"))

        if not symbol:
            continue

        by_symbol[symbol] = stock

    return list(by_symbol.values())


# =========================================================
# جلب الأسعار
# =========================================================

def fetch_quotes_batch(
    symbols: List[str],
) -> tuple[List[Dict[str, Any]], bool, List[str]]:
    stocks: List[Dict[str, Any]] = []
    errors: List[str] = []
    rate_limited = False

    groups = list(chunked(symbols, BATCH_SIZE))

    print(
        f"📦 Batch groups: {len(groups)} "
        f"× up to {BATCH_SIZE} symbols"
    )

    for group_index, group in enumerate(groups, start=1):
        try:
            print(
                f"🔄 Batch {group_index}/{len(groups)}: "
                f"{','.join(group)}"
            )

            payload = sahmk_get(
                "quotes/",
                {
                    "symbols": ",".join(group),
                },
            )

            rows = extract_quote_rows(payload)

            normalized_count = 0

            for row in rows:
                quote = normalize_quote(row)

                if quote:
                    stocks.append(quote)
                    normalized_count += 1

            print(
                f"✅ Batch {group_index}: "
                f"{normalized_count} valid quotes"
            )

        except SahmkRateLimitError as exc:
            rate_limited = True
            errors.append(str(exc))

            print(
                "❌ توقف جلب Batch بسبب تجاوز حد "
                "طلبات Sahmk"
            )

            break

        except SahmkError as exc:
            errors.append(
                f"Batch {group_index}: {exc}"
            )

            print(
                f"⚠️ Batch {group_index} failed: {exc}"
            )

        if group_index < len(groups):
            time.sleep(REQUEST_GAP)

    return (
        deduplicate_stocks(stocks),
        rate_limited,
        errors,
    )


def fetch_quotes_single(
    symbols: List[str],
) -> tuple[List[Dict[str, Any]], bool, List[str]]:
    stocks: List[Dict[str, Any]] = []
    errors: List[str] = []
    rate_limited = False

    print(
        f"ℹ️ بدء الجلب الفردي البطيء لـ "
        f"{len(symbols)} سهمًا"
    )

    for index, symbol in enumerate(symbols, start=1):
        try:
            payload = sahmk_get(
                f"quote/{symbol}/"
            )

            rows = extract_quote_rows(payload)

            quote: Optional[Dict[str, Any]] = None

            if rows:
                quote = normalize_quote(
                    rows[0],
                    fallback_symbol=symbol,
                )

            elif isinstance(payload, dict):
                quote = normalize_quote(
                    payload,
                    fallback_symbol=symbol,
                )

            if quote:
                stocks.append(quote)

                print(
                    f"✅ {index}/{len(symbols)} "
                    f"{symbol}: "
                    f"{quote['current_price']} | "
                    f"{quote['change_percent']}%"
                )

            else:
                errors.append(
                    f"{symbol}: invalid quote"
                )

                print(
                    f"⚠️ {index}/{len(symbols)} "
                    f"{symbol}: invalid quote"
                )

        except SahmkRateLimitError as exc:
            rate_limited = True
            errors.append(
                f"{symbol}: {exc}"
            )

            print(
                f"❌ توقف الجلب الفردي عند {symbol} "
                "بسبب Sahmk 429"
            )

            break

        except SahmkError as exc:
            errors.append(
                f"{symbol}: {exc}"
            )

            print(
                f"⚠️ {index}/{len(symbols)} "
                f"{symbol}: quote failed: {exc}"
            )

        if index < len(symbols):
            time.sleep(REQUEST_GAP)

    return (
        deduplicate_stocks(stocks),
        rate_limited,
        errors,
    )


def fetch_market_summary() -> Dict[str, Any]:
    try:
        payload = sahmk_get(
            "market/summary/",
            {
                "index": "TASI",
            },
        )

        if isinstance(payload, dict):
            return payload

        return {}

    except SahmkRateLimitError:
        print(
            "⚠️ تم تجاوز حد Sahmk؛ "
            "تخطي market summary"
        )
        return {}

    except SahmkError as exc:
        print(
            f"⚠️ market summary failed: {exc}"
        )
        return {}


# =========================================================
# الحفظ
# =========================================================

def save_daily_data(
    stocks: List[Dict[str, Any]],
    market_summary: Dict[str, Any],
    requested_symbols: int,
    errors: List[str],
) -> None:
    output = {
        "provider": "sahmk",
        "data_source": "api",
        "engine": "rased_market_intelligence_sahmk_v2",
        "generated_at": now_iso(),
        "api_url": API_URL,
        "requested_symbols": requested_symbols,
        "market_summary": market_summary,
        "stocks": stocks,
        "count": len(stocks),
        "fetch_errors": errors[:30],
        "note": (
            "Real Sahmk API quotes only. "
            "No fallback or mock prices."
        ),
    }

    temporary_file = DAILY_FILE.with_suffix(
        ".json.tmp"
    )

    temporary_file.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_file.replace(DAILY_FILE)


# =========================================================
# التشغيل الرئيسي
# =========================================================

def main() -> int:
    print("=" * 68)
    print("راصد — Fetch Sahmk Daily Quotes v2")
    print("=" * 68)
    print(f"API URL: {API_URL}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Request gap: {REQUEST_GAP:.2f}s")
    print(f"Maximum retries: {MAX_RETRIES}")

    if not API_KEY:
        reason = (
            "API_KEY أو SAHMK_API_KEY غير موجود "
            "في GitHub Secrets"
        )

        print(f"❌ {reason}")

        write_fetch_status(
            status="FAIL",
            reason=reason,
            requested_symbols=0,
            fetched_stocks=0,
        )

        return 1

    symbols = get_symbols()

    if not symbols:
        reason = "قائمة الأسهم فارغة"

        print(f"❌ {reason}")

        write_fetch_status(
            status="FAIL",
            reason=reason,
            requested_symbols=0,
            fetched_stocks=0,
        )

        return 1

    print(f"📊 Symbols requested: {len(symbols)}")

    all_errors: List[str] = []

    stocks, batch_rate_limited, batch_errors = (
        fetch_quotes_batch(symbols)
    )

    all_errors.extend(batch_errors)

    # لا ننفذ عشرات الطلبات الفردية إذا ظهر 429؛
    # لأن ذلك يزيد الحظر بدل معالجته.
    if batch_rate_limited:
        reason = (
            "Sahmk أعاد HTTP 429 أثناء Batch. "
            "تم إيقاف الطلبات الإضافية لحماية حد الاشتراك."
        )

        print(f"❌ {reason}")

        write_fetch_status(
            status="RATE_LIMITED",
            reason=reason,
            requested_symbols=len(symbols),
            fetched_stocks=len(stocks),
            rate_limited=True,
            errors=all_errors,
        )

        return 1

    fetched_symbols = {
        safe_text(stock.get("symbol"))
        for stock in stocks
    }

    missing_symbols = [
        symbol
        for symbol in symbols
        if symbol not in fetched_symbols
    ]

    # نستخدم الجلب الفردي فقط للأسهم التي لم يُرجعها Batch،
    # وليس لكل القائمة.
    if missing_symbols:
        print(
            f"ℹ️ Missing after Batch: "
            f"{len(missing_symbols)} symbols"
        )

        single_stocks, single_rate_limited, single_errors = (
            fetch_quotes_single(missing_symbols)
        )

        stocks.extend(single_stocks)
        stocks = deduplicate_stocks(stocks)

        all_errors.extend(single_errors)

        if single_rate_limited:
            print(
                "⚠️ توقف استكمال الأسهم بسبب Sahmk 429"
            )

    if len(stocks) < MIN_ACCEPTED_STOCKS:
        reason = (
            f"عدد الأسهم المستلمة غير كافٍ: "
            f"{len(stocks)}/{MIN_ACCEPTED_STOCKS}. "
            "لن يتم استبدال daily.json بملف ناقص."
        )

        print(f"❌ {reason}")

        write_fetch_status(
            status="FAIL",
            reason=reason,
            requested_symbols=len(symbols),
            fetched_stocks=len(stocks),
            rate_limited=False,
            errors=all_errors,
        )

        return 1

    # لا نطلب ملخص السوق إلا بعد اكتمال الأسعار،
    # لتجنب استهلاك طلب إضافي عند فشل البيانات الأساسية.
    time.sleep(REQUEST_GAP)

    market_summary = fetch_market_summary()

    save_daily_data(
        stocks=stocks,
        market_summary=market_summary,
        requested_symbols=len(symbols),
        errors=all_errors,
    )

    reason = (
        f"تم جلب وحفظ {len(stocks)} سهمًا بنجاح"
    )

    write_fetch_status(
        status="PASS",
        reason=reason,
        requested_symbols=len(symbols),
        fetched_stocks=len(stocks),
        rate_limited=False,
        errors=all_errors,
    )

    print(f"✅ {reason}")
    print(f"✅ Saved to: {DAILY_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())