#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post signal to Telegram
"""

import os
import sys
import json
import requests
from pathlib import Path

def escape_markdown_v2(text):
    """
    Escape special characters for Telegram MarkdownV2
    """
    if text is None:
        return ""
    
    text = str(text)
    # Characters that need escaping in MarkdownV2
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

def send_to_telegram():
    print("=" * 60)
    print("🤖 راصد - النشر على تيليجرام")
    print("=" * 60)
    
    # 1. Get environment variables
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        sys.exit(1)
    
    # 2. Load validated signal data
    data_dir = Path(__file__).parent.parent / "data"
    signal_file = data_dir / "validated_signals.json"
    
    if not signal_file.exists():
        # Try signals.json as fallback
        signal_file = data_dir / "signals.json"
        if not signal_file.exists():
            print("❌ Error: No signal data found")
            sys.exit(1)
    
    with open(signal_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Get signals from validated_signals or signals
    signals = data.get('validated_signals', data.get('signals', []))
    
    if not signals:
        print("⚠️ No signals to post")
        sys.exit(0)
    
    # 3. Get first signal
    signal = signals[0]
    
    # 4. Format message (MarkdownV2)
    symbol = escape_markdown_v2(signal.get('symbol', ''))
    name = escape_markdown_v2(signal.get('name', ''))
    sector = escape_markdown_v2(signal.get('sector', ''))
    
    current_price = signal.get('current_price', 0)
    entry_point = signal.get('entry_point', 0)
    target1 = signal.get('target1', 0)
    target2 = signal.get('target2', 0)
    stop_loss = signal.get('stop_loss', 0)
    
    score = signal.get('score', 0)
    rsi = signal.get('rsi', 0)
    volume_ratio = signal.get('volume_ratio', 1.0)
    confidence = escape_markdown_v2(signal.get('confidence', 'عالية'))
    emoji = signal.get('emoji', '🟡')
    
    # Calculate percentages
    if current_price > 0:
        target1_change = ((target1 - current_price) / current_price) * 100
        target2_change = ((target2 - current_price) / current_price) * 100
        stop_loss_change = ((stop_loss - current_price) / current_price) * 100
    else:
        target1_change = target2_change = stop_loss_change = 0
    
    message = (
        f"📊 *{name} \\({symbol}\\)*\n"
        f"🏢 القطاع: {sector}\n\n"
        f"🎯 مستوى الثقة: {confidence} {emoji}\n\n"
        f"💰 السعر الحالي: `{current_price:.2f}` ريال\n"
        f"🎯 نقطة الدخول: `{entry_point:.2f}` ريال\n\n"
        f"📈 الأهداف:\n"
        f"الهدف الأول: `{target1:.2f}` ريال \\(+{target1_change:.1f}%\\) 🟢\n"
        f"الهدف الثاني: `{target2:.2f}` ريال \\(+{target2_change:.1f}%\\) 🟢\n\n"
        f"🛑 وقف الخسارة: `{stop_loss:.2f}` ريال \\({stop_loss_change:.1f}%\\) 🔴\n\n"
        f"📊 المؤشرات:\n"
        f"RSI: `{rsi:.1f}`\n"
        f"حجم التداول: `{volume_ratio:.1f}x`\n"
        f"النتيجة: *{score}/100*\n\n"
        f"⚠️ _محتوى تعليمي وتحليلي فقط \\— لا يعد توصية استثمارية_"
    )
    
    # 5. Send to Telegram
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'MarkdownV2'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            print("✅ تم النشر بنجاح على تيليجرام!")
            print(f"📊 Signal: {symbol} - Score: {score} - {confidence}")
            return True
        else:
            print(f"❌ Failed to post: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    success = send_to_telegram()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

