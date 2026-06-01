#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post weekly report to Telegram - Using HTML (Simpler)
"""

import os
import sys
import json
import requests
from pathlib import Path

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
    
    # 3. Format message using HTML (NO special escaping needed!)
    week_start = report.get('week_start', 'Unknown')
    week_end = report.get('week', 'Unknown')
    total_signals = report.get('total_signals', 0)
    profitable = report.get('profitable', 0)
    losing = report.get('losing', 0)
    success_rate = report.get('success_rate', 0)
    avg_score = report.get('avg_score', 0)
    
    top_performers = report.get('top_performers', [])
    worst_performers = report.get('worst_performers', [])
    
    # HTML message - MUCH SIMPLER!
    message = f"""📊 <b>التقرير الأسبوعي - راصد</b>
📅 الفترة: {week_start} إلى {week_end}

📊 <b>الإحصائيات:</b>
• إجمالي الإشارات: <b>{total_signals}</b>
• الإشارات الرابحة: <b>{profitable}</b>
• الإشارات الخاسرة: <b>{losing}</b>
• نسبة النجاح: <b>{success_rate:.1f}%</b>
• متوسط Score: <b>{avg_score:.1f} من 100</b>

"""
    
    if top_performers:
        message += "🏆 <b>أفضل الأسهم:</b>\n"
        for i, stock in enumerate(top_performers[:3], 1):
            symbol = stock.get('symbol', '')
            name = stock.get('name', '')
            gain = stock.get('gain', 0)
            message += f"{i}. {symbol} - {name} (+{gain:.1f}%)\n"
        message += "\n"
    
    if worst_performers:
        message += "📉 <b>الأسوأ أداءً:</b>\n"
        for i, stock in enumerate(worst_performers[:3], 1):
            symbol = stock.get('symbol', '')
            name = stock.get('name', '')
            loss = stock.get('loss', 0)
            message += f"{i}. {symbol} - {name} ({loss:.1f}%)\n"
        message += "\n"
    
    message += """💡 <b>التوصيات للأسبوع القادم:</b>
• راقب الأسهم ذات RSI بين 55-70
• ابحث عن حجم تداول أعلى من المتوسط
• التزم بوقف الخسارة دائمًا

═══════════════════════════
⚠️ <b>محتوى تعليمي وتحليلي - ليس توصية استثمارية</b>"""
    
    # 4. Send to Telegram using HTML parse mode
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'  # ✅ HTML is much easier!
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

