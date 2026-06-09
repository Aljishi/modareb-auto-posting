#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""راصد — بوابة النشر النهائية.

مهم:
- إذا OpenAI متاح: يشترط APPROVE.
- إذا OpenAI غير متاح بسبب quota أو غيره: لا يكسر النظام، لكن يطبق Python gate أكثر صرامة.
- لا يرجع خطأ عند عدم وجود إشارات؛ فقط لا ينشر.
"""

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

# تتوافق مع generate_signal.py v6
ENGINE_VERSION_PREFIX = os.getenv("ENGINE_VERSION_PREFIX", "rased_sahmk_historical")

MIN_SCORE = int(os.getenv("MIN_FINAL_SCORE", "72"))
MIN_RASED_SCORE = float(os.getenv("MIN_RASED_SCORE", "72"))
MIN_RR = float(os.getenv("MIN_RR", "1.7"))
MIN_RSI = float(os.getenv("MIN_RSI", "38"))
MAX_RSI = float(os.getenv("MAX_RSI", "80"))
MIN_VOL_RATIO = float(os.getenv("MIN_VOLUME_RATIO", "0.85"))
MIN_VALUE = float(os.getenv("MIN_VALUE_SAR", "750000"))
MIN_AI_CONFIDENCE = int(os.getenv("MIN_AI_CONFIDENCE", "75"))
MAX_HOLD_DAYS = int(os.getenv("MAX_HOLD_DAYS", "7"))
ALLOWED_AI_RISK = {"LOW", "MEDIUM"}

# عند غياب OpenAI نرفع العتبة لتعويض غياب مراجعة AI
PY_ONLY_MIN_RASED_SCORE = float(os.getenv("PY_ONLY_MIN_RASED_SCORE", "74"))
PY_ONLY_MIN_SCORE = int(os.getenv("PY_ONLY_MIN_SCORE", "72"))
PY_ONLY_MIN_RR = float(os.getenv("PY_ONLY_MIN_RR", "1.7"))
PY_ONLY_MIN_VOL_RATIO = float(os.getenv("PY_ONLY_MIN_VOLUME_RATIO", "0.85"))

MIN_TP1_PCT_NORMAL = float(os.getenv("MIN_TP1_PCT_NORMAL", "4.0"))
MIN_TP1_PCT_GOLDEN = float(os.getenv("MIN_TP1_PCT_GOLDEN", "6.0"))
MIN_TP1_PCT_PLATINUM = float(os.getenv("MIN_TP1_PCT_PLATINUM", "8.0"))
MIN_TP2_PCT_PLATINUM = float(os.getenv("MIN_TP2_PCT_PLATINUM", "10.0"))


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


def base_validate(sig: Dict[str, Any]) -> Tuple[bool, str]:
    if sig.get("data_source") != "sahmk_api_historical":
        return False, "مصدر البيانات ليس Sahmk Historical API"

    engine = str(sig.get("engine_version", ""))
    if not engine.startswith(ENGINE_VERSION_PREFIX):
        return False, f"نسخة المحرك غير متوافقة: {engine}"

    if fnum(sig.get("score")) < MIN_SCORE:
        return False, f"Score أقل من {MIN_SCORE}"
    if fnum(sig.get("rased_score")) < MIN_RASED_SCORE:
        return False, f"RASED SCORE أقل من {MIN_RASED_SCORE}"
    if fnum(sig.get("rr")) < MIN_RR:
        return False, f"R:R أقل من {MIN_RR}"
    if not (MIN_RSI <= fnum(sig.get("rsi")) <= MAX_RSI):
        return False, "RSI خارج النطاق المقبول"
    if fnum(sig.get("volume_ratio")) < MIN_VOL_RATIO:
        return False, "الحجم النسبي غير كافٍ"
    if fnum(sig.get("value")) < MIN_VALUE:
        return False, "السيولة المتداولة غير كافية"

    for field in (
        "atr14",
        "atr_pct",
        "resistance",
        "support",
        "entry_point",
        "target1",
        "target2",
        "stop_loss",
    ):
        if fnum(sig.get(field)) <= 0:
            return False, f"الحقل الفني ناقص أو صفر: {field}"

    if int(sig.get("historical_bars", 0)) < 25:
        return False, "البيانات التاريخية أقل من 25 شمعة"
    if fnum(sig.get("stop_loss")) >= fnum(sig.get("entry_point")):
        return False, "وقف الخسارة غير منطقي"
    if fnum(sig.get("target2")) <= fnum(sig.get("entry_point")):
        return False, "الهدف غير منطقي"
    if sig.get("seven_day_filter_passed") is not True:
        return False, "فلتر 7 أيام لم يجتز"
    if int(sig.get("expected_days_to_target2", 99)) > MAX_HOLD_DAYS:
        return False, "الهدف الثاني غير منطقي خلال 7 أيام"

    tp1_pct = fnum(sig.get("target1_percent", sig.get("tp1_pct")))
    tp2_pct = fnum(sig.get("target2_percent", sig.get("tp2_pct")))
    tier = str(sig.get("tier", ""))

    if tp1_pct < MIN_TP1_PCT_NORMAL:
        return False, f"TP1% أقل من الحد الأدنى للإشارة العادية {MIN_TP1_PCT_NORMAL}%"

    if tier == "Gold" and tp1_pct < MIN_TP1_PCT_GOLDEN:
        return False, f"Gold يحتاج TP1% لا يقل عن {MIN_TP1_PCT_GOLDEN}%"

    if tier == "Platinum" and tp1_pct < MIN_TP1_PCT_PLATINUM and tp2_pct < MIN_TP2_PCT_PLATINUM:
        return False, f"Platinum يحتاج TP1% >= {MIN_TP1_PCT_PLATINUM}% أو TP2% >= {MIN_TP2_PCT_PLATINUM}%"

    return True, "ok"


def ai_validate(sig: Dict[str, Any]) -> Tuple[bool, str]:
    ai_available = sig.get("ai_available") is True

    if ai_available:
        if sig.get("ai_decision") != "APPROVE":
            return False, f"OpenAI decision = {sig.get('ai_decision', 'missing')}"
        if int(sig.get("ai_confidence", 0)) < MIN_AI_CONFIDENCE:
            return False, f"OpenAI confidence أقل من {MIN_AI_CONFIDENCE}"
        if sig.get("ai_risk_level") not in ALLOWED_AI_RISK:
            return False, f"OpenAI risk غير مقبول: {sig.get('ai_risk_level')}"
        if int(sig.get("ai_expected_holding_days", 99)) > MAX_HOLD_DAYS:
            return False, "OpenAI يرى أن المدة المتوقعة تتجاوز 7 أيام"
        return True, "ai ok"

    # OpenAI غير متاح: بوابة Python أكثر صرامة
    if fnum(sig.get("score")) < PY_ONLY_MIN_SCORE:
        return False, f"OpenAI غير متاح و Score أقل من {PY_ONLY_MIN_SCORE}"
    if fnum(sig.get("rased_score")) < PY_ONLY_MIN_RASED_SCORE:
        return False, f"OpenAI غير متاح و RASED SCORE أقل من {PY_ONLY_MIN_RASED_SCORE}"
    if fnum(sig.get("rr")) < PY_ONLY_MIN_RR:
        return False, f"OpenAI غير متاح و R:R أقل من {PY_ONLY_MIN_RR}"
    if fnum(sig.get("volume_ratio")) < PY_ONLY_MIN_VOL_RATIO:
        return False, f"OpenAI غير متاح و Volume أقل من {PY_ONLY_MIN_VOL_RATIO}x"

    sig["ai_available"] = False
    sig["ai_review_used"] = False
    sig["ai_decision"] = "SKIPPED_PYTHON_STRICT_APPROVED"
    sig["ai_confidence"] = 0
    sig["ai_risk_level"] = "UNKNOWN"
    sig["ai_telegram_note"] = sig.get("key_insight", "")
    sig["ai_arabic_summary"] = sig.get("signal_reason", "")
    return True, "python strict fallback ok"


def validate(sig: Dict[str, Any]) -> Tuple[bool, str]:
    ok, msg = base_validate(sig)
    if not ok:
        return ok, msg
    return ai_validate(sig)


def main() -> int:
    print("=" * 60)
    print("✅ راصد — Final Posting Gate")
    print("=" * 60)

    if posted_today():
        print("⚠️ تم النشر مسبقاً اليوم — منع نشر مكرر")
        return 0

    if not SIGNALS_FILE.exists():
        print("ℹ️ signals.json غير موجود — لا يوجد نشر")
        return 0

    data = json.loads(SIGNALS_FILE.read_text(encoding="utf-8"))
    signals = data.get("signals", [])
    if not signals:
        print("ℹ️ لا توجد إشارات — لا يوجد نشر")
        VALIDATED_FILE.write_text(
            json.dumps(
                {
                    "validated_signals": [],
                    "total_checked": 0,
                    "total_valid": 0,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "status": "NO_SIGNALS",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return 0

    validated = []
    for sig in signals:
        sym = sig.get("stock_symbol", sig.get("symbol", ""))
        ok, msg = validate(sig)
        if ok:
            sig["final_approved"] = True
            sig["final_approved_at"] = datetime.now().isoformat(timespec="seconds")
            validated.append(sig)
            print(
                f"✅ {sym}: {sig.get('tier')} | RASED {sig.get('rased_score')} | "
                f"AI {sig.get('ai_decision')} | TP2 {sig.get('target2_percent')}%"
            )
        else:
            print(f"❌ {sym}: {msg}")

    validated.sort(
        key=lambda s: (
            fnum(s.get("rased_score")),
            fnum(s.get("ai_confidence")),
            fnum(s.get("rr")),
        ),
        reverse=True,
    )
    validated = validated[:1]

    out = {
        "validated_signals": validated,
        "total_checked": len(signals),
        "total_valid": len(validated),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "status": "HAS_VALID_SIGNAL" if validated else "NO_VALID_SIGNAL",
        "rules": {
            "min_score": MIN_SCORE,
            "min_rased_score": MIN_RASED_SCORE,
            "min_rr": MIN_RR,
            "min_ai_confidence": MIN_AI_CONFIDENCE,
            "max_holding_days": MAX_HOLD_DAYS,
            "python_only_min_score": PY_ONLY_MIN_SCORE,
            "python_only_min_rased_score": PY_ONLY_MIN_RASED_SCORE,
            "min_tp1_pct_normal": MIN_TP1_PCT_NORMAL,
            "min_tp1_pct_golden": MIN_TP1_PCT_GOLDEN,
            "min_tp1_pct_platinum": MIN_TP1_PCT_PLATINUM,
            "min_tp2_pct_platinum": MIN_TP2_PCT_PLATINUM,
        },
        "disclaimer": "لا يوجد ضمان لتحقيق الأهداف. الفلاتر مصممة لاختيار إشارات مرشحة فنياً خلال 1-7 أيام فقط.",
    }
    VALIDATED_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ Final approved: {len(validated)}/{len(signals)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
