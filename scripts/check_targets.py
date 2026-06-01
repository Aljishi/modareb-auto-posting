#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
track_results.py
يجمع إحصائيات الإشارات المغلقة ويُحدّث ملف السجل التاريخي.
يستدعي check_targets.py للتحقق من الأهداف اللحظية.
"""

import json, sys, subprocess
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def run_target_check():
    """استدعاء check_targets.py أولاً لتحديث حالات الإشارات."""
    script = Path(__file__).parent / "check_targets.py"
    if script.exists():
        result = subprocess.run([sys.executable, str(script)], capture_output=False)
        return result.returncode == 0
    return False


def build_stats():
    """احسب الإحصائيات من open_signals.json."""
    open_file = DATA_DIR / "open_signals.json"
    if not open_file.exists():
        return {"total": 0, "target2": 0, "target1_only": 0,
                "stop_hit": 0, "open": 0, "expired": 0, "win_rate": 0}

    entries = json.load(open(open_file, encoding="utf-8"))
    stats   = {"total": len(entries), "target2": 0, "target1_only": 0,
               "stop_hit": 0, "open": 0, "expired": 0}

    for e in entries:
        status = e.get("status", "open")
        if   status == "closed":      stats["target2"]      += 1
        elif status == "target1_hit": stats["target1_only"] += 1
        elif status == "stop_hit":    stats["stop_hit"]     += 1
        elif status == "expired":     stats["expired"]      += 1
        else:                         stats["open"]         += 1

    closed = stats["target2"] + stats["target1_only"] + stats["stop_hit"]
    stats["win_rate"] = round(
        (stats["target2"] + stats["target1_only"]) / closed * 100, 1
    ) if closed > 0 else 0

    return stats


def main():
    print("="*60)
    print("📊 راصد — تحديث نتائج الإشارات")
    print("="*60)

    # أولاً: فحص الأهداف ومتابعة الأسعار
    print("\n🔍 فحص الأهداف...")
    run_target_check()

    # ثانياً: بناء إحصائيات السجل
    stats = build_stats()
    output = {**stats, "updated_at": datetime.now().isoformat()}

    out_file = DATA_DIR / "track_record.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n📈 الإجمالي    : {stats['total']}")
    print(f"   مفتوحة      : {stats['open']}")
    print(f"   هدف ثانٍ ✅ : {stats['target2']}")
    print(f"   هدف أول فقط : {stats['target1_only']}")
    print(f"   وقف خسارة ❌ : {stats['stop_hit']}")
    print(f"   منتهية       : {stats['expired']}")
    print(f"   نسبة النجاح  : {stats['win_rate']}%")
    print(f"\n💾 محفوظ في {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
