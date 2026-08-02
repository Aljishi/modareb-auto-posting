#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Portfolio Exposure Gate

وظيفة الملف:
1. منع نشر إشارة جديدة لنفس السهم إذا كانت هناك إشارة مفتوحة عليه.
2. منع تكرار التعرض لنفس القطاع أثناء وجود إشارة نشطة.
3. منع تجاوز الحد الأقصى للإشارات المفتوحة.
4. اختيار أفضل إشارة فقط عند ظهور عدة إشارات من القطاع نفسه.
5. تجاهل الإشارات القديمة التي تجاوزت فترة الاحتفاظ القصوى.
6. حفظ تقرير كامل عن قرارات القبول والرفض.
7. تحديث validated_signals.json قبل إنشاء الصورة والنشر.

هذا الملف لا ينفذ صفقات ولا يقدم توصية شخصية.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# =========================================================
# المسارات
# =========================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

VALIDATED_FILE = DATA_DIR / "validated_signals.json"
OPEN_SIGNALS_FILE = DATA_DIR / "open_signals.json"
PUBLISHED_FILE = DATA_DIR / "published_signals.csv"

REPORT_FILE = DATA_DIR / "portfolio_exposure_report.json"


# =========================================================
# إعدادات التعرض
# =========================================================

# الحد الأقصى لإجمالي الإشارات المفتوحة في الوقت نفسه.
MAX_OPEN_POSITIONS = max(
    1,
    int(os.getenv("RASED_MAX_OPEN_POSITIONS", "4")),
)

# الحد الأقصى للإشارات المفتوحة في القطاع نفسه.
# القيمة 1 تعني: لا يُنشر سهم ثانٍ من القطاع نفسه.
MAX_OPEN_POSITIONS_PER_SECTOR = max(
    1,
    int(
        os.getenv(
            "RASED_MAX_OPEN_POSITIONS_PER_SECTOR",
            "1",
        )
    ),
)

# منع نشر السهم نفسه مرة أخرى أثناء بقاء إشارته مفتوحة.
BLOCK_DUPLICATE_SYMBOL = (
    os.getenv("RASED_BLOCK_DUPLICATE_SYMBOL", "true")
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)

# عند وجود أكثر من إشارة جديدة من القطاع نفسه،
# يحتفظ النظام بأفضل إشارة فقط وفق ترتيب الجودة.
KEEP_BEST_SIGNAL_PER_SECTOR = (
    os.getenv(
        "RASED_KEEP_BEST_SIGNAL_PER_SECTOR",
        "true",
    )
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)

# إذا لم تتوفر فترة الاحتفاظ في الإشارة القديمة.
DEFAULT_MAX_HOLDING_DAYS = max(
    1,
    int(os.getenv("RASED_DEFAULT_MAX_HOLDING_DAYS", "7")),
)

# الإشارات القديمة جدًا تُستبعد احترازيًا حتى لو بقيت
# حالتها OPEN بسبب تأخر تحديث سجل الأداء.
MAX_STALE_OPEN_DAYS = max(
    DEFAULT_MAX_HOLDING_DAYS,
    int(os.getenv("RASED_MAX_STALE_OPEN_DAYS", "10")),
)


# =========================================================
# خريطة القطاعات الاحتياطية
# =========================================================

SECTOR_MAP: Dict[str, str] = {
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
    "1301": "المواد الأساسية",
    "1302": "المواد الأساسية",
    "1303": "المواد الأساسية",
    "1304": "المواد الأساسية",
    "1320": "المواد الأساسية",
    "1321": "المواد الأساسية",
    "1322": "المواد الأساسية",
    "2010": "المواد الأساسية",
    "2090": "المواد الأساسية",
    "2230": "المواد الأساسية",
    "2310": "المواد الأساسية",
    "2330": "المواد الأساسية",
    "2350": "المواد الأساسية",
    "2380": "المواد الأساسية",
    "2381": "المواد الأساسية",
    "2382": "المواد الأساسية",
    "3008": "المواد الأساسية",

    # السلع الرأسمالية
    "1212": "السلع الرأسمالية",
    "1810": "الخدمات التجارية والمهنية",
    "1832": "الخدمات التجارية والمهنية",
    "2001": "السلع الرأسمالية",
    "2002": "السلع الرأسمالية",
    "2003": "السلع الرأسمالية",
    "2004": "السلع الرأسمالية",
    "2020": "السلع الرأسمالية",
    "2030": "السلع الرأسمالية",
    "2060": "السلع الرأسمالية",
    "2200": "السلع الرأسمالية",

    # النقل
    "4030": "النقل",
    "4031": "النقل",
    "4110": "النقل",

    # الرعاية الصحية
    "4002": "الرعاية الصحية",
    "4004": "الرعاية الصحية",
    "4005": "الرعاية الصحية",
    "4007": "الرعاية الصحية",
    "4010": "الرعاية الصحية",
    "4011": "الرعاية الصحية",

    # التجزئة والخدمات
    "4001": "تجزئة وتوزيع السلع الاستهلاكية",
    "4003": "تجزئة السلع الكمالية",
    "4164": "تجزئة السلع الكمالية",
    "4190": "تجزئة السلع الكمالية",
    "4191": "تجزئة السلع الكمالية",
    "4192": "تجزئة السلع الكمالية",
    "4194": "تجزئة السلع الكمالية",
    "4260": "الخدمات الاستهلاكية",
    "4261": "الخدمات الاستهلاكية",
    "4262": "الخدمات الاستهلاكية",
    "6004": "الإعلام والترفيه",
    "6010": "الإعلام والترفيه",

    # العقارات
    "4020": "إدارة وتطوير العقارات",
    "4130": "إدارة وتطوير العقارات",
    "4250": "إدارة وتطوير العقارات",
    "4321": "الصناديق العقارية المتداولة",
    "4349": "الصناديق العقارية المتداولة",

    # الاتصالات والتقنية
    "7010": "الاتصالات",
    "7020": "الاتصالات",
    "7030": "الاتصالات",
    "7202": "التطبيقات وخدمات التقنية",
    "7203": "التطبيقات وخدمات التقنية",
    "7204": "التطبيقات وخدمات التقنية",

    # التأمين
    "8010": "التأمين",
    "8060": "التأمين",
    "8210": "التأمين",
    "8311": "التأمين",

    # الأغذية
    "2050": "إنتاج الأغذية",
    "2270": "إنتاج الأغذية",
    "2280": "إنتاج الأغذية",
    "2286": "إنتاج الأغذية",
    "6001": "إنتاج الأغذية",
}


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

        number = float(value)

        if not math.isfinite(number):
            return default

        return number

    except (TypeError, ValueError):
        return default


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        ).replace(tzinfo=None)

    except (TypeError, ValueError):
        pass

    try:
        return datetime.strptime(text[:10], "%Y-%m-%d")

    except (TypeError, ValueError):
        return None


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(
                path.read_text(encoding="utf-8")
            )

    except Exception as exc:
        print(f"⚠️ تعذر قراءة {path.name}: {exc}")

    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def safe_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def normalize_symbol(value: Any) -> str:
    symbol = safe_text(value)

    if symbol.endswith(".0"):
        symbol = symbol[:-2]

    return symbol


def signal_symbol(signal: Dict[str, Any]) -> str:
    return normalize_symbol(
        signal.get("stock_symbol")
        or signal.get("symbol")
        or signal.get("ticker")
    )


def signal_sector(signal: Dict[str, Any]) -> str:
    symbol = signal_symbol(signal)

    sector = safe_text(
        signal.get("sector")
        or signal.get("sector_name")
        or signal.get("sector_name_ar")
    )

    if sector:
        return sector

    fundamental = signal.get("fundamental_raw")

    if isinstance(fundamental, dict):
        sector = safe_text(
            fundamental.get("sector")
        )

        if sector:
            return sector

    return SECTOR_MAP.get(symbol, "غير محدد")


def signal_name(signal: Dict[str, Any]) -> str:
    return safe_text(
        signal.get("stock_name")
        or signal.get("name")
        or signal_symbol(signal)
    )


def extract_validated_signals(
    payload: Any,
) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [
            item
            for item in payload
            if isinstance(item, dict)
        ]

    if not isinstance(payload, dict):
        return []

    candidates = (
        payload.get("validated_signals"),
        payload.get("signals"),
    )

    for candidate in candidates:
        if isinstance(candidate, list):
            return [
                item
                for item in candidate
                if isinstance(item, dict)
            ]

    return []


# =========================================================
# ترتيب جودة الإشارات
# =========================================================

def signal_quality_key(
    signal: Dict[str, Any],
) -> Tuple[float, float, float, float, float]:
    """
    ترتيب الإشارات من الأفضل إلى الأقل.

    الأولوية:
    1. RASED SCORE
    2. Score الفني
    3. موافقة وثقة OpenAI
    4. R:R
    5. نسبة الحجم
    """

    rased_score = fnum(
        signal.get("rased_score")
        or signal.get("score")
    )

    technical_score = fnum(
        signal.get("score")
        or signal.get("technical_score")
    )

    ai_confidence = fnum(
        signal.get("ai_confidence")
    )

    rr = fnum(
        signal.get("rr")
        or signal.get("rr_ratio")
    )

    volume_ratio = fnum(
        signal.get("volume_ratio")
    )

    return (
        rased_score,
        technical_score,
        ai_confidence,
        rr,
        volume_ratio,
    )


# =========================================================
# قراءة الإشارات المفتوحة
# =========================================================

def is_active_open_record(
    *,
    status: str,
    opened_at: Optional[datetime],
    max_holding_days: int,
) -> bool:
    normalized_status = status.strip().upper()

    if normalized_status not in {
        "OPEN",
        "ACTIVE",
        "PENDING",
        "STILL_ACTIVE",
    }:
        return False

    if opened_at is None:
        # عند غياب التاريخ نعتبرها مفتوحة احترازيًا.
        return True

    age_days = (datetime.now() - opened_at).days

    expiry_days = min(
        max(
            max_holding_days,
            DEFAULT_MAX_HOLDING_DAYS,
        ),
        MAX_STALE_OPEN_DAYS,
    )

    return age_days <= expiry_days


def load_open_signals_json() -> List[Dict[str, Any]]:
    payload = load_json(
        OPEN_SIGNALS_FILE,
        [],
    )

    if not isinstance(payload, list):
        return []

    active: List[Dict[str, Any]] = []

    for record in payload:
        if not isinstance(record, dict):
            continue

        signal = record.get("signal")

        if not isinstance(signal, dict):
            signal = record

        status = safe_text(
            record.get("status")
            or signal.get("status")
            or "OPEN"
        )

        opened_at = parse_datetime(
            record.get("posted_at")
            or record.get("published_at")
            or record.get("date")
            or signal.get("published_at")
            or signal.get("generated_at")
        )

        max_days = int(
            fnum(
                record.get("max_holding_days")
                or record.get("expires_at_days")
                or signal.get("max_holding_days"),
                DEFAULT_MAX_HOLDING_DAYS,
            )
        )

        if not is_active_open_record(
            status=status,
            opened_at=opened_at,
            max_holding_days=max_days,
        ):
            continue

        symbol = signal_symbol(signal)

        if not symbol:
            continue

        active.append(
            {
                "symbol": symbol,
                "name": signal_name(signal),
                "sector": signal_sector(signal),
                "status": status.upper(),
                "opened_at": (
                    opened_at.isoformat(timespec="seconds")
                    if opened_at
                    else None
                ),
                "max_holding_days": max_days,
                "source": str(OPEN_SIGNALS_FILE),
                "signal_id": safe_text(
                    signal.get("signal_id")
                    or record.get("signal_id")
                ),
            }
        )

    return active


def load_open_published_csv() -> List[Dict[str, Any]]:
    if not PUBLISHED_FILE.exists():
        return []

    active: List[Dict[str, Any]] = []

    try:
        with PUBLISHED_FILE.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            if not reader.fieldnames:
                return []

            for row in reader:
                if not isinstance(row, dict):
                    continue

                status = safe_text(
                    row.get("status")
                )

                opened_at = parse_datetime(
                    row.get("published_at")
                )

                max_days = int(
                    fnum(
                        row.get("max_holding_days"),
                        DEFAULT_MAX_HOLDING_DAYS,
                    )
                )

                if not is_active_open_record(
                    status=status,
                    opened_at=opened_at,
                    max_holding_days=max_days,
                ):
                    continue

                symbol = normalize_symbol(
                    row.get("symbol")
                )

                if not symbol:
                    continue

                sector = safe_text(
                    row.get("sector")
                )

                if not sector:
                    sector = SECTOR_MAP.get(
                        symbol,
                        "غير محدد",
                    )

                active.append(
                    {
                        "symbol": symbol,
                        "name": safe_text(
                            row.get("name")
                        ),
                        "sector": sector,
                        "status": status.upper(),
                        "opened_at": (
                            opened_at.isoformat(
                                timespec="seconds"
                            )
                            if opened_at
                            else None
                        ),
                        "max_holding_days": max_days,
                        "source": str(PUBLISHED_FILE),
                        "signal_id": safe_text(
                            row.get("signal_id")
                        ),
                    }
                )

    except Exception as exc:
        print(
            "⚠️ تعذر قراءة published_signals.csv: "
            f"{exc}"
        )

    return active


def deduplicate_open_positions(
    records: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for record in records:
        symbol = normalize_symbol(
            record.get("symbol")
        )

        if not symbol:
            continue

        # نستخدم الرمز كمفتاح لأن وجود أكثر من سجل مفتوح
        # للسهم نفسه لا يجب أن يضاعف التعرض.
        if symbol in seen:
            continue

        seen.add(symbol)
        result.append(record)

    return result


def load_active_open_positions() -> List[Dict[str, Any]]:
    json_positions = load_open_signals_json()
    csv_positions = load_open_published_csv()

    return deduplicate_open_positions(
        [*json_positions, *csv_positions]
    )


# =========================================================
# تطبيق بوابة التعرض
# =========================================================

def build_existing_exposure(
    positions: List[Dict[str, Any]],
) -> Tuple[Set[str], Dict[str, int]]:
    symbols: Set[str] = set()
    sectors: Dict[str, int] = {}

    for position in positions:
        symbol = normalize_symbol(
            position.get("symbol")
        )

        sector = safe_text(
            position.get("sector")
        ) or "غير محدد"

        if symbol:
            symbols.add(symbol)

        if sector != "غير محدد":
            sectors[sector] = sectors.get(sector, 0) + 1

    return symbols, sectors


def apply_exposure_gate(
    signals: List[Dict[str, Any]],
    active_positions: List[Dict[str, Any]],
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    approved: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    existing_symbols, existing_sectors = (
        build_existing_exposure(active_positions)
    )

    total_open_after_gate = len(active_positions)

    # نبدأ بأفضل الإشارات حتى تأخذ الإشارة الأعلى جودة
    # أولوية القطاع والمكان المتاح في المحفظة.
    ordered_signals = sorted(
        signals,
        key=signal_quality_key,
        reverse=True,
    )

    newly_accepted_symbols: Set[str] = set()
    newly_accepted_sectors: Dict[str, int] = {}

    for signal in ordered_signals:
        item = dict(signal)

        symbol = signal_symbol(item)
        sector = signal_sector(item)
        name = signal_name(item)

        reasons: List[str] = []

        if not symbol:
            reasons.append(
                "رمز السهم غير موجود أو غير صالح"
            )

        if (
            BLOCK_DUPLICATE_SYMBOL
            and symbol
            and (
                symbol in existing_symbols
                or symbol in newly_accepted_symbols
            )
        ):
            reasons.append(
                f"توجد إشارة مفتوحة بالفعل على السهم {symbol}"
            )

        existing_sector_count = existing_sectors.get(
            sector,
            0,
        )

        new_sector_count = newly_accepted_sectors.get(
            sector,
            0,
        )

        combined_sector_count = (
            existing_sector_count
            + new_sector_count
        )

        if (
            sector != "غير محدد"
            and combined_sector_count
            >= MAX_OPEN_POSITIONS_PER_SECTOR
        ):
            reasons.append(
                f"التعرض لقطاع {sector} بلغ الحد "
                f"{MAX_OPEN_POSITIONS_PER_SECTOR}"
            )

        if (
            KEEP_BEST_SIGNAL_PER_SECTOR
            and sector != "غير محدد"
            and new_sector_count > 0
        ):
            reasons.append(
                f"تم اختيار إشارة أعلى جودة من قطاع {sector}"
            )

        if total_open_after_gate >= MAX_OPEN_POSITIONS:
            reasons.append(
                "المحفظة بلغت الحد الأقصى "
                f"للإشارات المفتوحة: {MAX_OPEN_POSITIONS}"
            )

        exposure_decision = {
            "checked_at": now_iso(),
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "existing_open_positions": len(
                active_positions
            ),
            "existing_sector_positions": (
                existing_sector_count
            ),
            "max_open_positions": (
                MAX_OPEN_POSITIONS
            ),
            "max_positions_per_sector": (
                MAX_OPEN_POSITIONS_PER_SECTOR
            ),
        }

        if reasons:
            item["portfolio_exposure_approved"] = False
            item["portfolio_exposure_reasons"] = reasons
            item["portfolio_exposure_decision"] = (
                exposure_decision
            )

            rejected.append(item)

            print(
                f"❌ {symbol or 'UNKNOWN'} — "
                + " | ".join(reasons)
            )

            continue

        item["sector"] = sector
        item["sector_name"] = sector
        item["portfolio_exposure_approved"] = True
        item["portfolio_exposure_reasons"] = []
        item["portfolio_exposure_decision"] = (
            exposure_decision
        )

        approved.append(item)

        newly_accepted_symbols.add(symbol)

        if sector != "غير محدد":
            newly_accepted_sectors[sector] = (
                newly_accepted_sectors.get(
                    sector,
                    0,
                )
                + 1
            )

        total_open_after_gate += 1

        print(
            f"✅ {symbol} — تم اعتماد التعرض | "
            f"القطاع: {sector}"
        )

    return approved, rejected


# =========================================================
# حفظ النتيجة
# =========================================================

def update_validated_payload(
    original_payload: Any,
    approved: List[Dict[str, Any]],
    exposure_rejected: List[Dict[str, Any]],
    active_positions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if isinstance(original_payload, dict):
        output = dict(original_payload)
    else:
        output = {}

    previous_rejected = output.get("rejected", [])

    if not isinstance(previous_rejected, list):
        previous_rejected = []

    output["signals"] = approved
    output["validated_signals"] = approved

    output["rejected"] = [
        *previous_rejected,
        *exposure_rejected,
    ]

    output["total"] = len(approved)
    output["total_approved"] = len(approved)

    output["total_rejected"] = len(
        output["rejected"]
    )

    output["portfolio_exposure_checked"] = True
    output["portfolio_exposure_checked_at"] = now_iso()

    output["portfolio_exposure"] = {
        "max_open_positions": MAX_OPEN_POSITIONS,
        "max_positions_per_sector": (
            MAX_OPEN_POSITIONS_PER_SECTOR
        ),
        "block_duplicate_symbol": (
            BLOCK_DUPLICATE_SYMBOL
        ),
        "active_positions_before_gate": len(
            active_positions
        ),
        "approved_after_gate": len(approved),
        "rejected_by_exposure_gate": len(
            exposure_rejected
        ),
    }

    output["status"] = (
        "HAS_VALID_SIGNALS"
        if approved
        else "NO_VALID_SIGNALS"
    )

    return output


def build_report(
    *,
    input_count: int,
    approved: List[Dict[str, Any]],
    rejected: List[Dict[str, Any]],
    active_positions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    sector_exposure: Dict[str, int] = {}

    for position in active_positions:
        sector = safe_text(
            position.get("sector")
        ) or "غير محدد"

        sector_exposure[sector] = (
            sector_exposure.get(sector, 0)
            + 1
        )

    return {
        "generated_at": now_iso(),
        "status": (
            "PASS"
            if approved
            else "NO_CAPACITY_OR_SECTOR_CONFLICT"
        ),
        "configuration": {
            "max_open_positions": (
                MAX_OPEN_POSITIONS
            ),
            "max_positions_per_sector": (
                MAX_OPEN_POSITIONS_PER_SECTOR
            ),
            "block_duplicate_symbol": (
                BLOCK_DUPLICATE_SYMBOL
            ),
            "keep_best_signal_per_sector": (
                KEEP_BEST_SIGNAL_PER_SECTOR
            ),
            "default_max_holding_days": (
                DEFAULT_MAX_HOLDING_DAYS
            ),
            "max_stale_open_days": (
                MAX_STALE_OPEN_DAYS
            ),
        },
        "input_validated_signals": input_count,
        "approved_signals": len(approved),
        "rejected_signals": len(rejected),
        "active_open_positions": len(
            active_positions
        ),
        "current_sector_exposure": (
            sector_exposure
        ),
        "open_positions": active_positions,
        "approved": [
            {
                "symbol": signal_symbol(item),
                "name": signal_name(item),
                "sector": signal_sector(item),
                "rased_score": fnum(
                    item.get("rased_score")
                ),
            }
            for item in approved
        ],
        "rejected": [
            {
                "symbol": signal_symbol(item),
                "name": signal_name(item),
                "sector": signal_sector(item),
                "rased_score": fnum(
                    item.get("rased_score")
                ),
                "reasons": item.get(
                    "portfolio_exposure_reasons",
                    [],
                ),
            }
            for item in rejected
        ],
    }


# =========================================================
# التشغيل الرئيسي
# =========================================================

def main() -> int:
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = load_json(
        VALIDATED_FILE,
        {},
    )

    validated_signals = extract_validated_signals(
        payload
    )

    active_positions = load_active_open_positions()

    print("=" * 68)
    print("راصد — Portfolio Exposure Gate")
    print("=" * 68)

    print(
        f"📊 الإشارات المجازة قبل بوابة التعرض: "
        f"{len(validated_signals)}"
    )

    print(
        f"📂 الإشارات المفتوحة الفعالة: "
        f"{len(active_positions)}"
    )

    print(
        f"🎯 الحد الأقصى للمحفظة: "
        f"{MAX_OPEN_POSITIONS}"
    )

    print(
        f"🏢 الحد الأقصى لكل قطاع: "
        f"{MAX_OPEN_POSITIONS_PER_SECTOR}"
    )

    if not validated_signals:
        report = build_report(
            input_count=0,
            approved=[],
            rejected=[],
            active_positions=active_positions,
        )

        write_json(
            REPORT_FILE,
            report,
        )

        print(
            "ℹ️ لا توجد إشارات مجازة لفحص التعرض"
        )

        return 0

    approved, exposure_rejected = (
        apply_exposure_gate(
            signals=validated_signals,
            active_positions=active_positions,
        )
    )

    updated_payload = update_validated_payload(
        original_payload=payload,
        approved=approved,
        exposure_rejected=exposure_rejected,
        active_positions=active_positions,
    )

    write_json(
        VALIDATED_FILE,
        updated_payload,
    )

    report = build_report(
        input_count=len(validated_signals),
        approved=approved,
        rejected=exposure_rejected,
        active_positions=active_positions,
    )

    write_json(
        REPORT_FILE,
        report,
    )

    print(
        f"📊 Exposure Gate — "
        f"Input: {len(validated_signals)} | "
        f"Approved: {len(approved)} | "
        f"Rejected: {len(exposure_rejected)}"
    )

    print(f"📄 التقرير: {REPORT_FILE}")

    # عدم وجود مساحة في المحفظة ليس خطأ تقنيًا.
    # يعاد 0 كي يستمر Workflow إلى خطوة فحص العدد،
    # التي ستمنع الصورة والنشر عند عدم وجود إشارات.
    return 0


if __name__ == "__main__":
    sys.exit(main())