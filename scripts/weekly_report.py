#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — RASED Investor Weekly Review v2.0

الهدف:
- تحويل التقرير الأسبوعي من عدّ الأهداف فقط إلى تقرير أداء قابل للتقييم.
- فصل "الإشارات المنشورة هذا الأسبوع" عن "الإشارات التي أغلقت هذا الأسبوع".
- حساب العائد التقريبي، التوقع الرياضي، Profit Factor، Payoff Ratio، وسلاسل الخسارة.
- إظهار حجم العينة صراحةً ومنع إعطاء انطباع زائف بالدقة.
- إضافة سياق السوق الحالي والقطاعات القيادية.

المدخلات:
- data/published_signals.csv
- data/signal_performance_summary.json
- data/market_brief.json
- data/market_regime.json
- data/sector_rotation.json
- data/quality_dashboard.json

المخرجات:
- data/weekly_report.json
- data/weekly_performance_report.txt
"""

from __future__ import annotations

import csv
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PUBLISHED_FILE = DATA_DIR / "published_signals.csv"
SUMMARY_FILE = DATA_DIR / "signal_performance_summary.json"
MARKET_BRIEF_FILE = DATA_DIR / "market_brief.json"
MARKET_REGIME_FILE = DATA_DIR / "market_regime.json"
SECTOR_ROTATION_FILE = DATA_DIR / "sector_rotation.json"
QUALITY_DASHBOARD_FILE = DATA_DIR / "quality_dashboard.json"

WEEKLY_REPORT_JSON = DATA_DIR / "weekly_report.json"
WEEKLY_REPORT_TXT = DATA_DIR / "weekly_performance_report.txt"

ENGINE_VERSION = "rased_investor_weekly_review_v2_0"
CLOSED_STATUSES = {"TP1", "TP2", "SL", "EXPIRED"}


def fnum(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "").replace("%", "").strip())
    except Exception:
        return default


def fint(value: Any, default: int = 0) -> int:
    try:
        return int(round(fnum(value, default)))
    except Exception:
        return default


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"⚠️ cannot read {path.name}: {exc}")
    return default


def read_csv_rows() -> List[Dict[str, str]]:
    if not PUBLISHED_FILE.exists():
        return []
    with PUBLISHED_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_dt(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(text[:10])
    except Exception:
        return None


def in_period(dt: Optional[datetime], start: date, end: date) -> bool:
    return bool(dt and start <= dt.date() <= end)


def pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100.0, 1) if denominator else 0.0


def moneyless_ratio(value: float) -> str:
    if math.isinf(value):
        return "∞"
    return f"{value:.2f}"


def realized_return_pct(row: Dict[str, str]) -> Optional[float]:
    status = str(row.get("status") or "").upper().strip()

    explicit_keys = (
        "realized_return_pct",
        "return_pct",
        "result_pct",
        "pnl_pct",
    )
    for key in explicit_keys:
        raw = str(row.get(key) or "").strip()
        if raw:
            return fnum(raw)

    if status == "TP2":
        return fnum(row.get("target2_percent"))
    if status == "TP1":
        return fnum(row.get("target1_percent"))
    if status == "SL":
        return -abs(fnum(row.get("stop_loss_percent")))
    if status == "EXPIRED":
        return None
    return None


def close_date(row: Dict[str, str]) -> Optional[datetime]:
    return parse_dt(row.get("closed_at"))


def published_date(row: Dict[str, str]) -> Optional[datetime]:
    return parse_dt(row.get("published_at"))


def reliability_label(closed_count: int) -> str:
    if closed_count < 10:
        return "غير كافية للحكم"
    if closed_count < 30:
        return "أولية"
    if closed_count < 100:
        return "متوسطة"
    return "قوية نسبيًا"


def sample_warning(closed_count: int) -> str:
    if closed_count < 10:
        return "العينة شديدة الصغر؛ لا تستخدم نسب النجاح لاتخاذ قرار مستقل."
    if closed_count < 30:
        return "العينة أقل من 30 إشارة مغلقة؛ الأرقام اتجاهية وليست نهائية."
    return "العينة أصبحت قابلة للمقارنة، مع بقاء الأداء السابق غير ضامن للمستقبل."


def outcome_stats(rows: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    closed = [row for row in rows if str(row.get("status") or "").upper() in CLOSED_STATUSES]
    open_rows = [row for row in rows if str(row.get("status") or "").upper() == "OPEN"]
    wins = [
        row for row in closed
        if str(row.get("status") or "").upper() in {"TP1", "TP2"}
    ]
    tp2 = [row for row in closed if str(row.get("status") or "").upper() == "TP2"]
    losses = [row for row in closed if str(row.get("status") or "").upper() == "SL"]
    expired = [row for row in closed if str(row.get("status") or "").upper() == "EXPIRED"]

    returns = [
        r for r in (realized_return_pct(row) for row in closed) if r is not None
    ]
    positive_returns = [r for r in returns if r > 0]
    negative_returns = [r for r in returns if r < 0]

    gross_profit = sum(positive_returns)
    gross_loss = abs(sum(negative_returns))
    profit_factor = (
        gross_profit / gross_loss if gross_loss > 0
        else (math.inf if gross_profit > 0 else 0.0)
    )

    avg_win = mean(positive_returns) if positive_returns else 0.0
    avg_loss = abs(mean(negative_returns)) if negative_returns else 0.0
    payoff_ratio = (
        avg_win / avg_loss if avg_loss > 0
        else (math.inf if avg_win > 0 else 0.0)
    )

    days_tp1 = [
        fnum(row.get("days_to_tp1"))
        for row in wins
        if str(row.get("days_to_tp1") or "").strip()
    ]
    days_tp2 = [
        fnum(row.get("days_to_tp2"))
        for row in tp2
        if str(row.get("days_to_tp2") or "").strip()
    ]

    return {
        "published": len(rows),
        "closed": len(closed),
        "open": len(open_rows),
        "wins": len(wins),
        "tp1_or_better": len(wins),
        "tp2_hits": len(tp2),
        "stop_losses": len(losses),
        "expired": len(expired),
        "win_rate_closed": pct(len(wins), len(closed)),
        "tp2_rate_closed": pct(len(tp2), len(closed)),
        "stop_rate_closed": pct(len(losses), len(closed)),
        "evaluated_return_count": len(returns),
        "expectancy_pct": round(mean(returns), 2) if returns else 0.0,
        "gross_profit_pct_points": round(gross_profit, 2),
        "gross_loss_pct_points": round(gross_loss, 2),
        "profit_factor": profit_factor,
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "payoff_ratio": payoff_ratio,
        "avg_days_to_tp1": round(mean(days_tp1), 1) if days_tp1 else 0.0,
        "avg_days_to_tp2": round(mean(days_tp2), 1) if days_tp2 else 0.0,
        "reliability": reliability_label(len(closed)),
    }


def max_loss_streak(rows: Sequence[Dict[str, str]]) -> int:
    closed = [
        row for row in rows
        if str(row.get("status") or "").upper() in CLOSED_STATUSES
    ]
    closed.sort(
        key=lambda row: (
            close_date(row) or published_date(row) or datetime.min
        )
    )

    maximum = 0
    current = 0
    for row in closed:
        if str(row.get("status") or "").upper() == "SL":
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def best_worst(rows: Sequence[Dict[str, str]]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    evaluated: List[Dict[str, Any]] = []
    for row in rows:
        ret = realized_return_pct(row)
        if ret is None:
            continue
        evaluated.append(
            {
                "symbol": row.get("symbol", ""),
                "name": row.get("name", ""),
                "status": row.get("status", ""),
                "return_pct": round(ret, 2),
                "published_at": row.get("published_at", ""),
                "closed_at": row.get("closed_at", ""),
            }
        )

    if not evaluated:
        return None, None

    return (
        max(evaluated, key=lambda x: x["return_pct"]),
        min(evaluated, key=lambda x: x["return_pct"]),
    )


def group_performance(
    rows: Sequence[Dict[str, str]],
    key: str,
    minimum_closed: int = 2,
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, str]]] = {}

    for row in rows:
        group = str(row.get(key) or "غير محدد").strip() or "غير محدد"
        groups.setdefault(group, []).append(row)

    result: List[Dict[str, Any]] = []

    for group, items in groups.items():
        stats = outcome_stats(items)
        if stats["closed"] < minimum_closed:
            continue
        result.append(
            {
                "group": group,
                "published": stats["published"],
                "closed": stats["closed"],
                "win_rate_closed": stats["win_rate_closed"],
                "expectancy_pct": stats["expectancy_pct"],
                "profit_factor": stats["profit_factor"],
            }
        )

    result.sort(
        key=lambda row: (
            row["expectancy_pct"],
            row["win_rate_closed"],
        ),
        reverse=True,
    )
    return result


def current_market_context() -> Dict[str, Any]:
    brief = load_json(MARKET_BRIEF_FILE, {})
    regime = load_json(MARKET_REGIME_FILE, {})
    rotation = load_json(SECTOR_ROTATION_FILE, {})
    quality = load_json(QUALITY_DASHBOARD_FILE, {})

    market_score = brief.get("market_score", {}) if isinstance(brief, dict) else {}
    full_market = brief.get("full_market", {}) if isinstance(brief, dict) else {}
    sectors = rotation.get("top_sectors", []) if isinstance(rotation, dict) else []

    return {
        "market_score": fnum(market_score.get("score")),
        "market_label": str(market_score.get("label") or ""),
        "market_risk": str(market_score.get("risk") or ""),
        "index_value": fnum(full_market.get("index_value")),
        "index_change_pct": fnum(full_market.get("index_change_pct")),
        "breadth_pct": fnum(full_market.get("breadth_pct")),
        "regime": str(regime.get("regime_ar") or regime.get("regime") or ""),
        "posture": str(regime.get("posture") or ""),
        "top_sectors": [
            {
                "sector": str(row.get("sector") or ""),
                "rotation_score": fnum(row.get("rotation_score")),
                "grade": str(row.get("grade") or ""),
                "avg_change_pct": fnum(row.get("avg_change_pct")),
                "advancing_ratio": fnum(row.get("advancing_ratio")),
            }
            for row in sectors[:3]
            if isinstance(row, dict)
        ],
        "data_quality_score": fnum(
            quality.get("system_health", {}).get("data_quality_score")
            if isinstance(quality, dict)
            else 0
        ),
    }


def build_report() -> Tuple[Dict[str, Any], str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = read_csv_rows()
    summary = load_json(SUMMARY_FILE, {})

    today = datetime.now().date()
    period_start = today - timedelta(days=6)

    published_this_week = [
        row for row in rows
        if in_period(published_date(row), period_start, today)
    ]
    closed_this_week = [
        row for row in rows
        if in_period(close_date(row), period_start, today)
    ]

    all_stats = outcome_stats(rows)
    published_week_stats = outcome_stats(published_this_week)
    closed_week_stats = outcome_stats(closed_this_week)

    best_all, worst_all = best_worst(rows)
    best_week, worst_week = best_worst(closed_this_week)

    report = {
        "engine_version": ENGINE_VERSION,
        "week_start": period_start.isoformat(),
        "week_end": today.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "all_time": all_stats,
        "this_week": {
            "published_count": len(published_this_week),
            "closed_count": len(closed_this_week),
            "published_cohort": published_week_stats,
            "closed_during_week": closed_week_stats,
        },
        "risk_statistics": {
            "max_consecutive_stop_losses": max_loss_streak(rows),
        },
        "best_all_time": best_all,
        "worst_all_time": worst_all,
        "best_this_week": best_week,
        "worst_this_week": worst_week,
        "by_tier": group_performance(rows, "tier"),
        "by_signal_type": group_performance(rows, "signal_type"),
        "market_context": current_market_context(),
        "sample_quality": {
            "closed_sample": all_stats["closed"],
            "reliability": all_stats["reliability"],
            "warning": sample_warning(all_stats["closed"]),
        },
        "raw_summary": summary,
        "note": (
            "العائد المحقق تقديري وفق حالة الإغلاق المسجلة: TP1=نسبة الهدف الأول، "
            "TP2=نسبة الهدف الثاني، SL=-نسبة وقف الخسارة. "
            "EXPIRED لا يدخل في حساب العائد ما لم يتوفر عائد فعلي."
        ),
    }

    text = build_text(report)
    WEEKLY_REPORT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    WEEKLY_REPORT_TXT.write_text(text, encoding="utf-8")
    return report, text


def signal_line(item: Optional[Dict[str, Any]]) -> str:
    if not item:
        return "لا توجد بيانات كافية"
    return (
        f"{item.get('name') or item.get('symbol')} ({item.get('symbol')}) "
        f"{item.get('return_pct'):+.2f}% | {item.get('status')}"
    )


def build_text(report: Dict[str, Any]) -> str:
    all_stats = report["all_time"]
    week = report["this_week"]
    closed_week = week["closed_during_week"]
    market = report.get("market_context", {})
    sample = report.get("sample_quality", {})

    pf = all_stats.get("profit_factor", 0.0)
    payoff = all_stats.get("payoff_ratio", 0.0)

    lines: List[str] = [
        "📊 RASED INVESTOR WEEKLY REVIEW",
        "تقرير راصد الأسبوعي — أداء النظام + حالة السوق",
        "━━━━━━━━━━━━━━",
        f"📅 {report.get('week_start')} إلى {report.get('week_end')}",
        "",
        "🎯 أداء راصد — السجل الكامل",
        f"• منشور: {all_stats['published']} | مغلق: {all_stats['closed']} | مفتوح: {all_stats['open']}",
        f"• نسبة النجاح من المغلق: {all_stats['win_rate_closed']:.1f}% | "
        f"TP2: {all_stats['tp2_rate_closed']:.1f}% | SL: {all_stats['stop_rate_closed']:.1f}%",
        f"• Expectancy لكل إشارة مقيمة: {all_stats['expectancy_pct']:+.2f}%",
        f"• Profit Factor: {moneyless_ratio(pf)} | Payoff Ratio: {moneyless_ratio(payoff)}",
        f"• متوسط الربح/الخسارة: +{all_stats['avg_win_pct']:.2f}% / -{all_stats['avg_loss_pct']:.2f}%",
        f"• متوسط الوصول TP1/TP2: {all_stats['avg_days_to_tp1']:.1f} / {all_stats['avg_days_to_tp2']:.1f} يوم",
        f"• أقصى سلسلة وقف خسارة: {fint(report.get('risk_statistics', {}).get('max_consecutive_stop_losses'))}",
        "",
        "🧪 جودة العينة",
        f"• الإشارات المغلقة: {fint(sample.get('closed_sample'))} — موثوقية العينة: {sample.get('reliability')}",
        f"• {sample.get('warning')}",
        "",
        "📆 هذا الأسبوع",
        f"• نُشرت {fint(week.get('published_count'))} إشارة | أُغلقت {fint(week.get('closed_count'))} إشارة خلال الفترة",
        f"• نتائج المغلق هذا الأسبوع: نجاح {closed_week['win_rate_closed']:.1f}% | "
        f"SL {closed_week['stop_rate_closed']:.1f}% | Expectancy {closed_week['expectancy_pct']:+.2f}%",
        f"• أفضل إغلاق: {signal_line(report.get('best_this_week'))}",
        f"• أضعف إغلاق: {signal_line(report.get('worst_this_week'))}",
        "",
        "🇸🇦 حالة السوق الحالية",
        f"• TASI: {fnum(market.get('index_value')):,.2f} | {fnum(market.get('index_change_pct')):+.2f}%",
        f"• صحة السوق: {fnum(market.get('market_score')):.1f}/100 — "
        f"{market.get('market_label') or market.get('regime')} | المخاطرة: {market.get('market_risk')}",
        f"• اتساع السوق: {fnum(market.get('breadth_pct')):.1f}% | "
        f"وضع راصد: {market.get('posture') or 'غير متوفر'}",
    ]

    top_sectors = market.get("top_sectors", [])
    if top_sectors:
        lines.extend(["", "🏭 القطاعات القيادية الآن"])
        for row in top_sectors[:3]:
            lines.append(
                f"• {row.get('sector')}: دوران {fnum(row.get('rotation_score')):.1f}/100 | "
                f"{row.get('grade')} | اتساع {fnum(row.get('advancing_ratio')) * 100:.0f}%"
            )

    if report.get("by_tier"):
        lines.extend(["", "📐 أين يعمل النظام أفضل؟"])
        for row in report["by_tier"][:3]:
            lines.append(
                f"• {row.get('group')}: عينة {fint(row.get('closed'))} | "
                f"نجاح {fnum(row.get('win_rate_closed')):.1f}% | "
                f"Expectancy {fnum(row.get('expectancy_pct')):+.2f}%"
            )

    lines.extend(
        [
            "",
            "🧠 قراءة للمستثمر",
            "• لا تُقيّم جودة راصد بنسبة النجاح وحدها؛ راقب Expectancy وProfit Factor وحجم العينة معًا.",
            "• عند ضعف اتساع السوق، يقل وزن أي إشارة منفردة مهما كان Score مرتفعًا.",
            "• إذا بقيت العينة صغيرة، الأفضل تشديد الفلاتر بدل استنتاج أن النظام ناجح أو فاشل مبكرًا.",
            "",
            "📌 ما الذي يجب تحسينه الأسبوع القادم؟",
        ]
    )

    if all_stats["closed"] < 10:
        lines.append("• الأولوية: زيادة عينة الإشارات المغلقة مع الحفاظ على الجودة؛ لا تخفف الفلاتر فقط لزيادة العدد.")
    if all_stats["stop_rate_closed"] > 45 and all_stats["closed"] >= 2:
        lines.append("• راجع إشارات المطاردة وR:R والباك تست قبل النشر؛ نسبة SL الحالية مرتفعة.")
    if fnum(market.get("breadth_pct")) < 45:
        lines.append("• اجعل بيئة السوق الضعيفة عامل تشديد إضافي في قبول الإشارات.")
    if not lines[-1].startswith("•"):
        lines.append("• استمر في معايرة الثقة والباك تست وربطهما بمستوى المخاطرة.")

    lines.extend(
        [
            "",
            "⚠️ الأداء السابق لا يضمن النتائج المستقبلية. التقرير تحليلي وتعليمي آلي.",
            "#راصد #تاسي #السوق_السعودي",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    print("=" * 64)
    print("📊 RASED Investor Weekly Review v2.0")
    print("=" * 64)
    _, text = build_report()
    print(text)
    print(f"✅ Saved: {WEEKLY_REPORT_JSON}")
    print(f"✅ Saved: {WEEKLY_REPORT_TXT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
