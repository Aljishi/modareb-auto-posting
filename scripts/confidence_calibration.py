#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Historical Confidence Calibration

وظيفة الملف:
1. قراءة النتائج الفعلية من data/published_signals.csv.
2. اعتبار TP1 وTP2 نجاحًا، وSL وEXPIRED إخفاقًا.
3. حساب نسبة نجاح تاريخية لكل نطاق من درجات RASED SCORE.
4. تطبيق Bayesian Shrinkage لمنع التضليل عند صغر العينة.
5. دمج الثقة التاريخية مع ثقة OpenAI بدرجة تعتمد على حجم العينة.
6. حفظ ثقة OpenAI الخام دون تعديلها.
7. تحديث data/signals.json قبل بوابة التحقق النهائية.
8. إنشاء data/confidence_calibration.json للتدقيق والشفافية.

مهم:
- هذا الملف لا يخفّض أو يرفع RASED SCORE.
- هذا الملف لا يقرر نشر الإشارة.
- وظيفته الوحيدة هي تحويل "الثقة" إلى تقدير معاير تاريخيًا.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =========================================================
# المسارات
# =========================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

SIGNALS_FILE = DATA_DIR / "signals.json"
PUBLISHED_FILE = DATA_DIR / "published_signals.csv"
CALIBRATION_FILE = DATA_DIR / "confidence_calibration.json"


# =========================================================
# الإعدادات
# =========================================================

# الحد الأدنى للعينة قبل الاعتماد القوي على مجموعة محددة.
MIN_GROUP_SAMPLE = max(
    1,
    int(os.getenv("CONFIDENCE_MIN_GROUP_SAMPLE", "8")),
)

# عند بلوغ هذا العدد يصبح الوزن التاريخي في حده الأعلى.
FULL_WEIGHT_SAMPLE = max(
    MIN_GROUP_SAMPLE,
    int(os.getenv("CONFIDENCE_FULL_WEIGHT_SAMPLE", "30")),
)

# عرض نطاقات RASED SCORE بعرض خمس نقاط:
# 75–79.9، 80–84.9، 85–89.9...
SCORE_BUCKET_SIZE = max(
    1,
    int(os.getenv("CONFIDENCE_SCORE_BUCKET_SIZE", "5")),
)

# Bayesian prior:
# 3 نجاحات و2 إخفاقات افتراضية = متوسط أولي 60%.
# يمنع نسبة 100% أو 0% من عينة صغيرة جدًا.
PRIOR_SUCCESSES = max(
    0.0,
    float(os.getenv("CONFIDENCE_PRIOR_SUCCESSES", "3")),
)

PRIOR_FAILURES = max(
    0.0,
    float(os.getenv("CONFIDENCE_PRIOR_FAILURES", "2")),
)

# عند عدم وجود سجل تاريخي كافٍ، لا نعرض ثقة مرتفعة جدًا.
NO_HISTORY_MAX_CONFIDENCE = min(
    100.0,
    max(
        0.0,
        float(
            os.getenv(
                "CONFIDENCE_NO_HISTORY_MAX",
                "75",
            )
        ),
    ),
)

# الحدود النهائية المعروضة.
MIN_DISPLAY_CONFIDENCE = min(
    100.0,
    max(
        0.0,
        float(
            os.getenv(
                "CONFIDENCE_DISPLAY_MIN",
                "40",
            )
        ),
    ),
)

MAX_DISPLAY_CONFIDENCE = min(
    100.0,
    max(
        MIN_DISPLAY_CONFIDENCE,
        float(
            os.getenv(
                "CONFIDENCE_DISPLAY_MAX",
                "95",
            )
        ),
    ),
)

# الحالات النهائية فقط.
SUCCESS_STATUSES = {"TP1", "TP2"}
FAILURE_STATUSES = {"SL", "EXPIRED"}
CLOSED_STATUSES = SUCCESS_STATUSES | FAILURE_STATUSES


# =========================================================
# أدوات عامة
# =========================================================

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def fnum(
    value: Any,
    default: float = 0.0,
) -> float:
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


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(minimum, min(maximum, value))


def safe_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def load_json(
    path: Path,
    default: Any,
) -> Any:
    try:
        if path.exists():
            return json.loads(
                path.read_text(encoding="utf-8")
            )

    except Exception as exc:
        print(f"⚠️ تعذر قراءة {path.name}: {exc}")

    return default


def write_json(
    path: Path,
    payload: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary.replace(path)


def extract_signals(
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

    signals = payload.get("signals", [])

    if not isinstance(signals, list):
        return []

    return [
        item
        for item in signals
        if isinstance(item, dict)
    ]


def score_bucket(
    score: float,
) -> str:
    score = clamp(score, 0.0, 100.0)

    lower = int(score // SCORE_BUCKET_SIZE) * SCORE_BUCKET_SIZE
    upper = min(
        100,
        lower + SCORE_BUCKET_SIZE - 1,
    )

    return f"{lower}-{upper}"


def normalize_tier(
    value: Any,
) -> str:
    tier = safe_text(value).upper()

    aliases = {
        "STANDARD": "STANDARD",
        "PREMIUM": "PREMIUM",
        "GOLD": "GOLD",
        "GOLDEN": "GOLD",
        "PLATINUM": "PLATINUM",
    }

    return aliases.get(
        tier,
        tier or "UNKNOWN",
    )


def normalize_signal_type(
    value: Any,
) -> str:
    signal_type = safe_text(value).upper()

    if signal_type in {
        "NORMAL",
        "STANDARD",
        "PREMIUM",
    }:
        return "NORMAL"

    if signal_type in {
        "GOLD",
        "GOLDEN",
    }:
        return "GOLDEN"

    return signal_type or "NORMAL"


# =========================================================
# قراءة الأداء التاريخي
# =========================================================

def read_closed_history() -> List[Dict[str, Any]]:
    if not PUBLISHED_FILE.exists():
        return []

    rows: List[Dict[str, Any]] = []

    try:
        with PUBLISHED_FILE.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            for raw in reader:
                if not isinstance(raw, dict):
                    continue

                status = safe_text(
                    raw.get("status")
                ).upper()

                if status not in CLOSED_STATUSES:
                    continue

                rased_score = fnum(
                    raw.get("rased_score"),
                    -1.0,
                )

                if rased_score < 0:
                    continue

                rows.append(
                    {
                        "signal_id": safe_text(
                            raw.get("signal_id")
                        ),
                        "symbol": safe_text(
                            raw.get("symbol")
                        ),
                        "status": status,
                        "success": (
                            status in SUCCESS_STATUSES
                        ),
                        "rased_score": rased_score,
                        "score_bucket": score_bucket(
                            rased_score
                        ),
                        "tier": normalize_tier(
                            raw.get("tier")
                        ),
                        "signal_type": (
                            normalize_signal_type(
                                raw.get("signal_type")
                            )
                        ),
                    }
                )

    except Exception as exc:
        print(
            "⚠️ تعذر قراءة سجل الإشارات المنشورة: "
            f"{exc}"
        )

        return []

    return rows


# =========================================================
# بناء الإحصاءات
# =========================================================

def empty_counter() -> Dict[str, int]:
    return {
        "sample": 0,
        "successes": 0,
        "failures": 0,
    }


def add_outcome(
    counter: Dict[str, int],
    success: bool,
) -> None:
    counter["sample"] += 1

    if success:
        counter["successes"] += 1
    else:
        counter["failures"] += 1


def bayesian_rate(
    successes: int,
    failures: int,
) -> float:
    numerator = successes + PRIOR_SUCCESSES

    denominator = (
        successes
        + failures
        + PRIOR_SUCCESSES
        + PRIOR_FAILURES
    )

    if denominator <= 0:
        return 0.0

    return round(
        (numerator / denominator) * 100,
        2,
    )


def raw_rate(
    successes: int,
    sample: int,
) -> float:
    if sample <= 0:
        return 0.0

    return round(
        (successes / sample) * 100,
        2,
    )


def enrich_counter(
    counter: Dict[str, int],
) -> Dict[str, Any]:
    sample = int(counter.get("sample", 0))
    successes = int(
        counter.get("successes", 0)
    )
    failures = int(
        counter.get("failures", 0)
    )

    return {
        "sample": sample,
        "successes": successes,
        "failures": failures,
        "raw_success_rate": raw_rate(
            successes,
            sample,
        ),
        "bayesian_success_rate": bayesian_rate(
            successes,
            failures,
        ),
    }


def build_statistics(
    history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    global_counter = empty_counter()

    by_score_bucket: Dict[
        str,
        Dict[str, int],
    ] = defaultdict(empty_counter)

    by_tier: Dict[
        str,
        Dict[str, int],
    ] = defaultdict(empty_counter)

    by_type: Dict[
        str,
        Dict[str, int],
    ] = defaultdict(empty_counter)

    by_type_and_score: Dict[
        str,
        Dict[str, int],
    ] = defaultdict(empty_counter)

    by_tier_and_score: Dict[
        str,
        Dict[str, int],
    ] = defaultdict(empty_counter)

    for row in history:
        success = bool(row.get("success"))

        bucket = safe_text(
            row.get("score_bucket")
        )

        tier = normalize_tier(
            row.get("tier")
        )

        signal_type = normalize_signal_type(
            row.get("signal_type")
        )

        add_outcome(
            global_counter,
            success,
        )

        add_outcome(
            by_score_bucket[bucket],
            success,
        )

        add_outcome(
            by_tier[tier],
            success,
        )

        add_outcome(
            by_type[signal_type],
            success,
        )

        add_outcome(
            by_type_and_score[
                f"{signal_type}|{bucket}"
            ],
            success,
        )

        add_outcome(
            by_tier_and_score[
                f"{tier}|{bucket}"
            ],
            success,
        )

    return {
        "global": enrich_counter(
            global_counter
        ),
        "by_score_bucket": {
            key: enrich_counter(value)
            for key, value
            in sorted(by_score_bucket.items())
        },
        "by_tier": {
            key: enrich_counter(value)
            for key, value
            in sorted(by_tier.items())
        },
        "by_signal_type": {
            key: enrich_counter(value)
            for key, value
            in sorted(by_type.items())
        },
        "by_type_and_score": {
            key: enrich_counter(value)
            for key, value
            in sorted(
                by_type_and_score.items()
            )
        },
        "by_tier_and_score": {
            key: enrich_counter(value)
            for key, value
            in sorted(
                by_tier_and_score.items()
            )
        },
    }


# =========================================================
# اختيار المجموعة التاريخية الأنسب
# =========================================================

def get_group(
    stats: Dict[str, Any],
    category: str,
    key: str,
) -> Optional[Dict[str, Any]]:
    groups = stats.get(category, {})

    if not isinstance(groups, dict):
        return None

    group = groups.get(key)

    if not isinstance(group, dict):
        return None

    return group


def select_historical_group(
    signal: Dict[str, Any],
    stats: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    rased_score = fnum(
        signal.get("rased_score")
        or signal.get("score")
    )

    bucket = score_bucket(
        rased_score
    )

    tier = normalize_tier(
        signal.get("tier")
    )

    signal_type = normalize_signal_type(
        signal.get("signal_type")
        or (
            "GOLDEN"
            if tier in {"GOLD", "PLATINUM"}
            else "NORMAL"
        )
    )

    candidates = [
        (
            "signal_type_and_score",
            get_group(
                stats,
                "by_type_and_score",
                f"{signal_type}|{bucket}",
            ),
        ),
        (
            "tier_and_score",
            get_group(
                stats,
                "by_tier_and_score",
                f"{tier}|{bucket}",
            ),
        ),
        (
            "score_bucket",
            get_group(
                stats,
                "by_score_bucket",
                bucket,
            ),
        ),
        (
            "tier",
            get_group(
                stats,
                "by_tier",
                tier,
            ),
        ),
        (
            "signal_type",
            get_group(
                stats,
                "by_signal_type",
                signal_type,
            ),
        ),
        (
            "global",
            stats.get("global"),
        ),
    ]

    # نأخذ أكثر مجموعة تخصصًا إذا كانت عينتها كافية.
    for source, group in candidates:
        if not isinstance(group, dict):
            continue

        if int(group.get("sample", 0)) >= MIN_GROUP_SAMPLE:
            return source, group

    # إذا لم توجد عينة كافية، نستخدم أكبر مجموعة متاحة.
    available = [
        (source, group)
        for source, group in candidates
        if isinstance(group, dict)
        and int(group.get("sample", 0)) > 0
    ]

    if available:
        return max(
            available,
            key=lambda item: int(
                item[1].get("sample", 0)
            ),
        )

    return (
        "no_history",
        {
            "sample": 0,
            "successes": 0,
            "failures": 0,
            "raw_success_rate": 0.0,
            "bayesian_success_rate": 0.0,
        },
    )


# =========================================================
# معايرة الإشارة
# =========================================================

def ai_confidence_for(
    signal: Dict[str, Any],
) -> float:
    return clamp(
        fnum(
            signal.get("ai_confidence")
            or signal.get("confidence")
            or signal.get("rased_score")
            or signal.get("score"),
            0.0,
        ),
        0.0,
        100.0,
    )


def historical_weight(
    sample: int,
) -> float:
    """
    العينة الصغيرة لا تسيطر على الرقم النهائي.

    أقل من 8:
        وزن تاريخي منخفض.

    من 8 إلى 30:
        يزيد تدريجيًا.

    30 فأكثر:
        التاريخ يأخذ 80%،
        مع إبقاء 20% لمراجعة الإشارة الحالية.
    """

    if sample <= 0:
        return 0.0

    if sample < MIN_GROUP_SAMPLE:
        return round(
            0.15 * (
                sample / MIN_GROUP_SAMPLE
            ),
            4,
        )

    progress = (
        sample - MIN_GROUP_SAMPLE
    ) / max(
        1,
        FULL_WEIGHT_SAMPLE - MIN_GROUP_SAMPLE,
    )

    progress = clamp(
        progress,
        0.0,
        1.0,
    )

    return round(
        0.35 + (0.45 * progress),
        4,
    )


def calibrate_signal(
    signal: Dict[str, Any],
    stats: Dict[str, Any],
) -> Dict[str, Any]:
    item = dict(signal)

    raw_ai_confidence = ai_confidence_for(
        item
    )

    source, group = select_historical_group(
        item,
        stats,
    )

    sample = int(
        group.get("sample", 0)
    )

    successes = int(
        group.get("successes", 0)
    )

    failures = int(
        group.get("failures", 0)
    )

    historical_confidence = fnum(
        group.get("bayesian_success_rate"),
        0.0,
    )

    weight = historical_weight(
        sample
    )

    if sample <= 0:
        calibrated = min(
            raw_ai_confidence,
            NO_HISTORY_MAX_CONFIDENCE,
        )

        confidence_label = (
            "تقديري — لا توجد عينة تاريخية مغلقة"
        )

    else:
        calibrated = (
            historical_confidence * weight
            + raw_ai_confidence * (1.0 - weight)
        )

        if sample < MIN_GROUP_SAMPLE:
            confidence_label = (
                f"معايرة أولية — عينة {sample}"
            )
        else:
            confidence_label = (
                f"ثقة تاريخية معايرة — عينة {sample}"
            )

    calibrated = round(
        clamp(
            calibrated,
            MIN_DISPLAY_CONFIDENCE,
            MAX_DISPLAY_CONFIDENCE,
        ),
        1,
    )

    item["raw_ai_confidence"] = round(
        raw_ai_confidence,
        1,
    )

    item["historical_confidence"] = round(
        historical_confidence,
        1,
    )

    item["calibrated_confidence"] = calibrated

    # تبقى ai_confidence كما هي لأغراض التدقيق.
    # confidence تصبح القيمة المخصصة للعرض.
    item["confidence"] = f"{calibrated:.1f}%"

    item["confidence_calibrated"] = True
    item["confidence_source"] = source
    item["confidence_label"] = confidence_label
    item["confidence_sample_size"] = sample
    item["confidence_successes"] = successes
    item["confidence_failures"] = failures
    item["confidence_historical_weight"] = weight

    item["confidence_calibration"] = {
        "source": source,
        "sample_size": sample,
        "successes": successes,
        "failures": failures,
        "raw_ai_confidence": round(
            raw_ai_confidence,
            1,
        ),
        "historical_confidence": round(
            historical_confidence,
            1,
        ),
        "historical_weight": weight,
        "calibrated_confidence": calibrated,
        "label": confidence_label,
        "calibrated_at": now_iso(),
    }

    return item


# =========================================================
# التشغيل الرئيسي
# =========================================================

def main() -> int:
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = load_json(
        SIGNALS_FILE,
        {},
    )

    signals = extract_signals(
        payload
    )

    if not signals:
        report = {
            "status": "NO_SIGNALS",
            "generated_at": now_iso(),
            "closed_history_sample": 0,
            "message": (
                "لا توجد إشارات لمعايرة الثقة"
            ),
        }

        write_json(
            CALIBRATION_FILE,
            report,
        )

        print(
            "ℹ️ لا توجد إشارات لمعايرة الثقة"
        )

        return 0

    history = read_closed_history()
    statistics = build_statistics(
        history
    )

    calibrated_signals = [
        calibrate_signal(
            signal,
            statistics,
        )
        for signal in signals
    ]

    if isinstance(payload, dict):
        updated_payload = dict(payload)
    else:
        updated_payload = {}

    updated_payload["signals"] = (
        calibrated_signals
    )

    updated_payload[
        "confidence_calibration_applied"
    ] = True

    updated_payload[
        "confidence_calibrated_at"
    ] = now_iso()

    updated_payload[
        "confidence_closed_history_sample"
    ] = len(history)

    write_json(
        SIGNALS_FILE,
        updated_payload,
    )

    report_signals: List[Dict[str, Any]] = []

    for signal in calibrated_signals:
        symbol = safe_text(
            signal.get("stock_symbol")
            or signal.get("symbol")
        )

        print(
            f"✅ {symbol}: "
            f"AI={signal.get('raw_ai_confidence')}% | "
            f"Historical="
            f"{signal.get('historical_confidence')}% | "
            f"Calibrated="
            f"{signal.get('calibrated_confidence')}% | "
            f"Sample="
            f"{signal.get('confidence_sample_size')}"
        )

        report_signals.append(
            {
                "symbol": symbol,
                "rased_score": fnum(
                    signal.get("rased_score")
                ),
                "raw_ai_confidence": (
                    signal.get(
                        "raw_ai_confidence"
                    )
                ),
                "historical_confidence": (
                    signal.get(
                        "historical_confidence"
                    )
                ),
                "calibrated_confidence": (
                    signal.get(
                        "calibrated_confidence"
                    )
                ),
                "source": signal.get(
                    "confidence_source"
                ),
                "sample_size": signal.get(
                    "confidence_sample_size"
                ),
                "label": signal.get(
                    "confidence_label"
                ),
            }
        )

    report = {
        "status": "PASS",
        "engine": (
            "rased_confidence_calibration_v1"
        ),
        "generated_at": now_iso(),
        "configuration": {
            "minimum_group_sample": (
                MIN_GROUP_SAMPLE
            ),
            "full_weight_sample": (
                FULL_WEIGHT_SAMPLE
            ),
            "score_bucket_size": (
                SCORE_BUCKET_SIZE
            ),
            "prior_successes": (
                PRIOR_SUCCESSES
            ),
            "prior_failures": (
                PRIOR_FAILURES
            ),
            "no_history_max_confidence": (
                NO_HISTORY_MAX_CONFIDENCE
            ),
            "display_min": (
                MIN_DISPLAY_CONFIDENCE
            ),
            "display_max": (
                MAX_DISPLAY_CONFIDENCE
            ),
        },
        "closed_history_sample": len(
            history
        ),
        "statistics": statistics,
        "signals": report_signals,
    }

    write_json(
        CALIBRATION_FILE,
        report,
    )

    print(
        f"📊 تمت معايرة ثقة "
        f"{len(calibrated_signals)} إشارة"
    )

    print(
        f"📚 العينة التاريخية المغلقة: "
        f"{len(history)}"
    )

    print(
        f"📄 التقرير: {CALIBRATION_FILE}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())