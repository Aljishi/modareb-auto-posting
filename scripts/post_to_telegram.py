#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RASED Telegram Publisher v10
============================

التحسينات:
- الثقة التاريخية المعايرة لها الأولوية على AI confidence.
- لا نعرض ثقة مرتفعة بشكل مضلل عندما تكون العينة التاريخية صغيرة.
- عرض نتيجة الباك تست بوضوح.
- عرض تحذير المطاردة.
- استخدام مستوى المخاطرة المصحح من Quality Gate.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN"
)

CHAT_ID = os.environ.get(
    "TELEGRAM_CHAT_ID"
)

DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
)

IMAGE_FILE = Path(
    "output.png"
)


def escape(
    text: Any,
) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def fnum(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None or value == "":
            return default

        if isinstance(value, str):
            value = (
                value
                .replace("%", "")
                .replace(",", "")
                .strip()
            )

        return float(value)

    except Exception:
        return default


def fint(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(
            fnum(value, default)
        )
    except Exception:
        return default


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(value, maximum),
    )


def load_signal() -> Optional[Dict[str, Any]]:
    for filename in (
        "validated_signals.json",
        "signals.json",
    ):
        path = DATA_DIR / filename

        if not path.exists():
            continue

        try:
            raw = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

        except Exception as exc:
            print(
                f"⚠️ تعذر قراءة {filename}: {exc}"
            )
            continue

        if isinstance(raw, list):
            signals = raw

        elif isinstance(raw, dict):
            signals = raw.get(
                "validated_signals",
                raw.get("signals", []),
            )

        else:
            signals = []

        if (
            isinstance(signals, list)
            and signals
            and isinstance(signals[0], dict)
        ):
            return signals[0]

    return None


def fmt_price(
    value: Any,
) -> str:
    return f"{fnum(value):.2f}"


def fmt_days(
    value: Any,
) -> str:
    try:
        days = int(
            float(value)
        )

        return str(
            max(1, days)
        )

    except Exception:
        return "1–7"


def risk_emoji_for(
    risk: str,
) -> str:
    text = str(risk).strip()

    if "منخفض" in text:
        return "🟢"

    if "متوسط" in text:
        return "🟡"

    if "مرتفع" in text:
        return "🔴"

    return "⚪"


# ============================================================
# Confidence
# ============================================================

def displayed_confidence(
    signal: Dict[str, Any],
    rased_score: float,
) -> int:
    """
    ترتيب الثقة:

    1. calibrated_confidence
    2. confidence إذا كانت معايرة
    3. AI confidence
    4. RASED score

    ثم نطبق سقفاً إذا كانت العينة التاريخية صغيرة.
    """

    calibrated = fnum(
        signal.get(
            "calibrated_confidence"
        ),
        0,
    )

    if calibrated > 0:
        confidence = calibrated

    else:
        confidence_is_calibrated = bool(
            signal.get(
                "confidence_calibrated"
            )
        )

        normal_confidence = fnum(
            signal.get("confidence"),
            0,
        )

        if (
            confidence_is_calibrated
            and normal_confidence > 0
        ):
            confidence = normal_confidence

        else:
            ai_available = (
                signal.get("ai_available")
                is True
            )

            ai_decision = str(
                signal.get(
                    "ai_decision",
                    "",
                )
            ).upper()

            ai_confidence = fnum(
                signal.get(
                    "ai_confidence"
                ),
                0,
            )

            if (
                ai_available
                and ai_decision == "APPROVE"
                and ai_confidence > 0
            ):
                confidence = ai_confidence
            else:
                confidence = rased_score

    # --------------------------------------------------------
    # Historical sample safeguards
    # --------------------------------------------------------

    sample = fint(
        signal.get(
            "confidence_sample_size"
        )
        or signal.get(
            "backtest_trades"
        )
    )

    bt_win = fnum(
        signal.get(
            "backtest_win_rate"
        )
    )

    # لا توجد عينة كافية = لا نعرض 90+ وكأنها حقيقة
    if sample <= 0:
        confidence = min(
            confidence,
            75,
        )

    elif sample <= 3:
        confidence = min(
            confidence,
            80,
        )

    elif sample <= 7:
        if bt_win < 50:
            confidence = min(
                confidence,
                82,
            )
        else:
            confidence = min(
                confidence,
                88,
            )

    confidence = clamp(
        confidence,
        40,
        95,
    )

    return int(
        round(confidence)
    )


def confidence_label(
    signal: Dict[str, Any],
) -> str:
    label = str(
        signal.get(
            "confidence_label",
            "",
        )
    ).strip()

    if label:
        return label

    sample = fint(
        signal.get(
            "confidence_sample_size"
        )
    )

    if sample > 0:
        return (
            f"ثقة معايرة — عينة {sample}"
        )

    return (
        "ثقة تقديرية — عينة تاريخية محدودة"
    )


# ============================================================
# Backtest
# ============================================================

def backtest_text(
    signal: Dict[str, Any],
) -> str:
    trades = fint(
        signal.get(
            "backtest_trades"
        )
    )

    win_rate = fnum(
        signal.get(
            "backtest_win_rate"
        )
    )

    grade = str(
        signal.get(
            "backtest_grade",
            "",
        )
    ).strip()

    if trades <= 0:
        return (
            "غير متوفر | "
            "لا توجد عينة مشابهة كافية"
        )

    grade_text = (
        f"{escape(grade)} | "
        if grade
        else ""
    )

    return (
        f"{grade_text}"
        f"نجاح تاريخي: "
        f"{win_rate:.1f}% | "
        f"الحالات المشابهة: {trades}"
    )


# ============================================================
# Momentum text
# ============================================================

def momentum_text(
    signal: Dict[str, Any],
) -> str:
    rsi = fnum(
        signal.get("rsi")
    )

    if rsi >= 70:
        return (
            f"مرتفع جداً ({rsi:.1f}) "
            "— احتمال مطاردة"
        )

    if rsi >= 68:
        return (
            f"مرتفع ({rsi:.1f}) "
            "— يحتاج تأكيد"
        )

    if 52 <= rsi <= 65:
        return (
            f"صحي ({rsi:.1f})"
        )

    return (
        f"مقبول ({rsi:.1f})"
    )


# ============================================================
# Caption
# ============================================================

def build_caption(
    signal: Dict[str, Any],
) -> str:
    name = escape(
        signal.get(
            "stock_name",
            signal.get(
                "name",
                "",
            ),
        )
    )

    symbol = escape(
        signal.get(
            "stock_symbol",
            signal.get(
                "symbol",
                "",
            ),
        )
    )

    tier = escape(
        signal.get(
            "tier",
            "Standard",
        )
    )

    tier_emoji = str(
        signal.get(
            "tier_emoji",
            "✅",
        )
    )

    rased_score = fnum(
        signal.get(
            "rased_score"
        ),
        fnum(
            signal.get(
                "score"
            ),
            0,
        ),
    )

    confidence = displayed_confidence(
        signal,
        rased_score,
    )

    conf_label = escape(
        confidence_label(signal)
    )

    risk = escape(
        signal.get(
            "risk_level_ar"
        )
        or signal.get(
            "risk_level"
        )
        or "متوسط"
    )

    risk_emoji = (
        signal.get("risk_emoji")
        or risk_emoji_for(risk)
    )

    ai_reviewed = (
        signal.get("ai_available")
        is True
        and str(
            signal.get(
                "ai_decision",
                "",
            )
        ).upper()
        == "APPROVE"
    )

    if ai_reviewed:
        review_line = (
            "اجتازت فلاتر راصد، "
            "بوابة الجودة، "
            "والمراجعة بالذكاء الاصطناعي."
        )

        summary = escape(
            signal.get(
                "ai_arabic_summary"
            )
            or signal.get(
                "signal_reason"
            )
            or (
                "إشارة اجتازت مراحل "
                "التحقق الآلية."
            )
        )

        note = escape(
            signal.get(
                "ai_telegram_note"
            )
            or signal.get(
                "key_insight"
            )
            or (
                "الالتزام بوقف الخسارة "
                "شرط أساسي."
            )
        )

    else:
        review_line = (
            "اجتازت فلاتر راصد "
            "وبوابة الجودة الآلية. "
            "لم تتوفر مراجعة AI "
            "لهذا التشغيل."
        )

        summary = escape(
            signal.get(
                "signal_reason"
            )
            or (
                "إشارة فنية اجتازت "
                "فلاتر الجودة."
            )
        )

        note = escape(
            signal.get(
                "key_insight"
            )
            or (
                "إدارة رأس المال "
                "ووقف الخسارة أساسيان."
            )
        )

    expected_days = fmt_days(
        signal.get(
            "ai_expected_holding_days"
        )
        if ai_reviewed
        else signal.get(
            "expected_days_to_target2"
        )
    )

    rsi = fnum(
        signal.get("rsi")
    )

    volume_ratio = fnum(
        signal.get(
            "volume_ratio"
        )
    )

    rr = fnum(
        signal.get(
            "rr",
            signal.get(
                "rr_ratio"
            ),
        )
    )

    atr_pct = fnum(
        signal.get(
            "atr_pct"
        )
    )

    fundamental_grade = escape(
        signal.get(
            "fundamental_grade",
            "غير متوفر",
        )
    )

    fundamental_bonus = fint(
        signal.get(
            "fundamental_bonus"
        ),
        0,
    )

    fundamental_text = (
        f"{fundamental_grade} "
        f"({fundamental_bonus:+d})"
    )

    sector = escape(
        signal.get(
            "sector",
            "غير متوفر",
        )
    )

    sector_bonus = fint(
        signal.get(
            "sector_strength_bonus"
        ),
        0,
    )

    sector_grade = escape(
        signal.get(
            "sector_strength_grade",
            "",
        )
    )

    bt_text = backtest_text(
        signal
    )

    chase_warning = bool(
        signal.get(
            "chase_warning"
        )
        or rsi >= 68
    )

    chase_line = ""

    if chase_warning:
        chase_line = (
            "\n⚠️ <b>تنبيه الزخم:</b> "
            "الزخم مرتفع؛ تجنب مطاردة "
            "السعر بعيداً عن نقطة الدخول.\n"
        )

    now = (
        datetime.now()
        .strftime(
            "%Y-%m-%d | %I:%M %p KSA"
        )
        .replace("AM", "ص")
        .replace("PM", "م")
    )

    caption = (
        f"{tier_emoji} "
        f"<b>RASED {tier.upper()} SIGNAL</b>\n\n"

        f"📈 <b>{name} ({symbol})</b>\n\n"

        f"💰 <b>نقطة الدخول</b>\n"
        f"<code>"
        f"{fmt_price(signal.get('entry_point') or signal.get('entry'))}"
        f"</code> ريال\n\n"

        f"🎯 <b>الهدف الأول</b>\n"
        f"<code>{fmt_price(signal.get('target1'))}</code> "
        f"ريال "
        f"(+{fnum(signal.get('target1_percent') or signal.get('tp1_pct')):.2f}%)\n\n"

        f"🎯 <b>الهدف الثاني</b>\n"
        f"<code>{fmt_price(signal.get('target2'))}</code> "
        f"ريال "
        f"(+{fnum(signal.get('target2_percent') or signal.get('tp2_pct')):.2f}%)\n\n"

        f"🛑 <b>وقف الخسارة</b>\n"
        f"<code>{fmt_price(signal.get('stop_loss'))}</code> "
        f"ريال "
        f"(-{abs(fnum(signal.get('stop_loss_percent') or signal.get('sl_pct'))):.2f}%)\n\n"

        f"━━━━━━━━━━━━━━\n\n"

        f"⭐ <b>RASED SCORE™</b>\n"
        f"{rased_score:.1f} / 100\n\n"

        f"🤖 <b>الثقة المعايرة</b>\n"
        f"{confidence}%\n"
        f"<i>{conf_label}</i>\n\n"

        f"{risk_emoji} <b>مستوى المخاطرة</b>\n"
        f"{risk}\n\n"

        f"⏳ <b>مدة الصفقة المتوقعة</b>\n"
        f"{expected_days} أيام أو أقل\n\n"

        f"━━━━━━━━━━━━━━\n\n"

        f"📊 <b>مؤشرات راصد</b>\n"
        f"الزخم: {escape(momentum_text(signal))}\n"
        f"السيولة: {volume_ratio:.2f}x\n"
        f"R:R: {rr:.2f}\n"
        f"ATR: {atr_pct:.2f}%\n"
        f"الأساسيات: {fundamental_text}\n\n"

        f"🏭 <b>القطاع</b>\n"
        f"{sector}"
        f" | {sector_grade}"
        f" ({sector_bonus:+d})\n\n"

        f"🧪 <b>الاختبار التاريخي</b>\n"
        f"{escape(bt_text)}\n"

        f"{chase_line}\n"

        f"━━━━━━━━━━━━━━\n\n"

        f"🏆 <b>الحالة</b>\n"
        f"{escape(review_line)}\n\n"

        f"📌 <b>ملخص سريع</b>\n"
        f"{summary}\n\n"

        f"💡 {note}\n\n"

        f"⏰ {escape(now)}\n\n"

        f"⚠️ محتوى تحليلي وتعليمي آلي "
        f"وليس توصية استثمارية أو ضماناً للأداء.\n"
        f"الالتزام بوقف الخسارة وإدارة رأس المال "
        f"مسؤولية المتداول.\n\n"

        f"#راصد #تاسي #السوق_السعودي"
    )

    return caption


# ============================================================
# Open signal tracking
# ============================================================

def load_open_signals() -> List[Dict[str, Any]]:
    path = DATA_DIR / "open_signals.json"

    if not path.exists():
        return []

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(payload, list):
            return payload

    except Exception:
        pass

    return []


def save_open_signal(
    signal: Dict[str, Any],
) -> None:
    path = DATA_DIR / "open_signals.json"

    signals = load_open_signals()

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    symbol = str(
        signal.get(
            "stock_symbol",
            signal.get(
                "symbol",
                "",
            ),
        )
    )

    already_exists = any(
        item.get("date") == today
        and str(
            item.get(
                "signal",
                {},
            ).get(
                "stock_symbol",
                item.get(
                    "signal",
                    {},
                ).get(
                    "symbol",
                    "",
                ),
            )
        )
        == symbol
        for item in signals
    )

    if already_exists:
        print(
            f"ℹ️ {symbol}: الإشارة موجودة "
            "مسبقاً في open_signals.json"
        )
        return

    signals.append(
        {
            "signal": signal,
            "date": today,
            "posted_at": (
                datetime.now()
                .isoformat(
                    timespec="seconds"
                )
            ),
            "target1_hit": False,
            "target1_hit_at": None,
            "target2_hit": False,
            "target2_hit_at": None,
            "stop_hit": False,
            "stop_hit_at": None,
            "max_holding_days": fint(
                signal.get(
                    "max_holding_days"
                ),
                7,
            ),
            "expires_at_days": fint(
                signal.get(
                    "max_holding_days"
                ),
                7,
            ),
            "status": "open",
        }
    )

    path.write_text(
        json.dumps(
            signals,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "✅ الإشارة محفوظة في "
        "open_signals.json للمتابعة"
    )


# ============================================================
# Telegram
# ============================================================

def send_photo(
    caption: str,
) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print(
            "❌ TELEGRAM_BOT_TOKEN أو "
            "TELEGRAM_CHAT_ID غير موجود"
        )
        return False

    if not IMAGE_FILE.exists():
        print(
            "❌ output.png غير موجود"
        )
        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendPhoto"
    )

    try:
        with IMAGE_FILE.open(
            "rb"
        ) as photo:
            response = requests.post(
                url,
                data={
                    "chat_id": CHAT_ID,
                    "caption": caption,
                    "parse_mode": "HTML",
                },
                files={
                    "photo": photo,
                },
                timeout=30,
            )

    except Exception as exc:
        print(
            f"❌ Telegram request failed: {exc}"
        )
        return False

    if response.status_code != 200:
        print(
            f"❌ Telegram error "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )
        return False

    print(
        "✅ تم نشر الإشارة في تيليغرام"
    )

    return True


def main() -> int:
    signal = load_signal()

    if not signal:
        print(
            "❌ لا توجد إشارة صالحة للنشر"
        )
        return 1

    if (
        signal.get(
            "quality_gate_passed"
        )
        is False
    ):
        print(
            "❌ الإشارة لم تجتز "
            "RASED Quality Gate"
        )
        return 1

    caption = build_caption(
        signal
    )

    if not send_photo(
        caption
    ):
        return 1

    save_open_signal(
        signal
    )

    (
        DATA_DIR
        / "last_post_date.txt"
    ).write_text(
        datetime.now().strftime(
            "%Y-%m-%d"
        ),
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())