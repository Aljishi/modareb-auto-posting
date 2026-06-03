#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""راصد — محرك إشارة Premium يعتمد على Sahmk Historical API مباشرة.

ماذا يفعل:
- لا ينتظر market_history.json.
- يجلب Historical OHLCV لكل سهم من Sahmk: /historical/{symbol}/?interval=1d
- يحسب ATR / RSI / Volume Ratio / Support / Resistance من البيانات التاريخية الحقيقية.
- يرفض الإشارة إذا هدف TP2 غير منطقي فنياً خلال 1–7 أيام.

مهم: لا يوجد ضمان لتحقيق الأهداف خلال 7 أيام. الكود يختار فقط الإشارات ذات الاحتمال الفني الأعلى.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_FILE = DATA_DIR / "daily.json"
SIGNALS_FILE = DATA_DIR / "signals.json"
HIST_CACHE_FILE = DATA_DIR / "historical_cache.json"

API_URL = os.getenv("API_URL", "https://app.sahmk.sa/api/v1").rstrip("/")
API_KEY = os.getenv("API_KEY") or os.getenv("SAHMK_API_KEY")
TIMEOUT = int(os.getenv("SAHMK_TIMEOUT", "20"))
ENGINE_VERSION = "rased_sahmk_paid_historical_7d_v1"

HIST_DAYS = int(os.getenv("HIST_DAYS", "75"))
MIN_HISTORY_BARS = int(os.getenv("MIN_HISTORY_BARS", "30"))
LOOKBACK_RESISTANCE = int(os.getenv("LOOKBACK_RESISTANCE", "20"))
MAX_HOLD_DAYS = int(os.getenv("MAX_HOLD_DAYS", "7"))

MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", "84"))
MIN_RR = float(os.getenv("MIN_RR", "2.2"))
MIN_VOLUME_RATIO = float(os.getenv("MIN_VOLUME_RATIO", "1.7"))
MIN_VALUE_SAR = float(os.getenv("MIN_VALUE_SAR", "3000000"))
MAX_ENTRY_GAP_PCT = float(os.getenv("MAX_ENTRY_GAP_PCT", "1.2"))
MAX_TP2_ATR_MULTIPLE_7D = float(os.getenv("MAX_TP2_ATR_MULTIPLE_7D", "5.0"))
MIN_ATR_PCT = float(os.getenv("MIN_ATR_PCT", "0.7"))
MAX_ATR_PCT = float(os.getenv("MAX_ATR_PCT", "8.0"))
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "30"))


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
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def headers() -> Dict[str, str]:
    if not API_KEY:
        raise RuntimeError("API_KEY / SAHMK_API_KEY غير موجود")
    return {"X-API-Key": API_KEY, "Accept": "application/json"}


def sahmk_get(path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = f"{API_URL}/{path.lstrip('/')}"
    r = requests.get(url, headers=headers(), params=params or {}, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"SAHMK {r.status_code}: {r.text[:250]}")
    return r.json()


def fetch_historical(symbol: str, days: int = HIST_DAYS) -> List[Dict[str, Any]]:
    to_d = date.today()
    from_d = to_d - timedelta(days=days + 20)  # buffer للويكند والإجازات
    payload = sahmk_get(
        f"historical/{symbol}/",
        {"from": from_d.isoformat(), "to": to_d.isoformat(), "interval": "1d"},
    )
    rows = payload.get("data", [])
    if not isinstance(rows, list):
        return []
    clean = []
    for r in rows:
        high = fnum(r.get("high")); low = fnum(r.get("low")); close = fnum(r.get("close")); volume = fnum(r.get("volume"))
        if high > 0 and low > 0 and close > 0 and high >= low and volume > 0:
            clean.append({
                "date": r.get("date") or r.get("timestamp"),
                "open": fnum(r.get("open")),
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "turnover": fnum(r.get("turnover")),
            })
    clean.sort(key=lambda x: str(x.get("date")))
    return clean[-days:]


def true_range_rows(rows: List[Dict[str, Any]]) -> List[float]:
    trs = []
    for i, r in enumerate(rows):
        high = fnum(r.get("high")); low = fnum(r.get("low"))
        prev_close = fnum(rows[i - 1].get("close")) if i > 0 else fnum(r.get("close"))
        if high > 0 and low > 0 and prev_close > 0 and high >= low:
            trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return trs


def atr(rows: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
    trs = true_range_rows(rows)
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
    if len(vols) < 10 or current_volume <= 0:
        return 0.0
    avg = mean(vols)
    return round(current_volume / avg, 2) if avg > 0 else 0.0


def resistance_support(rows: List[Dict[str, Any]], lookback: int = LOOKBACK_RESISTANCE) -> Tuple[Optional[float], Optional[float]]:
    prior = rows[-lookback - 1:-1]
    highs = [fnum(r.get("high")) for r in prior if fnum(r.get("high")) > 0]
    lows = [fnum(r.get("low")) for r in prior if fnum(r.get("low")) > 0]
    if len(highs) < 10 or len(lows) < 10:
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


def pct(diff: float, entry: float) -> float:
    return round((diff / entry) * 100, 2) if entry > 0 else 0.0


def expected_days_to_target(target_pct: float, atr_pct: float, volume_factor: float, is_breakout: bool) -> int:
    if atr_pct <= 0:
        return 99
    boost = 1.0
    if volume_factor >= 3:
        boost = 1.35
    elif volume_factor >= 2:
        boost = 1.20
    elif volume_factor >= 1.7:
        boost = 1.10
    if is_breakout:
        boost *= 1.15
    effective_daily_range = max(atr_pct * 0.75 * boost, 0.3)
    return max(1, int(round(target_pct / effective_daily_range + 0.49)))


def classify_tier(score: float) -> Tuple[str, str]:
    if score >= 95:
        return "Platinum", "👑"
    if score >= 90:
        return "Gold", "🌟"
    if score >= 85:
        return "Premium", "⭐"
    return "Standard", "✅"


def risk_label(rr: float, atr_pct: float, rsi: float) -> Tuple[str, str]:
    if rr >= 3 and 1.0 <= atr_pct <= 4.5 and rsi <= 64:
        return "منخفض", "🟢"
    if rr >= 2.2 and 0.7 <= atr_pct <= 6.0 and rsi <= 68:
        return "متوسط", "🟡"
    return "مرتفع", "🔴"


def get_candidates(daily: Dict[str, Any]) -> List[Dict[str, Any]]:
    stocks = daily.get("stocks", []) if isinstance(daily, dict) else []
    good = []
    for s in stocks:
        sym = str(s.get("symbol", "")).strip()
        price = fnum(s.get("current_price") or s.get("price"))
        if sym and price > 0:
            good.append(s)
    return good[:MAX_CANDIDATES]


def calc_signal(stock: Dict[str, Any], rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    symbol = str(stock.get("symbol", "")).strip()
    price = fnum(stock.get("current_price") or stock.get("price"))
    high = fnum(stock.get("high")); low = fnum(stock.get("low")); prev = fnum(stock.get("previous_close"))
    volume = fnum(stock.get("volume"))
    value = fnum(stock.get("value") or stock.get("turnover")) or price * volume
    change_pct = fnum(stock.get("change_percent"))

    if not symbol or price <= 0 or volume <= 0 or value < MIN_VALUE_SAR:
        return None
    if len(rows) < MIN_HISTORY_BARS:
        print(f"  ⚠️ {symbol}: Historical غير كافٍ من Sahmk ({len(rows)}/{MIN_HISTORY_BARS})")
        return None

    # أضف شمعة اليوم من quote إذا كانت أحدث من التاريخي
    today = date.today().isoformat()
    if high > 0 and low > 0 and price > 0:
        today_row = {"date": today, "open": stock.get("open") or prev or price, "high": high, "low": low, "close": price, "volume": volume, "turnover": value}
        if not rows or str(rows[-1].get("date")) != today:
            rows = rows + [today_row]
        else:
            rows = rows[:-1] + [today_row]

    atr14 = atr(rows, 14)
    if not atr14 or atr14 <= 0:
        return None
    atr_pct = round((atr14 / price) * 100, 2)
    if not (MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT):
        return None

    resistance, support = resistance_support(rows)
    if not resistance or not support:
        return None

    closes = [fnum(r.get("close")) for r in rows]
    rsi = calc_rsi(closes, 14)
    if rsi is None:
        return None
    vol_ratio = volume_ratio(rows[:-1], volume, 20)
    trend_ok, trend_reasons, trend_vals = trend_state(rows)
    if not trend_ok:
        return None

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
    stop_loss_pct = abs(pct(stop_loss - entry, entry))

    max_reasonable_7d_pct = round(atr_pct * MAX_TP2_ATR_MULTIPLE_7D, 2)
    expected_days_tp1 = expected_days_to_target(target1_pct, atr_pct, vol_ratio, is_breakout)
    expected_days_tp2 = expected_days_to_target(target2_pct, atr_pct, vol_ratio, is_breakout)
    if expected_days_tp2 > MAX_HOLD_DAYS or target2_pct > max_reasonable_7d_pct:
        return None

    if not (48 <= rsi <= 68):
        return None
    if vol_ratio < MIN_VOLUME_RATIO:
        return None
    if not (0.3 <= change_pct <= 7.0):
        return None

    score = 0
    reasons: List[str] = []
    score += 18; reasons += trend_reasons
    if 52 <= rsi <= 64:
        score += 18; reasons.append(f"زخم صحي RSI {rsi:.1f}")
    else:
        score += 12; reasons.append(f"RSI مقبول {rsi:.1f}")
    if vol_ratio >= 3:
        score += 18; reasons.append(f"سيولة قوية جداً {vol_ratio:.1f}x")
    elif vol_ratio >= 2:
        score += 15; reasons.append(f"سيولة قوية {vol_ratio:.1f}x")
    else:
        score += 10; reasons.append(f"سيولة مؤكدة {vol_ratio:.1f}x")
    if is_breakout:
        score += 22; reasons.append("اختراق مقاومة مؤكد")
    else:
        score += 16; reasons.append("قريب من اختراق مقاومة مهمة")
    if 0.5 <= change_pct <= 5.5:
        score += 10; reasons.append(f"زخم يومي صحي {change_pct:+.1f}%")
    elif 5.5 < change_pct <= 7.0:
        score += 4; reasons.append("زخم مرتفع — مراقبة عدم المطاردة")
    if value >= 5_000_000:
        score += 9; reasons.append("قيمة تداول مناسبة")
    if expected_days_tp2 <= 5:
        score += 5; reasons.append("الهدف الثاني منطقي زمنياً")

    score = min(score, 100)
    if score < MIN_SIGNAL_SCORE:
        return None

    rr_score = min(rr * 28, 100)
    time_score = max(0, 100 - (expected_days_tp2 - 1) * 8)
    rased_score = round(score * 0.50 + rr_score * 0.25 + time_score * 0.25, 1)
    tier, tier_emoji = classify_tier(rased_score)
    risk_text, risk_emoji = risk_label(rr, atr_pct, rsi)

    return {
        "stock_symbol": symbol,
        "symbol": symbol,
        "stock_name": stock.get("name") or stock.get("name_ar") or symbol,
        "name": stock.get("name") or stock.get("name_ar") or symbol,
        "sector": stock.get("sector", ""),
        "current_price": round(price, 2),
        "entry_point": entry,
        "entry": entry,
        "target1": target1,
        "target2": target2,
        "stop_loss": stop_loss,
        "target1_percent": target1_pct,
        "target2_percent": target2_pct,
        "stop_loss_percent": round(stop_loss_pct, 2),
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
        "data_source": "sahmk_api_historical",
        "provider": "sahmk",
        "historical_bars": len(rows),
        "engine_version": ENGINE_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": "لا يوجد ضمان لتحقيق الأهداف خلال 7 أيام. هذه قراءة فنية آلية فقط.",
    }


def save_blocked(reason: str, total_screened: int = 0) -> int:
    out = {
        "signals": [],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": 0,
        "total_screened": total_screened,
        "blocked_reason": reason,
        "engine_version": ENGINE_VERSION,
    }
    write_json(SIGNALS_FILE, out)
    print(f"🚫 {reason}")
    return 1


def main() -> int:
    print("=" * 60)
    print("🚀 راصد — Sahmk Historical Premium Signal Engine 7D")
    print("=" * 60)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not API_KEY:
        return save_blocked("API_KEY غير موجود")

    daily = load_json(DAILY_FILE, {})
    if daily.get("provider") != "sahmk" or daily.get("data_source") != "api":
        return save_blocked("daily.json ليس من Sahmk API الحقيقي")

    candidates = get_candidates(daily)
    if not candidates:
        return save_blocked("لا توجد أسهم مرشحة في daily.json")

    hist_cache: Dict[str, Any] = {"updated_at": datetime.now().isoformat(timespec="seconds"), "symbols": {}}
    signals: List[Dict[str, Any]] = []

    for stock in candidates:
        sym = str(stock.get("symbol", "")).strip()
        try:
            rows = fetch_historical(sym, HIST_DAYS)
            hist_cache["symbols"][sym] = {"count": len(rows), "latest": rows[-1].get("date") if rows else None}
            sig = calc_signal(stock, rows)
            if sig:
                signals.append(sig)
                print(f"✅ {sym}: {sig['tier']} | RASED {sig['rased_score']} | TP2 +{sig['target2_percent']}% | {sig['expected_days_to_target2']}d")
            else:
                print(f"— {sym}: لا يطابق فلاتر راصد")
        except Exception as exc:
            print(f"⚠️ {sym}: historical failed: {exc}")

    write_json(HIST_CACHE_FILE, hist_cache)

    signals.sort(key=lambda s: (s.get("rased_score", 0), s.get("score", 0), s.get("rr", 0)), reverse=True)
    signals = signals[:5]
    out = {
        "signals": signals,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(signals),
        "total_screened": len(candidates),
        "engine_version": ENGINE_VERSION,
        "provider": "sahmk",
        "historical_source": "GET /historical/{symbol}/ interval=1d",
        "note": "لا يوجد ضمان لتحقيق الأهداف. النظام يفلتر فقط الإشارات الأقرب فنياً لمدة 1-7 أيام.",
    }
    write_json(SIGNALS_FILE, out)

    if not signals:
        print("🚫 لا توجد إشارات تحقق شروط راصد Premium اليوم")
        return 1
    print(f"\n✅ Generated {len(signals)} Sahmk historical premium signals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
