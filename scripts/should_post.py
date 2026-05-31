#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validate signal before posting
"""

import json
import sys
from datetime import datetime
from pathlib import Path

def load_signals():
    """Load generated signals"""
    data_dir = Path(__file__).parent.parent / "data"
    signals_file = data_dir / "signals.json"
    
    if not signals_file.exists():
        print("❌ No signals file found")
        return []
    
    with open(signals_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data.get('signals', [])

def validate_signal(signal):
    """
    Validate signal conditions:
    - Score threshold (>= 70)
    - RSI range (42-68)
    - Volume ratio (>= 1.5)
    - Risk:Reward ratio (>= 2.0)
    """
    score = signal.get('score', 0)
    rsi = signal.get('rsi', 50)
    volume_ratio = signal.get('volume_ratio', 1.0)
    
    # Calculate Risk:Reward
    entry = signal.get('entry_point', 0)
    target1 = signal.get('target1', 0)
    stop_loss = signal.get('stop_loss', 0)
    
    if entry > 0 and stop_loss > 0 and target1 > 0:
        risk = entry - stop_loss
        reward = target1 - entry
        rr_ratio = reward / risk if risk > 0 else 0
    else:
        rr_ratio = 0
    
    # Validation logic
    reasons = []
    
    # RSI must be in golden zone
    if not (42 <= rsi <= 68):
        reasons.append(f"RSI {rsi:.1f} out of range [42-68]")
    
    # Volume must be above average
    if volume_ratio < 1.5:
        reasons.append(f"Volume {volume_ratio:.1f}x < 1.5x minimum")
    
    # Risk:Reward must be >= 2.0
    if rr_ratio < 2.0:
        reasons.append(f"R:R {rr_ratio:.1f} < 2.0 minimum")
    
    # Score threshold (minimum 70)
    if score < 70:
        reasons.append(f"Score {score} < 70 minimum")
    
    # If all conditions met
    if not reasons:
        confidence = signal.get('confidence', 'عالية')
        emoji = signal.get('emoji', '🟡')
        return True, {
            'should_post': True,
            'confidence': confidence,
            'emoji': emoji,
            'score': score,
            'rr_ratio': rr_ratio
        }
    
    return False, {
        'should_post': False,
        'reasons': reasons,
        'score': score
    }

def main():
    print("=" * 60)
    print("✅ Validating Signals...")
    print("=" * 60)
    
    signals = load_signals()
    
    if not signals:
        print("⚠️ No signals to validate")
        # Create empty output for workflow continuity
        output = {
            'validated_signals': [],
            'total_checked': 0,
            'total_valid': 0,
            'timestamp': datetime.now().isoformat()
        }
        with open('data/validated_signals.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        sys.exit(0)
    
    validated = []
    
    for signal in signals:
        is_valid, result = validate_signal(signal)
        
        if is_valid:
            validated.append({**signal, **result})
            print(f"✅ {signal.get('symbol')}: {result['confidence']} {result['emoji']} (Score: {result['score']})")
        else:
            print(f"❌ {signal.get('symbol')}: Rejected - {', '.join(result['reasons'])}")
    
    # Save validated signals
    output = {
        'validated_signals': validated,
        'total_checked': len(signals),
        'total_valid': len(validated),
        'timestamp': datetime.now().isoformat()
    }
    
    with open('data/validated_signals.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n📊 Results: {len(validated)}/{len(signals)} signals approved")
    
    # Exit with success even if no signals (normal behavior)
    sys.exit(0)

if __name__ == "__main__":
    main()

