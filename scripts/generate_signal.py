#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — محرك الإشارات باستخدام Sahmk Starter بأقصى استفادة ممكنة.

الإضافات الحالية:
1) Sector Strength Score
2) Revenue & Profit Growth Score عبر fundamental_score.py
3) Dividend Catalyst Score عبر fundamental_score.py
4) Backtest Score من التاريخ السعري نفسه

القواعد المهمة:
- الإشارة العادية لا تُقبل إذا كان TP1 أقل من 4%.
- Gold لا يبقى Gold إلا إذا كان TP1 >= 6%.
- Platinum لا يبقى Platinum إلا إذا كان TP1 >= 8% أو TP2 >= 10%.
- لا يتوقف النظام إذا لم توجد إشارات.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from fundamental_score import score_symbol
except Exception:
    score_symbol = None

try:
    from self_learning_engine import get_learning_adjustment, load_learning_model
except Exception:
    get_learning_adjustment = None
    load_learning_model = None

try:
    from sector_rotation import build_sector_rotation
except Exception:
    build_sector_rotation = None

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_FILE = DATA_DIR / "daily.json"
SIGNALS_FILE = DATA_DIR / "signals.json"
HIST_CACHE_FILE = DATA_DIR / "historical_cache.json"

API_URL = os.getenv("API_URL", "https://app.sahmk.sa/api/v1").rstrip("/")
API_KEY = os.getenv("API_KEY") or os.getenv("SAHMK_API_KEY")
TIMEOUT = int(os.getenv("SAHMK_TIMEOUT", "20"))

ENGINE_VERSION = "rased_sahmk_starter_plus_v9"

HIST_DAYS = int(os.getenv("HIST_DAYS", "75"))
MIN_HISTORY_BARS = int(os.getenv("MIN_HISTORY_BARS", "25"))
LOOKBACK_RESISTANCE = int(os.getenv("LOOKBACK_RESISTANCE", "20"))
MAX_HOLD_DAYS = int(os.getenv("MAX_HOLD_DAYS", "7"))

MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", "72"))
MIN_RR = float(os.getenv("MIN_RR", "1.7"))
MIN_VOLUME_RATIO = float(os.getenv("MIN_VOLUME_RATIO", "0.85"))
MIN_VALUE_SAR = float(os.getenv("MIN_VALUE_SAR", "750000"))

MAX_ENTRY_GAP_PCT = float(os.getenv("MAX_ENTRY_GAP_PCT", "5.0"))
MAX_NEAR_RESISTANCE_PCT = float(os.getenv("MAX_NEAR_RESISTANCE_PCT", "10.0"))
MAX_TP2_ATR_MULTIPLE_7D = float(os.getenv("MAX_TP2_ATR_MULTIPLE_7D", "5.5"))

MIN_ATR_PCT = float(os.getenv("MIN_ATR_PCT", "0.5"))
MAX_ATR_PCT = float(os.getenv("MAX_ATR_PCT", "9.0"))
MIN_RSI = float(os.getenv("MIN_RSI", "38"))
MAX_RSI = float(os.getenv("MAX_RSI", "80"))

MIN_TP1_PCT_NORMAL = float(os.getenv("MIN_TP1_PCT_NORMAL", "4.0"))
MIN_TP1_PCT_GOLDEN = float(os.getenv("MIN_TP1_PCT_GOLDEN", "6.0"))
MIN_TP1_PCT_PLATINUM = float(os.getenv("MIN_TP1_PCT_PLATINUM", "8.0"))
MIN_TP2_PCT_PLATINUM = float(os.getenv("MIN_TP2_PCT_PLATINUM", "10.0"))

MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "50"))
ENABLE_FUNDAMENTAL_SCORE = os.getenv("ENABLE_FUNDAMENTAL_SCORE", "true").lower() != "false"
BLOCK_WEAK_FUNDAMENTALS = os.getenv("BLOCK_WEAK_FUNDAMENTALS", "false").lower() != "false"
ENABLE_SECTOR_STRENGTH = os.getenv("ENABLE_SECTOR_STRENGTH", "true").lower() != "false"
ENABLE_BACKTEST_SCORE = os.getenv("ENABLE_BACKTEST_SCORE", "true").lower() != "false"
ENABLE_SELF_LEARNING = os.getenv("ENABLE_SELF_LEARNING", "true").lower() != "false"


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


def headers() -> Dict[str, str]:
    if not API_KEY:
        raise RuntimeError("API_KEY / SAHMK_API_KEY غير موجود")
    return {
        "X-API-Key": API_KEY,
        "Accept": "application/json",
        "User-Agent": "Rased-Signal-Engine/9.0",
    }


def sahmk_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{API_URL}/{path.lstrip('/')}"
    r = requests.get(url, headers=headers(), params=params or {}, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"SAHMK {r.status_code}: {r.text[:250]}")
    return r.json()


def reject(symbol: str, reason: str) -> None:
    print(f"⚠️ {symbol}: {reason}")


def fetch_historical(symbol: str, days: int = HIST_DAYS) -> List[Dict[str, Any]]:
    to_d = date.today()
    from_d = to_d - timedelta(days=days + 30)
    payload = sahmk_get(
        f"historical/{symbol}/",
        {"from": from_d.isoformat(), "to": to_d.isoformat(), "interval": "1d"},
    )
    rows = payload.get("data", [])
    if not isinstance(rows, list):
        return []

    clean: List[Dict[str, Any]] = []
    for r in rows:
        high = fnum(r.get("high"))
        low = fnum(r.get("low"))
        close = fnum(r.get("close"))
        volume = fnum(r.get("volume"))
        if high > 0 and low > 0 and close > 0 and high >= low and volume > 0:
            clean.append(
                {
                    "date": r.get("date") or r.get("timestamp"),
                    "open": fnum(r.get("open")),
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "turnover": fnum(r.get("turnover")),
                }
            )
    clean.sort(key=lambda x: str(x.get("date")))
    return clean[-days:]


def true_range_rows(rows: List[Dict[str, Any]]) -> List[float]:
    trs: List[float] = []
    for i, r in enumerate(rows):
        high = fnum(r.get("high"))
        low = fnum(r.get("low"))
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
    gains: List[float] = []
    losses: List[float] = []
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
    prior = rows[-lookback - 1 : -1]
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
    strong = last > sma10 > sma20
    acceptable = last > sma20 and sma10 >= sma20 * 0.995
    vals = {"sma10": round(sma10, 3), "sma20": round(sma20, 3)}
    if strong:
        return True, ["اتجاه صاعد مؤكد"], vals
    if acceptable:
        return True, ["اتجاه مقبول قريب من الصعود"], vals
    return False, ["الترند غير مناسب"], vals


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
    elif volume_factor >= 1.15:
        boost = 1.08
    if is_breakout:
        boost *= 1.15
    effective_daily_range = max(atr_pct * 0.75 * boost, 0.3)
    return max(1, int(round(target_pct / effective_daily_range + 0.49)))


def classify_tier(score: float) -> Tuple[str, str]:
    if score >= 92:
        return "Platinum", "👑"
    if score >= 85:
        return "Gold", "🌟"
    if score >= 75:
        return "Premium", "⭐"
    return "Standard", "✅"


def risk_label(rr: float, atr_pct: float, rsi: float) -> Tuple[str, str]:
    if rr >= 2.5 and 0.5 <= atr_pct <= 6.5 and rsi <= 76:
        return "منخفض", "🟢"
    if rr >= 1.7 and 0.5 <= atr_pct <= 8.0 and rsi <= 80:
        return "متوسط", "🟡"
    return "مرتفع", "🔴"


def get_candidates(daily: Dict[str, Any]) -> List[Dict[str, Any]]:
    stocks = daily.get("stocks", []) if isinstance(daily, dict) else []
    good: List[Dict[str, Any]] = []
    for s in stocks:
        sym = str(s.get("symbol", "")).strip()
        price = fnum(s.get("current_price") or s.get("price"))
        volume = fnum(s.get("volume"))
        value = fnum(s.get("value") or s.get("turnover")) or price * volume
        change_pct = fnum(s.get("change_percent"))
        if sym and price > 0 and volume > 0:
            s["_candidate_value"] = value
            s["_candidate_rank"] = (value, max(change_pct, -5), volume)
            good.append(s)
    good.sort(key=lambda x: x.get("_candidate_rank", (0, 0, 0)), reverse=True)
    return good[:MAX_CANDIDATES]


def build_sector_strength(stocks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for s in stocks:
        sector = str(s.get("sector") or s.get("sector_name") or "").strip()
        if not sector:
            continue
        groups.setdefault(sector, []).append(s)

    out: Dict[str, Dict[str, Any]] = {}
    for sector, items in groups.items():
        changes = [fnum(x.get("change_percent")) for x in items]
        values = [fnum(x.get("value") or x.get("turnover")) or fnum(x.get("price") or x.get("current_price")) * fnum(x.get("volume")) for x in items]
        advancing = sum(1 for c in changes if c > 0)
        avg_change = mean(changes) if changes else 0.0
        advance_ratio = advancing / len(items) if items else 0.0
        total_value = sum(values)
        if avg_change >= 1.2 and advance_ratio >= 0.65:
            bonus = 7
            grade = "قوي جداً"
        elif avg_change >= 0.5 and advance_ratio >= 0.55:
            bonus = 5
            grade = "قوي"
        elif avg_change >= 0 and advance_ratio >= 0.45:
            bonus = 2
            grade = "محايد إيجابي"
        elif avg_change <= -1.0 and advance_ratio <= 0.35:
            bonus = -5
            grade = "ضعيف"
        else:
            bonus = 0
            grade = "محايد"
        out[sector] = {
            "bonus": bonus,
            "grade": grade,
            "avg_change_pct": round(avg_change, 2),
            "advance_ratio": round(advance_ratio, 2),
            "members": len(items),
            "total_value": round(total_value, 2),
        }
    return out


def calc_backtest_score(rows: List[Dict[str, Any]], atr_pct_now: float) -> Dict[str, Any]:
    if len(rows) < 45:
        return {"available": False, "bonus": 0, "grade": "غير كافٍ", "win_rate": 0, "trades": 0}

    wins = 0
    losses = 0
    trades = 0
    max_checks = min(45, len(rows) - 12)
    start = len(rows) - max_checks - 8
    start = max(25, start)

    for i in range(start, len(rows) - 7):
        sample = rows[: i + 1]
        if len(sample) < 25:
            continue
        res, sup = resistance_support(sample, LOOKBACK_RESISTANCE)
        if not res or not sup:
            continue
        close = fnum(sample[-1].get("close"))
        if close <= 0:
            continue
        near = ((res / close) - 1) * 100
        breakout = close >= res * 1.002
        near_breakout = 0 <= near <= MAX_NEAR_RESISTANCE_PCT
        if not (breakout or near_breakout):
            continue
        tr_ok, _, _ = trend_state(sample)
        if not tr_ok:
            continue

        entry = close
        target = entry * (1 + MIN_TP1_PCT_NORMAL / 100)
        stop = entry * (1 - max(1.5, min(4.0, atr_pct_now)) / 100)
        future = rows[i + 1 : i + 1 + MAX_HOLD_DAYS]
        if len(future) < 2:
            continue
        trades += 1
        outcome = None
        for fr in future:
            if fnum(fr.get("low")) <= stop:
                outcome = "loss"
                break
            if fnum(fr.get("high")) >= target:
                outcome = "win"
                break
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1

    if trades < 3:
        return {"available": False, "bonus": 0, "grade": "عينة صغيرة", "win_rate": 0, "trades": trades}

    win_rate = wins / trades
    if win_rate >= 0.70:
        bonus = 6
        grade = "قوي"
    elif win_rate >= 0.55:
        bonus = 4
        grade = "جيد"
    elif win_rate >= 0.45:
        bonus = 1
        grade = "محايد"
    else:
        bonus = -4
        grade = "ضعيف"

    return {
        "available": True,
        "bonus": bonus,
        "grade": grade,
        "win_rate": round(win_rate * 100, 1),
        "wins": wins,
        "losses": losses,
        "trades": trades,
    }


def calc_signal(stock: Dict[str, Any], rows: List[Dict[str, Any]], sector_stats: Optional[Dict[str, Dict[str, Any]]] = None, learning_model: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    symbol = str(stock.get("symbol", "")).strip()
    price = fnum(stock.get("current_price") or stock.get("price"))
    high = fnum(stock.get("high"))
    low = fnum(stock.get("low"))
    prev = fnum(stock.get("previous_close"))
    volume = fnum(stock.get("volume"))
    value = fnum(stock.get("value") or stock.get("turnover")) or price * volume
    change_pct = fnum(stock.get("change_percent"))
    sector = str(stock.get("sector") or stock.get("sector_name") or "").strip()

    if not symbol:
        return None
    if price <= 0:
        reject(symbol, "السعر غير صالح")
        return None
    if volume <= 0:
        reject(symbol, "الحجم صفر أو غير صالح")
        return None
    if value < MIN_VALUE_SAR:
        reject(symbol, f"قيمة التداول {value:,.0f} أقل من {MIN_VALUE_SAR:,.0f}")
        return None
    if len(rows) < MIN_HISTORY_BARS:
        reject(symbol, f"Historical غير كافٍ من Sahmk ({len(rows)}/{MIN_HISTORY_BARS})")
        return None

    today = date.today().isoformat()
    if high > 0 and low > 0 and price > 0:
        today_row = {"date": today, "open": stock.get("open") or prev or price, "high": high, "low": low, "close": price, "volume": volume, "turnover": value}
        if not rows or str(rows[-1].get("date")) != today:
            rows = rows + [today_row]
        else:
            rows = rows[:-1] + [today_row]

    atr14 = atr(rows, 14)
    if not atr14 or atr14 <= 0:
        reject(symbol, "ATR غير صالح")
        return None
    atr_pct = round((atr14 / price) * 100, 2)
    if not (MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT):
        reject(symbol, f"ATR% {atr_pct} خارج النطاق {MIN_ATR_PCT}-{MAX_ATR_PCT}")
        return None

    resistance, support = resistance_support(rows)
    if not resistance or not support:
        reject(symbol, "الدعم/المقاومة غير كافية")
        return None

    closes = [fnum(r.get("close")) for r in rows]
    rsi = calc_rsi(closes, 14)
    if rsi is None:
        reject(symbol, "RSI غير متوفر")
        return None

    vol_ratio = volume_ratio(rows[:-1], volume, 20)
    trend_ok, trend_reasons, trend_vals = trend_state(rows)
    if not trend_ok:
        reject(symbol, "الترند غير مناسب")
        return None

    near_breakout_pct = ((resistance / price) - 1) * 100 if price > 0 else 99
    is_breakout = price >= resistance * 1.002
    is_near_breakout = 0 <= near_breakout_pct <= MAX_NEAR_RESISTANCE_PCT
    if is_breakout:
        entry = round(max(price, resistance * 1.003), 2)
        setup_type = "اختراق مؤكد"
    elif is_near_breakout:
        entry = round(resistance * 1.003, 2)
        setup_type = "دخول مشروط فوق المقاومة"
    else:
        reject(symbol, f"بعيد عن المقاومة: {near_breakout_pct:.2f}%")
        return None

    entry_gap_pct = round((entry / price - 1) * 100, 2)
    if entry_gap_pct > MAX_ENTRY_GAP_PCT:
        reject(symbol, f"فجوة الدخول {entry_gap_pct}% أكبر من {MAX_ENTRY_GAP_PCT}%")
        return None

    stop_by_atr = entry - atr14 * 1.25
    stop_by_support = support * 0.995
    stop_loss = round(max(stop_by_atr, stop_by_support), 2)
    risk_amount = round(entry - stop_loss, 4)
    if risk_amount <= 0:
        reject(symbol, "وقف الخسارة غير منطقي")
        return None

    target1 = round(entry + risk_amount * 1.45, 2)
    target2 = round(entry + risk_amount * MIN_RR, 2)
    rr = round((target2 - entry) / risk_amount, 2)
    if rr < MIN_RR:
        reject(symbol, f"R:R {rr} أقل من {MIN_RR}")
        return None

    target1_pct = pct(target1 - entry, entry)
    target2_pct = pct(target2 - entry, entry)
    stop_loss_pct = abs(pct(stop_loss - entry, entry))

    if target1_pct < MIN_TP1_PCT_NORMAL:
        reject(symbol, f"TP1% {target1_pct}% أقل من الحد الأدنى للإشارة العادية {MIN_TP1_PCT_NORMAL}%")
        return None

    max_reasonable_7d_pct = round(atr_pct * MAX_TP2_ATR_MULTIPLE_7D, 2)
    expected_days_tp1 = expected_days_to_target(target1_pct, atr_pct, vol_ratio, is_breakout)
    expected_days_tp2 = expected_days_to_target(target2_pct, atr_pct, vol_ratio, is_breakout)
    if expected_days_tp2 > MAX_HOLD_DAYS:
        reject(symbol, f"TP2 يحتاج {expected_days_tp2} أيام > {MAX_HOLD_DAYS}")
        return None
    if target2_pct > max_reasonable_7d_pct:
        reject(symbol, f"TP2% {target2_pct}% أعلى من المنطقي 7 أيام {max_reasonable_7d_pct}%")
        return None
    if not (MIN_RSI <= rsi <= MAX_RSI):
        reject(symbol, f"RSI {rsi} خارج النطاق {MIN_RSI}-{MAX_RSI}")
        return None
    if vol_ratio < MIN_VOLUME_RATIO:
        reject(symbol, f"Volume {vol_ratio}x أقل من {MIN_VOLUME_RATIO}x")
        return None
    if not (-1.0 <= change_pct <= 8.0):
        reject(symbol, f"التغير اليومي {change_pct}% غير مناسب")
        return None

    score = 0
    reasons: List[str] = []
    fundamental = {"available": False, "bonus": 0, "grade": "غير متوفر", "blocked": False, "details": "لم يتم تفعيل التحليل الأساسي", "raw": {}}
    sector_reading = {"available": False, "bonus": 0, "grade": "غير متوفر"}
    backtest = {"available": False, "bonus": 0, "grade": "غير متوفر", "win_rate": 0, "trades": 0}
    self_learning = {"available": False, "bonus": 0, "notes": [], "known_outcomes": 0}

    score += 18
    reasons += trend_reasons

    if 52 <= rsi <= 64:
        score += 18
        reasons.append(f"زخم صحي RSI {rsi:.1f}")
    elif MIN_RSI <= rsi <= MAX_RSI:
        score += 13
        reasons.append(f"RSI مقبول {rsi:.1f}")

    if vol_ratio >= 3:
        score += 18
        reasons.append(f"سيولة قوية جداً {vol_ratio:.1f}x")
    elif vol_ratio >= 2:
        score += 15
        reasons.append(f"سيولة قوية {vol_ratio:.1f}x")
    elif vol_ratio >= 1.15:
        score += 11
        reasons.append(f"سيولة مقبولة {vol_ratio:.1f}x")
    elif vol_ratio >= 0.85:
        score += 7
        reasons.append(f"سيولة طبيعية {vol_ratio:.1f}x")

    if is_breakout:
        score += 22
        reasons.append("اختراق مقاومة مؤكد")
    else:
        score += 16
        reasons.append("قريب من اختراق مقاومة مهمة")

    if 0.5 <= change_pct <= 5.5:
        score += 10
        reasons.append(f"زخم يومي صحي {change_pct:+.1f}%")
    elif -1.0 <= change_pct < 0.5:
        score += 5
        reasons.append("هدوء سعري قبل اختراق محتمل")
    elif 5.5 < change_pct <= 8.0:
        score += 4
        reasons.append("زخم مرتفع — مراقبة عدم المطاردة")

    if value >= 5_000_000:
        score += 9
        reasons.append("قيمة تداول مناسبة")
    elif value >= MIN_VALUE_SAR:
        score += 5
        reasons.append("قيمة تداول مقبولة")

    if expected_days_tp2 <= 5:
        score += 5
        reasons.append("الهدف الثاني منطقي زمنياً")
    elif expected_days_tp2 <= 7:
        score += 3
        reasons.append("الهدف الثاني ضمن نطاق 7 أيام")

    technical_score = score

    if ENABLE_SECTOR_STRENGTH and sector and sector_stats and sector in sector_stats:
        sector_reading = {"available": True, **sector_stats[sector]}
        sector_bonus = int(sector_reading.get("bonus", 0))
        score += sector_bonus
        if sector_bonus > 0:
            reasons.append(f"دعم قطاعي +{sector_bonus}: {sector_reading.get('grade')} ({sector_reading.get('avg_change_pct')}%)")
        elif sector_bonus < 0:
            reasons.append(f"ضغط قطاعي {sector_bonus}: {sector_reading.get('grade')} ({sector_reading.get('avg_change_pct')}%)")

    if ENABLE_BACKTEST_SCORE:
        backtest = calc_backtest_score(rows, atr_pct)
        bt_bonus = int(backtest.get("bonus", 0))
        score += bt_bonus
        if bt_bonus > 0:
            reasons.append(f"دعم باك تست +{bt_bonus}: نجاح {backtest.get('win_rate')}%")
        elif bt_bonus < 0:
            reasons.append(f"خصم باك تست {bt_bonus}: نجاح {backtest.get('win_rate')}%")

    if ENABLE_FUNDAMENTAL_SCORE and score_symbol is not None:
        try:
            fundamental = score_symbol(symbol, sector)
            if BLOCK_WEAK_FUNDAMENTALS and fundamental.get("blocked"):
                reject(symbol, f"أساسيات سلبية: {fundamental.get('details')}")
                return None
            bonus = int(fundamental.get("bonus", 0))
            score += bonus
            if bonus > 0:
                reasons.append(f"دعم أساسي +{bonus}: {fundamental.get('details')}")
            elif bonus < 0:
                reasons.append(f"خصم أساسي {bonus}: {fundamental.get('details')}")
            else:
                reasons.append(f"أساسيات محايدة: {fundamental.get('details')}")
        except Exception as exc:
            print(f"⚠️ {symbol}: fundamental score skipped: {exc}")


    if ENABLE_SELF_LEARNING and get_learning_adjustment is not None:
        try:
            learning_probe = {
                "symbol": symbol,
                "stock_symbol": symbol,
                "sector": sector,
                "rsi": rsi,
                "volume_ratio": vol_ratio,
                "rr": rr,
                "rr_ratio": rr,
            }
            self_learning = get_learning_adjustment(learning_probe, learning_model)
            learning_bonus = int(self_learning.get("bonus", 0))
            score += learning_bonus
            if learning_bonus > 0:
                reasons.append(f"تعلم ذاتي +{learning_bonus}: تحسن تاريخي في ظروف مشابهة")
            elif learning_bonus < 0:
                reasons.append(f"خصم تعلم ذاتي {learning_bonus}: أداء تاريخي أضعف في ظروف مشابهة")
        except Exception as exc:
            print(f"⚠️ {symbol}: self-learning skipped: {exc}")

    score = max(0, min(score, 100))
    if score < MIN_SIGNAL_SCORE:
        reject(symbol, f"Score {score} أقل من {MIN_SIGNAL_SCORE}")
        return None

    rr_score = min(rr * 28, 100)
    time_score = max(0, 100 - (expected_days_tp2 - 1) * 8)
    rased_score = round(score * 0.50 + rr_score * 0.25 + time_score * 0.25, 1)

    tier, tier_emoji = classify_tier(rased_score)
    if tier == "Platinum" and target1_pct < MIN_TP1_PCT_PLATINUM and target2_pct < MIN_TP2_PCT_PLATINUM:
        tier = "Gold"
        tier_emoji = "🌟"
    if tier == "Gold" and target1_pct < MIN_TP1_PCT_GOLDEN:
        tier = "Premium"
        tier_emoji = "⭐"

    risk_text, risk_emoji = risk_label(rr, atr_pct, rsi)
    signal_id = f"Signal #{datetime.now().strftime('%Y')}-{datetime.now().strftime('%j%H%M')}-{symbol}"

    return {
        "stock_symbol": symbol,
        "symbol": symbol,
        "stock_name": stock.get("name") or stock.get("name_ar") or symbol,
        "name": stock.get("name") or stock.get("name_ar") or symbol,
        "sector": sector,
        "current_price": round(price, 2),
        "entry_point": entry,
        "entry": entry,
        "target1": target1,
        "target2": target2,
        "stop_loss": stop_loss,
        "target1_percent": target1_pct,
        "target2_percent": target2_pct,
        "stop_loss_percent": round(stop_loss_pct, 2),
        "tp1_pct": target1_pct,
        "tp2_pct": target2_pct,
        "sl_pct": round(-stop_loss_pct, 2),
        "rr": rr,
        "rr_ratio": rr,
        "score": score,
        "technical_score": technical_score,
        "sector_strength_bonus": int(sector_reading.get("bonus", 0)),
        "sector_strength_grade": sector_reading.get("grade", "غير متوفر"),
        "sector_strength_raw": sector_reading,
        "backtest_bonus": int(backtest.get("bonus", 0)),
        "backtest_grade": backtest.get("grade", "غير متوفر"),
        "backtest_win_rate": backtest.get("win_rate", 0),
        "backtest_trades": backtest.get("trades", 0),
        "backtest_raw": backtest,
        "self_learning_bonus": int(self_learning.get("bonus", 0)),
        "self_learning_available": bool(self_learning.get("available", False)),
        "self_learning_known_outcomes": int(self_learning.get("known_outcomes", 0)),
        "self_learning_notes": self_learning.get("notes", []),
        "fundamental_bonus": int(fundamental.get("bonus", 0)),
        "fundamental_grade": fundamental.get("grade", "غير متوفر"),
        "fundamental_reading": fundamental.get("details", ""),
        "fundamental_raw": fundamental.get("raw", {}),
        "growth_bonus": int(fundamental.get("growth_bonus", 0)),
        "dividend_bonus": int(fundamental.get("dividend_bonus", 0)),
        "rased_score": rased_score,
        "tier": tier,
        "tier_emoji": tier_emoji,
        "risk_level": risk_text,
        "risk_level_ar": risk_text,
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
        "holding_period": "1 - 7 أيام",
        "max_holding_days": MAX_HOLD_DAYS,
        "expected_days_to_target1": expected_days_tp1,
        "expected_days_to_target2": expected_days_tp2,
        "seven_day_filter_passed": True,
        "max_reasonable_7d_pct": max_reasonable_7d_pct,
        "technical_reading": " — ".join(reasons[:7]),
        "signal_reason": "اجتازت فلاتر راصد الفنية مع تقييم القطاع، النمو المالي، التوزيعات، الباك تست، والتعلم الذاتي عند توفر البيانات.",
        "key_insight": "الإشارة مرشحة لمضاربة قصيرة المدى خلال 1-7 أيام بشرط الالتزام بوقف الخسارة.",
        "signal_id": signal_id,
        "data_source": "sahmk_api_historical_starter_plus",
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
        "status": "NO_SIGNALS",
        "message": reason,
        "engine_version": ENGINE_VERSION,
        "provider": "sahmk",
    }
    write_json(SIGNALS_FILE, out)
    print(f"ℹ️ {reason}")
    return 0


def main() -> int:
    print("=" * 60)
    print("🚀 راصد — Sahmk Starter Plus Signal Engine")
    print("=" * 60)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not API_KEY:
        return save_blocked("API_KEY غير موجود")

    daily = load_json(DAILY_FILE, {})
    if daily.get("provider") != "sahmk" or daily.get("data_source") != "api":
        return save_blocked("daily.json ليس من Sahmk API الحقيقي")

    stocks = daily.get("stocks", []) if isinstance(daily, dict) else []
    candidates = get_candidates(daily)
    if not candidates:
        return save_blocked("لا توجد أسهم مرشحة في daily.json")

    sector_stats = build_sector_strength(stocks)
    learning_model = None
    if ENABLE_SELF_LEARNING and load_learning_model is not None:
        try:
            learning_model = load_learning_model()
            print(f"🧠 Self-learning loaded: {learning_model.get('total_known_outcomes', 0)} outcomes")
        except Exception as exc:
            print(f"⚠️ self-learning unavailable: {exc}")
    hist_cache: Dict[str, Any] = {"updated_at": datetime.now().isoformat(timespec="seconds"), "symbols": {}}
    signals: List[Dict[str, Any]] = []

    for stock in candidates:
        sym = str(stock.get("symbol", "")).strip()
        try:
            rows = fetch_historical(sym, HIST_DAYS)
            hist_cache["symbols"][sym] = {"count": len(rows), "latest": rows[-1].get("date") if rows else None}
            sig = calc_signal(stock, rows, sector_stats, learning_model)
            if sig:
                signals.append(sig)
                print(f"✅ {sym}: {sig['tier']} | RASED {sig['rased_score']} | TP1 +{sig['target1_percent']}% | TP2 +{sig['target2_percent']}%")
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
        "sector_strength": sector_stats,
        "filters": {
            "MIN_SIGNAL_SCORE": MIN_SIGNAL_SCORE,
            "MIN_RR": MIN_RR,
            "MIN_VOLUME_RATIO": MIN_VOLUME_RATIO,
            "MIN_VALUE_SAR": MIN_VALUE_SAR,
            "MIN_RSI": MIN_RSI,
            "MAX_RSI": MAX_RSI,
            "MAX_HOLD_DAYS": MAX_HOLD_DAYS,
            "MIN_TP1_PCT_NORMAL": MIN_TP1_PCT_NORMAL,
            "MIN_TP1_PCT_GOLDEN": MIN_TP1_PCT_GOLDEN,
            "MIN_TP1_PCT_PLATINUM": MIN_TP1_PCT_PLATINUM,
            "MIN_TP2_PCT_PLATINUM": MIN_TP2_PCT_PLATINUM,
            "ENABLE_FUNDAMENTAL_SCORE": ENABLE_FUNDAMENTAL_SCORE,
            "ENABLE_SECTOR_STRENGTH": ENABLE_SECTOR_STRENGTH,
            "ENABLE_BACKTEST_SCORE": ENABLE_BACKTEST_SCORE,
            "ENABLE_SELF_LEARNING": ENABLE_SELF_LEARNING,
            "BLOCK_WEAK_FUNDAMENTALS": BLOCK_WEAK_FUNDAMENTALS,
        },
        "note": "لا يوجد ضمان لتحقيق الأهداف. النظام يفلتر فقط الإشارات الأقرب فنياً لمدة 1-7 أيام.",
    }

    if not signals:
        out["status"] = "NO_SIGNALS"
        out["message"] = "لا توجد إشارات تحقق شروط راصد اليوم"
        write_json(SIGNALS_FILE, out)
        print("ℹ️ لا توجد إشارات تحقق شروط راصد اليوم — انتهاء ناجح بدون خطأ")
        return 0

    out["status"] = "HAS_SIGNALS"
    write_json(SIGNALS_FILE, out)
    if build_sector_rotation is not None:
        try:
            build_sector_rotation()
        except Exception as exc:
            print(f"⚠️ sector rotation skipped: {exc}")
    print(f"\n✅ Generated {len(signals)} Sahmk Starter Plus signals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
