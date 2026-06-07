#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rasid Auto Posting - Instagram Publisher
Posts trading signals to Instagram
"""

import os
import sys
import json
from pathlib import Path


def load_config():
    """تحميل الإعدادات"""
    config_file = Path("data/daily.json")
    if not config_file.exists():
        return None

    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_caption(data: dict) -> str:
    """بناء نص المنشور"""
    # FIX: use 'stock_symbol' and 'entry' — matching the keys written by fetch_api_data.py
    symbol       = data.get('stock_symbol', data.get('symbol', ''))
    stock_name   = data.get('stock_name', '')
    entry        = data.get('entry', data.get('entry_point', ''))
    target1      = data.get('target1', '')
    target2      = data.get('target2', '')
    stop_loss    = data.get('stop_loss', '')
    score        = data.get('score', 0)
    rsi          = data.get('rsi', 0)
    volume_ratio = data.get('volume_ratio', 0)

    is_golden = data.get('type') == 'اشارة ذهبية'
    badge = "⭐ ذهبية" if is_golden else "📊 يومية"

    caption = (
        f"🔔 راصد — إشارة {badge}\n\n"
        f"📊 {stock_name} ({symbol})\n"
        f"💡 نقطة الدخول: {entry} ريال\n"
        f"🎯 الأهداف: {target1} | {target2}\n"
        f"🛑 وقف الخسارة: {stop_loss}\n\n"
        f"📈 المؤشرات:\n"
        f"• Score: {score}/100\n"
        f"• RSI: {rsi}\n"
        f"• Volume: {volume_ratio}x\n\n"
        f"⚠️ محتوى تعليمي — ليس توصية مالية\n\n"
        f"#راصد #تاسي #السوق_السعودي #تداول #أسهم #تحليل_فني"
    )

    return caption


def post_to_instagram():
    """نشر الإشارة على إنستغرام"""
    print("📤 بدء النشر على إنستغرام...")

    # تحميل البيانات
    data = load_config()
    if not data:
        print("❌ فشل في تحميل البيانات")
        return False

    # التحقق من الصورة
    image_path = Path("output.png")
    if not image_path.exists():
        print("❌ الصورة غير موجودة")
        return False

    # ملاحظات: إنستغرام يتطلب Instagram Graph API
    # أو استخدام مكتبات مثل instagrapi

    print("⚠️ النشر على إنستغرام يتطلب إعداد Instagram API")
    print("📝 راجع التوثيق: https://developers.facebook.com/docs/instagram-api")

    print("🔄 راصد - جاهز للنشر (يتطلب إعداد API)")

    return True


def main():
    """الدالة الرئيسية"""
    print("=" * 60)
    print("📤 راصد - النشر على إنستغرام")
    print("=" * 60)

    success = post_to_instagram()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
