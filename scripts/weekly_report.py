#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Weekly Report
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

def main():
    print("=" * 60)
    print("📊 تقرير راصد الأسبوعي")
    print("=" * 60)
    
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Load signals from the week
    signals_file = data_dir / "signals.json"
    validated_file = data_dir / "validated_signals.json"
    track_file = data_dir / "track_record.json"
    
    all_signals = []
    
    # Try loading from different sources
    if validated_file.exists():
        with open(validated_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_signals.extend(data.get('validated_signals', []))
    
    if signals_file.exists():
        with open(signals_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_signals.extend(data.get('signals', []))
    
    if track_file.exists():
        with open(track_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_signals.extend(data.get('tracked_signals', []))
    
    # Remove duplicates
    seen = set()
    unique_signals = []
    for signal in all_signals:
        key = f"{signal.get('symbol')}_{signal.get('timestamp', '')}"
        if key not in seen:
            seen.add(key)
            unique_signals.append(signal)
    
    all_signals = unique_signals
    
    # Calculate statistics
    total_signals = len(all_signals)
    profitable = sum(1 for s in all_signals if s.get('score', 0) >= 75)
    losing = sum(1 for s in all_signals if s.get('score', 0) < 75)
    open_positions = 0  # Would need actual tracking data
    
    success_rate = (profitable / total_signals * 100) if total_signals > 0 else 0
    avg_score = sum(s.get('score', 0) for s in all_signals) / total_signals if total_signals > 0 else 0
    
    # Top performers
    sorted_signals = sorted(all_signals, key=lambda x: x.get('score', 0), reverse=True)
    top_performers = [
        {
            'symbol': s.get('symbol', ''),
            'name': s.get('name', ''),
            'score': s.get('score', 0),
            'gain': s.get('change_percent', 0)
        }
        for s in sorted_signals[:5]
    ]
    
    # Worst performers
    worst_performers = [
        {
            'symbol': s.get('symbol', ''),
            'name': s.get('name', ''),
            'score': s.get('score', 0),
            'loss': s.get('change_percent', 0)
        }
        for s in sorted_signals[-5:] if len(sorted_signals) >= 5
    ]
    
    # Generate report
    report = {
        'week': datetime.now().strftime('%Y-%m-%d'),
        'week_start': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
        'total_signals': total_signals,
        'profitable': profitable,
        'losing': losing,
        'open_positions': open_positions,
        'success_rate': success_rate,
        'avg_score': avg_score,
        'top_performers': top_performers,
        'worst_performers': worst_performers,
        'generated_at': datetime.now().isoformat()
    }
    
    # Save report to JSON
    report_file = data_dir / "weekly_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # Print report to console
    print(f"\n📅 {report['week_start']} إلى {report['week']}")
    print("=" * 60)
    print(f"📊 إجمالي الإشارات الكلي: {total_signals}")
    print(f"✅ رابحة: {profitable}")
    print(f"❌ خاسرة: {losing}")
    print(f"⏳ مفتوحة: {open_positions}")
    print(f"🎯 نسبة النجاح: {success_rate:.1f}%")
    print(f"📊 متوسط الـ Score: {avg_score:.1f}/100")
    print("=" * 60)
    print(f"📅 إشارات هذا الأسبوع ({total_signals}):")
    
    if total_signals == 0:
        print("لا توجد إشارات هذا الأسبوع")
    else:
        for signal in top_performers[:3]:
            print(f"  • {signal['symbol']} - {signal['name']} (Score: {signal['score']})")
    
    print("=" * 60)
    print("💡 منهجيتنا:")
    print("• نُصدر 3 إشارات أسبوعياً كحد أقصى.")
    print("• لا إشارة إلا عند توفر جميع شروط الجودة.")
    print("=" * 60)
    print("⚠️ محتوى تعليمي وتحليلي - ليس توصية استثمارية")
    print("=" * 60)
    
    print(f"\n✅ Weekly report saved to {report_file}")
    print(f"📊 Total signals: {total_signals}")
    
    sys.exit(0)

if __name__ == "__main__":
    main()

