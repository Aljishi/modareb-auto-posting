#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RASED Signal Quality Gate v10
=============================

طبقة جودة مستقلة تعمل بعد generate_signal.py وقبل مراجعة OpenAI.

الهدف:
- منع الإشارات المتناقضة قبل وصولها للمستخدم.
- تشديد R:R والباك تست والمطاردة.
- تصحيح مستوى المخاطرة آليًا.
- ترتيب أفضل الإشارات والاحتفاظ بالأعلى جودة فقط.
- عدم جعل المحرك صارمًا لدرجة توقف الإشارات بالكامل.

هذه الطبقة لا تولد إشارة جديدة.
هي فقط تراجع signals.json الناتج من المحرك.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

SIGNALS_FILE = DATA_DIR / "signals.json"
REPORT_FILE = DATA_DIR / "signal_quality_gate.json"


# ============================================================
# Quality thresholds
# ============================================================

MIN_RASED_SCORE = float(
    os.getenv("QUALITY_MIN_RASED_SCORE", "82")
)

MIN_TECHNICAL_SCORE = float(
    os.getenv("QUALITY_MIN_TECHNICAL_SCORE", "80")
)

MIN_RR = float(
    os.getenv("QUALITY_MIN_RR", "2.00")
)

MIN_VOLUME_RATIO = float(
    os.getenv("QUALITY_MIN_VOLUME_RATIO", "1.15")
)

MAX_RSI = float(
    os.getenv("QUALITY_MAX_RSI", "70")
)

MAX_ATR_PCT = float(
    os.getenv("QUALITY_MAX_ATR_PCT", "8.0")
)

MIN_TP1_PCT = float(
    os.getenv("QUALITY_MIN_TP1_PCT", "4.0")
)

MIN_TP2_PCT = float(
    os.getenv("QUALITY_MIN_TP2_PCT", "6.0")
)

MAX_ENTRY_GAP_PCT = float(
    os.getenv("QUALITY_MAX_ENTRY_GAP_PCT", "3.0")
)

MAX_SIGNALS = int(
    os.getenv("QUALITY_MAX_SIGNALS", "3")
)


# ============================================================
# Backtest rules
# ============================================================

BACKTEST_ZERO_REJECT_MIN_TRADES = int(
    os.getenv(
        "QUALITY_BACKTEST_ZERO_REJECT_MIN_TRADES",
        "3",
    )
)

BACKTEST_HARD_MIN_TRADES = int(
    os.getenv(
        "QUALITY_BACKTEST_HARD_MIN_TRADES",
        "4",
    )
)

BACKTEST_MIN_WIN_RATE = float(
    os.getenv(
        "QUALITY_BACKTEST_MIN_WIN_RATE",
        "35",
    )
)


# ============================================================
# Chase / overextension rules
# ============================================================

CHASE_RSI = float(
    os.getenv("QUALITY_CHASE_RSI", "68")
)

CHASE_DAILY_CHANGE_PCT = float(
    os.getenv(
        "QUALITY_CHASE_DAILY_CHANGE_PCT",
        "5.5",
    )
)

CHASE_MIN_RR = float(
    os.getenv("QUALITY_CHASE_MIN_RR", "2.40")
)

CHASE_MIN_VOLUME_RATIO = float(
    os.getenv(
        "QUALITY_CHASE_MIN_VOLUME_RATIO",
        "2.0",
    )
)


# ============================================================
# Helpers
# ============================================================

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
                value
                .replace("%", "")
                .replace(",", "")
                .strip()
            )

        return float(value)

    except Exception:
        return default


def fint(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(fnum(value, default))
    except Exception:
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
    payload: Any,
) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def extract_signals(
    payload: Any,
) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [
            item
            for item in payload
            if isinstance(item, dict)
        ]

    if isinstance(payload, dict):
        signals = payload.get("signals", [])

        if isinstance(signals, list):
            return [
                item
                for item in signals
                if isinstance(item, dict)
            ]

    return []


def symbol_of(
    signal: Dict[str, Any],
) -> str:
    return str(
        signal.get("stock_symbol")
        or signal.get("symbol")
        or "UNKNOWN"
    ).strip()


# ============================================================
# Risk classification
# ============================================================

def corrected_risk(
    signal: Dict[str, Any],
) -> Tuple[str, str]:
    rr = fnum(
        signal.get("rr")
        or signal.get("rr_ratio")
    )

    rsi = fnum(
        signal.get("rsi")
    )

    atr_pct = fnum(
        signal.get("atr_pct")
    )

    bt_trades = fint(
        signal.get("backtest_trades")
    )

    bt_win = fnum(
        signal.get("backtest_win_rate")
    )

    # -----------------------------
    # منخفض
    # -----------------------------

    backtest_ok_for_low = (
        bt_trades < BACKTEST_HARD_MIN_TRADES
        or bt_win >= 50
    )

    if (
        rr >= 2.50
        and 0.50 <= atr_pct <= 6.50
        and rsi <= 68
        and backtest_ok_for_low
    ):
        return "منخفض", "🟢"

    # -----------------------------
    # متوسط
    # -----------------------------

    backtest_bad = (
        bt_trades >= BACKTEST_HARD_MIN_TRADES
        and bt_win < BACKTEST_MIN_WIN_RATE
    )

    if (
        rr >= MIN_RR
        and 0.50 <= atr_pct <= MAX_ATR_PCT
        and rsi <= MAX_RSI
        and not backtest_bad
    ):
        return "متوسط", "🟡"

    return "مرتفع", "🔴"


# ============================================================
# Historical quality
# ============================================================

def validate_backtest(
    signal: Dict[str, Any],
) -> List[str]:
    reasons: List[str] = []

    trades = fint(
        signal.get("backtest_trades")
    )

    win_rate = fnum(
        signal.get("backtest_win_rate")
    )

    if (
        trades >= BACKTEST_ZERO_REJECT_MIN_TRADES
        and win_rate <= 0
    ):
        reasons.append(
            f"الباك تست 0% على {trades} حالات مشابهة"
        )

        return reasons

    if (
        trades >= BACKTEST_HARD_MIN_TRADES
        and win_rate < BACKTEST_MIN_WIN_RATE
    ):
        reasons.append(
            f"الباك تست {win_rate:.1f}% أقل من "
            f"{BACKTEST_MIN_WIN_RATE:.0f}% "
            f"على {trades} حالات"
        )

    return reasons


# ============================================================
# Chase filter
# ============================================================

def validate_chase(
    signal: Dict[str, Any],
) -> List[str]:
    reasons: List[str] = []

    rsi = fnum(
        signal.get("rsi")
    )

    change_pct = fnum(
        signal.get("change_percent")
        or signal.get("change_pct")
    )

    rr = fnum(
        signal.get("rr")
        or signal.get("rr_ratio")
    )

    volume_ratio = fnum(
        signal.get("volume_ratio")
    )

    breakout = bool(
        signal.get("breakout")
    )

    is_chase = (
        rsi >= CHASE_RSI
        or change_pct > CHASE_DAILY_CHANGE_PCT
    )

    if not is_chase:
        return reasons

    # الإشارة المرتفعة في الزخم تحتاج شروطاً أعلى
    if not breakout:
        reasons.append(
            "زخم مرتفع دون اختراق مؤكد — احتمال مطاردة"
        )

    if rr < CHASE_MIN_RR:
        reasons.append(
            f"إشارة مطاردة تحتاج R:R >= "
            f"{CHASE_MIN_RR:.2f}"
        )

    if volume_ratio < CHASE_MIN_VOLUME_RATIO:
        reasons.append(
            f"إشارة مطاردة تحتاج Volume >= "
            f"{CHASE_MIN_VOLUME_RATIO:.2f}x"
        )

    return reasons


# ============================================================
# Main validation
# ============================================================

def validate_signal(
    signal: Dict[str, Any],
) -> List[str]:
    reasons: List[str] = []

    rased_score = fnum(
        signal.get("rased_score")
    )

    technical_score = fnum(
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

    atr_pct = fnum(
        signal.get("atr_pct")
    )

    tp1_pct = fnum(
        signal.get("target1_percent")
        or signal.get("tp1_pct")
    )

    tp2_pct = fnum(
        signal.get("target2_percent")
        or signal.get("tp2_pct")
    )

    entry_gap_pct = fnum(
        signal.get("entry_gap_pct")
    )

    expected_days = fint(
        signal.get("expected_days_to_target2"),
        99,
    )

    seven_day_passed = signal.get(
        "seven_day_filter_passed",
        True,
    )

    # --------------------------------------------------------
    # Core quality
    # --------------------------------------------------------

    if rased_score < MIN_RASED_SCORE:
        reasons.append(
            f"RASED SCORE {rased_score:.1f} "
            f"أقل من {MIN_RASED_SCORE:.1f}"
        )

    if technical_score < MIN_TECHNICAL_SCORE:
        reasons.append(
            f"Technical Score {technical_score:.1f} "
            f"أقل من {MIN_TECHNICAL_SCORE:.1f}"
        )

    if rr < MIN_RR:
        reasons.append(
            f"R:R {rr:.2f} أقل من "
            f"{MIN_RR:.2f}"
        )

    if volume_ratio < MIN_VOLUME_RATIO:
        reasons.append(
            f"Volume {volume_ratio:.2f}x أقل من "
            f"{MIN_VOLUME_RATIO:.2f}x"
        )

    if rsi > MAX_RSI:
        reasons.append(
            f"RSI {rsi:.1f} أعلى من "
            f"{MAX_RSI:.1f} — احتمال مطاردة"
        )

    if atr_pct > MAX_ATR_PCT:
        reasons.append(
            f"ATR {atr_pct:.2f}% أعلى من "
            f"{MAX_ATR_PCT:.2f}%"
        )

    if tp1_pct < MIN_TP1_PCT:
        reasons.append(
            f"TP1 {tp1_pct:.2f}% أقل من "
            f"{MIN_TP1_PCT:.2f}%"
        )

    if tp2_pct < MIN_TP2_PCT:
        reasons.append(
            f"TP2 {tp2_pct:.2f}% أقل من "
            f"{MIN_TP2_PCT:.2f}%"
        )

    if entry_gap_pct > MAX_ENTRY_GAP_PCT:
        reasons.append(
            f"فجوة الدخول {entry_gap_pct:.2f}% "
            f"أعلى من {MAX_ENTRY_GAP_PCT:.2f}%"
        )

    if expected_days > 7:
        reasons.append(
            f"الهدف الثاني يحتاج {expected_days} أيام"
        )

    if seven_day_passed is False:
        reasons.append(
            "فشل فلتر السبعة أيام"
        )

    # --------------------------------------------------------
    # Historical quality
    # --------------------------------------------------------

    reasons.extend(
        validate_backtest(signal)
    )

    # --------------------------------------------------------
    # Chase protection
    # --------------------------------------------------------

    reasons.extend(
        validate_chase(signal)
    )

    return reasons


# ============================================================
# Ranking
# ============================================================

def quality_score(
    signal: Dict[str, Any],
) -> float:
    rased = fnum(
        signal.get("rased_score")
    )

    rr = fnum(
        signal.get("rr")
        or signal.get("rr_ratio")
    )

    volume = fnum(
        signal.get("volume_ratio")
    )

    rsi = fnum(
        signal.get("rsi")
    )

    bt_trades = fint(
        signal.get("backtest_trades")
    )

    bt_win = fnum(
        signal.get("backtest_win_rate")
    )

    breakout = bool(
        signal.get("breakout")
    )

    score = rased

    # R:R bonus
    score += min(
        max(rr - 2.0, 0.0) * 8.0,
        8.0,
    )

    # Volume bonus
    score += min(
        max(volume - 1.0, 0.0) * 2.0,
        6.0,
    )

    # Confirmed breakout
    if breakout:
        score += 3.0

    # Backtest
    if bt_trades >= 4:
        if bt_win >= 60:
            score += 5.0
        elif bt_win >= 50:
            score += 3.0
        elif bt_win < 40:
            score -= 4.0

    # Healthy momentum bonus
    if 52 <= rsi <= 65:
        score += 3.0

    # Chase penalty
    if rsi >= 68:
        score -= 4.0

    return round(score, 2)


def enhance_signal(
    signal: Dict[str, Any],
) -> Dict[str, Any]:
    item = dict(signal)

    risk_text, risk_emoji = corrected_risk(
        item
    )

    item["risk_level"] = risk_text
    item["risk_level_ar"] = risk_text
    item["risk_emoji"] = risk_emoji

    item["quality_gate_passed"] = True
    item["quality_gate_version"] = (
        "rased_quality_gate_v10"
    )

    item["quality_score"] = quality_score(
        item
    )

    # تشخيص المطاردة
    rsi = fnum(item.get("rsi"))
    change_pct = fnum(
        item.get("change_percent")
        or item.get("change_pct")
    )

    item["chase_warning"] = bool(
        rsi >= CHASE_RSI
        or change_pct > CHASE_DAILY_CHANGE_PCT
    )

    return item


# ============================================================
# Main
# ============================================================

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
            "engine": "rased_quality_gate_v10",
            "generated_at": now_iso(),
            "input_count": 0,
            "approved_count": 0,
            "rejected_count": 0,
            "message": "لا توجد إشارات لفحص الجودة",
        }

        write_json(
            REPORT_FILE,
            report,
        )

        print(
            "ℹ️ Quality Gate: لا توجد إشارات للفحص"
        )

        return 0

    approved: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for signal in signals:
        symbol = symbol_of(signal)

        reasons = validate_signal(
            signal
        )

        if reasons:
            rejected.append(
                {
                    "symbol": symbol,
                    "rased_score": fnum(
                        signal.get("rased_score")
                    ),
                    "reasons": reasons,
                }
            )

            print(
                f"❌ {symbol}: "
                + " | ".join(reasons)
            )

            continue

        enhanced = enhance_signal(
            signal
        )

        approved.append(
            enhanced
        )

        print(
            f"✅ {symbol}: Quality PASS | "
            f"Q={enhanced['quality_score']:.1f} | "
            f"R:R={fnum(enhanced.get('rr')):.2f} | "
            f"Risk={enhanced.get('risk_level')}"
        )

    approved.sort(
        key=lambda item: (
            fnum(item.get("quality_score")),
            fnum(item.get("rased_score")),
            fnum(
                item.get("rr")
                or item.get("rr_ratio")
            ),
        ),
        reverse=True,
    )

    approved = approved[
        :MAX_SIGNALS
    ]

    if isinstance(payload, dict):
        output = dict(payload)
    else:
        output = {}

    output["signals"] = approved
    output["quality_gate_applied"] = True
    output["quality_gate_version"] = (
        "rased_quality_gate_v10"
    )
    output["quality_gate_at"] = now_iso()
    output["quality_gate_input_count"] = len(
        signals
    )
    output["quality_gate_approved_count"] = len(
        approved
    )
    output["quality_gate_rejected_count"] = len(
        rejected
    )
    output["quality_gate_rejected"] = rejected

    if approved:
        output["status"] = "HAS_SIGNALS"
    else:
        output["status"] = "NO_SIGNALS"
        output["message"] = (
            "لا توجد إشارات اجتازت بوابة الجودة V10"
        )

    write_json(
        SIGNALS_FILE,
        output,
    )

    report = {
        "status": (
            "PASS"
            if approved
            else "NO_VALID_SIGNAL"
        ),
        "engine": "rased_quality_gate_v10",
        "generated_at": now_iso(),
        "configuration": {
            "min_rased_score": MIN_RASED_SCORE,
            "min_technical_score": (
                MIN_TECHNICAL_SCORE
            ),
            "min_rr": MIN_RR,
            "min_volume_ratio": (
                MIN_VOLUME_RATIO
            ),
            "max_rsi": MAX_RSI,
            "max_atr_pct": MAX_ATR_PCT,
            "min_tp1_pct": MIN_TP1_PCT,
            "min_tp2_pct": MIN_TP2_PCT,
            "backtest_zero_reject_min_trades": (
                BACKTEST_ZERO_REJECT_MIN_TRADES
            ),
            "backtest_hard_min_trades": (
                BACKTEST_HARD_MIN_TRADES
            ),
            "backtest_min_win_rate": (
                BACKTEST_MIN_WIN_RATE
            ),
            "chase_rsi": CHASE_RSI,
            "chase_daily_change_pct": (
                CHASE_DAILY_CHANGE_PCT
            ),
            "chase_min_rr": CHASE_MIN_RR,
            "chase_min_volume_ratio": (
                CHASE_MIN_VOLUME_RATIO
            ),
            "max_signals": MAX_SIGNALS,
        },
        "input_count": len(signals),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "approved": [
            {
                "symbol": symbol_of(item),
                "rased_score": fnum(
                    item.get("rased_score")
                ),
                "quality_score": fnum(
                    item.get("quality_score")
                ),
                "rr": fnum(
                    item.get("rr")
                ),
                "risk": item.get(
                    "risk_level"
                ),
            }
            for item in approved
        ],
        "rejected": rejected,
    }

    write_json(
        REPORT_FILE,
        report,
    )

    print("=" * 68)
    print(
        f"RASED QUALITY GATE: "
        f"{len(approved)} approved / "
        f"{len(signals)} input"
    )
    print("=" * 68)

    return 0


if __name__ == "__main__":
    sys.exit(main())