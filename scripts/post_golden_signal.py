#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post Golden Signal to Telegram
- Uses HTML parse mode (safe from MarkdownV2 escaping issues)
- Reads from data/golden_signals.json
- Posts only if signals exist
"""

import os
import sys
import json
import requests
from pathlib import Path

def escape_html(text):
    """Simple HTML escaping for safety (minimal)"""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

def main():
    print("=" * 60)
    print("🌟 راصد - نشر الإشارة الذهبية")
    print("=" * 60)

    # 1. Load secrets
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("❌ خطأ: مفاتيح تيليجرام غير مضبوطة في Secrets")
        sys.exit(1)

    # 2. Load golden signals
    data_dir = Path(__file__).parent.parent / "data"
    golden_file = data_dir / "golden_signals.json"

    if not golden_file.exists():
        print("ℹ️ لا توجد ملف إشارات ذهبية — تخطي النشر")
        sys.exit(0)

    try:
        with open(golden_file, "r", encoding="utf-8") as f:
            signals = json.load(f)
    except Exception as e:
        print(f"❌ خطأ في قراءة golden_signals.json: {e}")
        sys.exit(1)

    if not signals:
        print("ℹ️ لا توجد إشارات ذهبية اليوم — تخطي النشر")
        sys.exit(0)

    # 3. Use first signal
    signal = signals[0]
    analysis = signal.get("analysis", {})
    score = analysis.get("score", 0)
    symbol = signal.get("symbol", "N/A")
    name = signal.get("name", "سهم غير معروف")
    sector = signal.get("sector", "غير محدد")
    current_price = signal.get("current_price", 0)
    entry_point = signal.get("entry_point", 0)
    target1 = signal.get("target1", 0)
    target2 = signal.get("target2", 0)
    stop_loss = signal.get("stop_loss", 0)
    rsi = analysis.get("indicators", {}).get("RSI", 50)
    volume_ratio = analysis.get("indicators", {}).get("volume_ratio", 1.0)

    # 4. Format message (HTML-safe)
    def pct(val, base):
        return f"{((val - base) / base * 100):.1f}" if base > 0 else "0.0"

    msg = f"""🌟 <b>إشارة ذهبية — راصد</b> 🌟

📊 <b>{escape_html(name)} ({escape_html(symbol)})</b>
🏢 القطاع: {escape_html(sector)}

🎯 مستوى الثقة: <b>عالية جداً</b> ✅
🏆 النتيجة: <b>{score}/100</b>

💰 السعر الحالي: <code>{current_price:.2f}</code> ريال  
➡️ نقطة الدخول: <code>{entry_point:.2f}</code> ريال  

📈 الأهداف:
• الهدف 1: <code>{target1:.2f}</code> ريال (+{pct(target1, current_price)}%) 🟢  
• الهدف 2: <code>{target2:.2f}</code> ريال (+{pct(target2, current_price)}%) 🟢  

🛑 وقف الخسارة: <code>{stop_loss:.2f}</code> ريال ({pct(stop_loss, current_price)}%) 🔴  

📊 مؤشرات فنية:
• RSI: <code>{rsi:.1f}</code>  
• حجم التداول: <code>{volume_ratio:.1f}x</code>  

⚠️ <i>محتوى تعليمي وتحليلي فقط — لا يُعتبر توصية استثمارية</i>"""

    # 5. Send to Telegram
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            print("✅ تم نشر الإشارة الذهبية بنجاح!")
            return 0
        else:
            print(f"❌ خطأ في النشر: {resp.status_code} | {resp.text}")
            return 1
    except Exception as e:
        print(f"❌ استثناء عند النشر: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

