#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
يرسل لوحة جودة راصد اليومية إلى Telegram كنص مختصر.
لا ينفذ أي طلب إلى مزود بيانات السوق.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent.parent
MESSAGE_FILE = ROOT / "data" / "quality_dashboard_message.txt"

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def main() -> int:
    if not TOKEN or not CHAT_ID:
        print("❌ TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID غير موجود")
        return 1

    if not MESSAGE_FILE.exists():
        print("❌ quality_dashboard_message.txt غير موجود")
        return 1

    text = MESSAGE_FILE.read_text(encoding="utf-8").strip()
    if not text:
        print("❌ رسالة لوحة الجودة فارغة")
        return 1

    response = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": "true",
        },
        timeout=30,
    )

    if response.status_code >= 400:
        print(f"❌ Telegram {response.status_code}: {response.text[:500]}")
        return 1

    payload = response.json()
    if not payload.get("ok"):
        print(f"❌ Telegram response: {payload}")
        return 1

    print("✅ Daily quality dashboard posted to Telegram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
