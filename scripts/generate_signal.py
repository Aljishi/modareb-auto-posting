#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
راصد — محرك الإشارة الاحترافي
هدفه: إشارات أكثر تحفظاً قابلة للتشغيل الآلي بدون تخمين.
مبدأ مهم: إذا لم تتوفر بيانات حقيقية كافية لا يتم النشر.
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_FILE = DATA_DIR / "daily.json"
HISTORY_FILE = DATA_DIR / "market_history.json"
SIGNALS_FILE = DATA_DIR / "signals.json"

MIN_HISTORY_BARS = int(__import__('os').environ.get("MIN_HISTORY_BARS", "14"))
MIN_SCORE = int(__import__('os').environ.get("MIN_SIGNAL_SCORE", "82"))
MIN_RR = float(__import__('os').environ.get("MIN_RR", "2.2"))
MIN_VOLUME_RATIO = float(__import__('os').environ.get("MIN_VOLUME_RATIO", "1.6"))
MIN_VALUE_SAR = float(__import__('os').environ.get("MIN_VALUE_SAR", "2000000"))
MAX_ENTRY_GAP_PCT = float(__import__('os').environ.get("MAX_ENTRY_GAP_PCT", "1.2"))
LOOKBACK_RESISTANCE = int(__import__('os').environ.get("LOOKBACK_RESISTANCE", "20"))


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_blocked(reason: str, total_screened: int = 0) -> None:
    out = {
        "signals": [],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": 0,
        "total_screened": total_screened,
        "blocked_reason": reason,
        "engine_version": "rased_pro_10_guarded",
    }
    SIGNALS_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"🚫 {reason}")


def validate_dataset(data: Dict[str, Any]) -> Tuple[bool, str]:
    if data.get("data_source") != "api":
        return False, f"مصدر البيانات غير مقبول: {data.get('data_source', 'unknown')}"
    if data.get("quality_status") not in ("real_api_data", None):
        return False, f"حالة جودة البيانات غير مقبولة: {data.get('quality_status')}"
    stocks = data.get("stocks", [])
    if not stocks:
        return False, "daily.json لا يحتوي أسهماً"
    bad = [s.get("symbol") for s in stocks if not s.get("has_real_ohlc") or not s.get("has_real_liquidity")]
    if len(bad) > len(stocks) * 0.2:
        return False, "نسبة كبيرة من الأسهم لا تحتوي OHLC/سيولة حقيقية"
    return True, "ok"


def true_range(row: Dict[str, Any]) -> float:
    high = fnum(row.get("high"))
    low = fnum(row.get("low"))
    prev_close = fnum(row.get("previous_close"), fnum(row.get("close")))
    if high <= 0 or low <= 0 or prev_close <= 0:
        return 0.0
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr(rows: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
    valid = [true_range(r) for r in rows if true_range(r) > 0]
    if len(valid) < period:
        return None
    return mean(valid[-period:])


def calc_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    closes = [c for c in closes if c > 0]
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def volume_ratio(rows: List[Dict[str, Any]], current_volume: float, period: int = 20) -> float:
    vols = [fnum(r.get("volume")) for r in rows[-period:] if fnum(r.get("volume")) > 0]
    if len(vols) < max(5, period // 2) or current_volume <= 0:
        return 0.0
    avg = mean(vols)
    return round(current_volume / avg, 2) if avg > 0 else 0.0


def resistance_support(rows: List[Dict[str, Any]], lookback: int = 20) -> Tuple[Optional[float], Optional[float]]:
    prior = rows[-lookback-1:-1] if len(rows) > 1 else []
    highs = [fnum(r.get("high")) for r in prior if fnum(r.get("high")) > 0]
    lows = [fnum(r.get("low")) for r in prior if fnum(r.get("low")) > 0]
    if len(highs) < 5 or len(lows) < 5:
        return None, None
    return max(highs), min(lows)


def trend_state(rows: List[Dict[str, Any]]) -> Tuple[bool, List[str], Dict[str, float]]:
    closes = [fnum(r.get("close")) for r in rows if fnum(r.get("close")) > 0]
    if len(closes) < 20:
        return False, ["تاريخ غير كافٍ للترند"], {}
    sma10 = mean(closes[-10:])
    sma20 = mean(closes[-20:])
    last = closes[-1]
    ok = last > sma10 > sma20
    reasons = []
    if ok:
        reasons.append("السعر فوق متوسط 10 و20")
    else:
        reasons.append("الترند غير مؤكد")
    return ok, reasons, {"sma10": round(sma10, 3), "sma20": round(sma20, 3)}


def market_filter(history: Dict[str, List[Dict[str, Any]]]) -> Tuple[bool, str]:
    # اختياري: إذا وفرت رمز المؤشر TASI في البيانات يستخدمه. إن لم يوجد لا يمنع النشر، لكن يخصم نقاطاً لاحقاً.
    for sym in ("TASI", "TASI.SR", "^TASI", "9999"):
        rows = history.get(sym, [])
        if len(rows) >= 20:
            ok, _, vals = trend_state(rows)
            return ok, f"TASI trend {'positive' if ok else 'negative'} {vals}"
    return True, "لا توجد بيانات مؤشر كافية — تم تجاهل فلتر السوق العام"


def calc_signal(stock: Dict[str, Any], history_rows: List[Dict[str, Any]], market_ok: bool) -> Optional[Dict[str, Any]]:
    symbol = str(stock.get("symbol", ""))
    price = fnum(stock.get("current_price"))
    high = fnum(stock.get("high"))
    low = fnum(stock.get("low"))
    prev_close = fnum(stock.get("previous_close"))
    volume = fnum(stock.get("volume"))
    value = fnum(stock.get("value"))
    change_pct = fnum(stock.get("change_percent"))

    if price <= 0 or high <= 0 or low <= 0 or prev_close <= 0:
        return None
    if value < MIN_VALUE_SAR and volume * price < MIN_VALUE_SAR:
        return None

    rows = list(history_rows)
    today = datetime.now().strftime("%Y-%m-%d")
    current_row = {"date": today, "open": stock.get("open"), "high": high, "low": low, "close": price, "previous_close": prev_close, "volume": volume, "value": value}
    if not rows or rows[-1].get("date") != today:
        rows.append(current_row)
    else:
        rows[-1] = current_row

    if len(rows) < MIN_HISTORY_BARS:
        print(f"  ⚠️ {symbol}: تاريخ غير كافٍ ({len(rows)}/{MIN_HISTORY_BARS})")
        return None

    atr14 = atr(rows, 14)
    if not atr14 or atr14 <= 0:
        return None
    atr_pct = atr14 / price * 100
    if atr_pct < 0.7 or atr_pct > 8.0:
        return None

    resistance, support = resistance_support(rows, LOOKBACK_RESISTANCE)
    if not resistance or not support:
        print(f"  ⚠️ {symbol}: لا توجد مقاومة/دعم كافية")
        return None

    closes = [fnum(r.get("close")) for r in rows]
    rsi = calc_rsi(closes, 14) or fnum(stock.get("rsi"), 0)
    vol_ratio = volume_ratio(rows[:-1], volume, 20) or fnum(stock.get("volume_ratio"), 0)
    trend_ok, trend_reasons, trend_vals = trend_state(rows)

    breakout_pct = ((price / resistance) - 1) * 100 if resistance > 0 else -99
    near_breakout_pct = ((resistance / price) - 1) * 100 if price > 0 else 99
    is_breakout = price >= resistance * 1.002
    is_near_breakout = 0 <= near_breakout_pct <= 1.5

    # دخول: إما بعد اختراق المقاومة أو فوق السعر قليلاً إذا قريب من المقاومة.
    if is_breakout:
        entry = round(max(price, resistance * 1.003), 2)
        setup_type = "اختراق مؤكد"
    elif is_near_breakout:
        entry = round(resistance * 1.003, 2)
        setup_type = "دخول مشروط فوق المقاومة"
    else:
        return None

    entry_gap = (entry / price - 1) * 100
    if entry_gap > MAX_ENTRY_GAP_PCT:
        return None

    stop_by_atr = entry - atr14 * 1.25
    stop_by_support = support * 0.995
    stop_loss = round(max(stop_by_atr, stop_by_support), 2)
    risk = entry - stop_loss
    if risk <= 0:
        return None

    target1 = round(entry + risk * 1.5, 2)
    target2 = round(entry + risk * MIN_RR, 2)
    rr = round((target2 - entry) / risk, 2)
    if rr < MIN_RR:
        return None

    score = 0
    reasons: List[str] = []
    if trend_ok:
        score += 18; reasons += trend_reasons
    if market_ok:
        score += 7; reasons.append("فلتر السوق العام مقبول")
    if 50 <= rsi <= 68:
        score += 18; reasons.append(f"RSI صحي {rsi:.1f}")
    elif 45 <= rsi < 50 or 68 < rsi <= 72:
        score += 9; reasons.append(f"RSI مقبول {rsi:.1f}")
    else:
        return None
    if vol_ratio >= 3:
        score += 18; reasons.append(f"حجم قوي جداً {vol_ratio:.1f}x")
    elif vol_ratio >= MIN_VOLUME_RATIO:
        score += 12; reasons.append(f"حجم مؤكد {vol_ratio:.1f}x")
    else:
        return None
    if is_breakout:
        score += 20; reasons.append("اختراق مقاومة فعلي")
    elif is_near_breakout:
        score += 12; reasons.append("قريب من مقاومة مهمة")
    if 0.4 <= change_pct <= 6.0:
        score += 10; reasons.append(f"زخم يومي صحي {change_pct:+.1f}%")
    elif change_pct > 6.0:
        score += 3; reasons.append("زخم مرتفع مع مخاطرة مطاردة")
    if value >= 5_000_000 or volume * price >= 5_000_000:
        score += 9; reasons.append("سيولة مناسبة")

    score = min(score, 100)
    if score < MIN_SCORE:
        return None

    return {
        "stock_symbol": symbol,
        "stock_name": stock.get("name", symbol),
        "sector": stock.get("sector", ""),
        "current_price": round(price, 2),
        "entry_point": entry,
        "entry_type": setup_type,
        "target1": target1,
        "target1_percent": round((target1 - entry) / entry * 100, 2),
        "target2": target2,
        "target2_percent": round((target2 - entry) / entry * 100, 2),
        "stop_loss": stop_loss,
        "stop_loss_percent": round((entry - stop_loss) / entry * 100, 2),
        "rr": rr,
        "atr14": round(atr14, 4),
        "atr_percent": round(atr_pct, 2),
        "resistance": round(resistance, 2),
        "support": round(support, 2),
        "breakout_percent": round(breakout_pct, 2),
        "rsi": round(rsi, 2),
        "volume_ratio": round(vol_ratio, 2),
        "value": round(value if value > 0 else volume * price, 2),
        "score": score,
        "technical_reading": " | ".join(reasons[:5]),
        "confidence": "عالية جداً" if score >= 90 else "عالية",
        "emoji": "🟢" if score >= 90 else "🟡",
        "level": "golden" if score >= 90 else "high",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_source": "api",
        "engine_version": "rased_pro_10_guarded",
        "risk_note": "إشارة آلية مشروطة؛ التنفيذ يكون عند تحقق نقطة الدخول فقط.",
        "trend": trend_vals,
    }


def main() -> int:
    print("=" * 60)
    print("🎯 راصد — محرك الإشارة الاحترافي")
    print("=" * 60)

    data = load_json(DAILY_FILE, {})
    ok, reason = validate_dataset(data)
    stocks = data.get("stocks", [])
    if not ok:
        save_blocked(reason, len(stocks))
        return 1

    history = load_json(HISTORY_FILE, {})
    market_ok, market_reason = market_filter(history)
    print(f"📌 فلتر السوق: {market_reason}")

    signals: List[Dict[str, Any]] = []
    for stock in stocks:
        sym = str(stock.get("symbol", ""))
        sig = calc_signal(stock, history.get(sym, []), market_ok)
        if sig:
            signals.append(sig)
            print(f"  ✅ {sym}: Score {sig['score']} | R:R {sig['rr']} | {sig['entry_type']}")

    signals.sort(key=lambda s: (s.get("score", 0), s.get("volume_ratio", 0), s.get("value", 0)), reverse=True)
    top = signals[:3]
    output = {
        "signals": top,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(top),
        "total_candidates": len(signals),
        "total_screened": len(stocks),
        "data_source": "api",
        "engine_version": "rased_pro_10_guarded",
        "selection_policy": "top 3 only after real ATR + resistance + liquidity + R:R filters",
    }
    SIGNALS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ {len(top)} إشارة نهائية من أصل {len(stocks)} سهم")
    return 0 if top else 1


if __name__ == "__main__":
    sys.exit(main())
