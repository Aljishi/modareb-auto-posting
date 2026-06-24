#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — التقرير اليومي الاحترافي للسوق السعودي

الغرض:
- إنشاء ملخص يومي احترافي بعد الإغلاق بصيغة مناسبة للمشتركين.
- لا يغير منطق الإشارات ولا الفلاتر.
- يعتمد على data/daily.json و data/signals.json و data/sector_rotation.json عند توفرها.

المخرجات:
- data/market_brief.json
- data/market_brief.txt
"""

import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_FILE = DATA_DIR / "daily.json"
SIGNALS_FILE = DATA_DIR / "signals.json"
SECTOR_ROTATION_FILE = DATA_DIR / "sector_rotation.json"
MARKET_BRIEF_JSON = DATA_DIR / "market_brief.json"
MARKET_BRIEF_TXT = DATA_DIR / "market_brief.txt"

ENGINE_VERSION = "rased_market_brief_v1_0"


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace(",", "").replace("%", "").strip()
        return float(x)
    except Exception:
        return default


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"⚠️ cannot read {path.name}: {exc}")
    return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_name(stock: Dict[str, Any]) -> str:
    return str(stock.get("name") or stock.get("name_ar") or stock.get("symbol") or "غير معروف").strip()


def stock_symbol(stock: Dict[str, Any]) -> str:
    return str(stock.get("symbol") or stock.get("stock_symbol") or "").strip()


def stock_price(stock: Dict[str, Any]) -> float:
    return fnum(stock.get("current_price") or stock.get("price") or stock.get("close"))


def stock_value(stock: Dict[str, Any]) -> float:
    price = stock_price(stock)
    volume = fnum(stock.get("volume"))
    return fnum(stock.get("value") or stock.get("turnover")) or price * volume


def stock_change(stock: Dict[str, Any]) -> float:
    return fnum(stock.get("change_percent") or stock.get("change_pct") or stock.get("pct_change"))


def stock_sector(stock: Dict[str, Any]) -> str:
    return str(stock.get("sector") or stock.get("sector_name") or "غير مصنف").strip() or "غير مصنف"


def pct_fmt(x: float, signed: bool = True) -> str:
    sign = "+" if signed and x > 0 else ""
    return f"{sign}{x:.2f}%"


def money_fmt(x: float) -> str:
    if x >= 1_000_000_000:
        return f"{x / 1_000_000_000:.2f} مليار ريال"
    if x >= 1_000_000:
        return f"{x / 1_000_000:.2f} مليون ريال"
    if x >= 1_000:
        return f"{x / 1_000:.0f} ألف ريال"
    return f"{x:.0f} ريال"


def build_sector_table(stocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for s in stocks:
        groups.setdefault(stock_sector(s), []).append(s)

    rows: List[Dict[str, Any]] = []
    for sector, items in groups.items():
        changes = [stock_change(x) for x in items]
        values = [stock_value(x) for x in items]
        advancing = sum(1 for c in changes if c > 0)
        declining = sum(1 for c in changes if c < 0)
        avg_change = mean(changes) if changes else 0.0
        total_value = sum(values)
        advance_ratio = advancing / len(items) if items else 0.0

        if avg_change >= 1.0 and advance_ratio >= 0.60:
            tone = "إيجابي قوي"
            icon = "🟢"
        elif avg_change >= 0.25 and advance_ratio >= 0.50:
            tone = "إيجابي"
            icon = "🟢"
        elif avg_change <= -1.0 and advance_ratio <= 0.35:
            tone = "سلبي قوي"
            icon = "🔴"
        elif avg_change < 0:
            tone = "سلبي"
            icon = "🔴"
        else:
            tone = "محايد"
            icon = "🟡"

        rows.append(
            {
                "sector": sector,
                "members": len(items),
                "avg_change_pct": round(avg_change, 2),
                "advance_ratio": round(advance_ratio, 2),
                "advancing": advancing,
                "declining": declining,
                "total_value": round(total_value, 2),
                "tone": tone,
                "icon": icon,
            }
        )

    rows.sort(key=lambda r: (r["avg_change_pct"], r["total_value"]), reverse=True)
    return rows


def market_bias(stocks: List[Dict[str, Any]], sectors: List[Dict[str, Any]]) -> Dict[str, Any]:
    changes = [stock_change(s) for s in stocks]
    values = [stock_value(s) for s in stocks]
    advancing = sum(1 for c in changes if c > 0)
    declining = sum(1 for c in changes if c < 0)
    unchanged = max(0, len(stocks) - advancing - declining)
    avg_change = mean(changes) if changes else 0.0
    total_value = sum(values)
    breadth = advancing / len(stocks) if stocks else 0.0

    strong_sectors = sum(1 for s in sectors if s.get("tone") in {"إيجابي", "إيجابي قوي"})
    weak_sectors = sum(1 for s in sectors if s.get("tone") in {"سلبي", "سلبي قوي"})

    if breadth >= 0.60 and avg_change > 0.35 and strong_sectors > weak_sectors:
        bias = "إيجابي انتقائي"
        risk = "متوسط"
        view = "السيولة تميل للأسهم الصاعدة مع أفضلية للقطاعات الأقوى."
    elif breadth <= 0.40 and avg_change < -0.25 and weak_sectors >= strong_sectors:
        bias = "حذر"
        risk = "مرتفع"
        view = "السوق يميل للضغط، والأولوية لإدارة المخاطر وعدم ملاحقة الارتدادات الضعيفة."
    elif total_value > 0 and strong_sectors >= weak_sectors:
        bias = "محايد مائل للإيجابية"
        risk = "متوسط"
        view = "السوق انتقائي؛ الفرص موجودة لكنها تحتاج فلترة صارمة حسب السيولة والترند."
    else:
        bias = "محايد"
        risk = "متوسط"
        view = "الصورة العامة متوازنة، والأفضلية للانتظار حتى تتضح قيادة القطاعات."

    return {
        "bias": bias,
        "risk": risk,
        "view": view,
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "breadth_pct": round(breadth * 100, 1),
        "avg_change_pct": round(avg_change, 2),
        "total_value": round(total_value, 2),
        "strong_sectors": strong_sectors,
        "weak_sectors": weak_sectors,
    }


def top_stocks(stocks: List[Dict[str, Any]], limit: int = 5) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    enriched: List[Dict[str, Any]] = []
    for s in stocks:
        enriched.append(
            {
                "symbol": stock_symbol(s),
                "name": safe_name(s),
                "sector": stock_sector(s),
                "change_pct": round(stock_change(s), 2),
                "value": round(stock_value(s), 2),
                "price": round(stock_price(s), 2),
            }
        )
    by_change = sorted(enriched, key=lambda x: x["change_pct"], reverse=True)[:limit]
    by_weakness = sorted(enriched, key=lambda x: x["change_pct"])[:limit]
    by_value = sorted(enriched, key=lambda x: x["value"], reverse=True)[:limit]
    return by_change, by_weakness, by_value


def load_signal_summary() -> Dict[str, Any]:
    data = load_json(SIGNALS_FILE, {})
    signals = data.get("signals", []) if isinstance(data, dict) else []
    return {
        "count": len(signals),
        "status": data.get("status", "غير متوفر") if isinstance(data, dict) else "غير متوفر",
        "message": data.get("message", "") if isinstance(data, dict) else "",
        "top": signals[:3],
    }


def render_stock_lines(items: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for item in items:
        name = item.get("name") or item.get("symbol")
        symbol = item.get("symbol")
        sector = item.get("sector")
        change = pct_fmt(fnum(item.get("change_pct")))
        value = money_fmt(fnum(item.get("value")))
        lines.append(f"• {name} ({symbol}) — {change} | {sector} | سيولة {value}")
    return lines


def render_sector_lines(sectors: List[Dict[str, Any]], limit: int = 6) -> List[str]:
    lines: List[str] = []
    for s in sectors[:limit]:
        lines.append(
            f"• {s['icon']} {s['sector']}: {s['tone']} | متوسط {pct_fmt(fnum(s['avg_change_pct']))} | سيولة {money_fmt(fnum(s['total_value']))}"
        )
    return lines


def build_text_report(brief: Dict[str, Any]) -> str:
    generated_at = brief.get("generated_at_human")
    bias = brief.get("market_bias", {})
    sectors = brief.get("sectors", [])
    top_gainers = brief.get("top_gainers", [])
    top_value = brief.get("top_value", [])
    top_losers = brief.get("top_losers", [])
    signal_summary = brief.get("signals", {})

    signal_line = "لا توجد إشارات راصد مستوفية للشروط الصارمة اليوم."
    if signal_summary.get("count", 0) > 0:
        signal_line = f"تم توليد {signal_summary.get('count')} إشارة مستوفية لشروط راصد."

    lines = [
        "📊 RASED DAILY MARKET BRIEF",
        "تقرير راصد اليومي للسوق السعودي",
        "━━━━━━━━━━━━━━",
        f"⏰ {generated_at} KSA",
        "",
        "🇸🇦 ملخص السوق",
        f"• المزاج العام: {bias.get('bias', 'غير متوفر')}",
        f"• مستوى المخاطرة: {bias.get('risk', 'غير متوفر')}",
        f"• الأسهم المرتفعة: {bias.get('advancing', 0)} | المنخفضة: {bias.get('declining', 0)} | المستقرة: {bias.get('unchanged', 0)}",
        f"• اتساع السوق: {bias.get('breadth_pct', 0)}%",
        f"• متوسط حركة العينة: {pct_fmt(fnum(bias.get('avg_change_pct')))}",
        f"• السيولة المرصودة: {money_fmt(fnum(bias.get('total_value')))}",
        "",
        "🏭 قيادة القطاعات",
        *render_sector_lines(sectors, 6),
        "",
        "💰 أعلى الأسهم من حيث السيولة",
        *render_stock_lines(top_value[:5]),
        "",
        "🔥 أقوى الأسهم حركة",
        *render_stock_lines(top_gainers[:5]),
        "",
        "⚠️ أضعف الأسهم حركة",
        *render_stock_lines(top_losers[:5]),
        "",
        "🎯 إشارات راصد",
        f"• {signal_line}",
        "",
        "🧠 قراءة راصد",
        f"• {bias.get('view', 'السوق يحتاج متابعة انتقائية حسب السيولة والقطاعات.')}",
        "• عند غياب الإشارات، فهذا يعني أن الفلاتر لم تجد فرصة بجودة كافية، وليس عطلاً في النظام.",
        "",
        "📌 جلسة الغد — ما نراقبه",
        "• استمرار قيادة القطاعات الخضراء مع تحسن السيولة.",
        "• تحوّل الأسهم عالية السيولة من التجميع إلى الاختراق.",
        "• تجنب المطاردة إذا ارتفع الزخم دون دعم من حجم التداول.",
        "",
        "⚠️ محتوى تحليلي وتعليمي آلي وليس توصية استثمارية أو ضماناً للأداء.",
        "#راصد #تاسي #السوق_السعودي",
    ]
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
        MARKET_BRIEF_TXT.write_text("📊 تقرير راصد اليومي\n\nلا توجد بيانات سوق كافية لإنشاء التقرير.", encoding="utf-8")
        print("ℹ️ لا توجد بيانات يومية كافية لإنشاء التقرير")
        return 0

    sectors = build_sector_table(stocks)
    bias = market_bias(stocks, sectors)
    top_gainers, top_losers, top_value = top_stocks(stocks, 5)
    signal_summary = load_signal_summary()

    generated_at = datetime.now()
    brief = {
        "status": "OK",
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "generated_at_human": generated_at.strftime("%Y-%m-%d | %I:%M %p"),
        "engine_version": ENGINE_VERSION,
        "provider": daily.get("provider", "sahmk") if isinstance(daily, dict) else "sahmk",
        "sample_size": len(stocks),
        "market_bias": bias,
        "sectors": sectors,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "top_value": top_value,
        "signals": signal_summary,
        "disclaimer": "محتوى تحليلي وتعليمي آلي وليس توصية استثمارية أو ضماناً للأداء.",
    }
    text = build_text_report(brief)

    brief["text"] = text
    write_json(MARKET_BRIEF_JSON, brief)
    MARKET_BRIEF_TXT.write_text(text, encoding="utf-8")

    print("✅ تم إنشاء تقرير راصد اليومي")
    print(text[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
