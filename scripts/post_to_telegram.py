#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rased Auto Posting - Telegram Publisher
Posts trading signal image + caption to Telegram channel
"""

import os
import sys
import json
import requests
from pathlib import Path

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

DATA_FILE  = "data/daily.json"
IMAGE_FILE = "output.png"

TRACK_URL  = "https://aljishi.github.io/modareb-auto-posting"


def load_data() -> dict:
    """تحميل بيانات الإشارة من daily.json"""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ خطأ في قراءة {DATA_FILE}: {e}")
        return {}


def build_caption(data: dict) -> str:
    """بناء نص الإشارة المرسلة إلى تيليغرام"""
    # FIX: check both key names for compatibility
    symbol = data.get("stock_symbol", data.get("symbol", ""))
    name   = data.get("stock_name", "")
    entry  = data.get("entry", data.get("entry_point", ""))
    t1     = data.get("target1", "")
    t2     = data.get("target2", "")
    sl     = data.get("stop_loss", "")
    score  = data.get("score", 0)
    rr     = data.get("rr", 0)

    is_golden = data.get("type") == "اشارة ذهبية"
    badge = "⭐ ذهبية" if is_golden else "📊 يومية"

    caption = (
        f"🔔 راصد — إشارة {badge}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📌 {name} ({symbol})\n"
        f"💰 الدخول: {entry} ريال\n"
        f"🎯 الهدف 1: {t1} ريال (+5%)\n"
        f"🎯 الهدف 2: {t2} ريال (+10%)\n"
        f"🛑 وقف الخسارة: {sl} ريال (-4%)\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 قوة الإشارة: {score}/100\n"
        f"⚖️ مكافأة/مخاطرة: {rr}:1\n"
        f"━━━━━━━━━━━━━━\n"
        f"📈 لوحة المتابعة: {TRACK_URL}\n"
        f"⚠️ محتوى تعليمي — ليس توصية مالية"
    )
    return caption


def send_photo(caption: str) -> bool:
    """إرسال صورة الإشارة مع النص إلى قناة تيليغرام"""
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN غير موجود في المتغيرات البيئية")
        return False
    if not CHAT_ID:
        print("❌ TELEGRAM_CHAT_ID غير موجود في المتغيرات البيئية")
        return False

    image_path = Path(IMAGE_FILE)
    if not image_path.exists():
        print(f"❌ الصورة غير موجودة: {IMAGE_FILE}")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    try:
        with open(image_path, "rb") as photo:
            response = requests.post(
                url,
                data={
                    "chat_id": CHAT_ID,
                    "caption": caption,
                    "parse_mode": "HTML",
                },
                files={"photo": photo},
                timeout=30,
            )

        result = response.json()
        print(f"Telegram response: {result}")

        if result.get("ok"):
            print("✅ تم الإرسال إلى تيليغرام بنجاح")
            return True
        else:
            print(f"❌ فشل الإرسال: {result.get('description', 'unknown error')}")
            return False

    except requests.exceptions.Timeout:
        print("❌ انتهت مهلة الاتصال بتيليغرام (30 ثانية)")
        return False
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {e}")
        return False


def main():
    print("=" * 60)
    print("📤 راصد - النشر على تيليغرام")
    print("=" * 60)

    data = load_data()
    if not data:
        print("❌ لا توجد بيانات — تم الإنهاء")
        sys.exit(1)

    symbol = data.get("stock_symbol", data.get("symbol", ""))
    name   = data.get("stock_name", "")
    score  = data.get("score", 0)
    stype  = data.get("type", "يومية")

    print(f"📌 الإشارة  : {name} ({symbol})")
    print(f"   النوع    : {stype}")
    print(f"   Score    : {score}/100")

    caption = build_caption(data)
    success = send_photo(caption)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
