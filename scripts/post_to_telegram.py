#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post signal to Telegram using HTML parse mode
"""

import os
import sys
import json
import requests
from pathlib import Path

def send_to_telegram():
    print("=" * 60)
    print("🤖 راصد - النشر على تيليجرام")
    print("=" * 60)
    
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        sys.exit(1)
    
    data_dir = Path(__file__).parent.parent / "data"
    
    # Try validated_signals first, then signals
    signal_file = data_dir / "validated_signals.json"
    if not signal_file.exists():
        signal_file = data_dir / "signals.json"
    
    if not signal_file.exists():
        print("❌ Error: No signal data found")
        sys.exit(1)
    
    with open(signal_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    signals = data.get('validated_signals', data.get('signals', []))
    
    if not signals:
        print("⚠️ No signals to post")
        sys.exit(0)
    
    signal = signals[0]
    
    symbol = signal.get('symbol', '')
    name = signal.get('name', '')
    sector = signal.get('sector', '')
    current_price = signal.get('current_price', 0)
    entry_point = signal.get('entry_point', 0)
    target1 = signal.get('target1', 0)
    target2 = signal.get('target2', 0)
    stop_loss = signal.get('stop_loss', 0)
    score = signal.get('score', 0)
    rsi = signal.get('rsi', 0)
    volume_ratio = signal.get('volume_ratio', 1.0)
    confidence = signal.get('confidence', 'عالية')
    
    # Calculate percentages safely
    def safe_pct(val, base):
        return ((val - base) / base * 100) if base > 0 else 0

    t1_pct = safe_pct(target1, current_price)
    t2_pct = safe_pct(target2, current_price)
    sl_pct = safe_pct(stop_loss, current_price)
    
    message = f"""📊 <b>{name} ({symbol})</b>
🏢 القطاع: {sector}

🎯 مستوى الثقة: {confidence}

💰 السعر الحالي: <code>{current_price:.2f}</code> ريال
🎯 نقطة الدخول: <code>{entry_point:.2f}</code> ريال

📈 الأهداف:
الهدف الأول: <code>{target1:.2f}</code> ريال (+{t1_pct:.1f}%) 🟢
الهدف الثاني: <code>{target2:.2f}</code> ريال (+{t2_pct:.1f}%) 🟢

🛑 وقف الخسارة: <code>{stop_loss:.2f}</code> ريال ({sl_pct:.1f}%) 🔴

📊 المؤشرات:
RSI: <code>{rsi:.1f}</code>
حجم التداول: <code>{volume_ratio:.1f}x</code>
النتيجة: <b>{score}/100</b>

⚠️ <i>محتوى تعليمي وتحليلي فقط — لا يعد توصية استثمارية</i>"""

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            print("✅ تم النشر بنجاح على تيليجرام!")
            return True
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = send_to_telegram()
    sys.exit(0 if success else 1)

