#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Post golden signal or confirmation/cancellation to Telegram."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GOLDEN_FILE = DATA_DIR / "golden_signals.json"
IMAGE_FILE = Path("golden_output.png")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def load_signal() -> Dict[str, Any]:
    if not GOLDEN_FILE.exists():
        return {}
    data = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data[0] if data else {}
    signals = data.get("golden_signals") or data.get("signals") or []
    return signals[0] if signals else data


def fmt(x: Any) -> str:
    return "-" if x is None or x == "" else str(x)


def build_message(s: Dict[str, Any]) -> str:
    status = str(s.get("status", "PREMARKET")).upper()
    name = s.get("stock_name") or s.get("name") or s.get("symbol")
    symbol = s.get("symbol") or s.get("stock_symbol") or ""
    now = datetime.now().strftime("%Y-%m-%d | %I:%M %p KSA")

    if status == "CONFIRMED":
        header = "🌟 تأكيد الإشارة الذهبية بعد الافتتاح"
        state = s.get("confirmation_reason", "الإشارة ما زالت صالحة بعد افتتاح السوق.")
    elif status == "CANCELLED":
        header = "⚠️ تحديث الإشارة الذهبية"
        state = s.get("confirmation_reason", "تم إلغاء الإشارة الذهبية لعدم اكتمال شروط التأكيد.")
    else:
        header = "👑 الإشارة الذهبية قبل الافتتاح"
        state = "سيتم تأكيد الإشارة مرة أخرى الساعة 10:30 بعد افتتاح السوق."

    return f"""{header}

📈 {name} ({symbol})

💰 الدخول: {fmt(s.get('entry') or s.get('entry_point'))} ريال
🎯 الهدف الأول: {fmt(s.get('target1'))}  (+{fmt(s.get('target1_percent') or s.get('tp1_pct'))}%)
🎯 الهدف الثاني: {fmt(s.get('target2'))}  (+{fmt(s.get('target2_percent') or s.get('tp2_pct'))}%)
🛑 وقف الخسارة: {fmt(s.get('stop_loss'))}

━━━━━━━━━━━━━━

⭐ RASED SCORE™
{fmt(s.get('rased_score') or s.get('score'))} / 100

📊 مؤشرات راصد
RSI: {fmt(s.get('rsi'))} | Volume: {fmt(s.get('volume_ratio'))}x | R:R: {fmt(s.get('rr') or s.get('rr_ratio'))}
ATR: {fmt(s.get('atr_pct'))}%

🏆 الحالة
{state}

💡 {fmt(s.get('key_insight'))}

⏰ {now}

⚠️ محتوى تعليمي آلي وليس توصية استثمارية أو ضماناً لتحقيق الأهداف.

#راصد #تاسي #السوق_السعودي #إشارة_ذهبية""".strip()


def send_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Telegram sendMessage failed: {r.text[:250]}")


def send_photo(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with IMAGE_FILE.open("rb") as f:
        r = requests.post(url, data={"chat_id": CHAT_ID, "caption": text}, files={"photo": f}, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Telegram sendPhoto failed: {r.text[:250]}")


def main() -> int:
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing")
        return 0

    signal = load_signal()
    if not signal:
        print("ℹ️ No golden signal to post")
        return 0

    message = build_message(signal)
    if IMAGE_FILE.exists():
        send_photo(message)
    else:
        send_message(message)

    print("✅ Golden signal posted to Telegram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
