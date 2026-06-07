#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_targets.py
يراقب الإشارات المفتوحة كل ساعة.
يرسل إشعاراً على تيليغرام عند تحقق الهدف الأول أو الثاني أو الوقف.
"""

import os, sys, json, requests
from datetime import datetime, timedelta
from pathlib import Path

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")
DATA_DIR  = Path(__file__).parent.parent / "data"
EXPIRY_DAYS = 10


def escape(text):
    return str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


def send_text(msg: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ بيانات تيليغرام غير موجودة"); return False
    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=30
        )
        return resp.json().get("ok", False)
    except Exception as e:
        print(f"❌ خطأ في الإرسال: {e}"); return False


def get_current_prices() -> dict:
    """يجلب الأسعار الحالية من daily.json (يُحدَّث كل 5 دقائق)."""
    daily = DATA_DIR / "daily.json"
    if not daily.exists():
        return {}
    try:
        data = json.load(open(daily, encoding="utf-8"))
        return {
            s.get("symbol", ""): float(s.get("current_price", 0))
            for s in data.get("stocks", [])
            if s.get("symbol")
        }
    except Exception as e:
        print(f"⚠️ خطأ في قراءة daily.json: {e}"); return {}


def is_expired(entry: dict) -> bool:
    try:
        posted = datetime.fromisoformat(entry.get("posted_at", ""))
        return (datetime.now() - posted).days >= EXPIRY_DAYS
    except Exception:
        return False


# ── رسائل الإشعارات (تستخدم النسب الحقيقية من الإشارة) ──────

def msg_target1(sig: dict) -> str:
    name  = escape(sig.get("stock_name",  sig.get("name",   "")))
    sym   = escape(sig.get("stock_symbol", sig.get("symbol", "")))
    t1    = sig.get("target1", 0)
    # FIX: استخدم النسب الحقيقية المحسوبة، ليس ثوابت مُضمَّنة
    t1p   = sig.get("target1_percent", 5)
    entry = sig.get("entry_point", sig.get("entry", 0))
    t2    = sig.get("target2", 0)
    t2p   = sig.get("target2_percent", 10)
    sl    = sig.get("stop_loss", 0)

    return (
        f"🎯 <b>تحقق الهدف الأول!</b>\n\n"
        f"📌 {name} ({sym})\n\n"
        f"✅ الهدف الأول: <code>{t1:.2f}</code> ريال (+{t1p}%) 🟢\n\n"
        f"💡 <b>نصيحة:</b> يمكنك تحريك وقف الخسارة\n"
        f"   إلى نقطة الدخول <code>{entry:.2f}</code>\n"
        f"   لتأمين صفقة بلا خسارة\n\n"
        f"🎯 الهدف الثاني لا يزال قائماً:\n"
        f"   <code>{t2:.2f}</code> ريال (+{t2p}%)\n"
        f"🛑 وقف الخسارة الأصلي: <code>{sl:.2f}</code>\n\n"
        f"⚠️ <i>محتوى تعليمي — ليس توصية استثمارية</i>"
    )


def msg_target2(sig: dict) -> str:
    name = escape(sig.get("stock_name",  sig.get("name",   "")))
    sym  = escape(sig.get("stock_symbol", sig.get("symbol", "")))
    t2   = sig.get("target2", 0)
    t2p  = sig.get("target2_percent", 10)

    return (
        f"🏆 <b>تحقق الهدف الثاني!</b>\n\n"
        f"📌 {name} ({sym})\n\n"
        f"✅ الهدف الثاني: <code>{t2:.2f}</code> ريال (+{t2p}%) 🟢\n\n"
        f"🎉 <b>إشارة ناجحة بالكامل!</b>\n\n"
        f"شكراً لمتابعتكم راصد 👁️\n\n"
        f"⚠️ <i>محتوى تعليمي — ليس توصية استثمارية</i>"
    )


def msg_stop_hit(sig: dict, current_price: float) -> str:
    name = escape(sig.get("stock_name",  sig.get("name",   "")))
    sym  = escape(sig.get("stock_symbol", sig.get("symbol", "")))
    sl   = sig.get("stop_loss", 0)
    slp  = sig.get("stop_loss_percent", 3)

    return (
        f"🛑 <b>تفعّل وقف الخسارة</b>\n\n"
        f"📌 {name} ({sym})\n\n"
        f"❌ وقف الخسارة: <code>{sl:.2f}</code> ريال (-{slp}%) 🔴\n"
        f"💹 السعر الحالي: <code>{current_price:.2f}</code>\n\n"
        f"📌 الالتزام بوقف الخسارة ضرورة لحماية رأس المال\n\n"
        f"⚠️ <i>محتوى تعليمي — ليس توصية استثمارية</i>"
    )


def msg_expired(sig: dict) -> str:
    name = escape(sig.get("stock_name",  sig.get("name",   "")))
    sym  = escape(sig.get("stock_symbol", sig.get("symbol", "")))
    return (
        f"⏰ <b>انتهت صلاحية الإشارة</b>\n\n"
        f"📌 {name} ({sym})\n\n"
        f"مرّ {EXPIRY_DAYS} أيام دون تحقق الأهداف.\n"
        f"يُنصح بمراجعة الوضع الفني للسهم.\n\n"
        f"⚠️ <i>محتوى تعليمي — ليس توصية استثمارية</i>"
    )


# ── المنطق الرئيسي ──────────────────────────────────────────

def check_targets():
    open_file = DATA_DIR / "open_signals.json"
    if not open_file.exists():
        print("ℹ️ لا توجد إشارات مفتوحة"); return 0

    entries = json.load(open(open_file, encoding="utf-8"))
    if not entries:
        print("ℹ️ القائمة فارغة"); return 0

    prices  = get_current_prices()
    changed = False

    for entry in entries:
        status = entry.get("status", "open")
        if status in ("closed", "stop_hit", "expired"):
            continue

        sig  = entry.get("signal", {})
        sym  = sig.get("stock_symbol", sig.get("symbol", ""))
        name = sig.get("stock_name",   sig.get("name",   sym))

        current = prices.get(sym)
        if not current:
            print(f"⚠️ {sym}: لا يوجد سعر حالي"); continue

        t1 = float(sig.get("target1",  0))
        t2 = float(sig.get("target2",  0))
        sl = float(sig.get("stop_loss", 0))

        print(f"\n📊 {name} ({sym})")
        print(f"   السعر: {current:.2f}  |  T1: {t1:.2f}  |  T2: {t2:.2f}  |  SL: {sl:.2f}")

        # وقف الخسارة — أولوية قصوى
        if sl > 0 and current <= sl and not entry.get("stop_hit"):
            print(f"   🛑 وقف الخسارة عند {current:.2f}")
            if send_text(msg_stop_hit(sig, current)):
                entry.update({"stop_hit": True, "stop_hit_at": datetime.now().isoformat(), "status": "stop_hit"})
                changed = True

        # الهدف الثاني (يُفحص قبل الأول لأن السعر قد يتخطاهما دفعة واحدة)
        elif t2 > 0 and current >= t2 and not entry.get("target2_hit"):
            print(f"   🏆 الهدف الثاني تحقق عند {current:.2f}")
            if send_text(msg_target2(sig)):
                entry.update({"target2_hit": True, "target2_hit_at": datetime.now().isoformat(), "status": "closed"})
                if not entry.get("target1_hit"):
                    entry.update({"target1_hit": True, "target1_hit_at": datetime.now().isoformat()})
                changed = True

        # الهدف الأول
        elif t1 > 0 and current >= t1 and not entry.get("target1_hit"):
            print(f"   🎯 الهدف الأول تحقق عند {current:.2f}")
            if send_text(msg_target1(sig)):
                entry.update({"target1_hit": True, "target1_hit_at": datetime.now().isoformat(), "status": "target1_hit"})
                changed = True

        # انتهاء الصلاحية
        elif is_expired(entry):
            print(f"   ⏰ انتهت الصلاحية")
            if send_text(msg_expired(sig)):
                entry["status"] = "expired"
                changed = True

        else:
            print(f"   ⏳ مفتوحة — لم تتحقق أهداف بعد")

    if changed:
        with open(open_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        print("\n💾 open_signals.json مُحدَّث")

    return 0


def main():
    print("="*60)
    print("🔍 راصد — فحص الأهداف")
    print("="*60)
    sys.exit(check_targets())


if __name__ == "__main__":
    main()
