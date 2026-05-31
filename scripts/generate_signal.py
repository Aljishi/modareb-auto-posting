#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate trading signals from market data
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

def load_market_data():
    """Load market data from JSON file"""
    data_dir = Path(__file__).parent.parent / "data"
    daily_file = data_dir / "daily.json"
    
    if not daily_file.exists():
        print("❌ Error: data/daily.json not found")
        return None
    
    try:
        with open(daily_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ Loaded market data from {daily_file}")
        return data
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None

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

def generate_signals(data):
    """Generate signals for all stocks"""
    stocks = data.get('stocks', [])
    signals = []
    
    print(f"\n📊 Analyzing {len(stocks)} stocks...")
    print("=" * 60)
    
    for stock in stocks:
        symbol = stock.get('symbol', 'Unknown')
        name = stock.get('name', 'Unknown')
        
        # Calculate score
        score = calculate_score(stock)
        
        # Determine if should generate signal
        rsi = stock.get('rsi', 50)
        volume_ratio = stock.get('volume_ratio', 1.0)
        
        # Signal conditions
        if score >= 75 and 42 <= rsi <= 68 and volume_ratio >= 1.5:
            signal = {
                'symbol': symbol,
                'name': name,
                'score': score,
                'current_price': stock.get('current_price', 0),
                'entry_point': stock.get('current_price', 0) * 1.01,  # 1% above current
                'target1': stock.get('current_price', 0) * 1.05,  # +5%
                'target2': stock.get('current_price', 0) * 1.10,  # +10%
                'stop_loss': stock.get('current_price', 0) * 0.97,  # -3%
                'rsi': rsi,
                'volume_ratio': volume_ratio,
                'rs_rank': stock.get('rs_rank', 0),
                'sector': stock.get('sector', 'Unknown'),
                'change_percent': stock.get('change_percent', 0),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            signals.append(signal)
            
            print(f"\n🎯 SIGNAL: {name} ({symbol})")
            print(f"   Score: {score}/100")
            print(f"   Price: {stock.get('current_price', 0):.2f} SAR")
            print(f"   RSI: {rsi:.1f} | Volume: {volume_ratio:.1f}x")
    
    print(f"\n{'='*60}")
    print(f"📊 Total signals generated: {len(signals)}")
    print(f"{'='*60}")
    
    return signals

def save_signals(signals):
    """Save signals to JSON file"""
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = data_dir / "signals.json"
    
    signal_data = {
        'signals': signals,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'timezone': 'Asia/Riyadh',
        'total_signals': len(signals)
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(signal_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Signals saved to {output_file}")
    return output_file

def main():
    print("=" * 60)
    print("🎯 راصد - توليد الإشارات")
    print("=" * 60)
    
    # Load market data
    data = load_market_data()
    if not data:
        print("❌ Failed to load market data")
        sys.exit(1)
    
    # Generate signals
    signals = generate_signals(data)
    
    # Save signals
    if signals:
        save_signals(signals)
        print(f"\n✅ Generated {len(signals)} signal(s)")
        sys.exit(0)
    else:
        print("\n⚠️ No signals generated (conditions not met)")
        # Create empty signals file
        save_signals([])
        sys.exit(0)

if __name__ == "__main__":
    main()

