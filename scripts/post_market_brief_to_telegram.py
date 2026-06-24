#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — نشر التقرير اليومي للسوق على تيليجرام.

يعتمد على:
- data/market_brief.txt
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import os
from pathlib import Path
from typing import List

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BRIEF_TXT = DATA_DIR / "market_brief.txt"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TIMEOUT = int(os.getenv("TELEGRAM_TIMEOUT", "20"))


def chunk_text(text: str, limit: int = 3900) -> List[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for line in text.splitlines():
        extra = len(line) + 1
        if current and current_len + extra > limit:
            chunks.append("\n".join(current).strip())
            current = [line]
            current_len = extra
        else:
            current.append(line)
            current_len += extra
    if current:
        chunks.append("\n".join(current).strip())
    return chunks


def send_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID غير موجود")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }
    response = requests.post(url, data=payload, timeout=TIMEOUT)
    if response.status_code >= 400:
        raise RuntimeError(f"Telegram {response.status_code}: {response.text[:300]}")


def main() -> int:
    if not BRIEF_TXT.exists():
        print("ℹ️ market_brief.txt غير موجود — لا يوجد تقرير للنشر")
        return 0

    text = BRIEF_TXT.read_text(encoding="utf-8").strip()
    if not text:
        print("ℹ️ market_brief.txt فارغ — لا يوجد تقرير للنشر")
        return 0

    chunks = chunk_text(text)
    for idx, chunk in enumerate(chunks, start=1):
        prefix = "" if len(chunks) == 1 else f"جزء {idx}/{len(chunks)}\n\n"
        send_message(prefix + chunk)
    print(f"✅ تم نشر تقرير السوق اليومي على تيليجرام ({len(chunks)} رسالة)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
