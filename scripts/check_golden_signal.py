#!/usr/bin/env python3
"""
Check if golden signals exist
Returns exit code 0 if signals found, 1 if not
"""

import json
import os

def main():
    golden_file = 'data/golden_signals.json'
    
    if not os.path.exists(golden_file):
        print("❌ No golden signals file found")
        exit(1)
    
    with open(golden_file, 'r', encoding='utf-8') as f:
        signals = json.load(f)
    
    if len(signals) > 0:
        print(f"✅ Found {len(signals)} golden signal(s)")
        for signal in signals:
            print(f"  - {signal['symbol']}: Score {signal['analysis']['score']}/100")
        exit(0)
    else:
        print("ℹ️ No golden signals today")
        exit(1)

if __name__ == "__main__":
    main()
