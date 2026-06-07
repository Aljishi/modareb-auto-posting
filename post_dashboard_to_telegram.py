import os
import csv
import requests
from datetime import datetime, date, timedelta, timezone

BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")
IMAGE_FILE = "data/weekly_report_card.png"
LOG_FILE   = "data/signals_log.csv"

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")


def has_signals_this_week():
    """تحقق أن في إشارات حقيقية هذا الأسبوع قبل الإرسال"""
    KSA        = timezone(timedelta(hours=3))
    today      = datetime.now(KSA).date()
    days_since_sunday = (today.weekday() + 1) % 7
    week_start = today - timedelta(days=days_since_sunday)
    week_end   = week_start + timedelta(days=4)

    try:
        with open(LOG_FILE, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    d = datetime.strptime(row["date"], "%Y-%m-%d").date()
                    if week_start <= d <= week_end:
                        return True
                except:
                    pass
    except:
        pass

    return False


# ── تحقق من وجود إشارات قبل الإرسال ───────────────────────
if not has_signals_this_week():
    print("⏭️  لا توجد إشارات هذا الأسبوع — تم تخطي إرسال التقرير")
    exit(0)

# ── إرسال الصورة ────────────────────────────────────────────
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

with open(IMAGE_FILE, "rb") as photo:
    response = requests.post(
        url,
        data={"chat_id": CHAT_ID},
        files={"photo": photo},
        timeout=30
    )

result = response.json()
print("Telegram response:", result)

if not result.get("ok"):
    raise Exception(f"Failed to send report image: {result}")

print("✅ Weekly report image sent to Telegram")
