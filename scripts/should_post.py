#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate signals before posting — includes duplicate-post guard"""

import json
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

MIN_SCORE  = 70
MIN_RSI    = 42
MAX_RSI    = 68
MIN_VOL    = 1.5
MIN_RR     = 2.0


def validate(signal):
    score = signal.get('score', 0)
    rsi   = signal.get('rsi', 50)
    vol   = signal.get('volume_ratio', 1.0)
    rr    = signal.get('rr', 0)

    if score < MIN_SCORE:
        return False, f"Score {score} < {MIN_SCORE}"
    if not (MIN_RSI <= rsi <= MAX_RSI):
        return False, f"RSI {rsi:.0f} خارج النطاق ({MIN_RSI}–{MAX_RSI})"
    if vol < MIN_VOL:
        return False, f"Volume {vol:.1f}x < {MIN_VOL}x"
    if rr < MIN_RR:
        return False, f"R:R {rr:.1f} < {MIN_RR}"

    return True, {"rr_ratio": rr}


def main():
    print("=" * 60)
    print("✅ راصد — التحقق من الإشارات")
    print("=" * 60)

    # ─── FIX: حارس النشر المزدوج ──────────────────────────
    today     = datetime.now().strftime('%Y-%m-%d')
    flag_file = DATA_DIR / "last_post_date.txt"
    if flag_file.exists() and flag_file.read_text().strip() == today:
        print(f"⚠️ تم النشر مسبقاً اليوم ({today}) — تم تخطي النشر")
        sys.exit(1)
    # ──────────────────────────────────────────────────────

    signals_file = DATA_DIR / "signals.json"
    if not signals_file.exists():
        print("❌ signals.json not found"); sys.exit(1)

    with open(signals_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    signals   = data.get('signals', [])
    validated = []

    for sig in signals:
        ok, result = validate(sig)
        sym = sig.get('stock_symbol', sig.get('symbol', ''))
        if ok:
            validated.append({**sig, **result})
            print(f"  ✅ {sym}: Score {sig.get('score')} | R:R {result['rr_ratio']}")
        else:
            print(f"  ❌ {sym}: {result}")

    output = {
        "validated_signals": validated,
        "total_checked": len(signals),
        "total_valid":   len(validated),
        "timestamp":     datetime.now().isoformat(),
    }

    out_file = DATA_DIR / "validated_signals.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(validated)}/{len(signals)} إشارة مقبولة")
    return 0 if validated else 1


if __name__ == "__main__":
    sys.exit(main())
