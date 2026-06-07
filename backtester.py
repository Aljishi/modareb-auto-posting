import os
import json
import requests
from datetime import datetime

API_KEY = os.environ.get("API_KEY")
API_URL = os.environ.get("API_URL", "https://app.sahmk.sa/api/v1")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

RESULTS_FILE = "data/backtest_results.json"

TASI_SYMBOLS = [
    "1010","1020","1030","1050","1060","1080","1120","1150",
    "2010","2020","2030","2060","2080","2090","2100","2110",
    "2120","2130","2150","2160","2170","2180","2190","2200",
    "2210","2220","2222","2223","2230","2240","2250","2290",
    "2310","2320","2330","2340","2350","2360","2370","2380",
    "4001","4002","4005","4007","4009","4020","4030","4031",
    "4040","4050","4061","4100","4150","4160","4170","4180",
    "4190","4200","4210","4220","4230","4240","4250","4261",
    "4300","4320","4321","4322","4323","4324","4327","4328",
    "5010","5020","5110","6001","6010","6013","6020","6040",
    "7010","7020","7030","7040","7203","7204",
    "8010","8020","8030","8040","8050","8060","8070","8100",
    "9516","9526","9527","9528","9529","9536","9543","9544",
    "9545","9546","9547","9548","9549","9553","9554","9555",
]


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def get(endpoint, params=None):
    try:
        r = requests.get(
            f"{API_URL}{endpoint}",
            headers=HEADERS,
            params=params or {},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  error: {e}")
    return None


def fetch_historical(symbol, period=60):
    data = get(f"/historical/{symbol}/", {"period": period})
    if not data:
        return None
    history = data.get("data", [])
    if len(history) < 20:
        return None
    return sorted(history, key=lambda x: x.get("date",""))


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period-1) + gains[i]) / period
        avg_loss = (avg_loss * (period-1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gain/avg_loss)), 2)


def calc_atr(highs, lows, closes, period=14):
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i]  - closes[i-1])
        )
        trs.append(tr)
    if not trs:
        return 0
    atr = sum(trs[:period]) / min(period, len(trs))
    for tr in trs[period:]:
        atr = (atr*(period-1) + tr) / period
    return round(atr, 4)


def score_window(history_window):
    """
    يحسب Score لفترة زمنية محددة
    نفس منطق fetch_api_data.py
    """
    closes  = [safe_float(d.get("close"))  for d in history_window]
    highs   = [safe_float(d.get("high"))   for d in history_window]
    lows    = [safe_float(d.get("low"))    for d in history_window]
    volumes = [safe_float(d.get("volume")) for d in history_window]

    if not closes or closes[-1] <= 0:
        return 0, 0, 0, 0

    price  = closes[-1]
    high   = highs[-1]
    low    = lows[-1]
    volume = volumes[-1]

    # RSI
    rsi = calc_rsi(closes)

    # ATR
    atr = calc_atr(highs, lows, closes)

    # Volume ratio
    avg_vol    = sum(volumes[-10:]) / 10 if len(volumes) >= 10 else volume
    vol_ratio  = volume / avg_vol if avg_vol > 0 else 1

    # Resistance = أعلى سعر في آخر 10 أيام
    resistance = max(highs[-10:]) if len(highs) >= 10 else high
    support    = min(lows[-10:])  if len(lows)  >= 10 else low

    # Change
    change_pct = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0

    score = 0

    # Breakout
    dist = (resistance - price) / price if resistance > 0 else 1
    if price >= resistance:
        score += 30
    elif dist <= 0.015:
        score += 22
    elif dist <= 0.03:
        score += 12

    # Volume
    if   vol_ratio >= 3:   score += 25
    elif vol_ratio >= 2:   score += 20
    elif vol_ratio >= 1.5: score += 10

    # RSI
    if   50 <= rsi <= 65:  score += 20
    elif 40 <= rsi < 50:   score += 12
    elif 65 < rsi <= 72:   score +=  8
    elif rsi > 75:         score -= 15

    # Close position
    rng       = high - low
    close_pos = (price - low) / rng if rng > 0 else 0.5
    if   close_pos >= 0.85: score += 20
    elif close_pos >= 0.70: score += 12

    # Momentum
    if   change_pct >= 3:   score += 15
    elif change_pct >= 1.5: score += 10

    # Entry & R:R
    entry     = round(resistance * 1.005 if resistance > price * 1.002 else price * 1.005, 2)
    t1        = round(min(entry + atr * 1.5, entry * 1.04), 2)
    stop_loss = round(max(support * 0.995, entry - atr * 1.5, entry * 0.97), 2)
    risk      = entry - stop_loss
    reward    = t1 - entry
    rr        = reward / risk if risk > 0 else 0

    if   rr >= 2.5: score += 15
    elif rr >= 1.5: score +=  8
    elif rr < 1:    score -= 10

    return min(score, 100), entry, t1, stop_loss


def check_outcome(future_history, entry, target1, stop_loss):
    """
    يفحص هل الإشارة نجحت أم فشلت
    بعد 5 أيام من الإشارة
    """
    for day in future_history[:5]:
        high = safe_float(day.get("high"))
        low  = safe_float(day.get("low"))

        # وصل الهدف الأول
        if high >= target1:
            return "WIN", target1

        # ضرب وقف الخسارة
        if low <= stop_loss:
            return "LOSS", stop_loss

    # لم يصل لأي منهما
    final_close = safe_float(future_history[min(4, len(future_history)-1)].get("close"))
    if final_close > entry:
        return "PARTIAL", final_close
    return "LOSS", final_close


def run_backtest():
    print("\n" + "="*60)
    print("Backtesting — اختبار النظام على التاريخ")
    print("="*60)

    all_signals = []
    wins = losses = partials = skipped = 0
    total_return = 0.0

    for i, sym in enumerate(TASI_SYMBOLS):
        history = fetch_historical(sym, period=60)
        if not history or len(history) < 25:
            skipped += 1
            continue

        sym_signals = 0

        # نختبر كل يوم من التاريخ
        for day_idx in range(15, len(history) - 5):
            window = history[:day_idx + 1]

            score, entry, target1, stop_loss = score_window(window)

            if score < 75:
                continue

            # فحص RSI
            closes = [safe_float(d.get("close")) for d in window]
            rsi    = calc_rsi(closes)
            if not (45 <= rsi <= 70):
                continue

            # فحص النتيجة
            future  = history[day_idx + 1:]
            outcome, exit_price = check_outcome(future, entry, target1, stop_loss)

            pnl = (exit_price - entry) / entry * 100

            signal = {
                "symbol":   sym,
                "date":     window[-1].get("date",""),
                "score":    score,
                "rsi":      round(rsi, 1),
                "entry":    entry,
                "target1":  target1,
                "stop_loss":stop_loss,
                "outcome":  outcome,
                "pnl_pct":  round(pnl, 2),
            }

            all_signals.append(signal)
            sym_signals += 1
            total_return += pnl

            if   outcome == "WIN":     wins     += 1
            elif outcome == "PARTIAL": partials += 1
            else:                      losses   += 1

        if (i+1) % 10 == 0:
            total = wins + losses + partials
            rate  = wins/total*100 if total > 0 else 0
            print(f"  [{i+1}/{len(TASI_SYMBOLS)}] إشارات: {total} | نجاح: {rate:.1f}%")

    # إحصائيات
    total_signals = wins + losses + partials
    win_rate      = wins / total_signals * 100 if total_signals > 0 else 0
    avg_return    = total_return / total_signals if total_signals > 0 else 0
    profit_factor = wins / losses if losses > 0 else wins

    print(f"\n{'='*60}")
    print("نتائج Backtesting:")
    print(f"{'='*60}")
    print(f"  إجمالي الإشارات : {total_signals}")
    print(f"  ربحية (Win)     : {wins} ({win_rate:.1f}%)")
    print(f"  خسارة (Loss)    : {losses} ({losses/total_signals*100:.1f}%)")
    print(f"  جزئية (Partial) : {partials}")
    print(f"  متوسط العائد    : {avg_return:+.2f}%")
    print(f"  Profit Factor   : {profit_factor:.2f}")
    print(f"  أسهم مختبرة     : {len(TASI_SYMBOLS) - skipped}")

    # تقييم النظام
    print(f"\n  تقييم النظام:")
    if win_rate >= 65:
        print(f"  ممتاز ✅ — نسبة نجاح {win_rate:.1f}%")
    elif win_rate >= 55:
        print(f"  جيد ✅ — نسبة نجاح {win_rate:.1f}%")
    elif win_rate >= 45:
        print(f"  متوسط ⚠️ — يحتاج تحسين")
    else:
        print(f"  ضعيف ❌ — يحتاج مراجعة جذرية")

    # أفضل وأسوأ إشارات
    if all_signals:
        best  = sorted(all_signals, key=lambda x: x["pnl_pct"], reverse=True)[:3]
        worst = sorted(all_signals, key=lambda x: x["pnl_pct"])[:3]

        print(f"\n  أفضل 3 إشارات:")
        for s in best:
            print(f"  {s['symbol']} {s['date']} +{s['pnl_pct']}% Score:{s['score']}")

        print(f"\n  أسوأ 3 إشارات:")
        for s in worst:
            print(f"  {s['symbol']} {s['date']} {s['pnl_pct']}% Score:{s['score']}")

    # حفظ النتائج
    results = {
        "generated_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_signals":  total_signals,
        "wins":           wins,
        "losses":         losses,
        "partials":       partials,
        "win_rate":       round(win_rate, 2),
        "avg_return":     round(avg_return, 2),
        "profit_factor":  round(profit_factor, 2),
        "signals":        all_signals[-100:],  # آخر 100 إشارة
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n  النتائج محفوظة في {RESULTS_FILE} ✅")
    return results


if __name__ == "__main__":
    if not API_KEY:
        print("API_KEY missing")
    else:
        run_backtest()
