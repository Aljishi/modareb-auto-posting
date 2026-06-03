#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
راصد — الإشارة الذهبية بدون بيانات مولدة
تعتمد فقط على market_history.json الذي يتم بناؤه من API snapshots.
إذا التاريخ غير كافٍ: لا توجد إشارة ذهبية.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_FILE = DATA_DIR / "market_history.json"
DAILY_FILE = DATA_DIR / "daily.json"
OUT_FILE = DATA_DIR / "golden_signals.json"

MIN_BARS = 50
MIN_SCORE = 88


def fnum(x: Any, default: float = 0.0) -> float:
    try:
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


def rsi(closes: List[float], period: int = 14) -> Optional[float]:
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


def ema(values: List[float], span: int) -> List[float]:
    if not values:
        return []
    alpha = 2 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def atr(rows: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
    trs = []
    for r in rows:
        h, l, pc = fnum(r.get("high")), fnum(r.get("low")), fnum(r.get("previous_close"), fnum(r.get("close")))
        if h > 0 and l > 0 and pc > 0:
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    return mean(trs[-period:])


def analyze_symbol(symbol: str, rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if len(rows) < MIN_BARS:
        return None
    closes = [fnum(r.get("close")) for r in rows if fnum(r.get("close")) > 0]
    vols = [fnum(r.get("volume")) for r in rows if fnum(r.get("volume")) > 0]
    if len(closes) < MIN_BARS or len(vols) < 20:
        return None

    price = closes[-1]
    sma20, sma50 = mean(closes[-20:]), mean(closes[-50:])
    rsi14 = rsi(closes, 14)
    atr14 = atr(rows, 14)
    if rsi14 is None or atr14 is None or atr14 <= 0:
        return None

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    macd_line = [a - b for a, b in zip(ema12[-len(ema26):], ema26)]
    macd_signal = ema(macd_line, 9)
    macd_ok = bool(macd_signal and macd_line[-1] > macd_signal[-1])

    prior_high = max(fnum(r.get("high")) for r in rows[-51:-1])
    vol_ratio = vols[-1] / mean(vols[-20:]) if mean(vols[-20:]) > 0 else 0
    breakout = price >= prior_high * 1.002

    score = 0
    conditions = []
    if price > sma20 > sma50:
        score += 22; conditions.append("✅ ترند صاعد فوق SMA20 وSMA50")
    if 52 <= rsi14 <= 68:
        score += 18; conditions.append(f"✅ RSI صحي {rsi14:.1f}")
    if vol_ratio >= 2.0:
        score += 18; conditions.append(f"✅ حجم قوي {vol_ratio:.1f}x")
    elif vol_ratio >= 1.6:
        score += 11; conditions.append(f"✅ حجم مقبول {vol_ratio:.1f}x")
    if breakout:
        score += 22; conditions.append("✅ اختراق قمة 50 يوم")
    if macd_ok:
        score += 10; conditions.append("✅ MACD إيجابي")
    if 0.8 <= (atr14 / price * 100) <= 6.0:
        score += 10; conditions.append("✅ تذبذب ATR مناسب")

    if score < MIN_SCORE:
        return None

    entry = round(max(price, prior_high * 1.003), 2)
    stop = round(entry - atr14 * 1.25, 2)
    risk = entry - stop
    if risk <= 0:
        return None
    target1 = round(entry + risk * 1.5, 2)
    target2 = round(entry + risk * 2.4, 2)

    return {
        "symbol": symbol,
        "stock_symbol": symbol,
        "stock_name": meta.get(symbol, {}).get("name", symbol),
        "sector": meta.get(symbol, {}).get("sector", ""),
        "score": score,
        "is_golden": True,
        "conditions": conditions,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "entry_point": entry,
        "target1": target1,
        "target2": target2,
        "stop_loss": stop,
        "rr": round((target2 - entry) / risk, 2),
        "current_price": round(price, 2),
        "rsi": rsi14,
        "volume_ratio": round(vol_ratio, 2),
        "atr14": round(atr14, 4),
        "resistance": round(prior_high, 2),
        "data_source": "api_history_only",
        "engine_version": "rased_golden_no_mock",
        "analysis": {"score": score, "conditions": conditions},
    }


def main() -> int:
    print("=" * 60)
    print("🌟 راصد — الإشارة الذهبية بدون Mock")
    print("=" * 60)
    history = load_json(HISTORY_FILE, {})
    daily = load_json(DAILY_FILE, {})
    meta = {str(s.get("symbol")): s for s in daily.get("stocks", [])}
    if not isinstance(history, dict) or not history:
        OUT_FILE.write_text("[]", encoding="utf-8")
        print("ℹ️ لا يوجد تاريخ كافٍ بعد")
        return 0

    results = []
    for symbol, rows in history.items():
        if symbol.upper().startswith("TASI"):
            continue
        sig = analyze_symbol(symbol, rows, meta)
        if sig:
            results.append(sig)
            print(f"✅ GOLDEN {symbol}: {sig['score']}/100")

    results.sort(key=lambda x: x["score"], reverse=True)
    OUT_FILE.write_text(json.dumps(results[:3], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"🌟 إشارات ذهبية: {len(results[:3])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
