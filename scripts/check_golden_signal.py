#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check if golden signals exist in data/golden_signals.json
Returns exit code 0 if found, 1 if not.
"""

import json
import sys
from pathlib import Path

def main():
    data_dir = Path(__file__).parent.parent / "data"
    golden_file = data_dir / "golden_signals.json"
    
    if not golden_file.exists():
        print("ℹ️ No golden_signals.json file found")
        sys.exit(1)
    
    try:
        with open(golden_file, 'r', encoding='utf-8') as f:
            signals = json.load(f)
        
        if isinstance(signals, list) and len(signals) > 0:
            print(f"✅ Found {len(signals)} golden signal(s)")
            for s in signals:
                print(f"   - {s.get('symbol', 'N/A')} (Score: {s.get('analysis', {}).get('score', 0)})")
            sys.exit(0)
        else:
            print("ℹ️ Golden signals list is empty")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error reading golden signals: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

