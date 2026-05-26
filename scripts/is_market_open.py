#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""التحقق من وقت السوق السعودي"""

import os, sys
from datetime import datetime
import pytz

def is_market_open():
    saudi = pytz.timezone('Asia/Riyadh')
    now = datetime.now(saudi)
    
    # الجمعة والسبت إجازة
    if now.weekday() >= 4:  # 4=Friday, 5=Saturday
        print(f"❌ Weekend: {now.strftime('%Y-%m-%d %H:%M')}")
        return False
    
    # وقت السوق: 10:00 - 15:00
    hour, minute = now.hour, now.minute
    current = hour * 60 + minute
    
    if current < 10*60 or current >= 15*60:
        print(f"❌ Outside market hours: {now.strftime('%H:%M')}")
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
    
    print(f"✅ Market open: {now.strftime('%Y-%m-%d %H:%M')}")
    return True

if __name__ == "__main__":
    sys.exit(0 if is_market_open() else 1)
