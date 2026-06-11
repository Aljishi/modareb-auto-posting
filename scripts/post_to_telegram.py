#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""نشر إشارة راصد إلى تيليغرام مع عرض إضافات Starter Plus."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VALIDATED_FILE = DATA_DIR / "validated_signals.json"
SIGNALS_FILE = DATA_DIR / "signals.json"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace("%", "").replace(",", "").strip()
        return float(x)
    except Exception:
        return default


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def get_signals() -> List[Dict[str, Any]]:
    data = load_json(VALIDATED_FILE, {})
    signals = data.get("signals", []) if isinstance(data, dict) else []
    if signals:
        return signals
    data = load_json(SIGNALS_FILE, {})
    return data.get("signals", []) if isinstance(data, dict) else []


def ar_time() -> str:
    return datetime.now().strftime("%Y-%m-%d | %I:%M %p KSA").replace("AM", "ص").replace("PM", "م")


def ai_status(signal: Dict[str, Any]) -> str:
    reviewed = bool(signal.get("ai_reviewed") or signal.get("ai_available"))
    decision = str(signal.get("ai_decision") or "").upper()
    confidence = int(fnum(signal.get("ai_confidence"), 0))
    if reviewed and decision in {"APPROVE", "APPROVED", "PASS", "YES"}:
        return f"إشارة معتمدة بعد اجتياز فلاتر راصد الآلية ومراجعة الذكاء الاصطناعي. ثقة AI: {confidence}%"
    if reviewed and decision:
        return f"إشارة اجتازت فلاتر راصد، مع نتيجة مراجعة AI: {decision}."
    return "إشارة معتمدة بعد اجتياز فلاتر راصد الآلية. لم تُستخدم مراجعة الذكاء الاصطناعي في هذا التشغيل."


def format_signal(signal: Dict[str, Any]) -> str:
    symbol = signal.get("stock_symbol") or signal.get("symbol") or ""
    name = signal.get("stock_name") or signal.get("name") or symbol
    tier = str(signal.get("tier") or "Premium").upper()
    tier_emoji = signal.get("tier_emoji") or "⭐"

    entry = fnum(signal.get("entry_point") or signal.get("entry"))
    target1 = fnum(signal.get("target1"))
    target2 = fnum(signal.get("target2"))
    stop = fnum(signal.get("stop_loss"))
    tp1 = fnum(signal.get("target1_percent") or signal.get("tp1_pct"))
    tp2 = fnum(signal.get("target2_percent") or signal.get("tp2_pct"))
    sl = abs(fnum(signal.get("stop_loss_percent") or signal.get("sl_pct")))
    rased = fnum(signal.get("rased_score") or signal.get("score"))
    confidence = int(round(fnum(signal.get("ai_confidence") or signal.get("rased_score") or signal.get("score"))))
    risk = signal.get("risk_level_ar") or signal.get("risk_level") or "متوسط"
    risk_emoji = signal.get("risk_emoji") or "🟡"
    days = int(fnum(signal.get("expected_days_to_target2"), 3))

    rsi = fnum(signal.get("rsi"))
    vol = fnum(signal.get("volume_ratio"))
    rr = fnum(signal.get("rr") or signal.get("rr_ratio"))
    atr = fnum(signal.get("atr_pct"))
    fundamental = signal.get("fundamental_grade") or "غير متوفر"
    fundamental_bonus = int(fnum(signal.get("fundamental_bonus")))
    sector_grade = signal.get("sector_strength_grade") or "غير متوفر"
    sector_bonus = int(fnum(signal.get("sector_strength_bonus")))
    growth_bonus = int(fnum(signal.get("growth_bonus")))
    dividend_bonus = int(fnum(signal.get("dividend_bonus")))
    backtest_grade = signal.get("backtest_grade") or "غير متوفر"
    backtest_win = fnum(signal.get("backtest_win_rate"))
    backtest_trades = int(fnum(signal.get("backtest_trades")))

    return f"""{tier_emoji} RASED {tier} SIGNAL

📈 {name} ({symbol})

💰 نقطة الدخول
{entry:.2f} ريال

🎯 الهدف الأول
{target1:.2f} ريال  (+{tp1:.2f}%)

🎯 الهدف الثاني
{target2:.2f} ريال  (+{tp2:.2f}%)

🛑 وقف الخسارة
{stop:.2f} ريال  (-{sl:.2f}%)

━━━━━━━━━━━━━━

⭐ RASED SCORE™
{rased:.1f} / 100

🤖 الثقة
{confidence}%

{risk_emoji} مستوى المخاطرة
{risk}

⏳ مدة الصفقة المتوقعة
{days} أيام أو أقل

━━━━━━━━━━━━━━

📊 مؤشرات راصد
RSI: {rsi:.1f} | Volume: {vol:.2f}x | R:R: {rr:.2f}
ATR: {atr:.2f}% | Fundamental: {fundamental} ({fundamental_bonus:+d})

🏭 القطاع
{sector_grade} ({sector_bonus:+d})

📈 النمو والتوزيعات
Growth: {growth_bonus:+d} | Dividend: {dividend_bonus:+d}

🧪 Backtest
{backtest_grade} | نجاح: {backtest_win:.1f}% | عينة: {backtest_trades}

━━━━━━━━━━━━━━

🏆 الحالة
{ai_status(signal)}

📌 ملخص سريع
{signal.get('signal_reason') or 'اجتازت فلاتر راصد الآلية.'}

💡 {signal.get('key_insight') or 'الإشارة مرشحة لمضاربة قصيرة المدى بشرط الالتزام بوقف الخسارة.'}

⏰ {ar_time()}

⚠️ محتوى تعليمي آلي وليس توصية استثمارية أو ضماناً لتحقيق الأهداف. الالتزام بوقف الخسارة وإدارة رأس المال مسؤولية المتداول.

#راصد #تاسي #السوق_السعودي"""


def send_message(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID غير موجود")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Telegram {r.status_code}: {r.text[:300]}")


def main() -> int:
    signals = get_signals()
    if not signals:
        print("ℹ️ No signal to post")
        return 0
    signal = signals[0]
    text = format_signal(signal)
    send_message(text)
    print("✅ Posted signal to Telegram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
