#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""راصد — بوابة النشر النهائية Premium."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SIGNALS_FILE = DATA_DIR / "signals.json"
VALIDATED_FILE = DATA_DIR / "validated_signals.json"
LAST_POST_FILE = DATA_DIR / "last_post_date.txt"

MIN_SCORE = int(os.getenv("MIN_FINAL_SCORE", "84"))
MIN_RASED_SCORE = float(os.getenv("MIN_RASED_SCORE", "85"))
MIN_RR = float(os.getenv("MIN_RR", "2.2"))
MIN_RSI = float(os.getenv("MIN_RSI", "48"))
MAX_RSI = float(os.getenv("MAX_RSI", "68"))
MIN_VOL_RATIO = float(os.getenv("MIN_VOLUME_RATIO", "1.7"))
MIN_VALUE = float(os.getenv("MIN_VALUE_SAR", "3000000"))
MIN_AI_CONFIDENCE = int(os.getenv("MIN_AI_CONFIDENCE", "82"))
MAX_HOLD_DAYS = int(os.getenv("MAX_HOLD_DAYS", "7"))
ALLOWED_AI_RISK = {"LOW", "MEDIUM"}
ENGINE_VERSION = "rased_sahmk_paid_historical_7d_v1"


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace("%", "").replace(",", "").strip()
        return float(x)
    except Exception:
        return default


def posted_today() -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        return LAST_POST_FILE.exists() and LAST_POST_FILE.read_text(encoding="utf-8").strip() == today
    except Exception:
        return False


def validate(sig: Dict[str, Any]) -> Tuple[bool, str]:
    if sig.get("data_source") != "sahmk_api_historical":
        return False, "مصدر البيانات ليس Sahmk Historical API"
    if sig.get("engine_version") != ENGINE_VERSION:
        return False, "الإشارة ليست من محرك Sahmk Historical الجديد"

    if fnum(sig.get("score")) < MIN_SCORE:
        return False, f"Score أقل من {MIN_SCORE}"
    if fnum(sig.get("rased_score")) < MIN_RASED_SCORE:
        return False, f"RASED SCORE أقل من {MIN_RASED_SCORE}"
    if fnum(sig.get("rr")) < MIN_RR:
        return False, f"R:R أقل من {MIN_RR}"
    if not (MIN_RSI <= fnum(sig.get("rsi")) <= MAX_RSI):
        return False, "RSI خارج النطاق الآمن"
    if fnum(sig.get("volume_ratio")) < MIN_VOL_RATIO:
        return False, "الحجم النسبي غير كافٍ"
    if fnum(sig.get("value")) < MIN_VALUE:
        return False, "السيولة المتداولة غير كافية"

    for field in ("atr14", "atr_pct", "resistance", "support", "entry_point", "target1", "target2", "stop_loss"):
        if fnum(sig.get(field)) <= 0:
            return False, f"الحقل الفني ناقص أو صفر: {field}"

    if int(sig.get("historical_bars", 0)) < 30:
        return False, "البيانات التاريخية أقل من 30 شمعة"
    if fnum(sig.get("stop_loss")) >= fnum(sig.get("entry_point")):
        return False, "وقف الخسارة غير منطقي"
    if fnum(sig.get("target2")) <= fnum(sig.get("entry_point")):
        return False, "الهدف غير منطقي"

    if sig.get("seven_day_filter_passed") is not True:
        return False, "فلتر 7 أيام لم يجتز"
    if int(sig.get("expected_days_to_target2", 99)) > MAX_HOLD_DAYS:
        return False, "الهدف الثاني غير منطقي خلال 7 أيام"

    if sig.get("ai_decision") != "APPROVE":
        return False, f"OpenAI decision = {sig.get('ai_decision', 'missing')}"
    if int(sig.get("ai_confidence", 0)) < MIN_AI_CONFIDENCE:
        return False, f"OpenAI confidence أقل من {MIN_AI_CONFIDENCE}"
    if sig.get("ai_risk_level") not in ALLOWED_AI_RISK:
        return False, f"OpenAI risk غير مقبول: {sig.get('ai_risk_level')}"
    if int(sig.get("ai_expected_holding_days", 99)) > MAX_HOLD_DAYS:
        return False, "OpenAI يرى أن المدة المتوقعة تتجاوز 7 أيام"

    return True, "ok"


def main() -> int:
    print("=" * 60)
    print("✅ راصد — Premium Final Posting Gate")
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
        sym = sig.get("stock_symbol", sig.get("symbol", ""))
        ok, msg = validate(sig)
        if ok:
            sig["final_approved"] = True
            sig["final_approved_at"] = datetime.now().isoformat(timespec="seconds")
            validated.append(sig)
            print(f"✅ {sym}: {sig.get('tier')} | RASED {sig.get('rased_score')} | AI {sig.get('ai_confidence')} | TP2 {sig.get('target2_percent')}%")
        else:
            print(f"❌ {sym}: {msg}")

    validated.sort(key=lambda s: (fnum(s.get("rased_score")), fnum(s.get("ai_confidence")), fnum(s.get("rr"))), reverse=True)
    validated = validated[:1]

    out = {
        "validated_signals": validated,
        "total_checked": len(signals),
        "total_valid": len(validated),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "engine_version": ENGINE_VERSION,
        "rules": {
            "min_score": MIN_SCORE,
            "min_rased_score": MIN_RASED_SCORE,
            "min_rr": MIN_RR,
            "min_ai_confidence": MIN_AI_CONFIDENCE,
            "max_holding_days": MAX_HOLD_DAYS,
        },
        "disclaimer": "لا يوجد ضمان لتحقيق الأهداف. الفلاتر مصممة لاختيار إشارات مرشحة فنياً خلال 1-7 أيام فقط.",
    }
    VALIDATED_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ Final approved: {len(validated)}/{len(signals)}")
    return 0 if validated else 1


if __name__ == "__main__":
    sys.exit(main())
