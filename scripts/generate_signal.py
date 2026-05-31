#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate trading signals from market data"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

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
        score = 80  # Default score
        if stock.get('score'):
            score = stock['score']
        
        if score >= 75:
            signal = {
                'symbol': stock.get('symbol', ''),
                'name': stock.get('name', ''),
                'score': score,
                'current_price': stock.get('current_price', 0),
                'entry_point': stock.get('current_price', 0) * 1.01,
                'target1': stock.get('current_price', 0) * 1.05,
                'target2': stock.get('current_price', 0) * 1.10,
                'stop_loss': stock.get('current_price', 0) * 0.97,
                'rsi': stock.get('rsi', 50),
                'volume_ratio': stock.get('volume_ratio', 1.0),
                'rs_rank': stock.get('rs_rank', 0),
                'sector': stock.get('sector', ''),
                'timestamp': datetime.now().isoformat()
            }
            signals.append(signal)
            print(f"🎯 Signal: {stock.get('symbol')} - Score: {score}")
    
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

