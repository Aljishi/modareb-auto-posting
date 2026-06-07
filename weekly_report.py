#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""راصد — تقرير أسبوعي مبني على سجل الأداء الحقيقي.

يعتمد على:
- data/signal_performance_summary.json
- data/published_signals.csv

ولا يستخدم score كبديل عن النجاح.
"""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PUBLISHED_FILE = DATA_DIR / "published_signals.csv"
SUMMARY_FILE = DATA_DIR / "signal_performance_summary.json"
WEEKLY_REPORT_JSON = DATA_DIR / "weekly_report.json"
WEEKLY_REPORT_TXT = DATA_DIR / "weekly_performance_report.txt"


def read_csv_rows() -> List[Dict[str, str]]:
    if not PUBLISHED_FILE.exists():
        return []
    with open(PUBLISHED_FILE, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_summary() -> Dict:
    if SUMMARY_FILE.exists():
        try:
            return json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def parse_date(value: str):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "")).date()
    except Exception:
        try:
            return datetime.fromisoformat(str(value)[:10]).date()
        except Exception:
            return None


def this_week_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    today = datetime.now().date()
    start = today - timedelta(days=7)
    out = []
    for r in rows:
        d = parse_date(r.get("published_at", ""))
        if d and start <= d <= today:
            out.append(r)
    return out


def pct(n: int, d: int) -> float:
    return round((n / d) * 100, 1) if d else 0.0


def fnum(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(str(v).replace(",", "").replace("%", "").strip())
    except Exception:
        return default


def build_report():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_csv_rows()
    week_rows = this_week_rows(rows)
    summary = load_summary()

    closed = [r for r in rows if r.get("status") in {"TP1", "TP2", "SL", "EXPIRED"}]
    open_rows = [r for r in rows if r.get("status") == "OPEN"]
    tp1 = [r for r in rows if r.get("status") in {"TP1", "TP2"}]
    tp2 = [r for r in rows if r.get("status") == "TP2"]
    sl = [r for r in rows if r.get("status") == "SL"]
    expired = [r for r in rows if r.get("status") == "EXPIRED"]

    closed_week = [r for r in week_rows if r.get("status") in {"TP1", "TP2", "SL", "EXPIRED"}]
    tp1_week = [r for r in week_rows if r.get("status") in {"TP1", "TP2"}]
    tp2_week = [r for r in week_rows if r.get("status") == "TP2"]
    sl_week = [r for r in week_rows if r.get("status") == "SL"]
    open_week = [r for r in week_rows if r.get("status") == "OPEN"]

    avg_days_tp1_values = [fnum(r.get("days_to_tp1")) for r in tp1 if str(r.get("days_to_tp1", "")).strip()]
    avg_days_tp2_values = [fnum(r.get("days_to_tp2")) for r in tp2 if str(r.get("days_to_tp2", "")).strip()]

    avg_days_tp1 = round(sum(avg_days_tp1_values) / len(avg_days_tp1_values), 1) if avg_days_tp1_values else 0.0
    avg_days_tp2 = round(sum(avg_days_tp2_values) / len(avg_days_tp2_values), 1) if avg_days_tp2_values else 0.0

    best_recent = []
    for r in rows[-20:]:
        if r.get("status") in {"TP1", "TP2"}:
            best_recent.append(
                {
                    "symbol": r.get("symbol", ""),
                    "name": r.get("name", ""),
                    "status": r.get("status", ""),
                    "target1_percent": fnum(r.get("target1_percent")),
                    "target2_percent": fnum(r.get("target2_percent")),
                    "closed_at": r.get("closed_at", ""),
                }
            )
    best_recent = best_recent[-5:]

    today = datetime.now().date()
    week_start = today - timedelta(days=7)

    report = {
        "week_start": week_start.isoformat(),
        "week_end": today.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_published": len(rows),
        "total_this_week": len(week_rows),
        "closed_signals": len(closed),
        "open_signals": len(open_rows),
        "tp1_hits": len(tp1),
        "tp2_hits": len(tp2),
        "stop_losses": len(sl),
        "expired": len(expired),
        "tp1_success_rate_closed": pct(len(tp1), len(closed)),
        "tp2_success_rate_closed": pct(len(tp2), len(closed)),
        "stop_loss_rate_closed": pct(len(sl), len(closed)),
        "this_week": {
            "published": len(week_rows),
            "closed": len(closed_week),
            "open": len(open_week),
            "tp1_hits": len(tp1_week),
            "tp2_hits": len(tp2_week),
            "stop_losses": len(sl_week),
            "tp1_success_rate_closed": pct(len(tp1_week), len(closed_week)),
            "tp2_success_rate_closed": pct(len(tp2_week), len(closed_week)),
        },
        "avg_days_to_tp1": avg_days_tp1,
        "avg_days_to_tp2": avg_days_tp2,
        "best_recent": best_recent,
        "minimum_sample_warning": len(closed) < 30,
        "note": "الإحصائيات مبنية على الإشارات المنشورة فعلياً فقط. الأداء السابق لا يضمن النتائج المستقبلية.",
        "raw_summary": summary,
    }

    WEEKLY_REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    warning = ""
    if report["minimum_sample_warning"]:
        warning = "\n⚠️ العينة الحالية أقل من 30 إشارة مغلقة؛ النسبة إرشادية وليست نهائية.\n"

    text = f"""📊 تقرير أداء راصد الأسبوعي

📅 الفترة:
{report['week_start']} إلى {report['week_end']}

━━━━━━━━━━━━━━

📌 إجمالي الإشارات المنشورة:
{report['total_published']}

📌 إشارات هذا الأسبوع:
{report['total_this_week']}

📌 الإشارات المغلقة:
{report['closed_signals']}

📌 الإشارات المفتوحة:
{report['open_signals']}

━━━━━━━━━━━━━━

🎯 تحقيق الهدف الأول:
{report['tp1_hits']} إشارة
نسبة النجاح من الإشارات المغلقة: {report['tp1_success_rate_closed']}%

🏆 تحقيق الهدف الثاني:
{report['tp2_hits']} إشارة
نسبة النجاح من الإشارات المغلقة: {report['tp2_success_rate_closed']}%

🛑 وقف الخسارة:
{report['stop_losses']} إشارة
النسبة: {report['stop_loss_rate_closed']}%

⏳ متوسط مدة تحقيق الهدف الأول:
{report['avg_days_to_tp1']} يوم

⏳ متوسط مدة تحقيق الهدف الثاني:
{report['avg_days_to_tp2']} يوم
{warning}
━━━━━━━━━━━━━━

منهجية راصد:
✓ بيانات Sahmk
✓ فلاتر فنية
✓ إدارة مخاطر
✓ مراجعة ذكاء اصطناعي عند توفرها
✓ تتبع حقيقي بعد النشر

تنبيه: الأداء السابق لا يضمن النتائج المستقبلية.
"""
    WEEKLY_REPORT_TXT.write_text(text, encoding="utf-8")
    return report, text


def main() -> int:
    print("=" * 60)
    print("📊 تقرير راصد الأسبوعي الحقيقي")
    print("=" * 60)
    report, text = build_report()
    print(text)
    print(f"✅ Saved: {WEEKLY_REPORT_JSON}")
    print(f"✅ Saved: {WEEKLY_REPORT_TXT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
