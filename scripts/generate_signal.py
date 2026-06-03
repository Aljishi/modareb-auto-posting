#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
راصد — محرك الإشارة الاحترافي Premium

الهدف:
- لا إشارات مبنية على تخمين أو بيانات وهمية.
- اختيار إشارات زخم/اختراق قابلة للمضاربة خلال 1–7 أيام.
- إضافة RASED SCORE™, tier, target percentages, stop percentage, holding period.

مهم:
لا يوجد أي نظام يضمن تحقق الهدف خلال 7 أيام. هذا المحرك يرفض الإشارة إذا كان
الهدف الثاني بعيداً فنياً مقارنة بالـ ATR والزخم والسيولة، حتى تكون مدة 1–7 أيام منطقية.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_FILE = DATA_DIR / "daily.json"
HISTORY_FILE = DATA_DIR / "market_history.json"
SIGNALS_FILE = DATA_DIR / "signals.json"

ENGINE_VERSION = "rased_premium_7d_ai_ready"

MIN_HISTORY_BARS = int(os.getenv("MIN_HISTORY_BARS", "20"))
MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", "84"))
MIN_RR = float(os.getenv("MIN_RR", "2.2"))
MIN_VOLUME_RATIO = float(os.getenv("MIN_VOLUME_RATIO", "1.7"))
MIN_VALUE_SAR = float(os.getenv("MIN_VALUE_SAR", "3000000"))
MAX_ENTRY_GAP_PCT = float(os.getenv("MAX_ENTRY_GAP_PCT", "1.2"))
LOOKBACK_RESISTANCE = int(os.getenv("LOOKBACK_RESISTANCE", "20"))
MAX_HOLD_DAYS = int(os.getenv("MAX_HOLD_DAYS", "7"))
MAX_TP2_ATR_MULTIPLE_7D = float(os.getenv("MAX_TP2_ATR_MULTIPLE_7D", "5.0"))
MIN_ATR_PCT = float(os.getenv("MIN_ATR_PCT", "0.7"))
MAX_ATR_PCT = float(os.getenv("MAX_ATR_PCT", "8.0"))


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


def save_blocked(reason: str, total_screened: int = 0) -> None:
    out = {
        "signals": [],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": 0,
        "total_screened": total_screened,
        "blocked_reason": reason,
        "engine_version": ENGINE_VERSION,
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
    if len(bad) > len(stocks) * 0.25:
        return False, "نسبة كبيرة من الأسهم لا تحتوي OHLC/سيولة حقيقية"
    return True, "ok"


def true_range(row: Dict[str, Any]) -> float:
    high = fnum(row.get("high"))
    low = fnum(row.get("low"))
    prev_close = fnum(row.get("previous_close"), fnum(row.get("close")))
    if high <= 0 or low <= 0 or prev_close <= 0 or high < low:
        return 0.0
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr(rows: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
    trs = [true_range(r) for r in rows if true_range(r) > 0]
    if len(trs) < period:
        return None
    return mean(trs[-period:])


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
    prior = rows[-lookback - 1:-1] if len(rows) > 1 else []
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
    return ok, (["اتجاه صاعد مؤكد"] if ok else ["الترند غير مؤكد"]), {"sma10": round(sma10, 3), "sma20": round(sma20, 3)}


def market_filter(history: Dict[str, List[Dict[str, Any]]]) -> Tuple[bool, str]:
    for sym in ("TASI", "TASI.SR", "^TASI", "9999"):
        rows = history.get(sym, [])
        if len(rows) >= 20:
            ok, _, vals = trend_state(rows)
            return ok, f"TASI trend {'positive' if ok else 'negative'} {vals}"
    return True, "لا توجد بيانات مؤشر كافية — لم يتم تعطيل الإشارات"


def pct(up_or_down: float, entry: float) -> float:
    if entry <= 0:
        return 0.0
    return round((up_or_down / entry) * 100, 2)


def classify_tier(rased_score: float) -> Tuple[str, str]:
    if rased_score >= 95:
        return "Platinum", "👑"
    if rased_score >= 90:
        return "Gold", "🌟"
    if rased_score >= 85:
        return "Premium", "⭐"
    return "Standard", "✅"


def risk_label(rr: float, atr_pct: float, rsi: float) -> Tuple[str, str]:
    if rr >= 3 and 1.0 <= atr_pct <= 4.5 and rsi <= 64:
        return "منخفض", "🟢"
    if rr >= 2.2 and 0.7 <= atr_pct <= 6.0 and rsi <= 68:
        return "متوسط", "🟡"
    return "مرتفع", "🔴"


def expected_days_to_target(target_pct: float, atr_pct: float, volume_factor: float, is_breakout: bool) -> int:
    if atr_pct <= 0:
        return 99
    momentum_boost = 1.0
    if volume_factor >= 3:
        momentum_boost = 1.35
    elif volume_factor >= 2:
        momentum_boost = 1.20
    elif volume_factor >= 1.7:
        momentum_boost = 1.10
    breakout_boost = 1.15 if is_breakout else 1.0
    effective_daily_range = max(atr_pct * 0.75 * momentum_boost * breakout_boost, 0.3)
    return max(1, int(round(target_pct / effective_daily_range + 0.49)))


def calc_signal(stock: Dict[str, Any], history_rows: List[Dict[str, Any]], market_ok: bool) -> Optional[Dict[str, Any]]:
    symbol = str(stock.get("symbol", "")).strip()
    price = fnum(stock.get("current_price"))
    high = fnum(stock.get("high"))
    low = fnum(stock.get("low"))
    prev_close = fnum(stock.get("previous_close"))
    volume = fnum(stock.get("volume"))
    value = fnum(stock.get("value")) or volume * price
    change_pct = fnum(stock.get("change_percent"))

    if not symbol or price <= 0 or high <= 0 or low <= 0 or prev_close <= 0:
        return None
    if not stock.get("has_real_ohlc") or not stock.get("has_real_liquidity"):
        return None
    if value < MIN_VALUE_SAR:
        return None

    rows = list(history_rows)
    today = datetime.now().strftime("%Y-%m-%d")
    current_row = {
        "date": today,
        "open": stock.get("open"),
        "high": high,
        "low": low,
        "close": price,
        "previous_close": prev_close,
        "volume": volume,
        "value": value,
    }
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
    atr_pct = round((atr14 / price) * 100, 2)
    if atr_pct < MIN_ATR_PCT or atr_pct > MAX_ATR_PCT:
        return None

    resistance, support = resistance_support(rows, LOOKBACK_RESISTANCE)
    if not resistance or not support:
        return None

    closes = [fnum(r.get("close")) for r in rows]
    rsi = calc_rsi(closes, 14) or fnum(stock.get("rsi"), 0)
    vol_ratio = volume_ratio(rows[:-1], volume, 20) or fnum(stock.get("volume_ratio"), 0)
    trend_ok, trend_reasons, trend_vals = trend_state(rows)

    near_breakout_pct = ((resistance / price) - 1) * 100 if price > 0 else 99
    is_breakout = price >= resistance * 1.002
    is_near_breakout = 0 <= near_breakout_pct <= 1.5

    if is_breakout:
        entry = round(max(price, resistance * 1.003), 2)
        setup_type = "اختراق مؤكد"
    elif is_near_breakout:
        entry = round(resistance * 1.003, 2)
        setup_type = "دخول مشروط فوق المقاومة"
    else:
        return None

    entry_gap_pct = round((entry / price - 1) * 100, 2)
    if entry_gap_pct > MAX_ENTRY_GAP_PCT:
        return None

    stop_by_atr = entry - atr14 * 1.25
    stop_by_support = support * 0.995
    stop_loss = round(max(stop_by_atr, stop_by_support), 2)
    risk_amount = round(entry - stop_loss, 4)
    if risk_amount <= 0:
        return None

    target1 = round(entry + risk_amount * 1.55, 2)
    target2 = round(entry + risk_amount * MIN_RR, 2)
    rr = round((target2 - entry) / risk_amount, 2)
    if rr < MIN_RR:
        return None

    target1_pct = pct(target1 - entry, entry)
    target2_pct = pct(target2 - entry, entry)
    stop_loss_pct = round(pct(stop_loss - entry, entry), 2)

    # فلتر 7 أيام: الهدف الثاني يجب أن يكون واقعياً مقارنة بالمدى اليومي والزخم.
    max_reasonable_7d_pct = round(atr_pct * MAX_TP2_ATR_MULTIPLE_7D, 2)
    expected_days_tp1 = expected_days_to_target(target1_pct, atr_pct, vol_ratio, is_breakout)
    expected_days_tp2 = expected_days_to_target(target2_pct, atr_pct, vol_ratio, is_breakout)
    if expected_days_tp2 > MAX_HOLD_DAYS:
        return None
    if target2_pct > max_reasonable_7d_pct:
        return None

    if not (48 <= rsi <= 68):
        return None
    if vol_ratio < MIN_VOLUME_RATIO:
        return None
    if not trend_ok:
        return None

    score = 0
    reasons: List[str] = []
    score += 18; reasons += trend_reasons
    if market_ok:
        score += 7; reasons.append("فلتر السوق العام مقبول")
    if 52 <= rsi <= 64:
        score += 18; reasons.append(f"زخم صحي RSI {rsi:.1f}")
    elif 48 <= rsi <= 68:
        score += 12; reasons.append(f"RSI مقبول {rsi:.1f}")
    if vol_ratio >= 3:
        score += 18; reasons.append(f"سيولة قوية جداً {vol_ratio:.1f}x")
    elif vol_ratio >= 2:
        score += 15; reasons.append(f"سيولة قوية {vol_ratio:.1f}x")
    else:
        score += 10; reasons.append(f"سيولة مؤكدة {vol_ratio:.1f}x")
    if is_breakout:
        score += 20; reasons.append("اختراق مقاومة مؤكد")
    else:
        score += 14; reasons.append("قريب من اختراق مقاومة مهمة")
    if 0.5 <= change_pct <= 5.5:
        score += 10; reasons.append(f"زخم يومي صحي {change_pct:+.1f}%")
    elif 5.5 < change_pct <= 7.0:
        score += 4; reasons.append("زخم مرتفع — مراقبة عدم المطاردة")
    else:
        return None
    if value >= 5_000_000:
        score += 9; reasons.append("قيمة تداول مناسبة")

    score = min(score, 100)
    if score < MIN_SIGNAL_SCORE:
        return None

    # RASED SCORE مبدئي قبل مراجعة OpenAI. سيتم تعزيزه لاحقاً في ai_signal_reviewer.
    rr_score = min(rr * 28, 100)
    time_score = max(0, 100 - (expected_days_tp2 - 1) * 8)
    rased_score = round(score * 0.50 + rr_score * 0.25 + time_score * 0.25, 1)
    tier, tier_emoji = classify_tier(rased_score)
    risk_text, risk_emoji = risk_label(rr, atr_pct, rsi)

    signal = {
        "stock_symbol": symbol,
        "symbol": symbol,
        "stock_name": stock.get("name", symbol),
        "name": stock.get("name", symbol),
        "sector": stock.get("sector", ""),
        "current_price": round(price, 2),
        "entry_point": entry,
        "entry": entry,
        "target1": target1,
        "target2": target2,
        "stop_loss": stop_loss,
        "target1_percent": target1_pct,
        "target2_percent": target2_pct,
        "stop_loss_percent": abs(stop_loss_pct),
        "rr": rr,
        "rr_ratio": rr,
        "score": score,
        "rased_score": rased_score,
        "tier": tier,
        "tier_emoji": tier_emoji,
        "risk_level": risk_text,
        "risk_emoji": risk_emoji,
        "confidence": f"{int(round(rased_score))}%",
        "rsi": round(rsi, 2),
        "volume_ratio": vol_ratio,
        "rs_rank": fnum(stock.get("rs_rank"), 0),
        "atr14": round(atr14, 4),
        "atr_pct": atr_pct,
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "trend": "صاعد",
        "trend_values": trend_vals,
        "setup_type": setup_type,
        "breakout": bool(is_breakout),
        "entry_gap_pct": entry_gap_pct,
        "value": round(value, 2),
        "expected_holding_period": "1-7 أيام",
        "max_holding_days": MAX_HOLD_DAYS,
        "expected_days_to_target1": expected_days_tp1,
        "expected_days_to_target2": expected_days_tp2,
        "seven_day_filter_passed": True,
        "max_reasonable_7d_pct": max_reasonable_7d_pct,
        "technical_reading": " — ".join(reasons[:5]),
        "signal_reason": "اجتازت فلاتر راصد الخاصة بالاختراق والسيولة والزخم وإدارة المخاطر.",
        "key_insight": "الإشارة مرشحة لمضاربة قصيرة المدى خلال 1-7 أيام بشرط الالتزام بوقف الخسارة.",
        "data_source": "api",
        "engine_version": ENGINE_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    return signal


def main() -> int:
    print("=" * 60)
    print("🚀 راصد — Premium Signal Engine 7D")
    print("=" * 60)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    daily = load_json(DAILY_FILE, {})
    history = load_json(HISTORY_FILE, {})

    ok, msg = validate_dataset(daily)
    if not ok:
        save_blocked(msg)
        return 1

    stocks = daily.get("stocks", [])
    market_ok, market_msg = market_filter(history)
    print(f"📌 Market filter: {market_msg}")

    signals: List[Dict[str, Any]] = []
    for stock in stocks:
        sym = str(stock.get("symbol", ""))
        rows = history.get(sym, [])
        sig = calc_signal(stock, rows, market_ok)
        if sig:
            signals.append(sig)
            print(f"✅ {sym}: {sig['tier']} | Score {sig['score']} | RASED {sig['rased_score']} | TP2 {sig['target2_percent']}% | {sig['expected_days_to_target2']}d")

    signals.sort(key=lambda s: (s.get("rased_score", 0), s.get("score", 0), s.get("rr", 0)), reverse=True)
    signals = signals[:5]

    out = {
        "signals": signals,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(signals),
        "total_screened": len(stocks),
        "engine_version": ENGINE_VERSION,
        "note": "لا يوجد ضمان لتحقيق الأهداف. النظام يفلتر فقط الإشارات الأقرب فنياً لمدة 1-7 أيام.",
    }
    SIGNALS_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    if not signals:
        print("🚫 لا توجد إشارات تحقق شروط راصد Premium اليوم")
        return 1

    print(f"\n✅ Generated {len(signals)} premium signals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
