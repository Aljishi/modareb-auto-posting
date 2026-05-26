#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, json, requests
from pathlib import Path

def send_signal_to_telegram():
    print("=" * 60)
    print("🤖 راصد - النشر على تيليجرام")
    print("=" * 60)

    # 1. المتغيرات البيئية
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("❌ خطأ: تأكد من إضافة TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID في Secrets")
        sys.exit(1)

    # 2. مسار الملفات
    base_dir = Path(__file__).parent.parent
    json_path = base_dir / "data" / "daily.json"
    if not json_path.exists():
        json_path = base_dir / "data" / "golden_signal.json"
    
    if not json_path.exists():
        print("❌ خطأ: ملف البيانات غير موجود")
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 3. مسار الصورة
    image_path = base_dir / "output.png"
    if not image_path.exists():
        image_path = base_dir / "output_golden.png"
    
    if not image_path.exists():
        print("❌ خطأ: الصورة غير موجودة")
        sys.exit(1)

    # 4. بناء الرسالة (MarkdownV2 format)
    stock_name = data.get("stock_name", "غير معروف")
    symbol = data.get("symbol", "")
    
    # Escape special chars for MarkdownV2
    def escape_md(text):
        chars = r'\_*[]()~`>#+-=|{}.!'
        return ''.join(f'\\{c}' if c in chars else c for c in str(text))
    
    caption = (
        f"📊 *{escape_md(stock_name)} ({escape_md(symbol)})*\n"
        f"🏢 القطاع: {escape_md(data.get('sector', ''))}\n"
        f"💰 السعر: `{data.get('current_price', 0)}` ريال\n\n"
        f"📈 نقطة الدخول: `{data.get('entry_point', 0)}`\n"
        f"🎯 الهدف 1: `{data.get('target1', 0)}` \\(+5%\\)\n"
        f"🎯 الهدف 2: `{data.get('target2', 0)}` \\(+10%\\)\n"
        f"🛑 وقف الخسارة: `{data.get('stop_loss', 0)}`\n\n"
        f"🏆 النتيجة: *{data.get('score', 0)}/100*\n\n"
        f"⚠️ _محتوى تعليمي فقط — لا يعد توصية استثمارية_"
    )

    # 5. الإرسال
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    try:
        with open(image_path, 'rb') as photo:
            payload = {
                'chat_id': chat_id,
                'caption': caption,
                'parse_mode': 'MarkdownV2'  # ✅ تم التعديل
            }
            files = {'photo': photo}
            response = requests.post(url, data=payload, files=files, timeout=30)
            
            if response.status_code == 200:
                print("✅ تم النشر بنجاح!")
                return True
            else:
                print(f"❌ فشل النشر: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False

if __name__ == "__main__":
    success = send_signal_to_telegram()
    sys.exit(0 if success else 1)
