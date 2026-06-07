import json
import time
from fetch_api_data import load_market_data, calculate_score

THRESHOLD = 80  # الحد الأدنى للإشارة القوية

def is_breakout(stock):
    price = float(stock.get("price", 0))
    resistance = float(stock.get("resistance", 0))

    return resistance > 0 and price >= resistance * 0.995


def volume_spike(stock):
    vol = float(stock.get("volume", 0))
    avg = float(stock.get("avg_volume", 1))

    return vol / avg >= 2


def main():
    stocks = load_market_data()

    signals = []

    for stock in stocks:
        score, reasons, rr, vol_ratio = calculate_score(stock)

        if (
            score >= THRESHOLD
            and is_breakout(stock)
            and volume_spike(stock)
        ):
            signals.append({
                "stock": stock,
                "score": score,
                "reasons": reasons,
                "rr": rr,
                "vol_ratio": vol_ratio
            })

    signals.sort(key=lambda x: x["score"], reverse=True)

    if not signals:
        print("No signals now")
        return

    best = signals[0]

    with open("data/live_signal.json", "w", encoding="utf-8") as f:
        json.dump(best, f, ensure_ascii=False, indent=2)

    print("LIVE SIGNAL FOUND:", best["stock"]["name"])


if __name__ == "__main__":
    main()
