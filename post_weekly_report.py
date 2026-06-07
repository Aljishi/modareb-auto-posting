#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشر تقرير الأداء الأسبوعي الحقيقي على تيليغرام."""

import html
import os
import sys
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORT_TXT = DATA_DIR / "weekly_performance_report.txt"


def post_message(text: str) -> bool:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("❌ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID غير موجود")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": html.escape(text),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    r = requests.post(url, json=payload, timeout=30)
    if r.status_code == 200:
        print("✅ تم نشر التقرير الأسبوعي")
        return True

    print(f"❌ Telegram failed: {r.status_code}")
    print(r.text[:500])
    return False


def main() -> int:
    print("=" * 60)
    print("📢 نشر التقرير الأسبوعي على تيليغرام")
    print("=" * 60)

    if not REPORT_TXT.exists():
        print("ℹ️ weekly_performance_report.txt غير موجود — لا يوجد نشر")
        return 0

    text = REPORT_TXT.read_text(encoding="utf-8").strip()
    if not text:
        print("ℹ️ التقرير فارغ — لا يوجد نشر")
        return 0

    ok = post_message(text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
