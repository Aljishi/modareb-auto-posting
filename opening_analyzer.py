import os
import json
import requests
from datetime import datetime, timezone, timedelta

API_KEY  = os.environ.get("API_KEY")
API_URL  = os.environ.get("API_URL", "https://app.sahmk.sa/api/v1")
HEADERS  = {"X-API-Key": API_KEY} if API_KEY else {}

OPENING_FILE = "data/opening_data.json"
OUTPUT_FILE  = "data/daily.json"

OPEN_HOUR     = 10
OPEN_MINUTE   = 0
SIGNAL_HOUR   = 10
SIGNAL_MINUTE = 20

KSA = timezone(timedelta(hours=3))


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
        print(f"  error {endpoint}: {e}")
    return None


def is_opening_period():
    now = datetime.now(KSA)
    if now.weekday() not in [6, 0, 1, 2, 3]:
        return False
    t = now.hour * 60 + now.minute
    open_t   = OPEN_HOUR * 60 + OPEN_MINUTE
    signal_t = SIGNAL_HOUR * 60 + SIGNAL_MINUTE
    return open_t <= t <= signal_t


def is_signal_time():
    now = datetime.now(KSA)
    t = now.hour * 60 + now.minute
    signal_t = SIGNAL_HOUR * 60 + SIGNAL_MINUTE
    return t >= signal_t


def fetch_stocks():
    stocks = {}
    for endpoint, key in [
        ("/market/gainers/", "gainers"),
        ("/market/volume/",  "stocks"),
    ]:
        data = get(endpoint, {"limit": 50, "index": "TASI"})
        if data:
            items = data if isinstance(data, list) else data.get(key, data.get("data", []))
            for s in items:
                sym = str(s.get("symbol", ""))
                if sym and sym not in stocks:
                    stocks[sym] = s
    return stocks


def load_opening_data():
    try:
        with open(OPENING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"snapshots": [], "stocks": {}}


def save_opening_data(data):
    with open(OPENING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def take_snapshot(opening_data):
    now    = datetime.now(KSA)
    stocks = fetch_stocks()

    if not stocks:
        print("  لا يوجد بيانات من API")
        return

    snapshot = {
        "time":   now.strftime("%H:%M"),
        "stocks": {}
    }

    for sym, s in stocks.items():
        price  = safe_float(s.get("price") or s.get("close"))
        volume = safe_float(s.get("volume"))
        if price > 0:
            snapshot["stocks"][sym] = {
                "price":      price,
                "volume":     volume,
                "change_pct": safe_float(s.get("change_percent") or s.get("change_pct")),
                "name":       s.get("name") or s.get("name_ar") or sym,
                "high":       safe_float(s.get("high"), price),
                "low":        safe_float(s.get("low"),  price),
            }

    opening_data["snapshots"].append(snapshot)

    for sym, stock_data in snapshot["stocks"].items():
        if sym not in opening_data["stocks"]:
            opening_data["stocks"][sym] = {
                "name":          stock_data["name"],
                "prices":        [],
                "volumes":       [],
                "times":         [],
                "opening_price": stock_data["price"],
                "opening_high":  stock_data["high"],
                "opening_low":   stock_data["low"],
            }

        s_data = opening_data["stocks"][sym]
        s_data["prices"].append(stock_data["price"])
        s_data["volumes"].append(stock_data["volume"])
        s_data["times"].append(snapshot["time"])
        s_data["last_price"]      = stock_data["price"]
        s_data["last_change_pct"] = stock_data["change_pct"]
        s_data["last_high"]       = stock_data["high"]
        s_data["last_low"]        = stock_data["low"]
        s_data["last_volume"]     = stock_data["volume"]

    print(f"  [{now.strftime('%H:%M')}] لقطة: {len(snapshot['stocks'])} سهم")
    save_opening_data(opening_data)


def analyze_opening_momentum(opening_data):
    stocks  = opening_data.get("stocks", {})
    results = []

    for sym, s in stocks.items():
        prices  = s.get("prices", [])
        volumes = s.get("volumes", [])

        if len(prices) < 2:
            continue

        opening_price = s.get("opening_price", prices[0])
        last_price    = prices[-1]
        opening_high  = s.get("opening_high", max(prices))
        opening_low   = s.get("opening_low",  min(prices))

        breakout_score = 0
        if last_price > opening_high:
            breakout_score = 30
        elif last_price > (opening_high + opening_low) / 2:
            breakout_score = 15

        up_moves    = sum(1 for i in range(1, len(prices)) if prices[i] > prices[i-1])
        total_moves = len(prices) - 1
        momentum_pct = (up_moves / total_moves * 100) if total_moves > 0 else 0
        momentum_score = 0
        if   momentum_pct >= 80: momentum_score = 25
        elif momentum_pct >= 60: momentum_score = 15
        elif momentum_pct >= 40: momentum_score = 5

        avg_vol_first = sum(volumes[:len(volumes)//2]) / max(len(volumes)//2, 1)
        avg_vol_last  = sum(volumes[len(volumes)//2:]) / max(len(volumes) - len(volumes)//2, 1)
        vol_acceleration = avg_vol_last / avg_vol_first if avg_vol_first > 0 else 0
        vol_score = 0
        if   vol_acceleration >= 2.0: vol_score = 25
        elif vol_acceleration >= 1.5: vol_score = 15
        elif vol_acceleration >= 1.2: vol_score = 8

        price_change = (last_price - opening_price) / opening_price * 100 if opening_price > 0 else 0
        change_score = 0
        if   price_change >= 3:   change_score = 20
        elif price_change >= 1.5: change_score = 12
        elif price_change >= 0.5: change_score = 6
        elif price_change < 0:    change_score = -20

        if len(prices) >= 3:
            diffs = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            positive_diffs = [d for d in diffs if d > 0]
            consistency = len(positive_diffs) / len(diffs) if diffs else 0
        else:
            consistency = 0.5
        consistency_score = int(consistency * 20)

        total_score = breakout_score + momentum_score + vol_score + change_score + consistency_score

        results.append({
            "symbol":           sym,
            "name":             s.get("name", sym),
            "last_price":       last_price,
            "opening_price":    opening_price,
            "price_change_pct": round(price_change, 2),
            "momentum_pct":     round(momentum_pct, 1),
            "vol_acceleration": round(vol_acceleration, 2),
            "last_volume":      s.get("last_volume", 0),
            "opening_score":    total_score,
            "breakout":         breakout_score > 0,
            "snapshots_count":  len(prices),
            "high":             s.get("last_high", last_price),
            "low":              s.get("last_low",  last_price),
        })

    results.sort(key=lambda x: x["opening_score"], reverse=True)
    return results


def build_signal(best, opening_data):
    price     = best["last_price"]
    entry     = round(price * 1.001, 2)
    # ✅ T1=+5%, T2=+10% متوافق مع النظام الجديد
    target1   = round(entry * 1.05, 2)
    target2   = round(entry * 1.10, 2)
    stop_loss = round(max(best.get("low", entry * 0.97) * 0.99, entry * 0.96), 2)
    risk      = entry - stop_loss
    # R:R على T2
    rr        = round((target2 - entry) / risk, 2) if risk > 0 else 0

    score    = best["opening_score"]
    momentum = (
        "قوي جداً" if score >= 85 else
        "قوي"      if score >= 60 else
        "متوسط"    if score >= 40 else "ضعيف"
    )

    now = datetime.now(KSA)
    note = (
        f"زخم افتتاح: ارتفاع {best['price_change_pct']:+.1f}% "
        f"+ تسارع حجم {best['vol_acceleration']:.1f}x "
        f"+ اتساق {best['momentum_pct']:.0f}%"
    )

    return {
        "brand":          "راصد",
        "mode":           "opening",
        "stock_name":     best["name"],
        "symbol":         best["symbol"],
        "price":          f"{price:.2f}",
        "entry":          f"{entry:.2f}",
        "target1":        f"{target1:.2f}",
        "target2":        f"{target2:.2f}",
        "stop_loss":      f"{stop_loss:.2f}",
        "momentum":       momentum,
        "score":          score,
        "rsi":            50,
        "rr":             rr,
        "volume_ratio":   best["vol_acceleration"],
        "target2_pct":    10.0,
        "expected_days":  3,
        "max_days":       5,
        "acceleration":   int(best["vol_acceleration"] * 20),
        "source":         "opening_analyzer",
        "generated_at":   now.strftime("%Y-%m-%d %H:%M"),
        "note":           note,
    }


def main():
    now = datetime.now(KSA)
    print(f"\n Opening Analyzer - {now.strftime('%H:%M')} KSA")
    print(f" {'='*55}")

    if not is_opening_period():
        print(f"  خارج نطاق الافتتاح (10:00 - 10:20) - تخطي")
        return

    opening_data = load_opening_data()

    today = now.strftime("%Y-%m-%d")
    if opening_data.get("date") != today:
        print(f"  يوم جديد - اعادة تعيين البيانات")
        opening_data = {"date": today, "snapshots": [], "stocks": {}}

    opening_data["date"] = today
    take_snapshot(opening_data)

    snapshots_count = len(opening_data["snapshots"])
    print(f"  اجمالي اللقطات: {snapshots_count}")

    if snapshots_count < 2:
        print(f"  نحتاج {2 - snapshots_count} لقطة اضافية قبل التحليل")
        save_opening_data(opening_data)
        return

    if is_signal_time():
        print(f"\n  10:20 - تحليل زخم الافتتاح...")
        results = analyze_opening_momentum(opening_data)

        if not results:
            print("  لا توجد اسهم كافية للتحليل")
            return

        print(f"\n  Top 5 اسهم بزخم الافتتاح:")
        print(f"  {'السهم':<20} {'التغير':>7} {'الزخم':>7} {'الحجم':>7} {'Score':>7}")
        print(f"  {'-'*55}")
        for r in results[:5]:
            print(f"  {r['name'][:20]:<20} {r['price_change_pct']:>+6.1f}%"
                  f" {r['momentum_pct']:>6.0f}%"
                  f" {r['vol_acceleration']:>6.1f}x"
                  f" {r['opening_score']:>7}")

        best = results[0]
        if best["opening_score"] < 40:
            print(f"\n  لا توجد اشارة افتتاح قوية (Score {best['opening_score']} < 40)")
            return

        signal = build_signal(best, opening_data)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(signal, f, ensure_ascii=False, indent=2)

        print(f"\n  الاشارة الافتتاحية:")
        print(f"  السهم  : {signal['stock_name']} ({signal['symbol']})")
        print(f"  السعر  : {signal['price']} | دخول: {signal['entry']}")
        print(f"  هدف1(+5%): {signal['target1']} | هدف2(+10%): {signal['target2']}")
        print(f"  وقف    : {signal['stop_loss']} | R:R: {signal['rr']}")
        print(f"  Score  : {signal['score']}")
    else:
        print(f"  جمع البيانات - الاشارة عند 10:20")

    save_opening_data(opening_data)


if __name__ == "__main__":
    main()
