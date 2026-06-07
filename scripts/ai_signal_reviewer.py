#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""راصد — مراجعة OpenAI اختيارية وآمنة.

الهدف:
- إذا كان OpenAI يعمل: يراجع الإشارة ويضيف ai_decision / ai_confidence.
- إذا كان OpenAI غير متاح أو الرصيد منتهي insufficient_quota: لا يفشل الـ workflow.
- يضع ai_available=false ويترك القرار النهائي لـ should_post.py بفلاتر Python الصارمة.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SIGNALS_FILE = DATA_DIR / "signals.json"
AI_REVIEW_FILE = DATA_DIR / "ai_review.json"

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MIN_AI_CONFIDENCE = int(os.getenv("MIN_AI_CONFIDENCE", "82"))
MAX_HOLD_DAYS = int(os.getenv("MAX_HOLD_DAYS", "7"))

REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {"type": "string", "enum": ["APPROVE", "REJECT"]},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
        "risk_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "rased_score_adjustment": {"type": "integer", "minimum": -10, "maximum": 10},
        "expected_holding_days": {"type": "integer", "minimum": 1, "maximum": 30},
        "main_reasons": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 5,
        },
        "rejection_reason": {"type": "string"},
        "arabic_summary": {"type": "string"},
        "telegram_note": {"type": "string"},
    },
    "required": [
        "decision",
        "confidence",
        "risk_level",
        "risk_score",
        "rased_score_adjustment",
        "expected_holding_days",
        "main_reasons",
        "rejection_reason",
        "arabic_summary",
        "telegram_note",
    ],
}


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace("%", "").replace(",", "").strip()
        return float(x)
    except Exception:
        return default


def classify_tier(score: float) -> Tuple[str, str]:
    if score >= 95:
        return "Platinum", "👑"
    if score >= 90:
        return "Gold", "🌟"
    if score >= 85:
        return "Premium", "⭐"
    return "Standard", "✅"


def load_signals() -> Dict[str, Any]:
    if not SIGNALS_FILE.exists():
        print("ℹ️ data/signals.json not found")
        return {"signals": []}
    data = json.loads(SIGNALS_FILE.read_text(encoding="utf-8"))
    if not data.get("signals"):
        print("ℹ️ No signals to review")
    return data


def build_prompt(signal: Dict[str, Any]) -> str:
    return f"""
You are a strict Saudi stock market signal reviewer for a paid Telegram signal service.

Approve only strong short-term momentum setups.
Reject unclear, overextended, weak-volume, high-risk, or unrealistic 7-day setups.

Return only JSON that matches the schema.

Signal:
Symbol: {signal.get("stock_symbol") or signal.get("symbol")}
Name: {signal.get("stock_name") or signal.get("name")}
Current price: {signal.get("current_price")}
Entry: {signal.get("entry_point")}
Target 1: {signal.get("target1")} ({signal.get("target1_percent")}%)
Target 2: {signal.get("target2")} ({signal.get("target2_percent")}%)
Stop loss: {signal.get("stop_loss")} ({signal.get("stop_loss_percent")}%)
R:R: {signal.get("rr")}
Score: {signal.get("score")}
RASED preliminary score: {signal.get("rased_score")}
RSI: {signal.get("rsi")}
Volume ratio: {signal.get("volume_ratio")}
ATR %: {signal.get("atr_pct")}
Resistance: {signal.get("resistance")}
Support: {signal.get("support")}
Breakout: {signal.get("breakout")}
Trend: {signal.get("trend")}
Expected days TP1: {signal.get("expected_days_to_target1")}
Expected days TP2: {signal.get("expected_days_to_target2")}
Seven-day filter passed: {signal.get("seven_day_filter_passed")}
Historical bars: {signal.get("historical_bars")}
Technical reading: {signal.get("technical_reading")}

Rules:
- APPROVE only if confidence >= 82.
- APPROVE only if risk is LOW or MEDIUM.
- APPROVE only if expected_holding_days <= 7.
- REJECT if TP2 looks unrealistic within 7 days.
- REJECT if RSI is overheated or volume confirmation is weak.
- REJECT if the setup is not clear.

Arabic fields:
- arabic_summary: short professional Arabic summary.
- telegram_note: short premium wording, no long technical list.
"""


def review_one(client: Any, signal: Dict[str, Any]) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "You are a strict trading-signal validation engine. Return only valid JSON matching the schema.",
            },
            {"role": "user", "content": build_prompt(signal)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "rased_signal_review",
                "strict": True,
                "schema": REVIEW_SCHEMA,
            },
        },
    )
    return json.loads(response.choices[0].message.content)


def apply_review(signal: Dict[str, Any], review: Dict[str, Any]) -> Dict[str, Any]:
    base = fnum(signal.get("rased_score"), fnum(signal.get("score"), 0))
    confidence = int(review.get("confidence", 0))
    rr_score = min(fnum(signal.get("rr")) * 28, 100)
    adjustment = int(review.get("rased_score_adjustment", 0))

    final_score = round(base * 0.45 + confidence * 0.35 + rr_score * 0.20 + adjustment, 1)
    final_score = max(0, min(100, final_score))
    tier, tier_emoji = classify_tier(final_score)

    signal["ai_available"] = True
    signal["ai_review"] = review
    signal["ai_decision"] = review.get("decision", "REJECT")
    signal["ai_confidence"] = confidence
    signal["ai_risk_level"] = review.get("risk_level", "HIGH")
    signal["ai_risk_score"] = review.get("risk_score", 100)
    signal["ai_expected_holding_days"] = review.get("expected_holding_days", 30)
    signal["ai_reasons"] = review.get("main_reasons", [])
    signal["ai_arabic_summary"] = review.get("arabic_summary", "")
    signal["ai_telegram_note"] = review.get("telegram_note", "")
    signal["ai_reviewed_at"] = datetime.now().isoformat(timespec="seconds")

    signal["rased_score"] = final_score
    signal["tier"] = tier
    signal["tier_emoji"] = tier_emoji
    signal["confidence"] = f"{confidence}%"

    risk_map = {"LOW": "منخفض", "MEDIUM": "متوسط", "HIGH": "مرتفع"}
    risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
    signal["risk_level"] = risk_map.get(signal["ai_risk_level"], signal.get("risk_level", ""))
    signal["risk_level_ar"] = signal["risk_level"]
    signal["risk_emoji"] = risk_emoji.get(signal["ai_risk_level"], signal.get("risk_emoji", "⚪"))
    return signal


def mark_ai_unavailable(data: Dict[str, Any], reason: str) -> None:
    reviewed = []
    for signal in data.get("signals", []):
        signal["ai_available"] = False
        signal["ai_decision"] = "SKIPPED"
        signal["ai_confidence"] = 0
        signal["ai_risk_level"] = "UNKNOWN"
        signal["ai_expected_holding_days"] = signal.get("expected_days_to_target2", 7)
        signal["ai_reasons"] = [reason]
        signal["ai_arabic_summary"] = signal.get("signal_reason", "")
        signal["ai_telegram_note"] = signal.get("key_insight", "")
        reviewed.append(signal)

    data["signals"] = reviewed
    data["ai_reviewed"] = False
    data["ai_available"] = False
    data["ai_error"] = reason
    data["ai_model"] = MODEL
    data["ai_reviewed_at"] = datetime.now().isoformat(timespec="seconds")
    SIGNALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    AI_REVIEW_FILE.write_text(
        json.dumps(
            {
                "model": MODEL,
                "available": False,
                "error": reason,
                "reviewed_at": datetime.now().isoformat(timespec="seconds"),
                "signals": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    print("=" * 60)
    print("🤖 راصد — OpenAI Premium Review")
    print("=" * 60)

    data = load_signals()
    if not data.get("signals"):
        return 0

    if OpenAI is None:
        reason = "openai package unavailable"
        print(f"⚠️ {reason}")
        mark_ai_unavailable(data, reason)
        return 0

    if not os.getenv("OPENAI_API_KEY"):
        reason = "OPENAI_API_KEY missing"
        print(f"⚠️ {reason}")
        mark_ai_unavailable(data, reason)
        return 0

    try:
        client = OpenAI()
    except Exception as exc:
        reason = f"OpenAI client init failed: {exc}"
        print(f"⚠️ {reason}")
        mark_ai_unavailable(data, reason)
        return 0

    reviewed: List[Dict[str, Any]] = []
    any_quota_error = False

    for signal in sorted(
        data.get("signals", []),
        key=lambda s: fnum(s.get("rased_score"), s.get("score", 0)),
        reverse=True,
    ):
        sym = signal.get("stock_symbol", signal.get("symbol", ""))
        print(f"🔎 Reviewing {sym}...")
        try:
            review = review_one(client, signal)
            signal = apply_review(signal, review)
            print(
                f"  {signal['ai_decision']} | Confidence {signal['ai_confidence']} | "
                f"Risk {signal['ai_risk_level']} | Days {signal['ai_expected_holding_days']}"
            )
        except Exception as exc:
            msg = str(exc)
            if "insufficient_quota" in msg or "429" in msg:
                any_quota_error = True
            signal["ai_available"] = False
            signal["ai_decision"] = "SKIPPED"
            signal["ai_confidence"] = 0
            signal["ai_risk_level"] = "UNKNOWN"
            signal["ai_expected_holding_days"] = signal.get("expected_days_to_target2", 7)
            signal["ai_reasons"] = [f"AI review skipped: {msg[:250]}"]
            signal["ai_arabic_summary"] = signal.get("signal_reason", "")
            signal["ai_telegram_note"] = signal.get("key_insight", "")
            print(f"  ⚠️ AI skipped for {sym}: {msg[:180]}")
        reviewed.append(signal)

    data["signals"] = reviewed
    data["ai_reviewed"] = not any_quota_error and any(s.get("ai_available") for s in reviewed)
    data["ai_available"] = any(s.get("ai_available") for s in reviewed)
    data["ai_model"] = MODEL
    data["ai_reviewed_at"] = datetime.now().isoformat(timespec="seconds")
    SIGNALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    approved = [
        s
        for s in reviewed
        if s.get("ai_decision") == "APPROVE"
        and int(s.get("ai_confidence", 0)) >= MIN_AI_CONFIDENCE
        and s.get("ai_risk_level") in ("LOW", "MEDIUM")
        and int(s.get("ai_expected_holding_days", 30)) <= MAX_HOLD_DAYS
    ]

    AI_REVIEW_FILE.write_text(
        json.dumps(
            {
                "model": MODEL,
                "available": data["ai_available"],
                "reviewed_at": datetime.now().isoformat(timespec="seconds"),
                "approved": len(approved),
                "total": len(reviewed),
                "signals": [
                    {
                        "stock_symbol": s.get("stock_symbol"),
                        "decision": s.get("ai_decision"),
                        "confidence": s.get("ai_confidence"),
                        "risk_level": s.get("ai_risk_level"),
                        "expected_holding_days": s.get("ai_expected_holding_days"),
                        "rased_score": s.get("rased_score"),
                        "tier": s.get("tier"),
                        "reasons": s.get("ai_reasons", []),
                    }
                    for s in reviewed
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if data["ai_available"]:
        print(f"\n✅ AI approved: {len(approved)}/{len(reviewed)}")
    else:
        print("\n⚠️ OpenAI unavailable — workflow will continue with strict Python gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
