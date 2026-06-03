#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
post_golden_signal.py
ينشر الإشارة الذهبية على تيليغرام مع الصورة المُولَّدة.
FIX: يقرأ الآن الحقول المباشرة (stock_name, sector, current_price, ...)
     بدلاً من التنقيب في analysis.indicators الذي كان يسبب الفراغات
"""

import os, sys, json, requests
from pathlib import Path

BOT_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID      = os.environ.get("TELEGRAM_CHAT_ID")
DATA_DIR     = Path(__file__).parent.parent / "data"
GOLDEN_IMAGE = Path("golden_output.png")


def escape(text):
    if not text: return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pct(val, base):
    if not base or base == 0: return "0.0"
    return f"{((val - base) / base * 100):.1f}"


def build_caption(signal):
    """
    FIX: يقرأ الحقول المباشرة من بنية الإشارة الجديدة
    يدعم أيضاً البنية القديمة {symbol, analysis: {indicators}} للتوافق
    """
    # ─ قراءة الحقول المباشرة أولاً (البنية الجديدة) ─────────────────────
    sym    = escape(signal.get("stock_symbol",  signal.get("symbol", "")))
    name   = escape(signal.get("stock_name",    signal.get("name",   "")))
    sector = escape(signal.get("sector",        ""))
    score  = signal.get("score",  0)
    price  = signal.get("current_price",  0)
    entry  = signal.get("entry_point",    signal.get("entry", 0))
    t1     = signal.get("target1",  0)
    t2     = signal.get("target2",  0)
    sl     = signal.get("stop_loss", 0)
    rsi    = signal.get("rsi",  50)
    vol    = signal.get("volume_ratio", 1.0)

    # ─ إذا كانت الحقول غير موجودة مباشرة → قراءة من analysis (بنية قديمة) ─
    if not score:
        analysis = signal.get("analysis", {})
        score    = analysis.get("score", 0)
    if not rsi or not vol:
        inds = signal.get("analysis", {}).get("indicators", {})
        rsi  = rsi  or inds.get("RSI", 50)
        vol  = vol  or inds.get("volume_ratio", 1.0)

    # ─ النسب المئوية ─────────────────────────────────────────────────────
    t1p = signal.get("target1_percent",  pct(t1, entry) if entry else pct(t1, price))
    t2p = signal.get("target2_percent",  pct(t2, entry) if entry else pct(t2, price))
    slp = signal.get("stop_loss_percent", pct(entry, sl) if entry else pct(price, sl))

    return (
        f"🌟 <b>إشارة ذهبية — راصد</b> 🌟\n\n"
        f"📊 <b>{name} ({sym})</b>\n"
        f"🏢 القطاع: {sector}\n\n"
        f"🏆 النتيجة: <b>{score}/100</b>\n\n"
        f"💰 السعر الحالي: <code>{float(price):.2f}</code> ريال\n"
        f"🎯 نقطة الدخول: <code>{float(entry):.2f}</code> ريال\n\n"
        f"📈 الأهداف:\n"
        f"• الهدف الأول:  <code>{float(t1):.2f}</code> (+{t1p}%) 🟢\n"
        f"• الهدف الثاني: <code>{float(t2):.2f}</code> (+{t2p}%) 🟢\n\n"
        f"🛑 وقف الخسارة: <code>{float(sl):.2f}</code> (-{slp}%) 🔴\n\n"
        f"📊 المؤشرات:\n"
        f"RSI: <code>{float(rsi):.1f}</code>  |  الحجم: <code>{float(vol):.1f}x</code>\n\n"
        f"⚠️ <i>محتوى تعليمي — ليس توصية استثمارية</i>"
    )


def main():
    print("=" * 60)
    print("🌟 راصد — نشر الإشارة الذهبية")
    print("=" * 60)

    if not BOT_TOKEN or not CHAT_ID:
        print("❌ TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID غير موجود")
        sys.exit(1)

    golden_file = DATA_DIR / "golden_signals.json"
    if not golden_file.exists():
        print("ℹ️ لا توجد إشارات ذهبية")
        sys.exit(0)

    signals = json.load(open(golden_file, encoding="utf-8"))
    if not signals:
        print("ℹ️ القائمة فارغة")
        sys.exit(0)

    signal  = signals[0]
    caption = build_caption(signal)

    # DEBUG: طباعة الحقول للتأكد
    print(f"📌 السهم: {signal.get('stock_name','')} ({signal.get('stock_symbol','')})")
    print(f"📌 القطاع: {signal.get('sector','')}")
    print(f"📌 السعر: {signal.get('current_price', 0)}")
    print(f"📌 النتيجة: {signal.get('score', 0)}")

    if GOLDEN_IMAGE.exists():
        url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        with open(GOLDEN_IMAGE, "rb") as photo:
            resp = requests.post(
                url,
                data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                files={"photo": photo},
                timeout=30,
            )
    else:
        print("⚠️ golden_output.png غير موجودة — إرسال نص فقط")
        url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": caption, "parse_mode": "HTML"},
            timeout=30,
        )

    result = resp.json()
    if result.get("ok"):
        print("✅ تم نشر الإشارة الذهبية!")
        sys.exit(0)
    else:
        print(f"❌ فشل: {result.get('description', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
