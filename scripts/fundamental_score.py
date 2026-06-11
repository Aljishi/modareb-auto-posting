#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Fundamental / Growth / Dividend Score

الملف مصمم ليعمل مع Sahmk Starter بأمان:
- يحاول قراءة fundamentals / financial statements / dividends من أكثر من endpoint شائع.
- إذا لم يكن endpoint متاحاً في Sahmk، لا يكسر النظام ويعيد نتيجة محايدة.
- يعطي نقاطاً للنمو المالي والتوزيعات والربحية والمديونية عند توفر البيانات.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_FILE = DATA_DIR / "fundamental_cache.json"

API_URL = os.getenv("API_URL", "https://app.sahmk.sa/api/v1").rstrip("/")
API_KEY = os.getenv("API_KEY") or os.getenv("SAHMK_API_KEY")
TIMEOUT = int(os.getenv("SAHMK_TIMEOUT", "20"))
CACHE_HOURS = int(os.getenv("FUNDAMENTAL_CACHE_HOURS", "24"))


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace(",", "").replace("%", "").strip()
        return float(x)
    except Exception:
        return default


def headers() -> Dict[str, str]:
    if not API_KEY:
        return {}
    return {"X-API-Key": API_KEY, "Accept": "application/json", "User-Agent": "Rased-Fundamental-Score/2.0"}


def read_cache() -> Dict[str, Any]:
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"symbols": {}}


def write_cache(cache: Dict[str, Any]) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def fresh(item: Dict[str, Any]) -> bool:
    ts = item.get("cached_at")
    if not ts:
        return False
    try:
        dt = datetime.fromisoformat(ts)
        return datetime.now() - dt < timedelta(hours=CACHE_HOURS)
    except Exception:
        return False


def safe_get(path: str) -> Optional[Any]:
    if not API_KEY:
        return None
    try:
        url = f"{API_URL}/{path.lstrip('/')}"
        r = requests.get(url, headers=headers(), timeout=TIMEOUT)
        if r.status_code >= 400:
            return None
        return r.json()
    except Exception:
        return None


def unwrap(payload: Any) -> Any:
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "financials", "statements", "dividends"):
            if key in payload:
                return payload[key]
    return payload


def first_payload(paths: List[str]) -> Any:
    for p in paths:
        data = safe_get(p)
        data = unwrap(data)
        if data not in (None, [], {}):
            return data
    return None


def newest_rows(data: Any, limit: int = 8) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []
    rows = [x for x in data if isinstance(x, dict)]
    rows.sort(key=lambda r: str(r.get("date") or r.get("period") or r.get("fiscal_period") or r.get("year") or ""), reverse=True)
    return rows[:limit]


def pick(row: Dict[str, Any], keys: List[str]) -> float:
    for k in keys:
        if k in row:
            v = fnum(row.get(k), None)  # type: ignore[arg-type]
            if v is not None:
                return fnum(row.get(k))
    return 0.0


def pct_growth(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return round(((current - previous) / abs(previous)) * 100, 2)


def score_growth(financial_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if len(financial_rows) < 2:
        return {"bonus": 0, "grade": "غير متوفر", "details": "لا توجد قوائم مالية كافية", "raw": {}}

    cur = financial_rows[0]
    prev = financial_rows[1]
    revenue_now = pick(cur, ["revenue", "total_revenue", "sales", "operating_revenue"])
    revenue_prev = pick(prev, ["revenue", "total_revenue", "sales", "operating_revenue"])
    profit_now = pick(cur, ["net_income", "net_profit", "profit", "netProfit"])
    profit_prev = pick(prev, ["net_income", "net_profit", "profit", "netProfit"])

    revenue_growth = pct_growth(revenue_now, revenue_prev) if revenue_now and revenue_prev else 0.0
    profit_growth = pct_growth(profit_now, profit_prev) if profit_now and profit_prev else 0.0

    bonus = 0
    notes: List[str] = []
    if revenue_growth >= 20:
        bonus += 4
        notes.append(f"نمو الإيرادات {revenue_growth}%")
    elif revenue_growth >= 10:
        bonus += 2
        notes.append(f"نمو إيرادات جيد {revenue_growth}%")
    elif revenue_growth <= -10:
        bonus -= 3
        notes.append(f"تراجع الإيرادات {revenue_growth}%")

    if profit_growth >= 25:
        bonus += 5
        notes.append(f"نمو الأرباح {profit_growth}%")
    elif profit_growth >= 10:
        bonus += 3
        notes.append(f"نمو أرباح جيد {profit_growth}%")
    elif profit_growth <= -15:
        bonus -= 5
        notes.append(f"تراجع الأرباح {profit_growth}%")

    if profit_now < 0:
        bonus -= 6
        notes.append("خسائر صافية")

    if bonus >= 7:
        grade = "نمو قوي"
    elif bonus >= 3:
        grade = "نمو جيد"
    elif bonus < 0:
        grade = "نمو ضعيف"
    else:
        grade = "محايد"

    return {
        "bonus": max(-8, min(9, bonus)),
        "grade": grade,
        "details": "، ".join(notes) if notes else "نمو مالي محايد",
        "raw": {
            "revenue_growth_pct": revenue_growth,
            "profit_growth_pct": profit_growth,
            "revenue_now": revenue_now,
            "profit_now": profit_now,
        },
    }


def score_quality(fundamentals: Any) -> Dict[str, Any]:
    row = fundamentals[0] if isinstance(fundamentals, list) and fundamentals else fundamentals
    if not isinstance(row, dict):
        return {"bonus": 0, "grade": "غير متوفر", "details": "أساسيات غير متوفرة", "raw": {}}

    roe = pick(row, ["roe", "return_on_equity", "returnOnEquity"])
    roa = pick(row, ["roa", "return_on_assets", "returnOnAssets"])
    debt_ratio = pick(row, ["debt_ratio", "debtToEquity", "debt_to_equity", "liabilities_to_assets"])
    pe = pick(row, ["pe", "p_e", "price_to_earnings", "trailing_pe"])

    bonus = 0
    notes: List[str] = []
    if roe >= 20:
        bonus += 4
        notes.append(f"ROE ممتاز {roe}")
    elif roe >= 12:
        bonus += 2
        notes.append(f"ROE جيد {roe}")
    elif 0 < roe < 5:
        bonus -= 2
        notes.append(f"ROE ضعيف {roe}")

    if roa >= 8:
        bonus += 2
        notes.append(f"ROA جيد {roa}")

    if debt_ratio >= 2.5:
        bonus -= 4
        notes.append("مديونية مرتفعة")
    elif 0 < debt_ratio <= 1.0:
        bonus += 1
        notes.append("مديونية مقبولة")

    if pe and pe > 0:
        if pe <= 18:
            bonus += 1
        elif pe >= 45:
            bonus -= 2

    if bonus >= 5:
        grade = "قوي"
    elif bonus >= 2:
        grade = "جيد"
    elif bonus < 0:
        grade = "ضعيف"
    else:
        grade = "محايد"

    return {
        "bonus": max(-6, min(7, bonus)),
        "grade": grade,
        "details": "، ".join(notes) if notes else "أساسيات محايدة",
        "raw": {"roe": roe, "roa": roa, "debt_ratio": debt_ratio, "pe": pe},
    }


def score_dividends(dividends: Any) -> Dict[str, Any]:
    rows = newest_rows(dividends, 8)
    if not rows:
        return {"bonus": 0, "grade": "غير متوفر", "details": "لا توجد بيانات توزيعات", "raw": {}}

    today = datetime.now().date()
    recent = False
    dividend_yield = 0.0
    amount = 0.0
    for r in rows:
        amount = max(amount, pick(r, ["amount", "dividend", "cash_dividend", "distribution_amount", "dps"]))
        dividend_yield = max(dividend_yield, pick(r, ["yield", "dividend_yield", "yield_percent"]))
        date_str = str(r.get("date") or r.get("announcement_date") or r.get("ex_date") or "")[:10]
        try:
            d = datetime.fromisoformat(date_str).date()
            if abs((today - d).days) <= 45:
                recent = True
        except Exception:
            pass

    bonus = 0
    notes: List[str] = []
    if recent:
        bonus += 3
        notes.append("توزيع حديث/قريب")
    if dividend_yield >= 4:
        bonus += 3
        notes.append(f"عائد توزيعات {dividend_yield}%")
    elif dividend_yield >= 2:
        bonus += 1
        notes.append(f"عائد توزيعات {dividend_yield}%")
    elif amount > 0 and not recent:
        bonus += 1
        notes.append("لديه سجل توزيعات")

    grade = "محفز توزيعات" if bonus >= 3 else "توزيعات عادية" if bonus > 0 else "محايد"
    return {"bonus": min(5, bonus), "grade": grade, "details": "، ".join(notes) if notes else "لا يوجد محفز توزيعات واضح", "raw": {"recent": recent, "yield": dividend_yield, "amount": amount}}


def load_symbol_data(symbol: str) -> Dict[str, Any]:
    cache = read_cache()
    item = cache.get("symbols", {}).get(symbol, {})
    if item and fresh(item):
        return item.get("data", {})

    fundamentals = first_payload([
        f"fundamentals/{symbol}/",
        f"fundamentals/{symbol}",
        f"stocks/{symbol}/fundamentals",
        f"companies/{symbol}/fundamentals",
    ])
    financials = first_payload([
        f"financial-statements/{symbol}/",
        f"financial-statements/{symbol}",
        f"financials/{symbol}/",
        f"financials/{symbol}",
        f"stocks/{symbol}/financials",
        f"companies/{symbol}/financial-statements",
    ])
    dividends = first_payload([
        f"dividends/{symbol}/",
        f"dividends/{symbol}",
        f"stocks/{symbol}/dividends",
        f"companies/{symbol}/dividends",
    ])

    data = {"fundamentals": fundamentals, "financials": financials, "dividends": dividends}
    cache.setdefault("symbols", {})[symbol] = {"cached_at": datetime.now().isoformat(timespec="seconds"), "data": data}
    write_cache(cache)
    return data


def score_symbol(symbol: str, sector: str = "") -> Dict[str, Any]:
    data = load_symbol_data(str(symbol).strip())
    fundamentals = data.get("fundamentals")
    financial_rows = newest_rows(data.get("financials"), 8)
    dividends = data.get("dividends")

    quality = score_quality(fundamentals)
    growth = score_growth(financial_rows)
    dividend = score_dividends(dividends)

    quality_bonus = int(quality.get("bonus", 0))
    growth_bonus = int(growth.get("bonus", 0))
    dividend_bonus = int(dividend.get("bonus", 0))
    total = quality_bonus + growth_bonus + dividend_bonus
    total = max(-12, min(16, total))

    blocked = total <= -9 or (growth_bonus <= -7 and quality_bonus < 0)
    if total >= 11:
        grade = "قوي جداً"
    elif total >= 6:
        grade = "قوي"
    elif total >= 2:
        grade = "جيد"
    elif total < 0:
        grade = "ضعيف"
    else:
        grade = "محايد"

    parts = []
    for x in (quality, growth, dividend):
        d = str(x.get("details") or "").strip()
        if d and d not in parts:
            parts.append(d)

    return {
        "available": any(data.values()),
        "bonus": total,
        "quality_bonus": quality_bonus,
        "growth_bonus": growth_bonus,
        "dividend_bonus": dividend_bonus,
        "grade": grade,
        "blocked": blocked,
        "details": " | ".join(parts) if parts else "بيانات أساسية غير كافية — نتيجة محايدة",
        "raw": {"quality": quality, "growth": growth, "dividend": dividend},
    }


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "1120"
    print(json.dumps(score_symbol(sym), ensure_ascii=False, indent=2))
