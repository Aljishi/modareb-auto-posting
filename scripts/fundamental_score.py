#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Fundamental Score
========================
يستفيد من البيانات المتاحة في باقة Sahmk Starter:
- القوائم المالية
- أساسيات الشركات
- توزيعات الأرباح

مبدأ مهم:
لا يتم رفض السهم بسبب عدم توفر البيانات الأساسية.
يتم الرفض فقط عند وجود علامة سلبية صريحة: خسائر، تدهور أرباح حاد، أو مديونية مفرطة مع تدفقات تشغيلية سلبية.
"""

import json
from pathlib import Path
from typing import Any, Dict, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FUNDAMENTALS_FILE = DATA_DIR / "fundamentals.json"

DEFAULT_SECTOR_PE = 20.0

SECTOR_BY_SYMBOL = {
    # البنوك
    "1010": "البنوك", "1020": "البنوك", "1030": "البنوك", "1050": "البنوك",
    "1060": "البنوك", "1080": "البنوك", "1120": "البنوك", "1140": "البنوك", "1150": "البنوك", "1180": "البنوك",
    # الطاقة والبتروكيماويات
    "2222": "الطاقة", "2380": "الطاقة", "2381": "الطاقة", "2382": "الطاقة",
    "2010": "البتروكيماويات", "2020": "البتروكيماويات", "2060": "البتروكيماويات", "2223": "البتروكيماويات", "2230": "البتروكيماويات",
    # الاتصالات والتقنية
    "7010": "الاتصالات", "7020": "الاتصالات", "7030": "الاتصالات",
    "7202": "التقنية", "7203": "التقنية", "7204": "التقنية", "9516": "التقنية", "9526": "التقنية", "9527": "التقنية",
    # الصحة والغذاء والتجزئة
    "4002": "الصحة", "4004": "الصحة", "4005": "الصحة", "4013": "الصحة",
    "6010": "الغذاء", "6020": "الغذاء", "2286": "الغذاء",
    "4190": "التجزئة", "4001": "التجزئة", "4003": "التجزئة",
    # العقار والنقل والصناعة
    "4020": "العقار", "4031": "العقار", "4321": "العقار", "4349": "العقار",
    "4030": "النقل", "4260": "النقل", "4261": "النقل", "4262": "النقل",
    "1211": "الصناعة", "1212": "الصناعة", "1301": "الصناعة", "1302": "الصناعة", "1303": "الصناعة", "1321": "الصناعة", "1322": "الصناعة", "4142": "الصناعة",
    # التأمين
    "8010": "التامين", "8060": "التامين", "8311": "التامين",
}


def fnum(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        return float(value)
    except Exception:
        return default


def load_fundamentals() -> Dict[str, Any]:
    try:
        if FUNDAMENTALS_FILE.exists():
            return json.loads(FUNDAMENTALS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"⚠️ fundamental_score: cannot read fundamentals.json: {exc}")
    return {"stocks": {}, "sector_pe": {}}


def detect_sector(symbol: str, stock_sector: str = "") -> str:
    stock_sector = (stock_sector or "").strip()
    if stock_sector:
        return stock_sector
    return SECTOR_BY_SYMBOL.get(str(symbol), "")


def get_first_number(data: Dict[str, Any], keys, default: float = 0.0) -> float:
    for key in keys:
        if key in data:
            value = fnum(data.get(key), default=None)
            if value is not None:
                return value
    return default


def score_symbol(symbol: str, sector: str = "") -> Dict[str, Any]:
    fundamentals = load_fundamentals()
    stocks = fundamentals.get("stocks", {}) if isinstance(fundamentals, dict) else {}
    data = stocks.get(str(symbol), {}) if isinstance(stocks, dict) else {}

    if not data:
        return {
            "available": False,
            "bonus": 0,
            "grade": "غير متوفر",
            "blocked": False,
            "details": "لا توجد بيانات أساسية كافية — لم يتم خصم نقاط",
            "raw": {},
        }

    sector = detect_sector(str(symbol), sector)
    sector_pe = fnum((fundamentals.get("sector_pe", {}) or {}).get(sector), DEFAULT_SECTOR_PE)
    if sector_pe <= 0:
        sector_pe = DEFAULT_SECTOR_PE

    pe = get_first_number(data, ["pe", "p_e", "pe_ratio"])
    eps = get_first_number(data, ["eps", "earnings_per_share"])
    revenue_growth = get_first_number(data, ["rev_growth", "revenue_growth", "sales_growth"])
    profit_growth = get_first_number(data, ["profit_growth", "net_income_growth", "earnings_growth"], default=0.0)
    roe = get_first_number(data, ["roe", "return_on_equity"])
    roa = get_first_number(data, ["roa", "return_on_assets"])
    debt_eq = get_first_number(data, ["debt_eq", "debt_to_equity", "debt_ratio"], default=0.0)
    dividend_yield = get_first_number(data, ["div_yield", "dividend_yield"])
    net_income = get_first_number(data, ["net_income", "net_profit"], default=0.0)
    operating_cash_flow = get_first_number(data, ["operating_cash_flow", "cash_flow_operations", "ocf"], default=0.0)

    score = 0
    details = []
    blocked = False
    block_reason = ""

    # إشارات رفض صريحة فقط
    if net_income < 0 or eps < 0:
        blocked = True
        block_reason = "خسائر أو EPS سلبي"
    elif profit_growth <= -40:
        blocked = True
        block_reason = "تراجع أرباح حاد"
    elif operating_cash_flow < 0 and debt_eq >= 1.5:
        blocked = True
        block_reason = "تدفقات تشغيلية سلبية مع مديونية مرتفعة"

    # P/E مقابل القطاع
    if pe > 0:
        pe_ratio = pe / sector_pe
        if pe_ratio <= 0.75:
            score += 3
            details.append(f"P/E أقل من القطاع ({pe:.1f})")
        elif pe_ratio <= 1.10:
            score += 1
            details.append(f"P/E مقبول ({pe:.1f})")
        elif pe_ratio >= 1.60:
            score -= 2
            details.append(f"P/E مرتفع ({pe:.1f})")

    # نمو الإيرادات والأرباح
    if revenue_growth >= 20:
        score += 4
        details.append(f"نمو إيرادات قوي {revenue_growth:+.1f}%")
    elif revenue_growth >= 10:
        score += 3
        details.append(f"نمو إيرادات جيد {revenue_growth:+.1f}%")
    elif revenue_growth > 0:
        score += 1
        details.append(f"نمو إيرادات {revenue_growth:+.1f}%")
    elif revenue_growth <= -15:
        score -= 3
        details.append(f"تراجع إيرادات {revenue_growth:.1f}%")

    if profit_growth >= 25:
        score += 4
        details.append(f"نمو أرباح قوي {profit_growth:+.1f}%")
    elif profit_growth >= 10:
        score += 2
        details.append(f"نمو أرباح {profit_growth:+.1f}%")
    elif profit_growth <= -20:
        score -= 3
        details.append(f"تراجع أرباح {profit_growth:.1f}%")

    # جودة الربحية
    if roe >= 20:
        score += 3
        details.append(f"ROE ممتاز {roe:.1f}%")
    elif roe >= 12:
        score += 2
        details.append(f"ROE جيد {roe:.1f}%")
    elif 0 < roe < 5:
        score -= 2
        details.append(f"ROE ضعيف {roe:.1f}%")

    if roa >= 8:
        score += 1
        details.append(f"ROA جيد {roa:.1f}%")

    # المديونية
    if debt_eq > 0:
        if debt_eq <= 0.50:
            score += 2
            details.append("مديونية منخفضة")
        elif debt_eq >= 1.50:
            score -= 3
            details.append("مديونية مرتفعة")

    # التوزيعات كمحفز إضافي لا كسبب شراء مستقل
    if dividend_yield >= 4:
        score += 2
        details.append(f"عائد توزيعات جيد {dividend_yield:.1f}%")
    elif dividend_yield >= 2:
        score += 1
        details.append(f"عائد توزيعات مقبول {dividend_yield:.1f}%")

    bonus = max(-8, min(12, int(round(score))))

    if blocked:
        bonus = min(bonus, -8)
        details.insert(0, block_reason)

    if bonus >= 9:
        grade = "قوي جداً"
    elif bonus >= 5:
        grade = "قوي"
    elif bonus >= 1:
        grade = "مقبول"
    elif bonus == 0:
        grade = "محايد"
    else:
        grade = "ضعيف"

    return {
        "available": True,
        "bonus": bonus,
        "grade": grade,
        "blocked": blocked,
        "details": " + ".join(details[:5]) if details else "بيانات أساسية محايدة",
        "raw": {
            "sector": sector,
            "sector_pe": sector_pe,
            "pe": pe,
            "eps": eps,
            "revenue_growth": revenue_growth,
            "profit_growth": profit_growth,
            "roe": roe,
            "roa": roa,
            "debt_eq": debt_eq,
            "dividend_yield": dividend_yield,
        },
    }


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "1120"
    print(json.dumps(score_symbol(sym), ensure_ascii=False, indent=2))
