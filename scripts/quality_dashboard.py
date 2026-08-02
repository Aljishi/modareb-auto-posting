#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Daily Quality Dashboard v1

يبني لوحة شفافية يومية من ملفات النظام الحالية، دون أي طلب API إضافي.

المدخلات الرئيسية:
- daily.json
- data_quality.json
- market_fetch_status.json
- market_regime.json
- rejection_report.json / no_signal_report.json
- signals.json
- validated_signals.json
- portfolio_exposure_report.json
- confidence_calibration.json

المخرجات:
- data/quality_dashboard.json
- data/quality_dashboard_message.txt
- docs/quality.html
"""

from __future__ import annotations

import html
import json
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"

DAILY = DATA / "daily.json"
QUALITY = DATA / "data_quality.json"
FETCH = DATA / "market_fetch_status.json"
REGIME = DATA / "market_regime.json"
REJECTION = DATA / "rejection_report.json"
NO_SIGNAL = DATA / "no_signal_report.json"
SIGNALS = DATA / "signals.json"
VALIDATED = DATA / "validated_signals.json"
EXPOSURE = DATA / "portfolio_exposure_report.json"
CALIBRATION = DATA / "confidence_calibration.json"

OUT_JSON = DATA / "quality_dashboard.json"
OUT_MESSAGE = DATA / "quality_dashboard_message.txt"
OUT_HTML = DOCS / "quality.html"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def fnum(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def read(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"⚠️ {path.name}: {exc}")
    return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def rows(payload: Any, *keys: str) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def stock_change(stock: Dict[str, Any]) -> float:
    return fnum(
        stock.get("change_percent")
        if "change_percent" in stock
        else stock.get("change_pct")
    )


def stock_value(stock: Dict[str, Any]) -> float:
    return fnum(
        stock.get("value")
        or stock.get("turnover")
        or stock.get("traded_value")
    )


def top_sector(stocks: List[Dict[str, Any]]) -> Tuple[str, float, int]:
    grouped: Dict[str, List[float]] = {}
    for stock in stocks:
        sector = str(
            stock.get("sector")
            or stock.get("sector_name")
            or "غير محدد"
        ).strip()
        grouped.setdefault(sector, []).append(stock_change(stock))

    candidates = []
    for sector, changes in grouped.items():
        if sector == "غير محدد" or not changes:
            continue
        candidates.append((sum(changes) / len(changes), sector, len(changes)))

    if not candidates:
        return "غير متوفر", 0.0, 0

    average, sector, count = max(candidates)
    return sector, round(average, 2), count


def best_stock(stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not stocks:
        return {}
    best = max(
        stocks,
        key=lambda item: (
            stock_change(item),
            stock_value(item),
        ),
    )
    return {
        "symbol": str(best.get("symbol", "")),
        "name": str(best.get("name") or best.get("name_ar") or ""),
        "change_pct": round(stock_change(best), 2),
        "value": round(stock_value(best), 2),
    }


def rejection_data() -> Dict[str, Any]:
    primary = read(REJECTION, {})
    if isinstance(primary, dict) and primary:
        return primary
    secondary = read(NO_SIGNAL, {})
    return secondary if isinstance(secondary, dict) else {}


def dominant_rejection(report: Dict[str, Any]) -> Tuple[str, int]:
    categories = report.get("categories", {})
    if not isinstance(categories, dict) or not categories:
        return "لا توجد بيانات", 0

    normalized = []
    for category, count in categories.items():
        normalized.append((int(fnum(count)), str(category)))
    count, category = max(normalized)
    return category, count


def build() -> Dict[str, Any]:
    daily = read(DAILY, {})
    quality = read(QUALITY, {})
    fetch = read(FETCH, {})
    regime = read(REGIME, {})
    rejection = rejection_data()
    signals_payload = read(SIGNALS, {})
    validated_payload = read(VALIDATED, {})
    exposure = read(EXPOSURE, {})
    calibration = read(CALIBRATION, {})

    stocks = rows(daily, "stocks")
    generated = rows(signals_payload, "signals")
    validated = rows(validated_payload, "validated_signals", "signals")

    sector, sector_avg, sector_members = top_sector(stocks)
    best = best_stock(stocks)
    reject_name, reject_count = dominant_rejection(rejection)

    advance_count = sum(1 for x in stocks if stock_change(x) > 0.05)
    decline_count = sum(1 for x in stocks if stock_change(x) < -0.05)
    unchanged_count = max(0, len(stocks) - advance_count - decline_count)

    confidence_rows = (
        calibration.get("signals", [])
        if isinstance(calibration, dict)
        else []
    )
    if not isinstance(confidence_rows, list):
        confidence_rows = []

    return {
        "status": "PASS",
        "engine": "rased_quality_dashboard_v1",
        "generated_at": now_iso(),
        "data_timestamp": (
            daily.get("generated_at") if isinstance(daily, dict) else None
        ),
        "provider": (
            daily.get("provider") if isinstance(daily, dict) else None
        ),
        "system_health": {
            "fetch_status": (
                fetch.get("status", "UNKNOWN") if isinstance(fetch, dict) else "UNKNOWN"
            ),
            "data_quality_status": (
                quality.get("status", "UNKNOWN")
                if isinstance(quality, dict)
                else "UNKNOWN"
            ),
            "data_quality_score": (
                fnum(quality.get("score"))
                if isinstance(quality, dict)
                else 0.0
            ),
            "stocks_received": len(stocks),
            "valid_stocks": (
                int(fnum(quality.get("valid_stocks")))
                if isinstance(quality, dict)
                else 0
            ),
        },
        "market": {
            "regime": regime.get("regime", "UNKNOWN"),
            "regime_ar": regime.get("regime_ar", "غير متوفر"),
            "posture": regime.get("posture", ""),
            "average_change_pct": fnum(regime.get("average_change_pct")),
            "advance_ratio": fnum(regime.get("advance_ratio")),
            "dispersion": fnum(regime.get("dispersion")),
            "dynamic_min_score": (
                regime.get("filter_profile", {}).get("MIN_SIGNAL_SCORE")
                if isinstance(regime.get("filter_profile"), dict)
                else None
            ),
            "advancing": advance_count,
            "declining": decline_count,
            "unchanged": unchanged_count,
        },
        "screening": {
            "screened": int(
                fnum(
                    signals_payload.get("total_screened", len(stocks))
                    if isinstance(signals_payload, dict)
                    else len(stocks)
                )
            ),
            "rejected": int(fnum(rejection.get("total_rejected"))),
            "generated": len(generated),
            "validated": len(validated),
            "dominant_rejection": reject_name,
            "dominant_rejection_count": reject_count,
            "categories": (
                rejection.get("categories", {})
                if isinstance(rejection.get("categories"), dict)
                else {}
            ),
        },
        "leadership": {
            "best_sector": sector,
            "best_sector_avg_change_pct": sector_avg,
            "best_sector_members": sector_members,
            "best_stock": best,
        },
        "portfolio_exposure": {
            "active_open_positions": int(
                fnum(exposure.get("active_open_positions"))
            ),
            "approved_after_gate": int(
                fnum(exposure.get("approved_signals"))
            ),
            "rejected_by_gate": int(
                fnum(exposure.get("rejected_signals"))
            ),
        },
        "confidence_calibration": {
            "status": (
                calibration.get("status", "UNKNOWN")
                if isinstance(calibration, dict)
                else "UNKNOWN"
            ),
            "closed_history_sample": int(
                fnum(calibration.get("closed_history_sample"))
                if isinstance(calibration, dict)
                else 0
            ),
            "signals_calibrated": len(confidence_rows),
        },
        "validated_signals": [
            {
                "symbol": item.get("symbol") or item.get("stock_symbol"),
                "name": item.get("name") or item.get("stock_name"),
                "sector": item.get("sector") or item.get("sector_name"),
                "rased_score": fnum(item.get("rased_score")),
                "confidence": (
                    item.get("calibrated_confidence")
                    or item.get("confidence")
                ),
            }
            for item in validated[:5]
        ],
    }


def message(data: Dict[str, Any]) -> str:
    health = data["system_health"]
    market = data["market"]
    screening = data["screening"]
    leadership = data["leadership"]
    best = leadership.get("best_stock", {})

    lines = [
        "📊 راصد | لوحة جودة السوق اليومية",
        "",
        f"🧭 حالة السوق: {market['regime_ar']} — {market['posture']}",
        f"🎯 حد راصد الحالي: {market['dynamic_min_score']}",
        (
            f"📈 اتساع السوق: {market['advancing']} صاعد | "
            f"{market['declining']} هابط | {market['unchanged']} دون تغير"
        ),
        "",
        f"🔍 الأسهم المفحوصة: {screening['screened']}",
        f"✅ الإشارات المولدة: {screening['generated']}",
        f"🟢 الإشارات المجازة: {screening['validated']}",
        f"⛔ المرفوضة: {screening['rejected']}",
        (
            f"📌 أبرز سبب رفض: {screening['dominant_rejection']} "
            f"({screening['dominant_rejection_count']})"
        ),
        "",
        (
            f"🏆 أقوى قطاع: {leadership['best_sector']} "
            f"({leadership['best_sector_avg_change_pct']:+.2f}%)"
        ),
    ]

    if best:
        lines.append(
            f"⭐ أفضل سهم حركة: {best.get('name') or best.get('symbol')} "
            f"({best.get('symbol')}) {best.get('change_pct', 0):+.2f}%"
        )

    lines.extend(
        [
            "",
            (
                f"🛡️ جودة البيانات: {health['data_quality_status']} "
                f"({health['data_quality_score']:.1f}%)"
            ),
            f"📡 حالة الجلب: {health['fetch_status']}",
            "",
            "تنبيه: قراءة آلية معلوماتية وليست توصية استثمارية شخصية.",
        ]
    )

    return "\n".join(lines)


def render_html(data: Dict[str, Any]) -> str:
    health = data["system_health"]
    market = data["market"]
    screening = data["screening"]
    leadership = data["leadership"]

    category_rows = ""
    categories = screening.get("categories", {})
    if isinstance(categories, dict):
        for category, count in sorted(
            categories.items(),
            key=lambda item: fnum(item[1]),
            reverse=True,
        ):
            category_rows += (
                f"<tr><td>{html.escape(str(category))}</td>"
                f"<td>{int(fnum(count))}</td></tr>"
            )

    signal_rows = ""
    for item in data.get("validated_signals", []):
        signal_rows += (
            "<tr>"
            f"<td>{html.escape(str(item.get('symbol', '')))}</td>"
            f"<td>{html.escape(str(item.get('name', '')))}</td>"
            f"<td>{html.escape(str(item.get('sector', '')))}</td>"
            f"<td>{fnum(item.get('rased_score')):.1f}</td>"
            f"<td>{html.escape(str(item.get('confidence', '')))}</td>"
            "</tr>"
        )

    if not signal_rows:
        signal_rows = "<tr><td colspan='5'>لا توجد إشارة مجازة في آخر تشغيل</td></tr>"

    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>راصد — لوحة الجودة</title>
<style>
body{{font-family:Arial,Tahoma,sans-serif;background:#071127;color:#eef3ff;margin:0}}
.wrap{{max-width:1100px;margin:auto;padding:24px}}
h1{{margin:0 0 6px;color:#d4af37}} .sub{{color:#a9b6d3;margin-bottom:22px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}
.card{{background:#101d3c;border:1px solid #243761;border-radius:14px;padding:18px}}
.value{{font-size:28px;font-weight:700;margin-top:8px}} .good{{color:#63d69b}}
.warn{{color:#f0c96a}} .muted{{color:#a9b6d3}}
table{{width:100%;border-collapse:collapse;background:#101d3c;border-radius:12px;overflow:hidden}}
th,td{{padding:12px;border-bottom:1px solid #243761;text-align:right}}
th{{color:#d4af37}} h2{{margin-top:26px}}
.footer{{margin-top:26px;color:#93a2c4;font-size:13px}}
</style>
</head>
<body><div class="wrap">
<h1>راصد | لوحة جودة السوق</h1>
<div class="sub">آخر تحديث: {html.escape(data['generated_at'])}</div>

<div class="grid">
<div class="card"><div class="muted">حالة السوق</div><div class="value">{html.escape(str(market['regime_ar']))}</div><div>{html.escape(str(market['posture']))}</div></div>
<div class="card"><div class="muted">الأسهم المفحوصة</div><div class="value">{screening['screened']}</div></div>
<div class="card"><div class="muted">الإشارات المجازة</div><div class="value good">{screening['validated']}</div></div>
<div class="card"><div class="muted">الإشارات المرفوضة</div><div class="value warn">{screening['rejected']}</div></div>
<div class="card"><div class="muted">جودة البيانات</div><div class="value">{health['data_quality_score']:.1f}%</div><div>{html.escape(str(health['data_quality_status']))}</div></div>
<div class="card"><div class="muted">أقوى قطاع</div><div class="value">{html.escape(str(leadership['best_sector']))}</div><div>{leadership['best_sector_avg_change_pct']:+.2f}%</div></div>
</div>

<h2>أسباب الرفض</h2>
<table><thead><tr><th>الفئة</th><th>العدد</th></tr></thead><tbody>{category_rows or "<tr><td colspan='2'>لا توجد بيانات</td></tr>"}</tbody></table>

<h2>الإشارات المجازة</h2>
<table><thead><tr><th>الرمز</th><th>الشركة</th><th>القطاع</th><th>راصد</th><th>الثقة</th></tr></thead><tbody>{signal_rows}</tbody></table>

<div class="footer">المحتوى معلوماتي وتعليمي ولا يُعد توصية استثمارية شخصية.</div>
</div></body></html>"""


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    dashboard = build()
    dashboard_message = message(dashboard)
    dashboard_html = render_html(dashboard)

    write_json(OUT_JSON, dashboard)
    OUT_MESSAGE.write_text(dashboard_message, encoding="utf-8")
    OUT_HTML.write_text(dashboard_html, encoding="utf-8")

    print(dashboard_message)
    print(f"✅ JSON: {OUT_JSON}")
    print(f"✅ HTML: {OUT_HTML}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
