#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

REPORT_FILE = DATA / "no_signal_report.json"
QUALITY_FILE = DATA / "data_quality.json"

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def read_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def build_message():
    report = read_json(REPORT_FILE, {})
    quality = read_json(QUALITY_FILE, {})

    categories = report.get("categories", {})
    total_rejected = report.get("total_rejected", 0)
    total_generated = report.get("total_generated", 0)
    total_validated = report.get("total_validated", 0)

    lines = [
        "📊 <b>راصد — ملخص فحص السوق</b>",
        "",
        f"🕒 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"📡 جودة البيانات: <b>{quality.get('score', 0)}%</b>",
        f"🔎 الإشارات المولدة: <b>{total_generated}</b>",
        f"✅ الإشارات المجازة للنشر: <b>{total_validated}</b>",
        "",
    ]

    if total_validated > 0:
        lines.append("✅ توجد إشارة مجازة، لا حاجة لنشر تقرير عدم وجود فرص.")
        return "\n".join(lines)

    lines += [
        "ℹ️ <b>لا توجد إشارة مجازة حالياً.</b>",
        "راصد فضّل عدم النشر لأن شروط الجودة لم تكتمل.",
        "",
        "أهم أسباب الاستبعاد:",
    ]

    if categories:
        for k, v in list(categories.items())[:6]:
            lines.append(f"• {k}: <b>{v}</b>")
    else:
        lines.append("• لم يتم تسجيل أسباب كافية من المحرك.")

    lines += [
        "",
        f"📌 إجمالي الأسهم/الحالات المستبعدة: <b>{total_rejected}</b>",
        "",
        "⚠️ محتوى تعليمي آلي وليس توصية استثمارية.",
    ]

    return "\n".join(lines)


def main():
    if not TOKEN or not CHAT_ID:
        print("⚠️ Telegram secrets missing — skip no-signal report")
        return 0

    msg = build_message()

    if "توجد إشارة مجازة" in msg:
        print("ℹ️ Valid signal exists — skip no-signal report")
        return 0

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )

    if r.status_code >= 400:
        print(r.text)
        return 1

    print("✅ No-signal report posted to Telegram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())