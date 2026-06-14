#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Subscriber Dashboard Builder
ينتج docs/index.html من بيانات الإشارات، الأداء، المحفظة، ودوران القطاعات.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
OUTPUT_FILE = DOCS_DIR / "index.html"


def load_json(name: str, default: Any) -> Any:
    path = DATA_DIR / name
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace(",", "").replace("%", "").strip()
        return float(x)
    except Exception:
        return default


def extract_signals(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("validated_signals") or data.get("signals") or []
    return []


def esc(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def build_rows(items: List[Dict[str, Any]], kind: str) -> str:
    if not items:
        return '<tr><td colspan="7">لا توجد بيانات حالياً</td></tr>'
    rows = []
    for item in items[:8]:
        if kind == "signals":
            rows.append(
                f"<tr><td>{esc(item.get('symbol') or item.get('stock_symbol'))}</td><td>{esc(item.get('name') or item.get('stock_name'))}</td><td>{esc(item.get('tier'))}</td><td>{fnum(item.get('entry') or item.get('entry_point')):.2f}</td><td>{fnum(item.get('target1')):.2f}</td><td>{fnum(item.get('stop_loss')):.2f}</td><td>{fnum(item.get('rased_score') or item.get('score')):.1f}</td></tr>"
            )
        elif kind == "portfolio":
            rows.append(
                f"<tr><td>{esc(item.get('symbol'))}</td><td>{esc(item.get('name'))}</td><td>{esc(item.get('sector'))}</td><td>{fnum(item.get('weight_pct')):.2f}%</td><td>{fnum(item.get('amount_sar')):,.0f}</td><td>{fnum(item.get('portfolio_risk_pct')):.2f}%</td><td>{esc(item.get('tier'))}</td></tr>"
            )
        else:
            rows.append(
                f"<tr><td>{esc(item.get('sector'))}</td><td>{fnum(item.get('rotation_score')):.1f}</td><td>{esc(item.get('grade'))}</td><td>{fnum(item.get('avg_change_pct')):.2f}%</td><td>{fnum(item.get('advancing_ratio')):.2f}</td><td>{int(fnum(item.get('signals_count')))}</td><td>{fnum(item.get('total_value')):,.0f}</td></tr>"
            )
    return "\n".join(rows)


def build_dashboard() -> str:
    signals_data = load_json("validated_signals.json", {})
    signals = extract_signals(signals_data)
    if not signals:
        signals = extract_signals(load_json("signals.json", {}))

    portfolio = load_json("portfolio_allocation.json", {})
    sector_rotation = load_json("sector_rotation.json", {})
    performance = load_json("signal_performance_summary.json", {})
    track = load_json("track_record.json", {})
    db_summary = load_json("rased_database_summary.json", {})

    positions = portfolio.get("positions", []) if isinstance(portfolio, dict) else []
    sectors = sector_rotation.get("top_sectors", []) if isinstance(sector_rotation, dict) else []
    win_rate = performance.get("win_rate") or track.get("win_rate") or 0
    total_signals = performance.get("total_signals") or track.get("total_signals") or len(signals)
    avg_return = performance.get("avg_return") or track.get("avg_return") or 0
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    html_doc = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>راصد | لوحة المشتركين</title>
  <style>
    body {{ margin:0; font-family: Tahoma, Arial, sans-serif; background:#0F1A3C; color:#F8F9FA; }}
    .wrap {{ max-width:1180px; margin:auto; padding:28px; }}
    .hero {{ background:linear-gradient(135deg,#1A2744,#0F1A3C); border:1px solid #334155; border-radius:22px; padding:28px; }}
    h1 {{ margin:0 0 8px; color:#D4AF37; font-size:34px; }}
    h2 {{ margin-top:30px; color:#D4AF37; }}
    .muted {{ color:#A4B0BE; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:16px; margin-top:18px; }}
    .card {{ background:#1A2744; border:1px solid #334155; border-radius:18px; padding:18px; }}
    .num {{ font-size:28px; font-weight:bold; color:#F8F9FA; }}
    table {{ width:100%; border-collapse:collapse; background:#1A2744; border-radius:18px; overflow:hidden; }}
    th,td {{ padding:12px; border-bottom:1px solid #334155; text-align:right; }}
    th {{ color:#D4AF37; background:#16213A; }}
    .footer {{ margin-top:30px; color:#A4B0BE; font-size:13px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>راصد — لوحة المشتركين</h1>
      <div class="muted">آخر تحديث: {esc(updated_at)} | منصة أبحاث وتحليلات سوقية آلية</div>
      <div class="grid">
        <div class="card"><div class="muted">عدد الإشارات</div><div class="num">{esc(total_signals)}</div></div>
        <div class="card"><div class="muted">نسبة النجاح</div><div class="num">{fnum(win_rate):.1f}%</div></div>
        <div class="card"><div class="muted">متوسط العائد</div><div class="num">{fnum(avg_return):+.2f}%</div></div>
        <div class="card"><div class="muted">مراكز المحفظة</div><div class="num">{len(positions)}</div></div>
      </div>
    </section>

    <h2>الإشارات الحالية</h2>
    <table><thead><tr><th>الرمز</th><th>الاسم</th><th>الفئة</th><th>الدخول</th><th>هدف 1</th><th>وقف</th><th>راصد</th></tr></thead><tbody>{build_rows(signals, 'signals')}</tbody></table>

    <h2>توزيع المحفظة المقترح</h2>
    <table><thead><tr><th>الرمز</th><th>الاسم</th><th>القطاع</th><th>الوزن</th><th>المبلغ</th><th>مخاطرة المحفظة</th><th>الفئة</th></tr></thead><tbody>{build_rows(positions, 'portfolio')}</tbody></table>

    <h2>دوران القطاعات</h2>
    <table><thead><tr><th>القطاع</th><th>القوة</th><th>التصنيف</th><th>متوسط التغير</th><th>نسبة الصعود</th><th>إشارات</th><th>السيولة</th></tr></thead><tbody>{build_rows(sectors, 'sectors')}</tbody></table>

    <div class="footer">
      قاعدة البيانات: {esc(db_summary.get('database', 'data/rased_research.db'))}<br>
      تنبيه: المحتوى معلوماتي وتعليمي ولا يُعد توصية استثمارية شخصية أو إدارة محفظة.
    </div>
  </div>
</body>
</html>
"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html_doc, encoding="utf-8")
    return html_doc


def main() -> int:
    build_dashboard()
    print(f"✅ Dashboard updated: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
