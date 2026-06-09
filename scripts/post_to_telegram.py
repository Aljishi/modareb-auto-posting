#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""راصد — نشر إشارة Premium/Gold/Platinum على تيليغرام + حفظها للمتابعة.

التحديثات:
- لا يعرض ثقة OpenAI = 0% عند عدم توفر OpenAI.
- يستخدم RASED Score كقيمة ثقة تشغيلية إذا كانت مراجعة OpenAI غير متاحة.
- يوضح في الحالة هل تمت مراجعة الذكاء الاصطناعي أم لا.
- يعرض مؤشرات RSI / Volume / R:R / ATR / Fundamental.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IMAGE_FILE = Path("output.png")


def escape(text: Any) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace("%", "").replace(",", "").strip()
        return float(x)
    except Exception:
        return default


def percent_from_signal(signal: Dict[str, Any], rased_score: float) -> int:
    """يرجع الثقة المعروضة للمشترك.

    إذا OpenAI متاح ومعتمد نستخدم ai_confidence.
    إذا OpenAI غير متاح أو skipped نستخدم RASED Score حتى لا تظهر 0%.
    """
    ai_available = signal.get("ai_available") is True
    ai_decision = signal.get("ai_decision")
    ai_conf = fnum(signal.get("ai_confidence"), 0)

    if ai_available and ai_decision == "APPROVE" and ai_conf > 0:
        return int(round(ai_conf))

    confidence = signal.get("confidence")
    conf_num = fnum(confidence, 0)
    if conf_num > 0:
        return int(round(conf_num))

    return int(round(rased_score))


def load_signal() -> Optional[Dict[str, Any]]:
    for fname in ("validated_signals.json", "signals.json"):
        f = DATA_DIR / fname
        if f.exists():
            raw = json.loads(f.read_text(encoding="utf-8"))
            sigs = raw.get("validated_signals", raw.get("signals", []))
            if sigs:
                return sigs[0]
    return None


def fmt_price(v: Any) -> str:
    return f"{fnum(v):.2f}"


def fmt_days(v: Any) -> str:
    try:
        n = int(float(v))
        return str(max(1, n))
    except Exception:
        return "1–7"


def build_caption(s: Dict[str, Any]) -> str:
    name = escape(s.get("stock_name", s.get("name", "")))
    sym = escape(s.get("stock_symbol", s.get("symbol", "")))
    tier = escape(s.get("tier", "Premium"))
    tier_emoji = s.get("tier_emoji", "⭐")
    rased_score = fnum(s.get("rased_score"), fnum(s.get("score"), 0))
    confidence = percent_from_signal(s, rased_score)

    risk = escape(s.get("risk_level", s.get("risk_level_ar", "متوسط")))
    risk_emoji = s.get("risk_emoji", "🟡")

    ai_reviewed = s.get("ai_available") is True and s.get("ai_decision") == "APPROVE"
    if ai_reviewed:
        review_line = "إشارة معتمدة بعد اجتياز فلاتر راصد الآلية ومراجعة الذكاء الاصطناعي."
        summary = escape(s.get("ai_arabic_summary") or s.get("signal_reason") or "إشارة مرشحة بعد مراجعة آلية وفنية.")
        note = escape(s.get("ai_telegram_note") or s.get("key_insight") or "الالتزام بوقف الخسارة وإدارة رأس المال شرط أساسي.")
    else:
        review_line = "إشارة معتمدة بعد اجتياز فلاتر راصد الآلية. لم تُستخدم مراجعة الذكاء الاصطناعي في هذا التشغيل."
        summary = escape(s.get("signal_reason") or "اجتازت الإشارة فلاتر راصد الخاصة بالزخم والسيولة وإدارة المخاطر.")
        note = escape(s.get("key_insight") or "الإشارة مرشحة لمضاربة قصيرة المدى بشرط الالتزام بوقف الخسارة.")

    expected_days = fmt_days(s.get("ai_expected_holding_days") if ai_reviewed else s.get("expected_days_to_target2"))

    rsi = fnum(s.get("rsi"))
    volume_ratio = fnum(s.get("volume_ratio"))
    rr = fnum(s.get("rr", s.get("rr_ratio")))
    atr_pct = fnum(s.get("atr_pct"))
    fundamental_grade = escape(s.get("fundamental_grade", "غير متوفر"))
    fundamental_bonus = int(fnum(s.get("fundamental_bonus"), 0))
    fundamental_text = f"{fundamental_grade} ({fundamental_bonus:+d})" if fundamental_grade else "غير متوفر"

    now = datetime.now().strftime("%Y-%m-%d | %I:%M %p KSA").replace("AM", "ص").replace("PM", "م")

    return (
        f"{tier_emoji} <b>RASED {tier.upper()} SIGNAL</b>\n\n"
        f"📈 <b>{name} ({sym})</b>\n\n"
        f"💰 <b>نقطة الدخول</b>\n<code>{fmt_price(s.get('entry_point', s.get('entry')))}</code> ريال\n\n"
        f"🎯 <b>الهدف الأول</b>\n<code>{fmt_price(s.get('target1'))}</code> ريال  <b>(+{fnum(s.get('target1_percent', s.get('tp1_pct'))):.2f}%)</b>\n\n"
        f"🎯 <b>الهدف الثاني</b>\n<code>{fmt_price(s.get('target2'))}</code> ريال  <b>(+{fnum(s.get('target2_percent', s.get('tp2_pct'))):.2f}%)</b>\n\n"
        f"🛑 <b>وقف الخسارة</b>\n<code>{fmt_price(s.get('stop_loss'))}</code> ريال  <b>(-{fnum(s.get('stop_loss_percent')):.2f}%)</b>\n\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"⭐ <b>RASED SCORE™</b>\n<b>{rased_score:.1f} / 100</b>\n\n"
        f"🤖 <b>الثقة</b>\n<b>{confidence}%</b>\n\n"
        f"{risk_emoji} <b>مستوى المخاطرة</b>\n<b>{risk}</b>\n\n"
        f"⏳ <b>مدة الصفقة المتوقعة</b>\n<b>{expected_days} أيام أو أقل</b>\n\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📊 <b>مؤشرات راصد</b>\n"
        f"RSI: <b>{rsi:.1f}</b> | Volume: <b>{volume_ratio:.2f}x</b> | R:R: <b>{rr:.2f}</b>\n"
        f"ATR: <b>{atr_pct:.2f}%</b> | Fundamental: <b>{escape(fundamental_text)}</b>\n\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🏆 <b>الحالة</b>\n{review_line}\n\n"
        f"📌 <b>ملخص سريع</b>\n{summary}\n\n"
        f"💡 {note}\n\n"
        f"⏰ {escape(now)}\n\n"
        f"⚠️ <i>محتوى تعليمي آلي وليس توصية استثمارية أو ضماناً لتحقيق الأهداف. الالتزام بوقف الخسارة وإدارة رأس المال مسؤولية المتداول.</i>\n\n"
        f"#راصد #تاسي #السوق_السعودي"
    )


def save_open_signal(signal: Dict[str, Any]) -> None:
    open_file = DATA_DIR / "open_signals.json"
    signals = []
    if open_file.exists():
        try:
            signals = json.loads(open_file.read_text(encoding="utf-8"))
        except Exception:
            signals = []

    today = datetime.now().strftime("%Y-%m-%d")
    sym = signal.get("stock_symbol", signal.get("symbol", ""))
    already = any(
        item.get("date") == today
        and item.get("signal", {}).get("stock_symbol", item.get("signal", {}).get("symbol", "")) == sym
        for item in signals
    )
    if already:
        return

    signals.append({
        "signal": signal,
        "date": today,
        "posted_at": datetime.now().isoformat(timespec="seconds"),
        "target1_hit": False,
        "target1_hit_at": None,
        "target2_hit": False,
        "target2_hit_at": None,
        "stop_hit": False,
        "stop_hit_at": None,
        "max_holding_days": int(signal.get("max_holding_days", 7)),
        "expires_at_days": 7,
        "status": "open",
    })
    open_file.write_text(json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8")
    print("💾 الإشارة محفوظة في open_signals.json للمتابعة")


def send_photo(caption: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID غير موجود")
        return False
    if not IMAGE_FILE.exists():
        print("❌ output.png غير موجود")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with IMAGE_FILE.open("rb") as photo:
        r = requests.post(
            url,
            data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"photo": photo},
            timeout=30,
        )
    if r.status_code != 200:
        print(f"❌ Telegram error {r.status_code}: {r.text}")
        return False
    print("✅ تم النشر في تيليغرام")
    return True


def main() -> int:
    signal = load_signal()
    if not signal:
        print("❌ لا توجد إشارة صالحة للنشر")
        return 1
    caption = build_caption(signal)
    if not send_photo(caption):
        return 1
    save_open_signal(signal)
    (DATA_DIR / "last_post_date.txt").write_text(datetime.now().strftime("%Y-%m-%d"), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
