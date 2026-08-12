#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RASED Sector Master v1.0
========================

مصدر مركزي لتوحيد أسماء القطاعات وتصحيح أخطاء مزود البيانات المعروفة.

المبدأ:
- نعتمد قطاع مزود البيانات ما دام موجودًا ومعقولًا.
- نطبع أسماء القطاعات إلى أسماء موحدة داخل راصد.
- نطبق Override بالرمز فقط عندما نملك تصحيحًا موثوقًا.
- لا نخمن قطاعًا غير معروف؛ نعيد "غير مصنف" بدل إدخال Bonus خاطئ.

ملاحظة:
4011 (لازوردي) مصنف رسميًا ضمن "السلع طويلة الاجل"،
وليس "الرعاية الصحية".
"""

from __future__ import annotations

from typing import Any, Dict


# ------------------------------------------------------------
# Canonical sector aliases
# ------------------------------------------------------------

SECTOR_ALIASES: Dict[str, str] = {
    # Banks
    "المصارف": "البنوك",
    "المصارف والخدمات المالية": "البنوك",
    "Banks": "البنوك",

    # Materials / petrochem / mining
    "المواد الاساسية": "المواد الأساسية",
    "المواد الأساسية": "المواد الأساسية",
    "Basic Materials": "المواد الأساسية",
    "الصناعات": "المواد الأساسية",

    # Energy
    "Energy": "الطاقة",
    "الطاقة": "الطاقة",

    # Healthcare
    "Health Care": "الرعاية الصحية",
    "Healthcare": "الرعاية الصحية",
    "الرعاية الصحية": "الرعاية الصحية",

    # Telecom
    "Telecommunication Services": "الاتصالات",
    "Telecom": "الاتصالات",
    "الاتصالات": "الاتصالات",

    # Transport
    "Transportation": "النقل",
    "النقل": "النقل",

    # Capital goods
    "Capital Goods": "السلع الرأسمالية",
    "السلع الرأسمالية": "السلع الرأسمالية",

    # Insurance
    "Insurance": "التأمين",
    "التأمين": "التأمين",

    # Consumer services
    "Consumer Services": "الخدمات الاستهلاكية",
    "الخدمات الإستهلاكية": "الخدمات الاستهلاكية",
    "الخدمات الاستهلاكية": "الخدمات الاستهلاكية",

    # Consumer durables
    "Consumer Durables & Apparel": "السلع طويلة الاجل",
    "السلع طويلة الأجل": "السلع طويلة الاجل",
    "السلع طويلة الاجل": "السلع طويلة الاجل",

    # Retail
    "Consumer Discretionary Distribution & Retail": "تجزئة وتوزيع السلع الكمالية",
    "تجزئة السلع الكمالية": "تجزئة وتوزيع السلع الكمالية",
    "تجزئة وتوزيع السلع الكمالية": "تجزئة وتوزيع السلع الكمالية",

    # Technology
    "Software & Services": "التطبيقات وخدمات التقنية",
    "التطبيقات وخدمات التقنية": "التطبيقات وخدمات التقنية",

    # Utilities
    "Utilities": "المرافق العامة",
    "المرافق العامة": "المرافق العامة",

    # Media
    "Media and Entertainment": "الإعلام والترفيه",
    "الإعلام والترفيه": "الإعلام والترفيه",

    # REITs
    "REITs": "الصناديق العقارية المتداولة",
    "الصناديق العقارية المتداولة": "الصناديق العقارية المتداولة",

    # Food
    "Food Production": "إنتاج الأغذية",
    "إنتاج الأغذية": "إنتاج الأغذية",

    # Real estate
    "Real Estate Management & Development": "إدارة وتطوير العقارات",
    "إدارة وتطوير العقارات": "إدارة وتطوير العقارات",
}


# ------------------------------------------------------------
# Symbol-specific authoritative corrections
# ------------------------------------------------------------
# Keep this list intentionally small. Add an override only when
# the provider is observed to be wrong and the official sector
# is verified.

SYMBOL_SECTOR_OVERRIDES: Dict[str, str] = {
    # Lazurde Company for Jewelry
    "4011": "السلع طويلة الاجل",

    # Defensive corrections for legacy/emergency data
    "1120": "البنوك",
    "1180": "البنوك",
    "2010": "المواد الأساسية",
    "2222": "الطاقة",
    "2050": "إنتاج الأغذية",
}


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    text = " ".join(text.split())
    return text


def canonicalize_sector(sector: Any) -> str:
    """
    Normalize a provider sector name to RASED canonical naming.
    Unknown non-empty sectors are preserved rather than guessed.
    """
    text = _clean(sector)
    if not text:
        return "غير مصنف"

    return SECTOR_ALIASES.get(text, text)


def resolve_sector(symbol: Any, provider_sector: Any = "") -> str:
    """
    Return the authoritative sector used by RASED.

    Priority:
    1) symbol-specific verified correction
    2) canonicalized provider sector
    3) "غير مصنف"
    """
    sym = _clean(symbol)

    if sym in SYMBOL_SECTOR_OVERRIDES:
        return SYMBOL_SECTOR_OVERRIDES[sym]

    return canonicalize_sector(provider_sector)


def sector_was_overridden(symbol: Any, provider_sector: Any = "") -> bool:
    sym = _clean(symbol)
    if sym not in SYMBOL_SECTOR_OVERRIDES:
        return False

    provider = canonicalize_sector(provider_sector)
    official = SYMBOL_SECTOR_OVERRIDES[sym]
    return provider != official


def normalize_stock_sector(stock: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a copy of a stock dict with normalized sector metadata.
    """
    item = dict(stock)

    symbol = item.get("symbol") or item.get("stock_symbol") or ""
    provider_sector = (
        item.get("sector")
        or item.get("sector_name")
        or ""
    )

    resolved = resolve_sector(symbol, provider_sector)

    item["sector_provider_raw"] = _clean(provider_sector)
    item["sector"] = resolved
    item["sector_name"] = resolved
    item["sector_source"] = (
        "symbol_override"
        if sector_was_overridden(symbol, provider_sector)
        else "provider_normalized"
    )

    return item


if __name__ == "__main__":
    # Lightweight self-test.
    assert resolve_sector("4011", "الرعاية الصحية") == "السلع طويلة الاجل"
    assert resolve_sector("1120", "المصارف") == "البنوك"
    assert resolve_sector("9999", "Insurance") == "التأمين"
    assert resolve_sector("9999", "") == "غير مصنف"

    print("✅ RASED Sector Master self-test passed")
