#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

LOG_FILE = DATA / "generation.log"
SIGNALS_FILE = DATA / "signals.json"
VALIDATED_FILE = DATA / "validated_signals.json"
OUT_FILE = DATA / "no_signal_report.json"

REJECT_RE = re.compile(r"⚠️\s*([0-9A-Z]+)\s*:\s*(.+)")


def classify(reason: str) -> str:
    r = reason.lower()

    if "سيولة" in reason or "قيمة التداول" in reason or "volume" in r or "حجم" in reason:
        return "ضعف السيولة أو الحجم"

    if "r:r" in r or "tp1" in r or "tp2" in r or "هدف" in reason:
        return "العائد مقابل المخاطرة غير مناسب"

    if "rsi" in r:
        return "الزخم غير مناسب"

    if "atr" in r:
        return "التذبذب غير مناسب"

    if "مقاومة" in reason or "breakout" in r:
        return "بعيد عن الاختراق أو قريب من مقاومة"

    if "تاريخ" in reason or "historical" in r or "شمعة" in reason:
        return "بيانات تاريخية غير كافية"

    if "ترند" in reason or "trend" in r:
        return "الاتجاه الفني غير مناسب"

    if "openai" in r or "ai" in r:
        return "مراجعة الذكاء الاصطناعي لم تجز الإشارة"

    return "أسباب فنية أخرى"


def read_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def main():
    DATA.mkdir(exist_ok=True)

    lines = []
    if LOG_FILE.exists():
        lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()

    rejected = []
    for line in lines:
        m = REJECT_RE.search(line)
        if m:
            rejected.append({
                "symbol": m.group(1),
                "reason": m.group(2).strip(),
                "category": classify(m.group(2).strip()),
            })

    signals_data = read_json(SIGNALS_FILE, {})
    validated_data = read_json(VALIDATED_FILE, {})

    total_generated = len(signals_data.get("signals", [])) if isinstance(signals_data, dict) else 0
    total_validated = len(validated_data.get("validated_signals", [])) if isinstance(validated_data, dict) else 0

    category_counts = Counter(x["category"] for x in rejected)

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_rejected": len(rejected),
        "total_generated": total_generated,
        "total_validated": total_validated,
        "categories": dict(category_counts.most_common()),
        "sample_rejections": rejected[:20],
        "status": "HAS_VALID_SIGNAL" if total_validated else "NO_VALID_SIGNAL",
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("✅ Rejection report generated")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()