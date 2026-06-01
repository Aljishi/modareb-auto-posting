#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_track_record.py
يُنشئ صفحة HTML على GitHub Pages تعرض سجل الإشارات وإحصائياتها.
يُستدعى من track-results job في post.yml.
"""

import json, sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DOCS_DIR = Path(__file__).parent.parent / "docs"


def load_data():
    # إحصائيات من track_record.json
    stats = {}
    tr = DATA_DIR / "track_record.json"
    if tr.exists():
        stats = json.load(open(tr, encoding="utf-8"))

    # تفاصيل الإشارات من open_signals.json
    signals = []
    os_file = DATA_DIR / "open_signals.json"
    if os_file.exists():
        try:
            signals = json.load(open(os_file, encoding="utf-8"))
        except Exception:
            signals = []

    return stats, signals


def status_label(status):
    return {
        "open":        ("⏳ مفتوحة",   "#3B82F6"),
        "target1_hit": ("🎯 هدف أول",  "#10B981"),
        "closed":      ("🏆 هدف ثانٍ", "#F59E0B"),
        "stop_hit":    ("🛑 وقف خسارة","#EF4444"),
        "expired":     ("⏰ منتهية",   "#6B7280"),
    }.get(status, ("❓ غير معروف",    "#6B7280"))


def main():
    print("📈 تحديث صفحة Track Record...")
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    stats, signals = load_data()

    total     = stats.get("total",    len(signals))
    target2   = stats.get("target2",   0)
    target1   = stats.get("target1_only", 0)
    stop_hit  = stats.get("stop_hit",  0)
    open_cnt  = stats.get("open",      0)
    win_rate  = stats.get("win_rate",  0)
    updated   = datetime.now().strftime("%Y-%m-%d %H:%M")

    # بناء صفوف الجدول
    rows_html = ""
    for entry in reversed(signals[-20:]):   # آخر 20 إشارة
        sig    = entry.get("signal", {})
        sym    = sig.get("stock_symbol", sig.get("symbol", ""))
        name   = sig.get("stock_name",   sig.get("name",   ""))
        score  = sig.get("score",  0)
        t1     = sig.get("target1_percent", "")
        t2     = sig.get("target2_percent", "")
        date   = entry.get("date", "")
        status = entry.get("status", "open")
        label, color = status_label(status)

        rows_html += f"""
        <tr>
          <td>{date}</td>
          <td><b>{sym}</b></td>
          <td>{name}</td>
          <td>{score}/100</td>
          <td>+{t1}% / +{t2}%</td>
          <td style="color:{color};font-weight:bold">{label}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>راصد — Track Record</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Cairo',Arial,sans-serif;background:#080D1A;color:#E2E8F0;padding:20px}}
    .container{{max-width:900px;margin:0 auto}}
    h1{{color:#D4AF37;text-align:center;font-size:2rem;margin:20px 0 4px}}
    .updated{{text-align:center;color:#7B8BA4;font-size:.85rem;margin-bottom:30px}}
    .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:32px}}
    .card{{background:#0F1525;border-radius:12px;padding:20px;text-align:center}}
    .card-value{{font-size:2rem;font-weight:bold;color:#D4AF37}}
    .card-label{{color:#7B8BA4;font-size:.85rem;margin-top:6px}}
    .card.green .card-value{{color:#10B981}}
    .card.red   .card-value{{color:#EF4444}}
    table{{width:100%;border-collapse:collapse;background:#0F1525;border-radius:12px;overflow:hidden}}
    th{{background:#1A2540;color:#D4AF37;padding:12px;text-align:right;font-size:.9rem}}
    td{{padding:12px;border-bottom:1px solid #1A2540;font-size:.9rem}}
    tr:last-child td{{border-bottom:none}}
    tr:hover td{{background:#131d33}}
  </style>
</head>
<body>
  <div class="container">
    <h1>👁️ راصد — سجل الإشارات</h1>
    <p class="updated">آخر تحديث: {updated}</p>

    <div class="cards">
      <div class="card"><div class="card-value">{total}</div><div class="card-label">إجمالي الإشارات</div></div>
      <div class="card green"><div class="card-value">{target2}</div><div class="card-label">هدف ثانٍ ✅</div></div>
      <div class="card green"><div class="card-value">{target1}</div><div class="card-label">هدف أول 🎯</div></div>
      <div class="card red"><div class="card-value">{stop_hit}</div><div class="card-label">وقف خسارة 🛑</div></div>
      <div class="card"><div class="card-value">{open_cnt}</div><div class="card-label">مفتوحة ⏳</div></div>
      <div class="card green"><div class="card-value">{win_rate}%</div><div class="card-label">نسبة النجاح</div></div>
    </div>

    <h2 style="color:#D4AF37;margin-bottom:12px">📋 آخر الإشارات</h2>
    <table>
      <tr><th>التاريخ</th><th>الرمز</th><th>الاسم</th><th>Score</th><th>الأهداف</th><th>الحالة</th></tr>
      {rows_html if rows_html else '<tr><td colspan="6" style="text-align:center;color:#7B8BA4">لا توجد إشارات بعد</td></tr>'}
    </table>
  </div>
</body>
</html>"""

    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"✅ Track Record محدَّث: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
