#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import os
from pathlib import Path
from datetime import datetime, date, timedelta

import requests

DATA_DIR = Path("data")
PUBLISHED_FILE = DATA_DIR / "published_signals.csv"
SUMMARY_FILE = DATA_DIR / "signal_performance_summary.json"
REPORT_FILE = DATA_DIR / "weekly_performance_report.txt"

API_URL = os.getenv("API_URL", "https://app.sahmk.sa/api/v1").rstrip("/")
API_KEY = os.getenv("API_KEY") or os.getenv("SAHMK_API_KEY")
TIMEOUT = int(os.getenv("SAHMK_TIMEOUT", "20"))


def fnum(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(str(v).replace(",", "").replace("%", "").strip())
    except Exception:
        return default


def parse_dt(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", ""))
    except Exception:
        return None


def headers():
    if not API_KEY:
        raise RuntimeError("API_KEY / SAHMK_API_KEY غير موجود")
    return {
        "X-API-Key": API_KEY,
        "Accept": "application/json",
        "User-Agent": "Rased-Performance-Tracker/1.0",
    }


def sahmk_get(path, params=None):
    url = f"{API_URL}/{path.lstrip('/')}"
    r = requests.get(url, headers=headers(), params=params or {}, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"Sahmk {r.status_code}: {r.text[:200]}")
    return r.json()


def fetch_historical(symbol, start_date, end_date):
    payload = sahmk_get(
        f"historical/{symbol}/",
        {
            "from": start_date,
            "to": end_date,
            "interval": "1d",
        },
    )

    rows = payload.get("data", [])
    clean = []

    if not isinstance(rows, list):
        return []

    for r in rows:
        high = fnum(r.get("high"))
        low = fnum(r.get("low"))
        close = fnum(r.get("close"))

        if high > 0 and low > 0 and close > 0:
            clean.append({
                "date": str(r.get("date") or r.get("timestamp") or "")[:10],
                "high": high,
                "low": low,
                "close": close,
            })

    clean.sort(key=lambda x: x["date"])
    return clean


def days_between(start_date, hit_date):
    try:
        d1 = datetime.fromisoformat(start_date[:10]).date()
        d2 = datetime.fromisoformat(hit_date[:10]).date()
        return max(0, (d2 - d1).days)
    except Exception:
        return ""


def evaluate_signal(row):
    if row.get("status") in {"TP2", "TP1", "SL", "EXPIRED"}:
        return row

    symbol = row.get("symbol", "").strip()
    if not symbol:
        row["status"] = "EXPIRED"
        row["result"] = "INVALID_SYMBOL"
        return row

    published_at = parse_dt(row.get("published_at"))
    if not published_at:
        row["status"] = "EXPIRED"
        row["result"] = "INVALID_DATE"
        return row

    max_days = int(fnum(row.get("max_holding_days"), 7))
    start = published_at.date()
    end = min(date.today(), start + timedelta(days=max_days))

    entry = fnum(row.get("entry"))
    tp1 = fnum(row.get("target1"))
    tp2 = fnum(row.get("target2"))
    sl = fnum(row.get("stop_loss"))

    if entry <= 0 or tp1 <= 0 or tp2 <= 0 or sl <= 0:
        row["status"] = "EXPIRED"
        row["result"] = "INVALID_LEVELS"
        return row

    try:
        hist = fetch_historical(symbol, start.isoformat(), end.isoformat())
    except Exception as e:
        print(f"⚠️ {symbol}: cannot fetch history: {e}")
        return row

    if not hist:
        return row

    highest = max(fnum(x["high"]) for x in hist)
    lowest = min(fnum(x["low"]) for x in hist)

    row["highest_price"] = round(highest, 4)
    row["lowest_price"] = round(lowest, 4)

    tp1_date = ""
    tp2_date = ""
    sl_date = ""

    for d in hist:
        high = fnum(d["high"])
        low = fnum(d["low"])

        if not sl_date and low <= sl:
            sl_date = d["date"]

        if not tp1_date and high >= tp1:
            tp1_date = d["date"]

        if not tp2_date and high >= tp2:
            tp2_date = d["date"]

    # تحفظ إحصائي: إذا ضرب وقف الخسارة والهدف في نفس اليوم، نحسبها وقف خسارة
    if sl_date and (not tp1_date or sl_date <= tp1_date):
        row["status"] = "SL"
        row["result"] = "STOP_LOSS"
        row["closed_at"] = sl_date
        return row

    if tp2_date:
        row["status"] = "TP2"
        row["result"] = "TARGET2_HIT"
        row["closed_at"] = tp2_date
        row["days_to_tp1"] = days_between(row["published_at"], tp1_date) if tp1_date else ""
        row["days_to_tp2"] = days_between(row["published_at"], tp2_date)
        return row

    if tp1_date:
        row["status"] = "TP1"
        row["result"] = "TARGET1_HIT"
        row["closed_at"] = tp1_date
        row["days_to_tp1"] = days_between(row["published_at"], tp1_date)
        return row

    if date.today() > start + timedelta(days=max_days):
        row["status"] = "EXPIRED"
        row["result"] = "NO_TARGET_WITHIN_PERIOD"
        row["closed_at"] = (start + timedelta(days=max_days)).isoformat()
        return row

    row["status"] = "OPEN"
    row["result"] = "STILL_ACTIVE"
    return row


def read_rows():
    if not PUBLISHED_FILE.exists():
        return []

    with open(PUBLISHED_FILE, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(rows):
    if not rows:
        return

    fields = list(rows[0].keys())

    with open(PUBLISHED_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_summary(rows):
    total = len(rows)
    closed = [r for r in rows if r.get("status") in {"TP1", "TP2", "SL", "EXPIRED"}]
    open_rows = [r for r in rows if r.get("status") == "OPEN"]

    tp1 = [r for r in rows if r.get("status") in {"TP1", "TP2"}]
    tp2 = [r for r in rows if r.get("status") == "TP2"]
    sl = [r for r in rows if r.get("status") == "SL"]
    expired = [r for r in rows if r.get("status") == "EXPIRED"]

    denominator = len(closed) if closed else 0

    def pct_count(n, d):
        return round((n / d) * 100, 1) if d else 0.0

    avg_days_tp1 = [
        fnum(r.get("days_to_tp1"), None)
        for r in tp1
        if str(r.get("days_to_tp1", "")).strip() != ""
    ]
    avg_days_tp2 = [
        fnum(r.get("days_to_tp2"), None)
        for r in tp2
        if str(r.get("days_to_tp2", "")).strip() != ""
    ]

    avg_days_tp1 = round(sum(avg_days_tp1) / len(avg_days_tp1), 1) if avg_days_tp1 else 0
    avg_days_tp2 = round(sum(avg_days_tp2) / len(avg_days_tp2), 1) if avg_days_tp2 else 0

    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "total_published": total,
        "closed_signals": len(closed),
        "open_signals": len(open_rows),
        "tp1_hits": len(tp1),
        "tp2_hits": len(tp2),
        "stop_losses": len(sl),
        "expired": len(expired),
        "tp1_success_rate_closed": pct_count(len(tp1), denominator),
        "tp2_success_rate_closed": pct_count(len(tp2), denominator),
        "stop_loss_rate_closed": pct_count(len(sl), denominator),
        "avg_days_to_tp1": avg_days_tp1,
        "avg_days_to_tp2": avg_days_tp2,
        "note": "الإحصائيات مبنية فقط على الإشارات المنشورة فعلياً في القناة."
    }


def build_weekly_report(summary):
    return f"""📊 تقرير أداء راصد الأسبوعي

إجمالي الإشارات المنشورة:
{summary['total_published']}

الإشارات المغلقة:
{summary['closed_signals']}

الإشارات المفتوحة:
{summary['open_signals']}

━━━━━━━━━━━━━━

🎯 تحقيق الهدف الأول:
{summary['tp1_hits']} إشارة
نسبة النجاح: {summary['tp1_success_rate_closed']}%

🏆 تحقيق الهدف الثاني:
{summary['tp2_hits']} إشارة
نسبة النجاح: {summary['tp2_success_rate_closed']}%

🛑 وقف الخسارة:
{summary['stop_losses']} إشارة
النسبة: {summary['stop_loss_rate_closed']}%

⏳ متوسط مدة تحقيق الهدف الأول:
{summary['avg_days_to_tp1']} يوم

━━━━━━━━━━━━━━

راصد يعتمد على:
✓ بيانات Sahmk
✓ فلاتر فنية
✓ إدارة مخاطر
✓ مراجعة ذكاء اصطناعي قبل النشر

تنبيه: الأداء السابق لا يضمن النتائج المستقبلية.
"""


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_rows()

    if not rows:
        print("ℹ️ No published signals yet.")
        SUMMARY_FILE.write_text(
            json.dumps({"total_published": 0}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return 0

    updated = []
    for row in rows:
        updated.append(evaluate_signal(row))

    write_rows(updated)

    summary = build_summary(updated)
    SUMMARY_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_weekly_report(summary)
    REPORT_FILE.write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"✅ Updated performance tracking: {PUBLISHED_FILE}")
    print(f"✅ Weekly report created: {REPORT_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())