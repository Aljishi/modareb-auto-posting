#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

MIN_SCORE = 75
MIN_RSI = 42
MAX_RSI = 68
MIN_VOL = 1.5
MIN_RR = 2.0
MIN_AI_CONFIDENCE = 80


def has_posted_today():
    today = datetime.now().strftime("%Y-%m-%d")
    flag_file = DATA_DIR / "last_post_date.txt"
    if flag_file.exists():
        return flag_file.read_text().strip() == today
    return False


def validate_python_rules(signal):
    score = float(signal.get("score", 0))
    rsi = float(signal.get("rsi", 50))
    vol = float(signal.get("volume_ratio", 1.0))
    rr = float(signal.get("rr", 0))

    if score < MIN_SCORE:
        return False, f"Score {score:.0f} < {MIN_SCORE}"

    if not (MIN_RSI <= rsi <= MAX_RSI):
        return False, f"RSI {rsi:.1f} خارج النطاق {MIN_RSI}-{MAX_RSI}"

    if vol < MIN_VOL:
        return False, f"Volume {vol:.1f}x < {MIN_VOL}x"

    if rr < MIN_RR:
        return False, f"R:R {rr:.1f} < {MIN_RR}"

    return True, "Python rules passed"


def validate_ai_rules(signal):
    decision = signal.get("ai_decision", "REJECT")
    confidence = int(signal.get("ai_confidence", 0))
    risk_level = signal.get("ai_risk_level", "HIGH")

    if decision != "APPROVE":
        return False, f"AI decision = {decision}"

    if confidence < MIN_AI_CONFIDENCE:
        return False, f"AI confidence {confidence} < {MIN_AI_CONFIDENCE}"

    if risk_level == "HIGH":
        return False, "AI risk level = HIGH"

    return True, "AI rules passed"


def main():
    print("=" * 60)
    print("✅ راصد — Final Posting Gate")
    print("=" * 60)

    if has_posted_today():
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"⚠️ Already posted today: {today}")
        sys.exit(1)

    signals_file = DATA_DIR / "signals.json"
    if not signals_file.exists():
        print("❌ signals.json not found")
        sys.exit(1)

    data = json.load(open(signals_file, encoding="utf-8"))
    signals = data.get("signals", [])

    if not signals:
        print("❌ No signals found")
        sys.exit(1)

    validated = []

    for sig in signals:
        sym = sig.get("stock_symbol", sig.get("symbol", ""))

        py_ok, py_reason = validate_python_rules(sig)
        if not py_ok:
            print(f"❌ {sym}: {py_reason}")
            continue

        ai_ok, ai_reason = validate_ai_rules(sig)
        if not ai_ok:
            print(f"❌ {sym}: {ai_reason}")
            continue

        sig["final_approved"] = True
        sig["final_approved_at"] = datetime.now().isoformat()
        sig["rr_ratio"] = sig.get("rr", 0)

        validated.append(sig)
        print(
            f"✅ {sym}: APPROVED | "
            f"Score {sig.get('score')} | "
            f"R:R {sig.get('rr')} | "
            f"AI {sig.get('ai_confidence')}"
        )

    validated.sort(
        key=lambda x: (
            x.get("ai_confidence", 0),
            x.get("score", 0),
            x.get("rr", 0)
        ),
        reverse=True
    )

    output = {
        "validated_signals": validated,
        "total_checked": len(signals),
        "total_valid": len(validated),
        "timestamp": datetime.now().isoformat(),
        "gate": {
            "min_score": MIN_SCORE,
            "min_rsi": MIN_RSI,
            "max_rsi": MAX_RSI,
            "min_volume_ratio": MIN_VOL,
            "min_rr": MIN_RR,
            "min_ai_confidence": MIN_AI_CONFIDENCE
        }
    }

    out_file = DATA_DIR / "validated_signals.json"
    json.dump(output, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n✅ Final approved: {len(validated)}/{len(signals)}")
    sys.exit(0 if validated else 1)


if __name__ == "__main__":
    main()
