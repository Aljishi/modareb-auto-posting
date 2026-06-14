#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Golden Signal Analysis

يدعم وضعين:
1) GOLDEN_RUN_MODE=premarket
   - يعمل 09:30 صباحاً KSA.
   - يبحث عن أفضل إشارة ذهبية قبل الافتتاح.
   - لا ينشر ذهبية إذا فشلت مراجعة OpenAI عند REQUIRE_OPENAI_FOR_GOLDEN=true.
   - يحفظ المرشح في data/golden_candidate.json لاستخدامه في تأكيد 10:30.

2) GOLDEN_RUN_MODE=confirmation
   - يعمل 10:30 صباحاً KSA.
   - يؤكد أو يلغي الإشارة الذهبية الصباحية بعد افتتاح السوق.
   - ينشر رسالة تأكيد أو إلغاء عبر data/golden_signals.json.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_FILE = DATA_DIR / "daily.json"
GOLDEN_FILE = DATA_DIR / "golden_signals.json"
GOLDEN_CANDIDATE_FILE = DATA_DIR / "golden_candidate.json"

API_URL = os.getenv("API_URL", "https://app.sahmk.sa/api/v1").rstrip("/")
API_KEY = os.getenv("API_KEY") or os.getenv("SAHMK_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

GOLDEN_RUN_MODE = os.getenv("GOLDEN_RUN_MODE", "premarket").strip().lower()
REQUIRE_OPENAI_FOR_GOLDEN = os.getenv("REQUIRE_OPENAI_FOR_GOLDEN", "true").lower() != "false"

MIN_GOLDEN_RASED_SCORE = float(os.getenv("MIN_GOLDEN_RASED_SCORE", "85"))
MIN_GOLDEN_TP1_PCT = float(os.getenv("MIN_GOLDEN_TP1_PCT", "6.0"))
MIN_GOLDEN_TP2_PCT = float(os.getenv("MIN_GOLDEN_TP2_PCT", "8.0"))
MIN_GOLDEN_RR = float(os.getenv("MIN_GOLDEN_RR", "2.5"))
MIN_GOLDEN_VOLUME_RATIO = float(os.getenv("MIN_GOLDEN_VOLUME_RATIO", "1.15"))
MIN_GOLDEN_VALUE = float(os.getenv("MIN_GOLDEN_VALUE", "1000000"))
MAX_GOLDEN_RSI = float(os.getenv("MAX_GOLDEN_RSI", "78"))
MIN_GOLDEN_RSI = float(os.getenv("MIN_GOLDEN_RSI", "42"))
MAX_HOLD_DAYS = int(os.getenv("MAX_HOLD_DAYS", "7"))

CONFIRM_MIN_VOLUME_RATIO = float(os.getenv("CONFIRM_MIN_VOLUME_RATIO", "1.00"))
CONFIRM_MAX_DROP_FROM_ENTRY_PCT = float(os.getenv("CONFIRM_MAX_DROP_FROM_ENTRY_PCT", "1.20"))
CONFIRM_MIN_CURRENT_VS_ENTRY_PCT = float(os.getenv("CONFIRM_MIN_CURRENT_VS_ENTRY_PCT", "-0.80"))

SYMBOLS_FALLBACK = [
    "1120", "1180", "2010", "2222", "2082", "2200", "1211", "2380", "1303", "4190",
    "7203", "7030", "8010", "4007", "2286", "1321", "4142", "4030", "1150", "1050",
]


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
        print(f"⚠️ Cannot read {path.name}: {exc}")
    return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def headers() -> Dict[str, str]:
    h = {"Accept": "application/json", "User-Agent": "Rased-Golden/2.0"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def sahmk_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{API_URL}/{path.lstrip('/')}"
    r = requests.get(url, headers=headers(), params=params or {}, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"SAHMK {r.status_code}: {r.text[:250]}")
    return r.json()


def fetch_historical(symbol: str, days: int = 90) -> List[Dict[str, Any]]:
    from datetime import date, timedelta

    to_d = date.today()
    from_d = to_d - timedelta(days=days + 30)

    try:
        payload = sahmk_get(
            f"historical/{symbol}/",
            {"from": from_d.isoformat(), "to": to_d.isoformat(), "interval": "1d"},
        )
        rows = payload.get("data", [])
        if not isinstance(rows, list):
            return []

        clean = []
        for r in rows:
            high = fnum(r.get("high"))
            low = fnum(r.get("low"))
            close = fnum(r.get("close"))
            volume = fnum(r.get("volume"))
            if high > 0 and low > 0 and close > 0 and high >= low:
                clean.append({
                    "date": r.get("date") or r.get("timestamp"),
                    "open": fnum(r.get("open"), close),
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "turnover": fnum(r.get("turnover")),
                })
        clean.sort(key=lambda x: str(x.get("date")))
        return clean[-days:]
    except Exception as exc:
        print(f"⚠️ {symbol}: historical fetch failed: {exc}")
        return []


def sma(values: List[float], period: int) -> Optional[float]:
    values = [v for v in values if v > 0]
    if len(values) < period:
        return None
    return mean(values[-period:])


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


def true_ranges(rows: List[Dict[str, Any]]) -> List[float]:
    trs = []
    for i, r in enumerate(rows):
        high = fnum(r.get("high"))
        low = fnum(r.get("low"))
        prev_close = fnum(rows[i - 1].get("close")) if i > 0 else fnum(r.get("close"))
        if high > 0 and low > 0 and prev_close > 0:
            trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return trs


def atr(rows: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
    trs = true_ranges(rows)
    if len(trs) < period:
        return None
    return mean(trs[-period:])


def volume_ratio(rows: List[Dict[str, Any]], current_volume: float, period: int = 20) -> float:
    vols = [fnum(r.get("volume")) for r in rows[-period:] if fnum(r.get("volume")) > 0]
    if len(vols) < 10 or current_volume <= 0:
        return 1.0
    avg = mean(vols)
    return round(current_volume / avg, 2) if avg > 0 else 1.0


def pct(v: float, base: float) -> float:
    return round((v / base) * 100, 2) if base > 0 else 0.0


def get_stocks_from_daily() -> List[Dict[str, Any]]:
    daily = load_json(DAILY_FILE, {})
    stocks = daily.get("stocks", []) if isinstance(daily, dict) else []
    if stocks:
        return stocks
    return [{"symbol": s, "name": s, "current_price": 0, "volume": 0, "value": 0} for s in SYMBOLS_FALLBACK]


def current_stock(symbol: str) -> Optional[Dict[str, Any]]:
    for s in get_stocks_from_daily():
        if str(s.get("symbol", "")).strip() == str(symbol):
            return s
    return None


def score_candidate(stock: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    symbol = str(stock.get("symbol", "")).strip()
    if not symbol:
        return None

    price = fnum(stock.get("current_price") or stock.get("price"))
    volume = fnum(stock.get("volume"))
    value = fnum(stock.get("value") or stock.get("turnover")) or price * volume
    change_pct = fnum(stock.get("change_percent"))

    if price <= 0 or volume <= 0 or value < MIN_GOLDEN_VALUE:
        return None

    rows = fetch_historical(symbol, 90)
    if len(rows) < 30:
        return None

    today_row = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "open": fnum(stock.get("open"), price),
        "high": max(fnum(stock.get("high"), price), price),
        "low": min(fnum(stock.get("low"), price), price),
        "close": price,
        "volume": volume,
        "turnover": value,
    }
    rows = rows[:-1] + [today_row] if rows and str(rows[-1].get("date")) == today_row["date"] else rows + [today_row]

    closes = [fnum(r.get("close")) for r in rows]
    rsi = calc_rsi(closes) or 50.0
    atr14 = atr(rows) or 0.0
    if atr14 <= 0:
        return None
    atr_pct = round((atr14 / price) * 100, 2)

    sma10 = sma(closes, 10) or price
    sma20 = sma(closes, 20) or price
    sma50 = sma(closes, 50) or sma20
    trend_ok = price > sma20 and sma10 >= sma20 * 0.995
    if not trend_ok:
        return None

    prior = rows[-21:-1]
    highs = [fnum(r.get("high")) for r in prior if fnum(r.get("high")) > 0]
    lows = [fnum(r.get("low")) for r in prior if fnum(r.get("low")) > 0]
    if len(highs) < 10 or len(lows) < 10:
        return None
    resistance = max(highs)
    support = min(lows)

    vol_ratio = volume_ratio(rows[:-1], volume)
    is_breakout = price >= resistance * 1.002
    near_breakout_pct = ((resistance / price) - 1) * 100 if price > 0 else 99
    near_breakout = 0 <= near_breakout_pct <= 6.0
    if not (is_breakout or near_breakout):
        return None

    entry = round(max(price, resistance * 1.003), 2)
    stop_loss = round(max(entry - atr14 * 1.25, support * 0.995), 2)
    risk_amount = entry - stop_loss
    if risk_amount <= 0:
        return None

    target1 = round(entry * (1 + MIN_GOLDEN_TP1_PCT / 100), 2)
    target2_by_rr = entry + risk_amount * MIN_GOLDEN_RR
    target2_by_pct = entry * (1 + MIN_GOLDEN_TP2_PCT / 100)
    target2 = round(max(target2_by_rr, target2_by_pct), 2)

    tp1_pct = pct(target1 - entry, entry)
    tp2_pct = pct(target2 - entry, entry)
    rr = round((target2 - entry) / risk_amount, 2)
    sl_pct = abs(pct(stop_loss - entry, entry))

    if not (MIN_GOLDEN_RSI <= rsi <= MAX_GOLDEN_RSI):
        return None
    if vol_ratio < MIN_GOLDEN_VOLUME_RATIO:
        return None
    if rr < MIN_GOLDEN_RR:
        return None
    if tp1_pct < MIN_GOLDEN_TP1_PCT:
        return None

    score = 0
    reasons = []

    if trend_ok:
        score += 20
        reasons.append("اتجاه صاعد")
    if is_breakout:
        score += 22
        reasons.append("اختراق مقاومة")
    else:
        score += 14
        reasons.append("قريب من اختراق مقاومة")
    if 52 <= rsi <= 66:
        score += 18
        reasons.append(f"RSI صحي {rsi:.1f}")
    else:
        score += 10
        reasons.append(f"RSI مقبول {rsi:.1f}")
    if vol_ratio >= 2:
        score += 18
        reasons.append(f"حجم قوي {vol_ratio:.2f}x")
    else:
        score += 10
        reasons.append(f"حجم مقبول {vol_ratio:.2f}x")
    if value >= 10_000_000:
        score += 10
        reasons.append("سيولة عالية")
    else:
        score += 6
        reasons.append("سيولة مقبولة")
    if rr >= 3:
        score += 8
        reasons.append(f"R:R قوي {rr:.2f}")
    else:
        score += 5
        reasons.append(f"R:R مقبول {rr:.2f}")
    if tp1_pct >= 8:
        score += 4
    elif tp1_pct >= 6:
        score += 3

    rased_score = min(100.0, round(score, 1))
    if rased_score < MIN_GOLDEN_RASED_SCORE:
        return None

    tier = "Platinum" if (rased_score >= 92 and (tp1_pct >= 8 or tp2_pct >= 10)) else "Gold"
    tier_emoji = "👑" if tier == "Platinum" else "🌟"

    return {
        "status": "PREMARKET",
        "golden_run_mode": "premarket",
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
        "target1_percent": tp1_pct,
        "target2_percent": tp2_pct,
        "stop_loss_percent": round(sl_pct, 2),
        "tp1_pct": tp1_pct,
        "tp2_pct": tp2_pct,
        "sl_pct": round(-sl_pct, 2),
        "rr": rr,
        "rr_ratio": rr,
        "rased_score": rased_score,
        "score": rased_score,
        "tier": tier,
        "tier_emoji": tier_emoji,
        "risk_level": "متوسط" if rr >= 2.5 and rsi <= 72 else "مرتفع",
        "risk_emoji": "🟡" if rr >= 2.5 and rsi <= 72 else "🔴",
        "confidence": f"{int(round(rased_score))}%",
        "rsi": round(rsi, 2),
        "volume_ratio": vol_ratio,
        "atr_pct": atr_pct,
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "value": round(value, 2),
        "change_percent": change_pct,
        "expected_holding_period": "1-7 أيام",
        "expected_days_to_target2": min(MAX_HOLD_DAYS, max(1, int(round(tp2_pct / max(atr_pct, 0.8))))),
        "technical_reading": " — ".join(reasons[:6]),
        "signal_reason": "إشارة ذهبية مرشحة قبل الافتتاح بعد اجتياز فلاتر الاختراق والسيولة والزخم والعائد المتوقع.",
        "key_insight": "سيتم تأكيد الإشارة مرة أخرى الساعة 10:30 بعد ظهور حركة الافتتاح والحجم الفعلي.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": "محتوى تعليمي آلي وليس توصية استثمارية أو ضماناً لتحقيق الأهداف.",
    }


def openai_review(signal: Dict[str, Any], mode: str) -> Tuple[bool, Dict[str, Any]]:
    if not OPENAI_API_KEY:
        return False, {"ai_available": False, "ai_decision": "SKIPPED", "ai_reason": "OPENAI_API_KEY missing"}

    prompt = f"""
You are reviewing a Saudi stock trading signal for risk control only.
Return JSON only with: decision, confidence, risk_level, reason.
Allowed decision values: APPROVE, CAUTION, REJECT.
Mode: {mode}
Signal:
{json.dumps(signal, ensure_ascii=False)}
Rules:
- Reject if risk/reward is weak, RSI is too hot, volume is weak, or holding period is unrealistic.
- For golden signals, require strong quality. Do not invent news.
""".strip()

    try:
        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "Return strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if r.status_code >= 400:
            return False, {"ai_available": False, "ai_decision": "ERROR", "ai_reason": r.text[:250]}
        content = r.json()["choices"][0]["message"]["content"]
        review = json.loads(content)
        decision = str(review.get("decision", "REJECT")).upper()
        confidence = int(fnum(review.get("confidence"), 0))
        risk = str(review.get("risk_level", "HIGH")).upper()
        approved = decision == "APPROVE" and confidence >= 80 and risk in {"LOW", "MEDIUM"}
        return approved, {
            "ai_available": True,
            "ai_reviewed": True,
            "ai_decision": decision,
            "ai_confidence": confidence,
            "ai_risk_level": risk,
            "ai_reason": review.get("reason", ""),
        }
    except Exception as exc:
        return False, {"ai_available": False, "ai_decision": "ERROR", "ai_reason": str(exc)}


def run_premarket() -> int:
    print("👑 Running pre-market golden scan 09:30 KSA")
    stocks = get_stocks_from_daily()
    candidates = []
    for stock in stocks:
        sig = score_candidate(stock)
        if sig:
            candidates.append(sig)
            print(f"✅ Candidate {sig['symbol']} | {sig['tier']} | RASED {sig['rased_score']} | TP1 {sig['tp1_pct']}%")

    candidates.sort(key=lambda x: (fnum(x.get("rased_score")), fnum(x.get("rr")), fnum(x.get("volume_ratio"))), reverse=True)

    if not candidates:
        write_json(GOLDEN_FILE, [])
        print("ℹ️ No pre-market golden signal")
        return 0

    best = candidates[0]
    ai_ok, ai_data = openai_review(best, "premarket")
    best.update(ai_data)

    if REQUIRE_OPENAI_FOR_GOLDEN and not ai_ok:
        write_json(GOLDEN_FILE, [])
        print(f"❌ Golden blocked by OpenAI gate: {ai_data.get('ai_decision')} | {ai_data.get('ai_reason')}")
        return 0

    best["ai_gate_passed"] = bool(ai_ok)
    best["status"] = "PREMARKET"
    best["golden_title"] = "👑 الإشارة الذهبية قبل الافتتاح"

    write_json(GOLDEN_FILE, [best])
    write_json(GOLDEN_CANDIDATE_FILE, best)
    print(f"✅ Pre-market golden selected: {best['symbol']}")
    return 0


def run_confirmation() -> int:
    print("🌟 Running golden confirmation scan 10:30 KSA")
    candidate = load_json(GOLDEN_CANDIDATE_FILE, {})
    if not candidate:
        write_json(GOLDEN_FILE, [])
        print("ℹ️ No previous golden candidate to confirm")
        return 0

    symbol = str(candidate.get("symbol") or candidate.get("stock_symbol") or "").strip()
    stock = current_stock(symbol)
    if not stock:
        msg = dict(candidate)
        msg.update({
            "status": "CANCELLED",
            "golden_run_mode": "confirmation",
            "golden_title": "⚠️ إلغاء الإشارة الذهبية",
            "confirmation_status": "CANCELLED",
            "confirmation_reason": "لم تتوفر بيانات السهم بعد الافتتاح لتأكيد الإشارة.",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        })
        write_json(GOLDEN_FILE, [msg])
        return 0

    current_price = fnum(stock.get("current_price") or stock.get("price"))
    current_volume = fnum(stock.get("volume"))
    entry = fnum(candidate.get("entry") or candidate.get("entry_point"))
    stop_loss = fnum(candidate.get("stop_loss"))

    rows = fetch_historical(symbol, 90)
    vol_ratio = volume_ratio(rows, current_volume) if rows else fnum(candidate.get("volume_ratio"), 1.0)
    current_vs_entry_pct = pct(current_price - entry, entry)

    fail_reasons = []
    if current_price <= 0:
        fail_reasons.append("السعر الحالي غير متوفر")
    if current_price <= stop_loss:
        fail_reasons.append("السعر كسر وقف الخسارة")
    if current_vs_entry_pct < CONFIRM_MIN_CURRENT_VS_ENTRY_PCT:
        fail_reasons.append(f"السعر أقل من الدخول بنسبة {current_vs_entry_pct}%")
    if vol_ratio < CONFIRM_MIN_VOLUME_RATIO:
        fail_reasons.append(f"الحجم غير كافٍ {vol_ratio}x")

    msg = dict(candidate)
    msg.update({
        "golden_run_mode": "confirmation",
        "current_price": round(current_price, 2),
        "volume_ratio": round(vol_ratio, 2),
        "current_vs_entry_pct": round(current_vs_entry_pct, 2),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    })

    if fail_reasons:
        msg.update({
            "status": "CANCELLED",
            "golden_title": "⚠️ إلغاء الإشارة الذهبية بعد الافتتاح",
            "confirmation_status": "CANCELLED",
            "confirmation_reason": " — ".join(fail_reasons),
            "key_insight": "تم إلغاء الإشارة لأن شروط التأكيد بعد الافتتاح لم تعد كافية.",
        })
        write_json(GOLDEN_FILE, [msg])
        print("⚠️ Golden cancelled:", msg["confirmation_reason"])
        return 0

    ai_ok, ai_data = openai_review(msg, "confirmation")
    msg.update(ai_data)

    if REQUIRE_OPENAI_FOR_GOLDEN and not ai_ok:
        msg.update({
            "status": "CANCELLED",
            "golden_title": "⚠️ عدم تأكيد الإشارة الذهبية",
            "confirmation_status": "CANCELLED",
            "confirmation_reason": f"لم تحصل على موافقة مراجعة الذكاء الاصطناعي: {ai_data.get('ai_reason', '')}",
            "key_insight": "تم منع تأكيد الذهبية لأن مراجعة الذكاء الاصطناعي لم تعتمد الإشارة.",
        })
        write_json(GOLDEN_FILE, [msg])
        print("❌ Golden confirmation blocked by AI")
        return 0

    msg.update({
        "status": "CONFIRMED",
        "golden_title": "🌟 تأكيد الإشارة الذهبية بعد الافتتاح",
        "confirmation_status": "CONFIRMED",
        "confirmation_reason": "الإشارة ما زالت صالحة بعد الافتتاح: السعر فوق منطقة الدخول والحجم مقبول ولم يتم كسر وقف الخسارة.",
        "key_insight": "تم تأكيد الإشارة بعد ظهور حركة الافتتاح والحجم الفعلي.",
        "ai_gate_passed": bool(ai_ok),
    })
    write_json(GOLDEN_FILE, [msg])
    print(f"✅ Golden confirmed: {symbol}")
    return 0


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if GOLDEN_RUN_MODE in {"confirm", "confirmation", "1030"}:
        return run_confirmation()
    return run_premarket()


if __name__ == "__main__":
    sys.exit(main())
