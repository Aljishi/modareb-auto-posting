#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""التحقق من وقت السوق السعودي"""

import os
import sys
from datetime import datetime
import pytz

def is_market_open():
    # استخدام توقيت السعودية
    saudi = pytz.timezone('Asia/Riyadh')
    now = datetime.now(saudi)
    
    # طباعة معلومات للتصحيح
    print(f"📅 Current time (KSA): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 Day of week: {now.strftime('%A')} (weekday={now.weekday()})")
    
    # ✅ الجمعة = 4, السبت = 5 فقط (إجازة)
    # ✅ الأحد = 6 (يوم عمل)
    if now.weekday() in [4, 5]:  # Friday and Saturday ONLY
        day_name = "Friday" if now.weekday() == 4 else "Saturday"
        print(f"❌ Weekend ({day_name}): {now.strftime('%Y-%m-%d')}")
        return False
    
    # وقت السوق: 10:00 - 15:00
    hour, minute = now.hour, now.minute
    current_minutes = hour * 60 + minute
    
    market_open = 10 * 60   # 10:00 AM
    market_close = 15 * 60  # 3:00 PM
    
    if current_minutes < market_open:
        print(f"❌ Before market open: {now.strftime('%H:%M')} (opens at 10:00)")
        return False
    
    if current_minutes >= market_close:
        print(f"❌ After market close: {now.strftime('%H:%M')} (closed at 15:00)")
        return False
    
    # العطلات الرسمية (2026)
    holidays = [
        (2, 22),  # يوم التأسيس
        (3, 19), (3, 20), (3, 21), (3, 22),  # عيد الفطر
        (5, 26), (5, 27), (5, 28), (5, 29),  # عيد الأضحى
        (9, 23),  # اليوم الوطني
    ]
    
    if (now.month, now.day) in holidays:
        print(f"❌ Public holiday: {now.strftime('%Y-%m-%d')}")
        return False
    
    # كل شيء جيد - السوق مفتوح!
    print(f"✅ Market OPEN: {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"   Trading hours: 10:00 - 15:00")
    return True

if __name__ == "__main__":
    sys.exit(0 if is_market_open() else 1)
