#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — RASED Investor Daily Brief v2.0

الهدف:
- تحويل التقرير اليومي من "ملخص حركة" إلى "لوحة قرار" مفيدة للمستثمر والمتداول.
- الفصل بين بيانات السوق الكاملة من market_summary وبين عينة راصد.
- دمج اتساع السوق، تركّز السيولة، دوران القطاعات، جودة البيانات، الإشارات، وسجل الأداء.
- عدم تغيير منطق توليد الإشارات أو فلاترها.

المدخلات الاختيارية:
- data/daily.json
- data/signals.json
- data/sector_rotation.json
- data/market_regime.json
- data/quality_dashboard.json
- data/signal_performance_summary.json
- data/portfolio_allocation.json
- data/data_quality.json

المخرجات:
- data/market_brief.json
- data/market_brief.txt
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any, Dict, Iterable, List, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DAILY_FILE = DATA_DIR / "daily.json"
SIGNALS_FILE = DATA_DIR / "signals.json"
SECTOR_ROTATION_FILE = DATA_DIR / "sector_rotation.json"
MARKET_REGIME_FILE = DATA_DIR / "market_regime.json"
QUALITY_DASHBOARD_FILE = DATA_DIR / "quality_dashboard.json"
PERFORMANCE_FILE = DATA_DIR / "signal_performance_summary.json"
PORTFOLIO_FILE = DATA_DIR / "portfolio_allocation.json"
DATA_QUALITY_FILE = DATA_DIR / "data_quality.json"

MARKET_BRIEF_JSON = DATA_DIR / "market_brief.json"
MARKET_BRIEF_TXT = DATA_DIR / "market_brief.txt"

ENGINE_VERSION = "rased_investor_daily_brief_v2_0"


def fnum(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        return float(value)
    except Exception:
        return default


def fint(value: Any, default: int = 0) -> int:
    try:
        return int(round(fnum(value, default)))
    except Exception:
        return default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"⚠️ cannot read {path.name}: {exc}")
    return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def safe_name(stock: Dict[str, Any]) -> str:
    return str(
        stock.get("name")
        or stock.get("name_ar")
        or stock.get("stock_name")
        or stock.get("symbol")
        or stock.get("stock_symbol")
        or "غير معروف"
    ).strip()


def stock_symbol(stock: Dict[str, Any]) -> str:
    return str(stock.get("symbol") or stock.get("stock_symbol") or "").strip()


def stock_price(stock: Dict[str, Any]) -> float:
    return fnum(stock.get("current_price") or stock.get("price") or stock.get("close"))


def stock_change(stock: Dict[str, Any]) -> float:
    return fnum(
        stock.get("change_percent")
        or stock.get("change_pct")
        or stock.get("pct_change")
    )


def stock_sector(stock: Dict[str, Any]) -> str:
    return str(stock.get("sector") or stock.get("sector_name") or "غير مصنف").strip() or "غير مصنف"


def stock_value(stock: Dict[str, Any]) -> float:
    direct = fnum(stock.get("value") or stock.get("turnover"))
    if direct > 0:
        return direct
    return max(0.0, stock_price(stock) * fnum(stock.get("volume")))


def pct_fmt(value: float, signed: bool = True, digits: int = 2) -> str:
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:.{digits}f}%"


def money_fmt(value: float) -> str:
    value = fnum(value)
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f} مليار ريال"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f} مليون ريال"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f} ألف ريال"
    return f"{value:.0f} ريال"


def score_label(score: float) -> str:
    if score >= 70:
        return "إيجابي"
    if score >= 58:
        return "إيجابي انتقائي"
    if score >= 45:
        return "محايد"
    if score >= 35:
        return "محايد مائل للسلبية"
    return "حذر"


def risk_label(
    full_breadth: float,
    sample_dispersion: float,
    top5_concentration: float,
    decline_liquidity_share: float,
) -> str:
    risk_points = 0
    if full_breadth < 40:
        risk_points += 2
    elif full_breadth < 48:
        risk_points += 1

    if sample_dispersion >= 2.4:
        risk_points += 2
    elif sample_dispersion >= 1.7:
        risk_points += 1

    if top5_concentration >= 65:
        risk_points += 1

    if decline_liquidity_share >= 60:
        risk_points += 1

    if risk_points >= 4:
        return "مرتفع"
    if risk_points >= 2:
        return "متوسط مرتفع"
    return "متوسط"


def full_market_snapshot(daily: Dict[str, Any]) -> Dict[str, Any]:
    summary = daily.get("market_summary", {}) if isinstance(daily, dict) else {}
    advancing = fint(summary.get("advancing"))
    declining = fint(summary.get("declining"))
    unchanged = fint(summary.get("unchanged"))
    breadth_den = advancing + declining + unchanged
    breadth = (advancing / breadth_den * 100.0) if breadth_den else 0.0

    return {
        "index": str(summary.get("index") or "TASI"),
        "index_value": fnum(summary.get("index_value")),
        "index_change": fnum(summary.get("index_change")),
        "index_change_pct": fnum(summary.get("index_change_percent")),
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "breadth_pct": round(breadth, 1),
        "total_volume": fnum(summary.get("total_volume")),
        "provider_mood": str(summary.get("market_mood") or ""),
        "is_delayed": bool(summary.get("is_delayed", False)),
        "timestamp": summary.get("timestamp"),
    }


def build_sample_internals(stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    changes = [stock_change(s) for s in stocks]
    values = [stock_value(s) for s in stocks]
    total_value = sum(values)

    advancing = sum(1 for c in changes if c > 0)
    declining = sum(1 for c in changes if c < 0)
    unchanged = max(0, len(stocks) - advancing - declining)

    positive_value = sum(stock_value(s) for s in stocks if stock_change(s) > 0)
    negative_value = sum(stock_value(s) for s in stocks if stock_change(s) < 0)

    sorted_values = sorted(values, reverse=True)
    top5_value = sum(sorted_values[:5])

    return {
        "sample_size": len(stocks),
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "breadth_pct": round((advancing / len(stocks) * 100.0) if stocks else 0.0, 1),
        "avg_change_pct": round(mean(changes), 3) if changes else 0.0,
        "median_change_pct": round(median(changes), 3) if changes else 0.0,
        "dispersion": round(pstdev(changes), 3) if len(changes) > 1 else 0.0,
        "total_value": round(total_value, 2),
        "positive_liquidity_share_pct": round(
            (positive_value / total_value * 100.0) if total_value else 0.0, 1
        ),
        "negative_liquidity_share_pct": round(
            (negative_value / total_value * 100.0) if total_value else 0.0, 1
        ),
        "top5_liquidity_concentration_pct": round(
            (top5_value / total_value * 100.0) if total_value else 0.0, 1
        ),
    }


def rotation_lookup(rotation_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = rotation_data.get("all_sectors", []) if isinstance(rotation_data, dict) else []
    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            sector = str(row.get("sector") or "").strip()
            if sector:
                result[sector] = row
    return result


def build_sector_table(
    stocks: List[Dict[str, Any]],
    rotation_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    total_market_value = sum(stock_value(s) for s in stocks)
    rot = rotation_lookup(rotation_data)

    for stock in stocks:
        groups.setdefault(stock_sector(stock), []).append(stock)

    rows: List[Dict[str, Any]] = []

    for sector, items in groups.items():
        changes = [stock_change(x) for x in items]
        values = [stock_value(x) for x in items]
        sector_value = sum(values)
        advancing = sum(1 for c in changes if c > 0)
        declining = sum(1 for c in changes if c < 0)
        advance_ratio = advancing / len(items) if items else 0.0

        weighted_change = 0.0
        if sector_value > 0:
            weighted_change = sum(
                stock_change(item) * stock_value(item) for item in items
            ) / sector_value

        avg_change = mean(changes) if changes else 0.0
        med_change = median(changes) if changes else 0.0
        value_share = sector_value / total_market_value if total_market_value else 0.0

        rotation_row = rot.get(sector, {})
        rotation_score = fnum(rotation_row.get("rotation_score"))
        rotation_grade = str(rotation_row.get("grade") or "")

        # عندما لا يتوفر sector_rotation نبني درجة بديلة محافظة.
        if rotation_score <= 0:
            momentum_component = clamp(50 + weighted_change * 12, 0, 100)
            breadth_component = advance_ratio * 100
            liquidity_component = clamp(value_share * 300, 0, 100)
            rotation_score = (
                momentum_component * 0.45
                + breadth_component * 0.35
                + liquidity_component * 0.20
            )

        if rotation_score >= 70 and weighted_change > 0:
            tone = "قيادة قوية"
            icon = "🟢"
        elif rotation_score >= 55 and weighted_change >= 0:
            tone = "قيادة إيجابية"
            icon = "🟢"
        elif rotation_score >= 40:
            tone = "محايد"
            icon = "🟡"
        elif weighted_change < -0.8:
            tone = "ضعيف"
            icon = "🔴"
        else:
            tone = "دون المتوسط"
            icon = "🟠"

        rows.append(
            {
                "sector": sector,
                "members": len(items),
                "avg_change_pct": round(avg_change, 2),
                "median_change_pct": round(med_change, 2),
                "liquidity_weighted_change_pct": round(weighted_change, 2),
                "advance_ratio": round(advance_ratio, 3),
                "advancing": advancing,
                "declining": declining,
                "total_value": round(sector_value, 2),
                "liquidity_share_pct": round(value_share * 100.0, 1),
                "rotation_score": round(rotation_score, 1),
                "rotation_grade": rotation_grade,
                "tone": tone,
                "icon": icon,
            }
        )

    rows.sort(
        key=lambda row: (
            fnum(row.get("rotation_score")),
            fnum(row.get("liquidity_weighted_change_pct")),
            fnum(row.get("total_value")),
        ),
        reverse=True,
    )
    return rows


def build_market_score(
    full_market: Dict[str, Any],
    sample: Dict[str, Any],
    sectors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    full_breadth = fnum(full_market.get("breadth_pct"), fnum(sample.get("breadth_pct")))
    sample_breadth = fnum(sample.get("breadth_pct"))
    positive_liq = fnum(sample.get("positive_liquidity_share_pct"))
    index_change = fnum(full_market.get("index_change_pct"))
    sector_positive_ratio = (
        sum(1 for s in sectors if fnum(s.get("liquidity_weighted_change_pct")) > 0)
        / len(sectors)
        * 100.0
        if sectors
        else 50.0
    )

    # المؤشر يحوّل حركة ±5% تقريباً إلى نطاق 0..100 حول نقطة حياد 50.
    index_component = clamp(50 + index_change * 10, 0, 100)

    score = (
        full_breadth * 0.30
        + sample_breadth * 0.20
        + positive_liq * 0.20
        + sector_positive_ratio * 0.15
        + index_component * 0.15
    )

    risk = risk_label(
        full_breadth=full_breadth,
        sample_dispersion=fnum(sample.get("dispersion")),
        top5_concentration=fnum(sample.get("top5_liquidity_concentration_pct")),
        decline_liquidity_share=fnum(sample.get("negative_liquidity_share_pct")),
    )

    label = score_label(score)

    if score >= 70:
        view = "الزخم واسع نسبيًا والسيولة تؤيد المخاطرة الانتقائية، مع تجنب مطاردة القفزات."
    elif score >= 58:
        view = "السوق إيجابي انتقائي؛ الأفضلية للقطاعات ذات اتساع وسيولة متزامنين."
    elif score >= 45:
        view = "السوق متوازن/انتقائي؛ جودة السهم والقطاع أهم من اتجاه المؤشر وحده."
    elif score >= 35:
        view = "القيادة ضيقة؛ السيولة الانتقائية لا تعني أن السوق كله داعم للمخاطرة."
    else:
        view = "اتساع السوق ضعيف؛ الأولوية لحماية رأس المال وانتظار تحسن المشاركة."

    return {
        "score": round(score, 1),
        "label": label,
        "risk": risk,
        "view": view,
        "sector_positive_ratio_pct": round(sector_positive_ratio, 1),
    }


def enrich_stocks(stocks: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for stock in stocks:
        result.append(
            {
                "symbol": stock_symbol(stock),
                "name": safe_name(stock),
                "sector": stock_sector(stock),
                "price": round(stock_price(stock), 2),
                "change_pct": round(stock_change(stock), 2),
                "value": round(stock_value(stock), 2),
                "volume": fnum(stock.get("volume")),
                "high": fnum(stock.get("high")),
                "low": fnum(stock.get("low")),
            }
        )
    return result


def top_tables(stocks: List[Dict[str, Any]], limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    items = enrich_stocks(stocks)
    return {
        "gainers": sorted(items, key=lambda x: x["change_pct"], reverse=True)[:limit],
        "losers": sorted(items, key=lambda x: x["change_pct"])[:limit],
        "liquidity": sorted(items, key=lambda x: x["value"], reverse=True)[:limit],
    }


def build_watchlist(
    stocks: List[Dict[str, Any]],
    sectors: List[Dict[str, Any]],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    sector_scores = {s["sector"]: fnum(s.get("rotation_score")) for s in sectors}
    total_value = sum(stock_value(s) for s in stocks)
    values = sorted(stock_value(s) for s in stocks)

    def percentile(value: float) -> float:
        if not values:
            return 0.0
        count = sum(1 for v in values if v <= value)
        return count / len(values) * 100.0

    candidates: List[Dict[str, Any]] = []

    for stock in stocks:
        change = stock_change(stock)
        value = stock_value(stock)
        sector = stock_sector(stock)
        sector_score = sector_scores.get(sector, 0.0)
        value_pctile = percentile(value)

        if value < 5_000_000 or change <= -0.5:
            continue

        chase_penalty = max(0.0, abs(change) - 4.0) * 6.0
        momentum_score = clamp(50 + change * 7, 0, 100)
        liquidity_score = value_pctile

        score = (
            sector_score * 0.42
            + liquidity_score * 0.35
            + momentum_score * 0.23
            - chase_penalty
        )

        reasons: List[str] = []
        if sector_score >= 55:
            reasons.append("قطاع قيادي")
        elif sector_score >= 40:
            reasons.append("قطاع متماسك")

        if value_pctile >= 80:
            reasons.append("سيولة مرتفعة")
        if 0.2 <= change <= 4.0:
            reasons.append("زخم غير مفرط")
        if abs(change) > 4.5:
            reasons.append("تحتاج عدم مطاردة")

        candidates.append(
            {
                "symbol": stock_symbol(stock),
                "name": safe_name(stock),
                "sector": sector,
                "price": round(stock_price(stock), 2),
                "change_pct": round(change, 2),
                "value": round(value, 2),
                "market_liquidity_share_pct": round(
                    value / total_value * 100.0 if total_value else 0.0, 1
                ),
                "sector_rotation_score": round(sector_score, 1),
                "watch_score": round(score, 1),
                "reason": " + ".join(reasons[:3]) or "مراقبة فنية",
                "not_a_signal": True,
            }
        )

    candidates.sort(key=lambda x: x["watch_score"], reverse=True)
    return candidates[:limit]


def build_divergences(
    full_market: Dict[str, Any],
    sample: Dict[str, Any],
    sectors: List[Dict[str, Any]],
    top_liquidity: List[Dict[str, Any]],
) -> List[str]:
    notes: List[str] = []

    full_breadth = fnum(full_market.get("breadth_pct"))
    index_change = fnum(full_market.get("index_change_pct"))
    positive_liq = fnum(sample.get("positive_liquidity_share_pct"))
    negative_liq = fnum(sample.get("negative_liquidity_share_pct"))
    concentration = fnum(sample.get("top5_liquidity_concentration_pct"))

    if index_change >= 0 and full_breadth < 45:
        notes.append("المؤشر متماسك لكن المشاركة ضعيفة؛ الصعود غير واسع.")
    elif index_change < 0 and full_breadth > 55:
        notes.append("المؤشر ضعيف رغم اتساع مقبول؛ قد يكون الضغط مركزًا في القياديات.")

    if negative_liq >= 60:
        notes.append("أكثر من 60% من السيولة المرصودة في الأسهم الهابطة؛ ضغط توزيع يحتاج حذرًا.")
    elif positive_liq >= 60:
        notes.append("السيولة تميل بوضوح للأسهم الصاعدة؛ دعم أفضل لاستمرار الزخم.")

    if concentration >= 65:
        notes.append("السيولة شديدة التركّز في عدد محدود من الأسهم؛ لا تعمم قوة القياديات على السوق.")

    positive_sectors = sum(1 for s in sectors if fnum(s.get("liquidity_weighted_change_pct")) > 0)
    if sectors and positive_sectors / len(sectors) < 0.40:
        notes.append("القطاعات الصاعدة أقلية؛ القيادة ضيقة وليست موجة سوق شاملة.")

    negative_liquidity_leaders = [
        x for x in top_liquidity[:5] if fnum(x.get("change_pct")) < 0
    ]
    if len(negative_liquidity_leaders) >= 3:
        notes.append("ثلاثة أو أكثر من قادة السيولة هابطون؛ الأموال الكبيرة ليست هجومية بالكامل.")

    return notes[:4]


def load_signal_summary() -> Dict[str, Any]:
    data = load_json(SIGNALS_FILE, {})
    if isinstance(data, list):
        signals = data
        status = "HAS_SIGNALS" if signals else "NO_SIGNALS"
        message = ""
    elif isinstance(data, dict):
        signals = data.get("signals", [])
        status = data.get("status", "غير متوفر")
        message = data.get("message", "")
    else:
        signals = []
        status = "غير متوفر"
        message = ""

    clean: List[Dict[str, Any]] = []
    for signal in signals[:3]:
        if not isinstance(signal, dict):
            continue
        clean.append(
            {
                "symbol": str(signal.get("symbol") or signal.get("stock_symbol") or ""),
                "name": str(signal.get("name") or signal.get("stock_name") or ""),
                "entry": fnum(signal.get("entry_point") or signal.get("entry")),
                "target1": fnum(signal.get("target1")),
                "target2": fnum(signal.get("target2")),
                "stop_loss": fnum(signal.get("stop_loss")),
                "rased_score": fnum(signal.get("rased_score") or signal.get("score")),
                "rr": fnum(signal.get("rr") or signal.get("rr_ratio")),
                "risk": str(signal.get("risk_level_ar") or signal.get("risk_level") or ""),
            }
        )

    return {
        "count": len(signals),
        "status": status,
        "message": message,
        "top": clean,
    }


def build_quality_summary(
    daily: Dict[str, Any],
    quality: Dict[str, Any],
    data_quality: Dict[str, Any],
) -> Dict[str, Any]:
    requested = fint(daily.get("requested_symbols"))
    actual = len(daily.get("stocks", [])) if isinstance(daily.get("stocks"), list) else 0

    system_health = quality.get("system_health", {}) if isinstance(quality, dict) else {}
    q_score = fnum(
        system_health.get("data_quality_score"),
        fnum(data_quality.get("score"), 0.0) if isinstance(data_quality, dict) else 0.0,
    )
    valid_stocks = fint(system_health.get("valid_stocks"), actual)
    fetch_status = str(system_health.get("fetch_status") or "غير متوفر")
    quality_status = str(system_health.get("data_quality_status") or "غير متوفر")

    return {
        "requested_symbols": requested,
        "stocks_received": actual,
        "valid_stocks": valid_stocks,
        "coverage_pct": round(actual / requested * 100.0, 1) if requested else 0.0,
        "data_quality_score": round(q_score, 1),
        "fetch_status": fetch_status,
        "data_quality_status": quality_status,
        "is_delayed": bool(daily.get("market_summary", {}).get("is_delayed", False)),
    }


def performance_context(performance: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(performance, dict):
        performance = {}

    closed = fint(performance.get("closed_signals"))
    published = fint(performance.get("total_published"))
    tp1_rate = fnum(performance.get("tp1_success_rate_closed"))
    stop_rate = fnum(performance.get("stop_loss_rate_closed"))

    if closed < 10:
        reliability = "عينة غير كافية للحكم"
    elif closed < 30:
        reliability = "عينة أولية"
    else:
        reliability = "عينة قابلة للتقييم"

    return {
        "total_published": published,
        "closed_signals": closed,
        "open_signals": fint(performance.get("open_signals")),
        "tp1_success_rate_closed": round(tp1_rate, 1),
        "tp2_success_rate_closed": round(fnum(performance.get("tp2_success_rate_closed")), 1),
        "stop_loss_rate_closed": round(stop_rate, 1),
        "reliability": reliability,
    }


def tomorrow_playbook(
    market_score: Dict[str, Any],
    sectors: List[Dict[str, Any]],
    watchlist: List[Dict[str, Any]],
) -> Dict[str, Any]:
    best_sector = sectors[0] if sectors else {}
    second_sector = sectors[1] if len(sectors) > 1 else {}
    watch1 = watchlist[0] if watchlist else {}

    confirmations: List[str] = []
    invalidations: List[str] = []

    if best_sector:
        confirmations.append(
            f"استمرار {best_sector.get('sector')} ضمن القيادة مع اتساع ≥ "
            f"{fnum(best_sector.get('advance_ratio')) * 100:.0f}% وسيولة داعمة."
        )
    if second_sector and fnum(second_sector.get("rotation_score")) >= 50:
        confirmations.append(
            f"ثبات {second_sector.get('sector')} كقطاع ثانٍ بدل اعتماد السوق على قائد واحد."
        )
    if watch1:
        confirmations.append(
            f"مراقبة {watch1.get('name')} ({watch1.get('symbol')}) فقط إذا استمرت السيولة دون فجوة مطاردة."
        )

    if fnum(market_score.get("score")) < 50:
        invalidations.append("هبوط اتساع السوق أكثر مع انتقال السيولة إلى الأسهم الهابطة.")
    else:
        invalidations.append("تراجع اتساع السوق تحت 45% رغم بقاء المؤشر متماسكًا.")

    if best_sector:
        invalidations.append(
            f"فقدان {best_sector.get('sector')} للاتساع أو تحوله إلى متوسط موزون سلبي."
        )

    invalidations.append("ارتفاعات فردية كبيرة بلا زيادة موازية في حجم التداول تعد مطاردة لا تأكيدًا.")

    return {
        "confirmations": confirmations[:3],
        "invalidations": invalidations[:3],
    }


def render_stock_lines(items: List[Dict[str, Any]], limit: int = 5) -> List[str]:
    lines: List[str] = []
    for item in items[:limit]:
        lines.append(
            f"• {item.get('name')} ({item.get('symbol')}) — "
            f"{pct_fmt(fnum(item.get('change_pct')))} | "
            f"{item.get('sector')} | سيولة {money_fmt(fnum(item.get('value')))}"
        )
    return lines


def render_sector_lines(sectors: List[Dict[str, Any]], limit: int = 5) -> List[str]:
    lines: List[str] = []
    for row in sectors[:limit]:
        lines.append(
            f"• {row.get('icon')} {row.get('sector')}: {row.get('tone')} | "
            f"دوران {fnum(row.get('rotation_score')):.1f}/100 | "
            f"موزون بالسيولة {pct_fmt(fnum(row.get('liquidity_weighted_change_pct')))} | "
            f"اتساع {fnum(row.get('advance_ratio')) * 100:.0f}% | "
            f"{money_fmt(fnum(row.get('total_value')))}"
        )
    return lines


def render_watchlist(items: List[Dict[str, Any]]) -> List[str]:
    if not items:
        return ["• لا توجد مرشحات مراقبة عالية الجودة من بيانات اليوم."]
    lines = []
    for item in items:
        lines.append(
            f"• {item.get('name')} ({item.get('symbol')}) — "
            f"مراقبة {fnum(item.get('watch_score')):.0f}/100 | "
            f"{item.get('reason')} | حركة {pct_fmt(fnum(item.get('change_pct')))}"
        )
    return lines


def render_signals(signals: Dict[str, Any]) -> List[str]:
    if fint(signals.get("count")) <= 0:
        return ["• لا توجد إشارات مستوفية للفلاتر الحالية — هذا قرار جودة وليس نقصًا في التقرير."]

    lines = [f"• عدد الإشارات المعتمدة: {fint(signals.get('count'))}"]
    for signal in signals.get("top", [])[:3]:
        lines.append(
            f"• {signal.get('name') or signal.get('symbol')} ({signal.get('symbol')}) | "
            f"دخول {fnum(signal.get('entry')):.2f} | "
            f"R:R {fnum(signal.get('rr')):.2f} | "
            f"RASED {fnum(signal.get('rased_score')):.1f}"
        )
    return lines


def build_text_report(brief: Dict[str, Any]) -> str:
    full = brief.get("full_market", {})
    sample = brief.get("sample_internals", {})
    market_score = brief.get("market_score", {})
    quality = brief.get("quality", {})
    performance = brief.get("performance", {})
    sectors = brief.get("sectors", [])
    tables = brief.get("tables", {})
    watchlist = brief.get("watchlist", [])
    divergences = brief.get("divergences", [])
    signals = brief.get("signals", {})
    playbook = brief.get("tomorrow_playbook", {})

    delayed = " | ⚠️ بيانات متأخرة" if full.get("is_delayed") else ""

    lines: List[str] = [
        "📊 RASED INVESTOR DAILY BRIEF",
        "تقرير راصد اليومي — قراءة سوق + قرار متابعة",
        "━━━━━━━━━━━━━━",
        f"⏰ {brief.get('generated_at_human')} KSA{delayed}",
        "",
        "🇸🇦 السوق الكامل — TASI",
        f"• المؤشر: {fnum(full.get('index_value')):,.2f} | {pct_fmt(fnum(full.get('index_change_pct')))}",
        f"• الاتساع الرسمي: {fint(full.get('advancing'))} مرتفع | "
        f"{fint(full.get('declining'))} منخفض | {fint(full.get('unchanged'))} ثابت "
        f"→ {fnum(full.get('breadth_pct')):.1f}% صاعدة",
        f"• مؤشر صحة السوق RASED: {fnum(market_score.get('score')):.1f}/100 — "
        f"{market_score.get('label')} | المخاطرة: {market_score.get('risk')}",
        f"• القراءة: {market_score.get('view')}",
        "",
        "🔬 داخل عينة راصد",
        f"• التغطية: {fint(quality.get('stocks_received'))}/{fint(quality.get('requested_symbols'))} "
        f"({fnum(quality.get('coverage_pct')):.1f}%) | جودة البيانات {fnum(quality.get('data_quality_score')):.0f}/100",
        f"• متوسط/وسيط الحركة: {pct_fmt(fnum(sample.get('avg_change_pct')))} / "
        f"{pct_fmt(fnum(sample.get('median_change_pct')))} | التشتت {fnum(sample.get('dispersion')):.2f}",
        f"• السيولة المرصودة: {money_fmt(fnum(sample.get('total_value')))} | "
        f"للصاعدة {fnum(sample.get('positive_liquidity_share_pct')):.1f}% | "
        f"للهابطة {fnum(sample.get('negative_liquidity_share_pct')):.1f}%",
        f"• تركّز أعلى 5 أسهم من السيولة: {fnum(sample.get('top5_liquidity_concentration_pct')):.1f}%",
        "",
        "🏭 دوران وقيادة القطاعات",
        *render_sector_lines(sectors, 5),
        "",
        "💰 قادة السيولة",
        *render_stock_lines(tables.get("liquidity", []), 5),
        "",
        "👀 مرشحات للمراقبة — ليست إشارات شراء",
        *render_watchlist(watchlist),
        "",
        "🎯 إشارات راصد",
        *render_signals(signals),
    ]

    if divergences:
        lines.extend(["", "⚖️ تناقضات يجب ألا يتجاهلها المستثمر"])
        lines.extend([f"• {note}" for note in divergences])

    lines.extend(
        [
            "",
            "🧭 خطة الجلسة القادمة",
            "تأكيد إيجابي:",
            *[f"• {x}" for x in playbook.get("confirmations", [])],
            "إلغاء/تحذير:",
            *[f"• {x}" for x in playbook.get("invalidations", [])],
            "",
            "📈 سجل راصد — سياق الثقة",
            f"• منشور {fint(performance.get('total_published'))} | مغلق {fint(performance.get('closed_signals'))} | "
            f"مفتوح {fint(performance.get('open_signals'))}",
            f"• نجاح TP1: {fnum(performance.get('tp1_success_rate_closed')):.1f}% | "
            f"وقف خسارة: {fnum(performance.get('stop_loss_rate_closed')):.1f}% | "
            f"{performance.get('reliability')}",
            "",
            "🧠 كيف تُستخدم هذه القراءة؟",
            "• المستثمر: راقب اتساع السوق والقطاعات قبل زيادة التعرض، ولا تستنتج قوة السوق من سهم واحد.",
            "• المتداول: لا يحوّل سهم المراقبة إلى صفقة إلا بعد تحقق شروط الدخول وإدارة المخاطر.",
            "• عند ضعف العينة التاريخية، تُعامل نسب النجاح كبيانات أولية لا كضمان.",
            "",
            "⚠️ محتوى تحليلي وتعليمي آلي وليس توصية استثمارية أو ضماناً للأداء.",
            "#راصد #تاسي #السوق_السعودي",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    daily = load_json(DAILY_FILE, {})
    stocks = daily.get("stocks", []) if isinstance(daily, dict) else []

    if not stocks:
        brief = {
            "status": "NO_DATA",
            "message": "لا توجد بيانات يومية كافية لإنشاء التقرير.",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "engine_version": ENGINE_VERSION,
        }
        write_json(MARKET_BRIEF_JSON, brief)
        MARKET_BRIEF_TXT.write_text(
            "📊 تقرير راصد اليومي\n\nلا توجد بيانات سوق كافية لإنشاء التقرير.",
            encoding="utf-8",
        )
        print("ℹ️ لا توجد بيانات يومية كافية لإنشاء التقرير")
        return 0

    rotation = load_json(SECTOR_ROTATION_FILE, {})
    regime = load_json(MARKET_REGIME_FILE, {})
    quality_dashboard = load_json(QUALITY_DASHBOARD_FILE, {})
    performance_raw = load_json(PERFORMANCE_FILE, {})
    portfolio = load_json(PORTFOLIO_FILE, {})
    data_quality = load_json(DATA_QUALITY_FILE, {})

    full = full_market_snapshot(daily)
    sample = build_sample_internals(stocks)
    sectors = build_sector_table(stocks, rotation)
    market_score = build_market_score(full, sample, sectors)
    tables = top_tables(stocks, 5)
    watchlist = build_watchlist(stocks, sectors, 3)
    divergences = build_divergences(
        full,
        sample,
        sectors,
        tables.get("liquidity", []),
    )
    signals = load_signal_summary()
    quality = build_quality_summary(daily, quality_dashboard, data_quality)
    performance = performance_context(performance_raw)
    playbook = tomorrow_playbook(market_score, sectors, watchlist)

    generated_at = datetime.now()

    brief = {
        "status": "OK",
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "generated_at_human": generated_at.strftime("%Y-%m-%d | %I:%M %p"),
        "engine_version": ENGINE_VERSION,
        "provider": daily.get("provider", "sahmk"),
        "data_source": daily.get("data_source", ""),
        "full_market": full,
        "sample_internals": sample,
        "market_score": market_score,
        "market_regime": regime,
        "quality": quality,
        "sectors": sectors,
        "tables": tables,
        "watchlist": watchlist,
        "divergences": divergences,
        "signals": signals,
        "performance": performance,
        "portfolio_context": portfolio,
        "tomorrow_playbook": playbook,
        "methodology": {
            "market_score": (
                "30% official breadth + 20% sample breadth + 20% positive-liquidity share "
                "+ 15% sector participation + 15% normalized index move"
            ),
            "sector_ranking": (
                "sector_rotation score when available, enriched with liquidity-weighted "
                "daily move, breadth and liquidity share"
            ),
            "watchlist": (
                "sector strength + liquidity percentile + non-excessive momentum; "
                "watchlist is not a signal"
            ),
        },
        "disclaimer": "محتوى تحليلي وتعليمي آلي وليس توصية استثمارية أو ضماناً للأداء.",
    }

    text = build_text_report(brief)
    brief["text"] = text

    write_json(MARKET_BRIEF_JSON, brief)
    MARKET_BRIEF_TXT.write_text(text, encoding="utf-8")

    print("✅ تم إنشاء RASED Investor Daily Brief v2.0")
    print(text[:1800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
