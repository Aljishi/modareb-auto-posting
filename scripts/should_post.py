#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — بوابة التحقق النهائية مع Dynamic RASED Score.

الخصائص:
1. تحديد حالة السوق تلقائيًا من data/daily.json.
2. تعديل الحد الأدنى لـ RASED SCORE حسب حالة السوق:
   - سوق قوي: 77
   - سوق طبيعي: 80
   - سوق ضعيف: 83
3. الإبقاء على ضوابط السيولة والمخاطر وR:R وRSI والـBacktest.
4. السماح بقبول حدودي منضبط في السوق الطبيعي فقط.
5. منع القبول الحدودي في السوق الضعيف.
6. حفظ حالة السوق والحد المطبق داخل validated_signals.json.
7. تسجيل أسباب قبول أو رفض كل إشارة.
"""

import json
import math
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =========================================================
# المسارات
# =========================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

SIGNALS_FILE = DATA_DIR / "signals.json"
VALIDATED_FILE = DATA_DIR / "validated_signals.json"
DAILY_FILE = DATA_DIR / "daily.json"
MARKET_REGIME_FILE = DATA_DIR / "market_regime.json"


# =========================================================
# حدود RASED SCORE الديناميكية
# =========================================================

STRONG_MARKET_MIN_RASED_SCORE = float(
    os.getenv("STRONG_MARKET_MIN_RASED_SCORE", "77")
)

NORMAL_MARKET_MIN_RASED_SCORE = float(
    os.getenv("NORMAL_MARKET_MIN_RASED_SCORE", "80")
)

WEAK_MARKET_MIN_RASED_SCORE = float(
    os.getenv("WEAK_MARKET_MIN_RASED_SCORE", "83")
)

# الحد الأدنى للقبول الحدودي في السوق الطبيعي فقط.
BORDERLINE_MIN_RASED_SCORE = float(
    os.getenv("BORDERLINE_MIN_RASED_SCORE", "78")
)


# =========================================================
# قواعد تصنيف حالة السوق
# =========================================================

MIN_MARKET_SAMPLE = int(
    os.getenv("MIN_MARKET_SAMPLE", "15")
)

STRONG_MARKET_MIN_AVG_CHANGE = float(
    os.getenv("STRONG_MARKET_MIN_AVG_CHANGE", "0.80")
)

STRONG_MARKET_MIN_ADVANCE_RATIO = float(
    os.getenv("STRONG_MARKET_MIN_ADVANCE_RATIO", "0.65")
)

WEAK_MARKET_MAX_AVG_CHANGE = float(
    os.getenv("WEAK_MARKET_MAX_AVG_CHANGE", "-0.50")
)

WEAK_MARKET_MAX_ADVANCE_RATIO = float(
    os.getenv("WEAK_MARKET_MAX_ADVANCE_RATIO", "0.35")
)

# إذا كان التذبذب العرضي مرتفعًا والسوق سلبيًا،
# تُعامل الحالة كسوق ضعيف.
HIGH_DISPERSION_THRESHOLD = float(
    os.getenv("HIGH_DISPERSION_THRESHOLD", "3.00")
)


# =========================================================
# الحدود الفنية
# =========================================================

MIN_SCORE = float(
    os.getenv("MIN_SIGNAL_SCORE", "80")
)

MIN_RR = float(
    os.getenv("MIN_RR", "1.8")
)

MIN_VOLUME_RATIO = float(
    os.getenv("MIN_VOLUME_RATIO", "0.85")
)

MIN_RSI = float(
    os.getenv("MIN_RSI", "38")
)

MAX_RSI = float(
    os.getenv("MAX_RSI", "74")
)

MIN_BACKTEST_WIN_RATE = float(
    os.getenv("MIN_BACKTEST_WIN_RATE", "40")
)

MIN_BACKTEST_TRADES = int(
    os.getenv(
        "MIN_BACKTEST_TRADES_FOR_HARD_REJECT",
        "8",
    )
)

MIN_TP1_PCT_NORMAL = float(
    os.getenv("MIN_TP1_PCT_NORMAL", "3.25")
)

MIN_TP1_PCT_GOLDEN = float(
    os.getenv("MIN_TP1_PCT_GOLDEN", "6.0")
)

MIN_TP1_PCT_PLATINUM = float(
    os.getenv("MIN_TP1_PCT_PLATINUM", "8.0")
)

MIN_TP2_PCT_PLATINUM = float(
    os.getenv("MIN_TP2_PCT_PLATINUM", "10.0")
)

MAX_HOLD_DAYS = int(
    os.getenv("MAX_HOLD_DAYS", "7")
)


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
                value.replace("%", "")
                .replace(",", "")
                .strip()
            )

        number = float(value)

        if not math.isfinite(number):
            return default

        return number

    except (TypeError, ValueError):
        return default


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
        print(
            f"⚠️ تعذر قراءة {path.name}: {exc}"
        )

    return default


def write_json(
    path: Path,
    data: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def get_signals(
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


def get_daily_stocks(
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

    stocks = payload.get("stocks", [])

    if not isinstance(stocks, list):
        return []

    return [
        item
        for item in stocks
        if isinstance(item, dict)
    ]


# =========================================================
# تحليل حالة السوق
# =========================================================

def detect_market_regime() -> Dict[str, Any]:
    """
    يصنف السوق إلى:

    STRONG:
        متوسط تغير السوق >= 0.80%
        ونسبة الأسهم الصاعدة >= 65%.

    WEAK:
        متوسط تغير السوق <= -0.50%
        أو نسبة الأسهم الصاعدة <= 35%.

    NORMAL:
        ما بين الحالتين.

    عند نقص البيانات يعود النظام إلى NORMAL حفاظًا على الأمان.
    """

    payload = load_json(
        DAILY_FILE,
        {},
    )

    stocks = get_daily_stocks(payload)

    changes: List[float] = []
    advancing = 0
    declining = 0
    unchanged = 0

    for stock in stocks:
        raw_change = (
            stock.get("change_percent")
            if "change_percent" in stock
            else stock.get("change_pct")
        )

        if raw_change is None or raw_change == "":
            continue

        change = fnum(
            raw_change,
            default=float("nan"),
        )

        if not math.isfinite(change):
            continue

        # حماية من بيانات غير منطقية أو تالفة.
        if change < -20 or change > 20:
            continue

        changes.append(change)

        if change > 0.05:
            advancing += 1

        elif change < -0.05:
            declining += 1

        else:
            unchanged += 1

    sample_size = len(changes)

    if sample_size < MIN_MARKET_SAMPLE:
        result = {
            "regime": "NORMAL",
            "regime_ar": "طبيعي",
            "grade": "بيانات السوق غير كافية",
            "dynamic_min_rased_score": (
                NORMAL_MARKET_MIN_RASED_SCORE
            ),
            "sample_size": sample_size,
            "minimum_sample_required": MIN_MARKET_SAMPLE,
            "average_change_pct": 0.0,
            "median_change_pct": 0.0,
            "advance_ratio": 0.0,
            "decline_ratio": 0.0,
            "unchanged_ratio": 0.0,
            "dispersion": 0.0,
            "reason": (
                "عينة تغيرات السوق غير كافية؛ "
                "تم استخدام الحد الطبيعي احترازيًا"
            ),
            "daily_generated_at": (
                payload.get("generated_at")
                if isinstance(payload, dict)
                else None
            ),
            "generated_at": now_iso(),
        }

        write_json(
            MARKET_REGIME_FILE,
            result,
        )

        return result

    average_change = round(
        sum(changes) / sample_size,
        3,
    )

    median_change = round(
        statistics.median(changes),
        3,
    )

    dispersion = round(
        statistics.pstdev(changes)
        if sample_size > 1
        else 0.0,
        3,
    )

    advance_ratio = round(
        advancing / sample_size,
        4,
    )

    decline_ratio = round(
        declining / sample_size,
        4,
    )

    unchanged_ratio = round(
        unchanged / sample_size,
        4,
    )

    strong_market = (
        average_change
        >= STRONG_MARKET_MIN_AVG_CHANGE
        and advance_ratio
        >= STRONG_MARKET_MIN_ADVANCE_RATIO
    )

    weak_market = (
        average_change
        <= WEAK_MARKET_MAX_AVG_CHANGE
        or advance_ratio
        <= WEAK_MARKET_MAX_ADVANCE_RATIO
        or (
            dispersion >= HIGH_DISPERSION_THRESHOLD
            and average_change < 0
            and decline_ratio > advance_ratio
        )
    )

    if strong_market:
        regime = "STRONG"
        regime_ar = "قوي"
        grade = "شهية مخاطرة مرتفعة"
        dynamic_score = (
            STRONG_MARKET_MIN_RASED_SCORE
        )
        reason = (
            f"متوسط تغير السوق {average_change}% "
            f"ونسبة الأسهم الصاعدة "
            f"{advance_ratio * 100:.1f}%"
        )

    elif weak_market:
        regime = "WEAK"
        regime_ar = "ضعيف"
        grade = "حماية رأس المال"
        dynamic_score = (
            WEAK_MARKET_MIN_RASED_SCORE
        )
        reason = (
            f"متوسط تغير السوق {average_change}% "
            f"ونسبة الأسهم الصاعدة "
            f"{advance_ratio * 100:.1f}%"
        )

    else:
        regime = "NORMAL"
        regime_ar = "طبيعي"
        grade = "انتقائي"
        dynamic_score = (
            NORMAL_MARKET_MIN_RASED_SCORE
        )
        reason = (
            f"متوسط تغير السوق {average_change}% "
            f"ونسبة الأسهم الصاعدة "
            f"{advance_ratio * 100:.1f}%"
        )

    result = {
        "regime": regime,
        "regime_ar": regime_ar,
        "grade": grade,
        "dynamic_min_rased_score": (
            dynamic_score
        ),
        "sample_size": sample_size,
        "average_change_pct": average_change,
        "median_change_pct": median_change,
        "advance_ratio": advance_ratio,
        "decline_ratio": decline_ratio,
        "unchanged_ratio": unchanged_ratio,
        "advancing_stocks": advancing,
        "declining_stocks": declining,
        "unchanged_stocks": unchanged,
        "dispersion": dispersion,
        "reason": reason,
        "rules": {
            "strong_min_average_change": (
                STRONG_MARKET_MIN_AVG_CHANGE
            ),
            "strong_min_advance_ratio": (
                STRONG_MARKET_MIN_ADVANCE_RATIO
            ),
            "weak_max_average_change": (
                WEAK_MARKET_MAX_AVG_CHANGE
            ),
            "weak_max_advance_ratio": (
                WEAK_MARKET_MAX_ADVANCE_RATIO
            ),
            "high_dispersion_threshold": (
                HIGH_DISPERSION_THRESHOLD
            ),
        },
        "daily_generated_at": (
            payload.get("generated_at")
            if isinstance(payload, dict)
            else None
        ),
        "generated_at": now_iso(),
    }

    write_json(
        MARKET_REGIME_FILE,
        result,
    )

    return result


# =========================================================
# مراجعة OpenAI
# =========================================================

def ai_was_reviewed(
    signal: Dict[str, Any],
) -> bool:
    return bool(
        signal.get("ai_reviewed")
        or signal.get("ai_available")
        or signal.get("ai_review")
    )


def ai_decision(
    signal: Dict[str, Any],
) -> str:
    direct = (
        signal.get("ai_decision")
        or signal.get("ai_verdict")
        or ""
    )

    if direct:
        return str(
            direct
        ).strip().upper()

    review = signal.get("ai_review")

    if isinstance(review, dict):
        return str(
            review.get("decision", "")
        ).strip().upper()

    return ""


def ai_rejected(
    signal: Dict[str, Any],
) -> bool:
    if not ai_was_reviewed(signal):
        return False

    return ai_decision(signal) in {
        "REJECT",
        "REJECTED",
        "BLOCK",
        "BLOCKED",
        "NO",
        "FAIL",
        "FAILED",
    }


def ai_approved(
    signal: Dict[str, Any],
) -> bool:
    if not ai_was_reviewed(signal):
        return False

    return ai_decision(signal) in {
        "APPROVE",
        "APPROVED",
        "PASS",
        "PASSED",
        "YES",
    }


def ai_reason(
    signal: Dict[str, Any],
) -> str:
    direct = (
        signal.get("ai_reason")
        or signal.get("ai_review_reason")
        or signal.get("ai_notes")
        or ""
    )

    if direct:
        return str(
            direct
        ).strip()

    review = signal.get("ai_review")

    if isinstance(review, dict):
        return str(
            review.get("rejection_reason")
            or review.get("arabic_summary")
            or ""
        ).strip()

    return ""


# =========================================================
# استخراج بيانات الإشارة
# =========================================================

def extract_signal_metrics(
    signal: Dict[str, Any],
) -> Dict[str, Any]:
    symbol = str(
        signal.get("stock_symbol")
        or signal.get("symbol")
        or "UNKNOWN"
    ).strip()

    tier = str(
        signal.get("tier")
        or "Standard"
    ).strip().title()

    rased_score = fnum(
        signal.get("rased_score")
        or signal.get("confidence")
    )

    score = fnum(
        signal.get("score")
        or signal.get("technical_score")
    )

    rr = fnum(
        signal.get("rr")
        or signal.get("rr_ratio")
    )

    volume_ratio = fnum(
        signal.get("volume_ratio")
    )

    rsi = fnum(
        signal.get("rsi")
    )

    backtest_win_rate = fnum(
        signal.get("backtest_win_rate")
    )

    backtest_trades = int(
        fnum(signal.get("backtest_trades"))
    )

    tp1_pct = fnum(
        signal.get("target1_percent")
        or signal.get("tp1_pct")
    )

    tp2_pct = fnum(
        signal.get("target2_percent")
        or signal.get("tp2_pct")
    )

    expected_days = int(
        fnum(
            signal.get("expected_days_to_target2")
            or signal.get(
                "ai_expected_holding_days"
            )
            or signal.get("max_holding_days"),
            99,
        )
    )

    seven_day_filter = signal.get(
        "seven_day_filter_passed",
        True,
    )

    trend = str(
        signal.get("trend")
        or ""
    ).strip()

    return {
        "symbol": symbol,
        "tier": tier,
        "rased_score": rased_score,
        "score": score,
        "rr": rr,
        "volume_ratio": volume_ratio,
        "rsi": rsi,
        "backtest_win_rate": (
            backtest_win_rate
        ),
        "backtest_trades": backtest_trades,
        "tp1_pct": tp1_pct,
        "tp2_pct": tp2_pct,
        "expected_days": expected_days,
        "seven_day_filter": (
            seven_day_filter
        ),
        "trend": trend,
    }


# =========================================================
# التحقق النهائي
# =========================================================

def validate_signal(
    signal: Dict[str, Any],
    market_regime: Dict[str, Any],
) -> Tuple[List[str], Dict[str, Any]]:
    reasons: List[str] = []

    metrics = extract_signal_metrics(
        signal
    )

    symbol = metrics["symbol"]
    tier = metrics["tier"]
    rased_score = metrics["rased_score"]
    score = metrics["score"]
    rr = metrics["rr"]
    volume_ratio = metrics["volume_ratio"]
    rsi = metrics["rsi"]

    backtest_win_rate = metrics[
        "backtest_win_rate"
    ]

    backtest_trades = metrics[
        "backtest_trades"
    ]

    tp1_pct = metrics["tp1_pct"]
    tp2_pct = metrics["tp2_pct"]

    expected_days = metrics[
        "expected_days"
    ]

    seven_day_filter = metrics[
        "seven_day_filter"
    ]

    trend = metrics["trend"]

    regime = str(
        market_regime.get(
            "regime",
            "NORMAL",
        )
    ).upper()

    dynamic_min_rased_score = fnum(
        market_regime.get(
            "dynamic_min_rased_score"
        ),
        NORMAL_MARKET_MIN_RASED_SCORE,
    )

    # -----------------------------------------------------
    # رفض OpenAI الصريح
    # -----------------------------------------------------

    if ai_rejected(signal):
        reason = ai_reason(signal)

        if reason:
            reasons.append(
                f"مراجعة OpenAI رفضت الإشارة: "
                f"{reason}"
            )

        else:
            reasons.append(
                "مراجعة OpenAI رفضت الإشارة"
            )

    # -----------------------------------------------------
    # سلامة القيم
    # -----------------------------------------------------

    if rased_score <= 0:
        reasons.append(
            "RASED SCORE غير موجود أو غير صالح"
        )

    if score <= 0:
        reasons.append(
            "Score غير موجود أو غير صالح"
        )

    if rr <= 0:
        reasons.append(
            "R:R غير موجود أو غير صالح"
        )

    if tp1_pct <= 0:
        reasons.append(
            "نسبة الهدف الأول غير صالحة"
        )

    # -----------------------------------------------------
    # القبول الحدودي
    #
    # يعمل فقط في السوق الطبيعي.
    # لا نحتاجه في السوق القوي لأن الحد أصبح 77.
    # يُلغى بالكامل في السوق الضعيف.
    # -----------------------------------------------------

    borderline_pass = (
        regime == "NORMAL"
        and BORDERLINE_MIN_RASED_SCORE
        <= rased_score
        < dynamic_min_rased_score
        and score >= 90
        and ai_approved(signal)
        and rr >= MIN_RR
        and volume_ratio >= 1.0
        and MIN_RSI <= rsi <= MAX_RSI
        and tp1_pct >= MIN_TP1_PCT_NORMAL
        and expected_days <= MAX_HOLD_DAYS
        and seven_day_filter is not False
        and trend not in {
            "هابط",
            "هابط بوضوح",
            "سلبي",
        }
    )

    if (
        rased_score
        < dynamic_min_rased_score
        and not borderline_pass
    ):
        reasons.append(
            f"RASED SCORE {rased_score} أقل من "
            f"الحد الديناميكي "
            f"{dynamic_min_rased_score} "
            f"لسوق {market_regime.get('regime_ar', 'طبيعي')}"
        )

    elif borderline_pass:
        print(
            f"🟡 {symbol}: قبول حدودي — "
            f"RASED SCORE {rased_score}، "
            f"الحد الأساسي "
            f"{dynamic_min_rased_score}"
        )

    # -----------------------------------------------------
    # الحد الفني
    # -----------------------------------------------------

    if score < MIN_SCORE:
        reasons.append(
            f"Score {score} أقل من {MIN_SCORE}"
        )

    if rr < MIN_RR:
        reasons.append(
            f"R:R {rr} أقل من {MIN_RR}"
        )

    if volume_ratio < MIN_VOLUME_RATIO:
        reasons.append(
            f"Volume {volume_ratio}x أقل من "
            f"{MIN_VOLUME_RATIO}x"
        )

    if rsi < MIN_RSI:
        reasons.append(
            f"RSI {rsi} أقل من {MIN_RSI}"
        )

    if rsi > MAX_RSI:
        reasons.append(
            f"RSI {rsi} أعلى من {MAX_RSI}"
        )

    # -----------------------------------------------------
    # الهدف والمدة
    # -----------------------------------------------------

    if tp1_pct < MIN_TP1_PCT_NORMAL:
        reasons.append(
            f"TP1 {tp1_pct}% أقل من "
            f"{MIN_TP1_PCT_NORMAL}%"
        )

    if expected_days > MAX_HOLD_DAYS:
        reasons.append(
            f"المدة المتوقعة "
            f"{expected_days} أيام أكبر من "
            f"{MAX_HOLD_DAYS}"
        )

    if seven_day_filter is False:
        reasons.append(
            "الإشارة لم تجتز فلتر السبعة أيام"
        )

    # -----------------------------------------------------
    # حدود الفئات
    # -----------------------------------------------------

    if (
        tier == "Gold"
        and tp1_pct < MIN_TP1_PCT_GOLDEN
    ):
        reasons.append(
            f"Gold يحتاج TP1 لا يقل عن "
            f"{MIN_TP1_PCT_GOLDEN}%"
        )

    if (
        tier == "Platinum"
        and tp1_pct
        < MIN_TP1_PCT_PLATINUM
        and tp2_pct
        < MIN_TP2_PCT_PLATINUM
    ):
        reasons.append(
            "Platinum يحتاج "
            f"TP1 >= {MIN_TP1_PCT_PLATINUM}% "
            "أو "
            f"TP2 >= {MIN_TP2_PCT_PLATINUM}%"
        )

    # -----------------------------------------------------
    # الباك تست
    # -----------------------------------------------------

    if (
        backtest_trades
        >= MIN_BACKTEST_TRADES
        and backtest_win_rate
        < MIN_BACKTEST_WIN_RATE
    ):
        reasons.append(
            f"Backtest {backtest_win_rate}% أقل من "
            f"{MIN_BACKTEST_WIN_RATE}% "
            f"على {backtest_trades} حالات مشابهة"
        )

    # -----------------------------------------------------
    # بيانات قرار البوابة
    # -----------------------------------------------------

    decision_info = {
        "market_regime": regime,
        "market_regime_ar": (
            market_regime.get("regime_ar")
        ),
        "dynamic_min_rased_score": (
            dynamic_min_rased_score
        ),
        "borderline_approval": borderline_pass,
        "rased_score": rased_score,
    }

    if reasons:
        print(
            f"❌ {symbol}: "
            + " | ".join(reasons)
        )

    else:
        approval_source = (
            "OpenAI + Dynamic Python Gate"
            if ai_approved(signal)
            else "Dynamic Python Gate"
        )

        print(
            f"✅ {symbol}: approved by "
            f"{approval_source} | "
            f"Market={regime} | "
            f"Dynamic minimum="
            f"{dynamic_min_rased_score}"
        )

    return reasons, decision_info


# =========================================================
# الحدود المسجلة
# =========================================================

def applied_limits(
    market_regime: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "dynamic_rased_score": {
            "current_market_regime": (
                market_regime.get("regime")
            ),
            "current_market_regime_ar": (
                market_regime.get(
                    "regime_ar"
                )
            ),
            "current_min_rased_score": (
                market_regime.get(
                    "dynamic_min_rased_score"
                )
            ),
            "strong_market_min": (
                STRONG_MARKET_MIN_RASED_SCORE
            ),
            "normal_market_min": (
                NORMAL_MARKET_MIN_RASED_SCORE
            ),
            "weak_market_min": (
                WEAK_MARKET_MIN_RASED_SCORE
            ),
            "borderline_min": (
                BORDERLINE_MIN_RASED_SCORE
            ),
        },
        "market_regime_rules": {
            "minimum_sample": MIN_MARKET_SAMPLE,
            "strong_min_average_change": (
                STRONG_MARKET_MIN_AVG_CHANGE
            ),
            "strong_min_advance_ratio": (
                STRONG_MARKET_MIN_ADVANCE_RATIO
            ),
            "weak_max_average_change": (
                WEAK_MARKET_MAX_AVG_CHANGE
            ),
            "weak_max_advance_ratio": (
                WEAK_MARKET_MAX_ADVANCE_RATIO
            ),
            "high_dispersion_threshold": (
                HIGH_DISPERSION_THRESHOLD
            ),
        },
        "signal_quality": {
            "MIN_SCORE": MIN_SCORE,
            "MIN_RR": MIN_RR,
            "MIN_VOLUME_RATIO": (
                MIN_VOLUME_RATIO
            ),
            "MIN_RSI": MIN_RSI,
            "MAX_RSI": MAX_RSI,
            "MIN_BACKTEST_WIN_RATE": (
                MIN_BACKTEST_WIN_RATE
            ),
            "MIN_BACKTEST_TRADES": (
                MIN_BACKTEST_TRADES
            ),
            "MIN_TP1_PCT_NORMAL": (
                MIN_TP1_PCT_NORMAL
            ),
            "MIN_TP1_PCT_GOLDEN": (
                MIN_TP1_PCT_GOLDEN
            ),
            "MIN_TP1_PCT_PLATINUM": (
                MIN_TP1_PCT_PLATINUM
            ),
            "MIN_TP2_PCT_PLATINUM": (
                MIN_TP2_PCT_PLATINUM
            ),
            "MAX_HOLD_DAYS": MAX_HOLD_DAYS,
        },
    }


# =========================================================
# التشغيل الرئيسي
# =========================================================

def main() -> int:
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    market_regime = detect_market_regime()

    print("=" * 64)
    print("راصد — Dynamic RASED Score")
    print("=" * 64)

    print(
        f"📊 حالة السوق: "
        f"{market_regime.get('regime_ar')} "
        f"({market_regime.get('regime')})"
    )

    print(
        f"📈 متوسط التغير: "
        f"{market_regime.get('average_change_pct')}%"
    )

    print(
        f"🟢 نسبة الأسهم الصاعدة: "
        f"{fnum(market_regime.get('advance_ratio')) * 100:.1f}%"
    )

    print(
        f"🎯 الحد الديناميكي الحالي: "
        f"{market_regime.get('dynamic_min_rased_score')}"
    )

    payload = load_json(
        SIGNALS_FILE,
        {},
    )

    signals = get_signals(
        payload
    )

    source_generated_at = (
        payload.get("generated_at")
        if isinstance(payload, dict)
        else None
    )

    if not signals:
        output = {
            "signals": [],
            "validated_signals": [],
            "rejected": [],
            "total": 0,
            "total_generated": 0,
            "total_approved": 0,
            "total_rejected": 0,
            "status": "NO_SIGNALS",
            "source": "should_post.py",
            "source_generated_at": (
                source_generated_at
            ),
            "generated_at": now_iso(),
            "market_regime": market_regime,
            "message": (
                "لا توجد إشارات مولدة للتحقق منها"
            ),
            "applied_limits": applied_limits(
                market_regime
            ),
        }

        write_json(
            VALIDATED_FILE,
            output,
        )

        print(
            "ℹ️ لا توجد إشارات مولدة للتحقق منها"
        )

        return 0

    approved: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for signal in signals:
        reasons, decision_info = (
            validate_signal(
                signal,
                market_regime,
            )
        )

        item = dict(signal)

        item["market_regime"] = (
            decision_info["market_regime"]
        )

        item["market_regime_ar"] = (
            decision_info[
                "market_regime_ar"
            ]
        )

        item["dynamic_min_rased_score"] = (
            decision_info[
                "dynamic_min_rased_score"
            ]
        )

        item["borderline_approval"] = (
            decision_info[
                "borderline_approval"
            ]
        )

        item["post_checked_at"] = now_iso()

        if reasons:
            item["post_approved"] = False
            item["post_rejected_reasons"] = (
                reasons
            )

            rejected.append(item)

        else:
            item["post_approved"] = True
            item["post_rejected_reasons"] = []

            item["post_approval_source"] = (
                "openai_and_dynamic_python"
                if ai_approved(signal)
                else "dynamic_python_gate"
            )

            approved.append(item)

    approved.sort(
        key=lambda item: (
            fnum(item.get("rased_score")),
            fnum(
                item.get("score")
                or item.get("technical_score")
            ),
            fnum(
                item.get("rr")
                or item.get("rr_ratio")
            ),
        ),
        reverse=True,
    )

    rejected.sort(
        key=lambda item: (
            fnum(item.get("rased_score")),
            fnum(
                item.get("score")
                or item.get("technical_score")
            ),
        ),
        reverse=True,
    )

    output = {
        "signals": approved,
        "validated_signals": approved,
        "rejected": rejected,
        "total": len(approved),
        "total_generated": len(signals),
        "total_approved": len(approved),
        "total_rejected": len(rejected),
        "status": (
            "HAS_VALID_SIGNALS"
            if approved
            else "NO_VALID_SIGNALS"
        ),
        "source": "should_post.py",
        "engine": (
            "rased_dynamic_score_gate_v1"
        ),
        "source_generated_at": (
            source_generated_at
        ),
        "generated_at": now_iso(),
        "market_regime": market_regime,
        "applied_limits": applied_limits(
            market_regime
        ),
    }

    write_json(
        VALIDATED_FILE,
        output,
    )

    print(
        f"📊 Generated: {len(signals)} | "
        f"Approved: {len(approved)} | "
        f"Rejected: {len(rejected)}"
    )

    if not approved:
        print(
            "ℹ️ لا توجد إشارات صالحة بعد "
            "بوابة النشر الديناميكية"
        )

        return 1

    print(
        f"✅ تم اعتماد {len(approved)} "
        "إشارة للنشر"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())