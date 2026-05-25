#!/usr/bin/env python3
"""
Check if Saudi Stock Market (Tadawul) is open.
Returns exit code 0 if open, 1 if closed.
"""

import os
from datetime import datetime, timedelta
import pytz

def is_saudi_market_open():
    """
    Check if Saudi market is open.
    Market hours: Sunday-Thursday, 10:00-15:00 KSA
    Returns: (bool, str) - is_open, reason
    """
    
    # Saudi Arabia timezone
    saudi_tz = pytz.timezone('Asia/Riyadh')
    now_saudi = datetime.now(saudi_tz)
    
    # Get current day of week (0=Monday, 6=Sunday)
    day_of_week = now_saudi.weekday()
    
    # Check if weekend (Friday=4, Saturday=5)
    if day_of_week >= 4:  # Friday or Saturday
        return False, f"Weekend - {now_saudi.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Check market hours (10:00 - 15:00)
    current_hour = now_saudi.hour
    current_minute = now_saudi.minute
    current_time = current_hour * 60 + current_minute  # Convert to minutes
    
    market_open_time = 10 * 60   # 10:00 AM in minutes
    market_close_time = 15 * 60  # 3:00 PM in minutes
    
    if current_time < market_open_time:
        return False, f"Before market open - {now_saudi.strftime('%Y-%m-%d %H:%M:%S')}"
    
    if current_time >= market_close_time:
        return False, f"After market close - {now_saudi.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Check for public holidays
    if is_saudi_holiday(now_saudi):
        return False, f"Public Holiday - {now_saudi.strftime('%Y-%m-%d %H:%M:%S')}"
    
    return True, f"Market Open - {now_saudi.strftime('%Y-%m-%d %H:%M:%S')}"

def is_saudi_holiday(date):
    """
    Check if the given date is a Saudi public holiday.
    """
    year = date.year
    
    # Saudi Public Holidays for 2026
    holidays = [
        # Founding Day
        (2, 22, "Founding Day"),
        
        # Eid Al-Fitr 2026 (approximate - 19-22 March)
        (3, 19, "Eid Al-Fitr"),
        (3, 20, "Eid Al-Fitr"),
        (3, 21, "Eid Al-Fitr"),
        (3, 22, "Eid Al-Fitr"),
        
        # Arafat Day & Eid Al-Adha 2026 (approximate - 26-29 May)
        (5, 26, "Arafat Day"),
        (5, 27, "Eid Al-Adha"),
        (5, 28, "Eid Al-Adha"),
        (5, 29, "Eid Al-Adha"),
        
        # Saudi National Day
        (9, 23, "Saudi National Day"),
    ]
    
    # Add holidays for different years
    if year == 2026:
        return any(date.month == h[0] and date.day == h[1] for h in holidays)
    elif year == 2027:
        # Add 2027 holidays (adjust as needed)
        holidays_2027 = [
            (2, 22, "Founding Day"),
            (9, 23, "Saudi National Day"),
        ]
        return any(date.month == h[0] and date.day == h[1] for h in holidays_2027)
    
    return False

def main():
    is_open, reason = is_saudi_market_open()
    
    print(f"📊 Saudi Market Status: {reason}")
    
    if not is_open:
        print("❌ Market is CLOSED - Skipping posting")
        exit(1)
    else:
        print("✅ Market is OPEN - Proceeding with posting")
        exit(0)

if __name__ == "__main__":
    main()
