#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Post initial signal image + caption — then save to open_signals.json"""

import os, sys, json, requests
from datetime import datetime
from pathlib import Path

BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")
DATA_DIR   = Path(__file__).parent.parent / "data"
IMAGE_FILE = Path("output.png")


def escape(text):
    return str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


def load_signal():
    for fname in ("validated_signals.json", "signals.json"):
        f = DATA_DIR / fname
        if f.exists():
            raw  = json.load(open(f, encoding="utf-8"))
            sigs = raw.get("validated_signals", raw.get("signals", []))
            if sigs:
                return sigs[0]
    return None


def build_caption(s):
    name    = escape(s.get("stock_name",  s.get("name",   "")))
    sym     = escape(s.get("stock_symbol", s.get("symbol", "")))
    sect    = escape(s.get("sector", ""))
    conf    = escape(s.get("confidence", "جيدة"))
    emoji   = s.get("emoji", "🟡")
    price   = s.get("current_price", 0)
    entry   = s.get("entry_point",   s.get("entry", 0))
    t1      = s.get("target1",  0);  t1p = s.get("target1_percent",  5)
    t2      = s.get("target2",  0);  t2p = s.get("target2_percent", 10)
    sl      = s.get("stop_loss", 0); slp = s.get("stop_loss_percent", 3)
    rsi     = s.get("rsi",  0)
    vol     = s.get("volume_ratio", 0)
    score   = s.get("score", 0)
    risk    = escape(s.get("risk_level", ""))
    insight = escape(s.get("key_insight", ""))
    summary = escape(s.get("company_summary", ""))
    reason  = escape(s.get("signal_reason", ""))
    is_claude = s.get("claude_analyzed", False)

    # ── الكابشن الأساسي ──────────────────────────────────
    cap = (
        f"📊 <b>{name} ({sym})</b>\n"
    )
    if sect:
        cap += f"🏢 {sect}\n"
    if summary:
        cap += f"ℹ️ <i>{summary}</i>\n"
    cap += "\n"

    cap += (
        f"🎯 الثقة: <b>{conf}</b> {emoji}\n"
    )
    if risk:
        risk_emoji = {"منخفض":"🟢","متوسط":"🟡","مرتفع":"🔴"}.get(risk,"⚪")
        cap += f"⚠️ المخاطرة: {risk} {risk_emoji}\n"
    cap += "\n"

    cap += (
        f"💰 السعر الحالي: <code>{price:.2f}</code> ريال\n"
        f"🎯 نقطة الدخول: <code>{entry:.2f}</code> ريال\n\n"
        f"📈 الأهداف:\n"
        f"• الهدف الأول:  <code>{t1:.2f}</code> (+{t1p:.1f}%) 🟢\n"
        f"• الهدف الثاني: <code>{t2:.2f}</code> (+{t2p:.1f}%) 🟢\n\n"
        f"🛑 وقف الخسارة: <code>{sl:.2f}</code> (-{slp:.1f}%) 🔴\n\n"
        f"📊 المؤشرات:\n"
        f"RSI: <code>{rsi:.1f}</code>  |  "
        f"الحجم: <code>{vol:.1f}x</code>  |  "
        f"Score: <b>{score}/100</b>\n"
    )

    # ── تحليل كلود (إذا كان متاحاً) ──────────────────────
    if is_claude:
        cap += "\n🤖 <b>تحليل الذكاء الاصطناعي:</b>\n"
        if reason:
            cap += f"📌 {reason}\n"
        if insight:
            cap += f"💡 {insight}\n"

    cap += "\n⚠️ <i>محتوى تعليمي — ليس توصية استثمارية</i>"
    return cap


def save_open_signal(signal):
    open_file = DATA_DIR / "open_signals.json"
    signals   = []
    if open_file.exists():
        try:
            signals = json.load(open(open_file, encoding="utf-8"))
        except Exception:
            signals = []

    today = datetime.now().strftime("%Y-%m-%d")
    sym   = signal.get("stock_symbol", signal.get("symbol", ""))
    already = any(
        s.get("date") == today and
        s.get("signal", {}).get("stock_symbol",
            s.get("signal", {}).get("symbol", "")) == sym
        for s in signals
    )
    if already:
        return

    signals.append({
        "signal":         signal,
        "date":           today,
        "posted_at":      datetime.now().isoformat(),
        "target1_hit":    False,
        "target1_hit_at": None,
        "target2_hit":    False,
        "target2_hit_at": None,
        "stop_hit":       False,
        "stop_hit_at":    None,
        "status":         "open",
    })

    with open(open_file, "w", encoding="utf-8") as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)
    print("💾 الإشارة محفوظة في open_signals.json للمتابعة")


def send_photo(caption):
    if not BOT_TOKEN: print("❌ TELEGRAM_BOT_TOKEN غير موجود"); return False
    if not CHAT_ID:   print("❌ TELEGRAM_CHAT_ID غير موجود");   return False
    if not IMAGE_FILE.exists():
        print(f"❌ الصورة غير موجودة: {IMAGE_FILE}"); return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(IMAGE_FILE, "rb") as photo:
        resp = requests.post(
            url,
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"photo": photo},
            timeout=30,
        )
    result = resp.json()
    if result.get("ok"):
        print("✅ تم النشر على تيليغرام")
        (DATA_DIR / "last_post_date.txt").write_text(
            datetime.now().strftime("%Y-%m-%d"))
        return True
    print(f"❌ فشل: {result.get('description','unknown')}")
    return False


def main():
    print("="*60)
    print("📤 راصد — الإشارة الأولى على تيليغرام")
    print("="*60)

    sig = load_signal()
    if not sig:
        print("❌ لا توجد إشارات"); sys.exit(1)

    caption = build_caption(sig)
    success = send_photo(caption)

    if success:
        save_open_signal(sig)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
