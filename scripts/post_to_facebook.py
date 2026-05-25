#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rasid Auto Posting - Facebook Publisher
Posts trading signals to Facebook page
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


def build_post_text(data: dict) -> str:
    """بناء نص المنشور"""
    # FIX: use 'stock_symbol' and 'entry' — matching the keys written by fetch_api_data.py
    symbol     = data.get('stock_symbol', data.get('symbol', ''))
    stock_name = data.get('stock_name', '')
    entry      = data.get('entry', data.get('entry_point', ''))
    target1    = data.get('target1', '')
    target2    = data.get('target2', '')
    stop_loss  = data.get('stop_loss', '')
    score      = data.get('score', 0)

    is_golden = data.get('type') == 'اشارة ذهبية'
    badge = "⭐ ذهبية" if is_golden else "📊 يومية"

    text = (
        f"🔔 راصد — إشارة {badge}\n\n"
        f"📌 {stock_name} ({symbol})\n"
        f"💰 نقطة الدخول: {entry} ريال\n"
        f"🎯 الهدف الأول: {target1} ريال\n"
        f"🎯 الهدف الثاني: {target2} ريال\n"
        f"🛑 وقف الخسارة: {stop_loss} ريال\n\n"
        f"📊 قوة الإشارة: {score}/100\n\n"
        f"⚠️ محتوى تعليمي — ليس توصية مالية\n\n"
        f"#راصد #تاسي #السوق_السعودي #تداول"
    )

    return text


def post_to_facebook():
    """نشر الإشارة على فيسبوك"""
    print("📤 بدء النشر على فيسبوك...")

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

    # ملاحظات: فيسبوك يتطلب إعدادات OAuth معقدة
    # هنا نضع placeholder للتنفيذ المستقبلي

    print("⚠️ النشر على فيسبوك يتطلب إعداد Facebook Graph API")
    print("📝 راجع التوثيق: https://developers.facebook.com/docs/graph-api")

    print("🔄 راصد - جاهز للنشر (يتطلب إعداد API)")

    return True


def main():
    """الدالة الرئيسية"""
    print("=" * 60)
    print("📤 راصد - النشر على فيسبوك")
    print("=" * 60)

    success = post_to_facebook()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
