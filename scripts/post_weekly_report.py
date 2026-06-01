#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post weekly report to Telegram
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime

def escape_markdown_v2(text):
    """
    Escape ALL special characters for Telegram MarkdownV2
    """
    if text is None:
        return ""
    
    text = str(text)
    # ALL special characters that need escaping in MarkdownV2
    escape_chars = r'\_*[]()~`>#+\-=|{}.!@'
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

def post_weekly_report():
    print("=" * 60)
    print("📢 نشر التقرير الأسبوعي على تيليجرام")
    print("=" * 60)
    
    # 1. Get environment variables
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ Error: Telegram credentials not set")
        sys.exit(1)
    
    # 2. Load weekly report
    data_dir = Path(__file__).parent.parent / "data"
    report_file = data_dir / "weekly_report.json"
    
    if not report_file.exists():
        print("⚠️ No weekly report found")
        sys.exit(0)
    
    with open(report_file, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    # 3. Format message (SIMPLIFIED - no complex formatting)
    week_start = report.get('week_start', 'Unknown')
    week_end = report.get('week', 'Unknown')
    total_signals = report.get('total_signals', 0)
    profitable = report.get('profitable', 0)
    losing = report.get('losing', 0)
    success_rate = report.get('success_rate', 0)
    avg_score = report.get('avg_score', 0)
    
    # Top performers
    top_performers = report.get('top_performers', [])
    worst_performers = report.get('worst_performers', [])
    
    # Build SIMPLE message (avoid special chars)
    message = (
        f"📊 *التقرير الأسبوعي - راصد*\n"
        f"📅 الفترة: {escape_markdown_v2(week_start)} إلى {escape_markdown_v2(week_end)}\n\n"
        f"📊 *الإحصائيات:*\n"
        f"• إجمالي الإشارات: *{total_signals}*\n"
        f"• الإشارات الرابحة: *{profitable}*\n"
        f"• الإشارات الخاسرة: *{losing}*\n"
        f"• نسبة النجاح: *{success_rate:.1f}%*\n"
        f"• متوسط Score: *{avg_score:.1f} من 100*\n\n"
    )
    
    if top_performers:
        message += f"🏆 *أفضل الأسهم:*\n"
        for i, stock in enumerate(top_performers[:3], 1):
            symbol = escape_markdown_v2(stock.get('symbol', ''))
            name = escape_markdown_v2(stock.get('name', ''))
            gain = stock.get('gain', 0)
            message += f"{i}\\- {symbol} \\- {name} \\(+{gain:.1f}%\\)\n"
        message += "\n"
    
    if worst_performers:
        message += f"📉 *الأسوأ أداءً:*\n"
        for i, stock in enumerate(worst_performers[:3], 1):
            symbol = escape_markdown_v2(stock.get('symbol', ''))
            name = escape_markdown_v2(stock.get('name', ''))
            loss = stock.get('loss', 0)
            message += f"{i}\\- {symbol} \\- {name} \\({loss:.1f}%\\)\n"
        message += "\n"
    
    message += (
        f"💡 *التوصيات للأسبوع القادم:*\n"
        f"• راقب الأسهم ذات RSI بين 55-70\n"
        f"• ابحث عن حجم تداول أعلى من المتوسط\n"
        f"• التزم بوقف الخسارة دائمًا\n\n"
        f"═══════════════════════════\n"
        f"⚠️ *محتوى تعليمي وتحليلي - ليس توصية استثمارية*"
    )
    
    # 4. Send to Telegram
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'MarkdownV2'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            print("✅ تم نشر التقرير الأسبوعي بنجاح!")
            print(f"📊 Total signals: {total_signals}")
            print(f"📈 Success rate: {success_rate:.1f}%")
            return True
        else:
            print(f"❌ Failed to post: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    success = post_weekly_report()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

