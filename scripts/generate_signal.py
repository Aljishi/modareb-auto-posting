#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate trading signals from market data"""

import json
import sys
from datetime import datetime
from pathlib import Path


def calculate_score(stock):
    """Score 0–100 across four dimensions"""
    score = 0

    # RSI (30 pts)
    rsi = stock.get('rsi', 50)
    if   42 <= rsi <= 68: score += 30
    elif 35 <= rsi < 42 or 68 < rsi <= 75: score += 20
    else: score += 10

    # Volume (25 pts)
    vol = stock.get('volume_ratio', 1.0)
    if   vol >= 2.0: score += 25
    elif vol >= 1.5: score += 20
    elif vol >= 1.2: score += 15
    else:            score += 5

    # Momentum (25 pts)
    chg = stock.get('change_percent', 0)
    if   2 <= chg <= 8: score += 25
    elif 0 <= chg <  2: score += 20
    elif -2 <= chg < 0: score += 10
    else:               score += 5

    # RS Rank (20 pts)
    rs = stock.get('rs_rank', 50)
    if   rs >= 85: score += 20
    elif rs >= 70: score += 15
    elif rs >= 50: score += 10
    else:          score += 5

    return min(score, 100)


def main():
    print("=" * 60)
    print("🎯 راصد — توليد الإشارات")
    print("=" * 60)

    data_dir  = Path(__file__).parent.parent / "data"
    daily_file = data_dir / "daily.json"

    if not daily_file.exists():
        print("❌ daily.json not found"); sys.exit(1)

    with open(daily_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    stocks  = data.get('stocks', [])
    signals = []

    for stock in stocks:
        score  = calculate_score(stock)
        if score < 70:
            continue

        price = float(stock.get('current_price', 0))
        if price <= 0:
            continue

        entry  = round(price * 1.01, 2)
        t1     = round(price * 1.05, 2)
        t2     = round(price * 1.10, 2)
        sl     = round(price * 0.97, 2)

        # FIX: pre-calculate percentages so image generator can display them
        t1p    = round((t1 - entry) / entry * 100, 1) if entry else 5.0
        t2p    = round((t2 - entry) / entry * 100, 1) if entry else 10.0
        slp    = round((entry - sl)  / entry * 100, 1) if entry else 3.0
        rr     = round(t2p / slp, 1) if slp else 0

        if   score >= 85: confidence, emoji, level = "عالية جداً", "🟢", "golden"
        elif score >= 78: confidence, emoji, level = "عالية",      "🟡", "high"
        else:             confidence, emoji, level = "متوسطة",     "🔵", "medium"

        signals.append({
            # Identity
            "stock_symbol":  stock.get('symbol', ''),
            "stock_name":    stock.get('name',   ''),
            "sector":        stock.get('sector', ''),
            # Prices
            "current_price": price,
            "entry_point":   entry,
            "target1":       t1,
            "target1_percent": t1p,
            "target2":       t2,
            "target2_percent": t2p,
            "stop_loss":     sl,
            "stop_loss_percent": slp,
            "rr":            rr,
            # Indicators
            "rsi":           stock.get('rsi', 50),
            "volume_ratio":  stock.get('volume_ratio', 1.0),
            "rs_rank":       stock.get('rs_rank', 50),
            "score":         score,
            # Meta
            "confidence":    confidence,
            "emoji":         emoji,
            "level":         level,
            "generated_at":  datetime.now().isoformat(),
        })
        print(f"  🎯 {stock.get('symbol')}: Score {score} — {confidence}")

    output = {
        "signals":      signals,
        "generated_at": datetime.now().isoformat(),
        "total":        len(signals),
    }

    out_file = data_dir / "signals.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(signals)} إشارة — حُفظت في {out_file}")
    return 0 if signals else 1


if __name__ == "__main__":
    sys.exit(main())
