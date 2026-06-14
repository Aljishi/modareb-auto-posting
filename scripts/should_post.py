#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — بوابة السماح بالنشر.

- إذا وُجدت مراجعة OpenAI ورفضت الإشارة: لا تنشر.
- إذا OpenAI غير متاح: استخدم Python Gate فقط.
- العادية أصبحت ألين قليلاً حتى لا تصبح القناة صامتة.
- الذهبية تبقى صارمة من ملفات الذهبية نفسها.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SIGNALS_FILE = DATA_DIR / "signals.json"
VALIDATED_FILE = DATA_DIR / "validated_signals.json"

PY_ONLY_MIN_RASED_SCORE = float(os.getenv("PY_ONLY_MIN_RASED_SCORE", "84"))
PY_ONLY_MIN_SCORE = float(os.getenv("PY_ONLY_MIN_SCORE", "84"))
PY_ONLY_MIN_RR = float(os.getenv("PY_ONLY_MIN_RR", "2.0"))
PY_ONLY_MIN_VOL_RATIO = float(os.getenv("PY_ONLY_MIN_VOL_RATIO", "0.80"))

PY_ONLY_MAX_RSI = float(os.getenv("PY_ONLY_MAX_RSI", "72"))
PY_ONLY_MIN_BACKTEST_WIN_RATE = float(os.getenv("PY_ONLY_MIN_BACKTEST_WIN_RATE", "40"))
PY_ONLY_MIN_BACKTEST_TRADES = int(os.getenv("PY_ONLY_MIN_BACKTEST_TRADES", "8"))

MIN_TP1_PCT_NORMAL = float(os.getenv("MIN_TP1_PCT_NORMAL", "3.0"))
MIN_TP1_PCT_GOLDEN = float(os.getenv("MIN_TP1_PCT_GOLDEN", "6.0"))
MIN_TP1_PCT_PLATINUM = float(os.getenv("MIN_TP1_PCT_PLATINUM", "8.0"))
MIN_TP2_PCT_PLATINUM = float(os.getenv("MIN_TP2_PCT_PLATINUM", "10.0"))

MAX_HOLD_DAYS = int(os.getenv("MAX_HOLD_DAYS", "7"))


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace("%", "").replace(",", "").strip()
        return float(x)
    except Exception:
        return default


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"⚠️ cannot read {path}: {exc}")
    return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ai_rejected(signal: Dict[str, Any]) -> bool:
    reviewed = bool(signal.get("ai_reviewed") or signal.get("ai_available"))
    decision = str(signal.get("ai_decision") or "").upper()

    if not reviewed:
        return False

    return decision in {"REJECT", "REJECTED", "BLOCK", "BLOCKED", "NO"}


def ai_approved(signal: Dict[str, Any]) -> bool:
    reviewed = bool(signal.get("ai_reviewed") or signal.get("ai_available"))
    decision = str(signal.get("ai_decision") or "").upper()

    return reviewed and decision in {"APPROVE", "APPROVED", "PASS", "YES"}


def validate_signal(signal: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []

    symbol = signal.get("stock_symbol") or signal.get("symbol") or "UNKNOWN"
    tier = str(signal.get("tier") or "").title()

    rased = fnum(signal.get("rased_score") or signal.get("confidence"))
    score = fnum(signal.get("score"))
    rr = fnum(signal.get("rr") or signal.get("rr_ratio"))
    vol = fnum(signal.get("volume_ratio"))
    rsi = fnum(signal.get("rsi"))
    backtest_win = fnum(signal.get("backtest_win_rate"))
    backtest_trades = int(fnum(signal.get("backtest_trades")))

    tp1 = fnum(signal.get("target1_percent") or signal.get("tp1_pct"))
    tp2 = fnum(signal.get("target2_percent") or signal.get("tp2_pct"))

    days = int(
        fnum(
            signal.get("expected_days_to_target2")
            or signal.get("ai_expected_holding_days"),
            99,
        )
    )

    if ai_rejected(signal):
        reasons.append("OpenAI rejected the signal")

    if tp1 < MIN_TP1_PCT_NORMAL:
        reasons.append(f"TP1 {tp1}% < {MIN_TP1_PCT_NORMAL}%")

    if tier == "Gold" and tp1 < MIN_TP1_PCT_GOLDEN:
        reasons.append(f"Gold TP1 {tp1}% < {MIN_TP1_PCT_GOLDEN}%")

    if tier == "Platinum" and tp1 < MIN_TP1_PCT_PLATINUM and tp2 < MIN_TP2_PCT_PLATINUM:
        reasons.append(
            f"Platinum needs TP1 >= {MIN_TP1_PCT_PLATINUM}% "
            f"or TP2 >= {MIN_TP2_PCT_PLATINUM}%"
        )

    if rased < PY_ONLY_MIN_RASED_SCORE:
        reasons.append(f"RASED {rased} < {PY_ONLY_MIN_RASED_SCORE}")

    if score < PY_ONLY_MIN_SCORE:
        reasons.append(f"Score {score} < {PY_ONLY_MIN_SCORE}")

    if rr < PY_ONLY_MIN_RR:
        reasons.append(f"R:R {rr} < {PY_ONLY_MIN_RR}")

    if rsi > PY_ONLY_MAX_RSI:
        reasons.append(f"RSI {rsi} > {PY_ONLY_MAX_RSI} (overbought)")

    if backtest_trades >= PY_ONLY_MIN_BACKTEST_TRADES and backtest_win < PY_ONLY_MIN_BACKTEST_WIN_RATE:
        reasons.append(
            f"Backtest win rate {backtest_win}% < {PY_ONLY_MIN_BACKTEST_WIN_RATE}% "
            f"on {backtest_trades} similar cases"
        )

    if vol < PY_ONLY_MIN_VOL_RATIO:
        reasons.append(f"Volume {vol}x < {PY_ONLY_MIN_VOL_RATIO}x")

    if days > MAX_HOLD_DAYS:
        reasons.append(f"Expected days {days} > {MAX_HOLD_DAYS}")

    if reasons:
        print(f"❌ {symbol}: " + " | ".join(reasons))
    else:
        ai_note = "AI approved" if ai_approved(signal) else "Python gate"
        print(f"✅ {symbol}: approved by {ai_note}")

    return reasons


def main() -> int:
    data = load_json(SIGNALS_FILE, {})
    signals = data.get("signals", []) if isinstance(data, dict) else []

    if not signals:
        print("ℹ️ No signals to validate")
        write_json(
            VALIDATED_FILE,
            {
                "signals": [],
                "total": 0,
                "status": "NO_SIGNALS",
            },
        )
        return 1

    approved = []
    rejected = []

    for signal in signals:
        reasons = validate_signal(signal)

        if reasons:
            item = dict(signal)
            item["post_rejected_reasons"] = reasons
            rejected.append(item)
        else:
            item = dict(signal)
            item["post_approved"] = True
            approved.append(item)

    approved.sort(
        key=lambda x: (
            fnum(x.get("rased_score")),
            fnum(x.get("score")),
            fnum(x.get("rr") or x.get("rr_ratio")),
        ),
        reverse=True,
    )

    out = {
        "signals": approved,
        "rejected": rejected,
        "total": len(approved),
        "status": "HAS_VALID_SIGNALS" if approved else "NO_VALID_SIGNALS",
        "source": "should_post.py",
    }

    write_json(VALIDATED_FILE, out)

    if not approved:
        print("ℹ️ No valid signals after post gate")
        return 1

    print(f"✅ Validated {len(approved)} signal(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())