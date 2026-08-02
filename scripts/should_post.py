#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — بوابة التحقق النهائية قبل النشر.

الهدف:
1. توحيد شروط النشر مع شروط generate_signal.py.
2. منع رفض إشارة اجتازت المحرك بسبب حدود مختلفة.
3. إبقاء رفض OpenAI الصريح بوابة نهائية.
4. تسجيل أسباب رفض كل إشارة في validated_signals.json.
5. عدم اعتبار عدم وجود إشارة خطأ تقنيًا.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


# =========================================================
# المسارات
# =========================================================

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

SIGNALS_FILE = DATA_DIR / "signals.json"
VALIDATED_FILE = DATA_DIR / "validated_signals.json"


# =========================================================
# حدود موحدة مع generate_signal.py
# =========================================================

MIN_RASED_SCORE = float(
    os.getenv("MIN_SIGNAL_SCORE", "80")
)

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

        return float(value)

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


def get_signals(payload: Any) -> List[Dict[str, Any]]:
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


# =========================================================
# مراجعة OpenAI
# =========================================================

def ai_was_reviewed(
    signal: Dict[str, Any],
) -> bool:
    return bool(
        signal.get("ai_reviewed")
        or signal.get("ai_available")
    )


def ai_decision(
    signal: Dict[str, Any],
) -> str:
    return str(
        signal.get("ai_decision")
        or signal.get("ai_verdict")
        or ""
    ).strip().upper()


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
    return str(
        signal.get("ai_reason")
        or signal.get("ai_review_reason")
        or signal.get("ai_notes")
        or ""
    ).strip()


# =========================================================
# التحقق النهائي
# =========================================================

def validate_signal(
    signal: Dict[str, Any],
) -> List[str]:
    reasons: List[str] = []

    symbol = str(
        signal.get("stock_symbol")
        or signal.get("symbol")
        or "UNKNOWN"
    )

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
            ),
            99,
        )
    )

    seven_day_filter = signal.get(
        "seven_day_filter_passed",
        True,
    )

    # -----------------------------------------------------
    # رفض OpenAI الصريح
    # -----------------------------------------------------

    if ai_rejected(signal):
        reason = ai_reason(signal)

        if reason:
            reasons.append(
                f"مراجعة OpenAI رفضت الإشارة: {reason}"
            )
        else:
            reasons.append(
                "مراجعة OpenAI رفضت الإشارة"
            )

    # -----------------------------------------------------
    # سلامة القيم الأساسية
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
    # الحدود الموحدة مع محرك التوليد
    # -----------------------------------------------------

    if rased_score < MIN_RASED_SCORE:
        reasons.append(
            f"RASED SCORE {rased_score} "
            f"أقل من {MIN_RASED_SCORE}"
        )

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
            f"Volume {volume_ratio}x "
            f"أقل من {MIN_VOLUME_RATIO}x"
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
            f"المدة المتوقعة {expected_days} أيام "
            f"أكبر من {MAX_HOLD_DAYS}"
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
        and tp1_pct < MIN_TP1_PCT_PLATINUM
        and tp2_pct < MIN_TP2_PCT_PLATINUM
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
        backtest_trades >= MIN_BACKTEST_TRADES
        and backtest_win_rate
        < MIN_BACKTEST_WIN_RATE
    ):
        reasons.append(
            f"Backtest {backtest_win_rate}% أقل من "
            f"{MIN_BACKTEST_WIN_RATE}% "
            f"على {backtest_trades} حالات مشابهة"
        )

    # -----------------------------------------------------
    # السجل
    # -----------------------------------------------------

    if reasons:
        print(
            f"❌ {symbol}: "
            + " | ".join(reasons)
        )

    else:
        approval_source = (
            "OpenAI + Python Gate"
            if ai_approved(signal)
            else "Python Gate"
        )

        print(
            f"✅ {symbol}: approved by "
            f"{approval_source}"
        )

    return reasons


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

    signals = get_signals(payload)

    source_generated_at = (
        payload.get("generated_at")
        if isinstance(payload, dict)
        else None
    )

    if not signals:
        output = {
            "signals": [],
            "rejected": [],
            "total": 0,
            "total_generated": 0,
            "total_approved": 0,
            "total_rejected": 0,
            "status": "NO_SIGNALS",
            "source": "should_post.py",
            "source_generated_at": source_generated_at,
            "generated_at": now_iso(),
            "message": (
                "لا توجد إشارات مولدة للتحقق منها"
            ),
            "applied_limits": {
                "MIN_RASED_SCORE": MIN_RASED_SCORE,
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
                "MAX_HOLD_DAYS": MAX_HOLD_DAYS,
            },
        }

        write_json(
            VALIDATED_FILE,
            output,
        )

        print(
            "ℹ️ لا توجد إشارات مولدة للتحقق منها"
        )

        # عدم وجود إشارة ليس خطأ تقنيًا.
        return 0

    approved: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for signal in signals:
        reasons = validate_signal(signal)

        item = dict(signal)

        if reasons:
            item["post_approved"] = False
            item["post_rejected_reasons"] = reasons
            item["post_checked_at"] = now_iso()

            rejected.append(item)

        else:
            item["post_approved"] = True
            item["post_rejected_reasons"] = []
            item["post_checked_at"] = now_iso()
            item["post_approval_source"] = (
                "openai_and_python"
                if ai_approved(signal)
                else "python_gate"
            )

            approved.append(item)

    approved.sort(
        key=lambda item: (
            fnum(item.get("rased_score")),
            fnum(item.get("score")),
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
            fnum(item.get("score")),
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
        "source_generated_at": source_generated_at,
        "generated_at": now_iso(),
        "applied_limits": {
            "MIN_RASED_SCORE": MIN_RASED_SCORE,
            "MIN_SCORE": MIN_SCORE,
            "MIN_RR": MIN_RR,
            "MIN_VOLUME_RATIO": MIN_VOLUME_RATIO,
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
            "بوابة النشر النهائية"
        )

        # يبقى الكود 1 متوافقًا مع continue-on-error
        # الموجود في Workflow، مع حفظ أسباب الرفض.
        return 1

    print(
        f"✅ تم اعتماد {len(approved)} "
        "إشارة للنشر"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())