#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
راصد — بوابة النشر النهائية
لا تسمح بالنشر إلا إذا كانت الإشارة مبنية على بيانات API حقيقية، ATR حقيقي، مقاومة/دعم، وسيولة كافية.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SIGNALS_FILE = DATA_DIR / "signals.json"
VALIDATED_FILE = DATA_DIR / "validated_signals.json"
LAST_POST_FILE = DATA_DIR / "last_post_date.txt"

MIN_SCORE = 82
MIN_RR = 2.2
MIN_VOL_RATIO = 1.6
MIN_VALUE = 2_000_000
MAX_RSI = 72
MIN_RSI = 45


def fnum(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def posted_today() -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    return LAST_POST_FILE.exists() and LAST_POST_FILE.read_text(encoding="utf-8").strip() == today


def validate(sig: Dict[str, Any]) -> Tuple[bool, str]:
    if sig.get("data_source") != "api":
        return False, "مصدر البيانات ليس API حقيقي"
    if sig.get("engine_version") != "rased_pro_10_guarded":
        return False, "الإشارة ليست من المحرك الاحترافي الجديد"
    if fnum(sig.get("score")) < MIN_SCORE:
        return False, f"Score أقل من {MIN_SCORE}"
    if fnum(sig.get("rr")) < MIN_RR:
        return False, f"R:R أقل من {MIN_RR}"
    if not (MIN_RSI <= fnum(sig.get("rsi")) <= MAX_RSI):
        return False, "RSI خارج النطاق الآمن"
    if fnum(sig.get("volume_ratio")) < MIN_VOL_RATIO:
        return False, "الحجم النسبي غير كافٍ"
    if fnum(sig.get("value")) < MIN_VALUE:
        return False, "السيولة المتداولة غير كافية"
    for field in ("atr14", "resistance", "support", "entry_point", "target1", "target2", "stop_loss"):
        if fnum(sig.get(field)) <= 0:
            return False, f"الحقل الفني ناقص أو صفر: {field}"
    if fnum(sig.get("stop_loss")) >= fnum(sig.get("entry_point")):
        return False, "وقف الخسارة غير منطقي"
    if fnum(sig.get("target2")) <= fnum(sig.get("entry_point")):
        return False, "الهدف غير منطقي"
    return True, "ok"


def main() -> int:
    print("=" * 60)
    print("✅ راصد — بوابة النشر النهائية")
    print("=" * 60)

    if posted_today():
        print("⚠️ تم النشر مسبقاً اليوم — منع نشر مكرر")
        return 1

    if not SIGNALS_FILE.exists():
        print("❌ signals.json غير موجود")
        return 1
    data = json.loads(SIGNALS_FILE.read_text(encoding="utf-8"))
    signals = data.get("signals", [])

    validated = []
    for sig in signals:
        ok, msg = validate(sig)
        sym = sig.get("stock_symbol", sig.get("symbol", ""))
        if ok:
            validated.append(sig)
            print(f"  ✅ {sym}: Score {sig.get('score')} | R:R {sig.get('rr')}")
        else:
            print(f"  ❌ {sym}: {msg}")

    out = {
        "validated_signals": validated,
        "total_checked": len(signals),
        "total_valid": len(validated),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "engine_version": "rased_pro_10_guarded",
    }
    VALIDATED_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ {len(validated)}/{len(signals)} إشارة صالحة للنشر")
    return 0 if validated else 1


if __name__ == "__main__":
    sys.exit(main())
