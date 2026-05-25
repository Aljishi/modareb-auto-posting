#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import requests
import json
from pathlib import Path

def send_signal_to_telegram():
    """
    يرسل إشارة التداول (الصورة والنص) إلى قناة تيليجرام.
    """
    print("=" * 60)
    print("🤖 راصد - النشر على تيليجرام")
    print("=" * 60)

    # 1. الحصول على المتغيرات البيئية
    # هذه المتغيرات تأتي من GitHub Actions secrets
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    # 🔍 تشخيص: طباعة حالة المتغيرات للتأكد
    print("🔍 فحص المتغيرات...")
    if not bot_token:
        print("❌ خطأ: TELEGRAM_BOT_TOKEN غير موجود!")
        print("💡 تأكد من إضافته في Settings -> Secrets -> Actions")
        sys.exit(1)
    
    if not chat_id:
        print("❌ خطأ: TELEGRAM_CHAT_ID غير موجود!")
        sys.exit(1)
        
    print("✅ تم العثور على المتغيرات بنجاح.")

    # 2. تحديد مسار الملفات
    base_dir = Path(__file__).parent.parent
    
    # البحث عن ملف البيانات (JSON)
    json_path = base_dir / "data" / "daily.json"
    if not json_path.exists():
        json_path = base_dir / "data" / "golden_signal.json"
    
    if not json_path.exists():
        print("❌ خطأ: لم يتم العثور على ملف البيانات (daily.json أو golden_signal.json)")
        sys.exit(1)

    # قراءة البيانات
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ خطأ في قراءة JSON: {e}")
        sys.exit(1)

    # 3. تحديد مسار الصورة (العادية أم الذهبية)
    # نفترض أن الصورة تم توليدها مسبقاً باسم output.png أو output_golden.png
    image_path = base_dir / "output.png"
    if not image_path.exists():
        image_path = base_dir / "output_golden.png"
        
    if not image_path.exists():
        print("❌ خطأ: لم يتم العثور على الصورة (output.png أو output_golden.png)")
        sys.exit(1)

    print(f"🖼️ سيتم نشر الصورة: {image_path.name}")

    # 4. بناء نص الرسالة (Caption)
    stock_name = data.get("stock_name", "غير معروف")
    symbol = data.get("symbol") or data.get("stock_symbol", "")
    sector = data.get("sector", "")
    current = data.get("current_price", 0)
    entry = data.get("entry_point", 0)
    t1 = data.get("target1", 0)
    t2 = data.get("target2", 0)
    sl = data.get("stop_loss", 0)
    score = data.get("score", 0)
    
    # تنسيق النص باستخدام HTML
    caption = f"""
📊 <b>{stock_name} ({symbol})</b>
🏢 القطاع: {sector}
💰 السعر: {current} ريال

📈 نقطة الدخول: {entry}
🎯 الهدف 1: {t1}
🎯 الهدف 2: {t2}
 وقف الخسارة: {sl}

🏆 النتيجة (Score): {score}/100
    """

    # 5. الإرسال عبر تيليجرام API
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    print(f"🚀 جاري الإرسال إلى Chat ID: {chat_id}...")

    try:
        with open(image_path, 'rb') as photo:
            # إرسال طلب POST مع الصورة والنص
            payload = {
                'chat_id': chat_id,
                'caption': caption,
                'parse_mode': 'HTML'
            }
            files = {'photo': photo}
            
            response = requests.post(url, data=payload, files=files)
            
            if response.status_code == 200:
                print("✅ تم النشر على تيليجرام بنجاح!")
                return True
            else:
                print(f"❌ فشل النشر. الحالة: {response.status_code}")
                print(f"الرد من تيليجرام: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ حدث خطأ أثناء الإرسال: {e}")
        return False

if __name__ == "__main__":
    success = send_signal_to_telegram()
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
