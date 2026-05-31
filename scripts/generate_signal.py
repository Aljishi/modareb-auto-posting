#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate trading signals from market data"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

def calculate_score(stock_data):
    """
    Calculate signal score (0-100) based on:
    - RSI (Relative Strength Index)
    - Volume ratio
    - Price momentum
    - Technical indicators
    """
    score = 0
    
    # RSI Score (0-30 points)
    rsi = stock_data.get('rsi', 50)
    if 42 <= rsi <= 68:  # Golden zone
        score += 30
    elif 35 <= rsi < 42 or 68 < rsi <= 75:
        score += 20
    else:
        score += 10
    
    # Volume Score (0-25 points)
    volume_ratio = stock_data.get('volume_ratio', 1.0)
    if volume_ratio >= 2.0:
        score += 25
    elif volume_ratio >= 1.5:
        score += 20
    elif volume_ratio >= 1.2:
        score += 15
    else:
        score += 5
    
    # Price Momentum Score (0-25 points)
    price_change = stock_data.get('change_percent', 0)
    if 2 <= price_change <= 8:  # Strong upward momentum
        score += 25
    elif 0 <= price_change < 2:
        score += 20
    elif -2 <= price_change < 0:
        score += 10
    else:
        score += 5
    
    # RS Rank Score (0-20 points)
    rs_rank = stock_data.get('rs_rank', 50)
    if rs_rank >= 85:
        score += 20
    elif rs_rank >= 70:
        score += 15
    elif rs_rank >= 50:
        score += 10
    else:
        score += 5
    
    return min(score, 100)

def get_confidence_level(score):
    """Return confidence level based on score"""
    if score >= 85:
        return "عالية جداً", "🟢", "golden"
    elif score >= 78:
        return "عالية", "🟡", "high"
    elif score >= 70:
        return "متوسطة", "🔵", "medium"
    else:
        return "منخفضة", "🔴", "low"

def main():
    print("=" * 60)
    print("🎯 Generating Signals...")
    print("=" * 60)
    
    # Load data
    data_dir = Path(__file__).parent.parent / "data"
    daily_file = data_dir / "daily.json"
    
    if not daily_file.exists():
        print("⚠️ No data/daily.json found, creating empty signals")
        signals_file = data_dir / "signals.json"
        with open(signals_file, 'w', encoding='utf-8') as f:
            json.dump({'signals': [], 'generated_at': datetime.now().isoformat()}, f, indent=2)
        print("✅ Created empty signals file")
        sys.exit(0)
    
    # Load and process
    with open(daily_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    stocks = data.get('stocks', [])
    signals = []
    
    for stock in stocks:
        # Calculate score
        score = calculate_score(stock)
        
        # Get confidence level
        confidence, emoji, level = get_confidence_level(score)
        
        # Only generate signals for score >= 70
        if score >= 70:
            current_price = stock.get('current_price', 0)
            signal = {
                'symbol': stock.get('symbol', ''),
                'name': stock.get('name', ''),
                'score': score,
                'confidence': confidence,
                'emoji': emoji,
                'level': level,
                'current_price': current_price,
                'entry_point': current_price * 1.01,  # 1% above current
                'target1': current_price * 1.05,  # +5%
                'target2': current_price * 1.10,  # +10%
                'stop_loss': current_price * 0.97,  # -3%
                'rsi': stock.get('rsi', 50),
                'volume_ratio': stock.get('volume_ratio', 1.0),
                'rs_rank': stock.get('rs_rank', 0),
                'sector': stock.get('sector', ''),
                'change_percent': stock.get('change_percent', 0),
                'timestamp': datetime.now().isoformat()
            }
            signals.append(signal)
            print(f"🎯 Signal: {stock.get('symbol')} - Score: {score} - {confidence} {emoji}")
    
    # Save signals
    signals_file = data_dir / "signals.json"
    with open(signals_file, 'w', encoding='utf-8') as f:
        json.dump({
            'signals': signals,
            'generated_at': datetime.now().isoformat(),
            'total_signals': len(signals)
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Generated {len(signals)} signal(s)")
    print(f"✅ Saved to {signals_file}")

if __name__ == "__main__":
    main()

