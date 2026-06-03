#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from openai import OpenAI

DATA_DIR = Path(__file__).parent.parent / "data"
SIGNALS_FILE = DATA_DIR / "signals.json"
AI_REVIEW_FILE = DATA_DIR / "ai_review.json"

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MIN_AI_CONFIDENCE = int(os.getenv("MIN_AI_CONFIDENCE", "80"))

REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {"type": "string", "enum": ["APPROVE", "REJECT"]},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
        "risk_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "main_reasons": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 5
        },
        "rejection_reason": {"type": "string"},
        "arabic_summary": {"type": "string"},
        "telegram_note": {"type": "string"}
    },
    "required": [
        "decision",
        "confidence",
        "risk_level",
        "risk_score",
        "main_reasons",
        "rejection_reason",
        "arabic_summary",
        "telegram_note"
    ]
}


def load_signals():
    if not SIGNALS_FILE.exists():
        print("❌ signals.json not found")
        sys.exit(1)

    data = json.load(open(SIGNALS_FILE, encoding="utf-8"))
    signals = data.get("signals", [])

    if not signals:
        print("❌ No signals to review")
        sys.exit(1)

    return data, signals


def build_prompt(signal):
    return f"""
You are a strict Saudi stock market signal risk reviewer.

Your job:
Approve or reject the trading signal BEFORE it is posted to Telegram.

You must be conservative.
Reject if the signal is weak, overextended, risky, unclear, or not supported by the data.

Important:
- Do not invent data.
- Do not override hard Python rules.
- Do not give investment advice.
- Return only the structured JSON schema.

Signal data:

Symbol: {signal.get("stock_symbol")}
Name: {signal.get("stock_name")}
Sector: {signal.get("sector")}
Current price: {signal.get("current_price")}
Entry: {signal.get("entry_point")}
Target 1: {signal.get("target1")}
Target 2: {signal.get("target2")}
Stop loss: {signal.get("stop_loss")}
R:R: {signal.get("rr")}
Score: {signal.get("score")}
RSI: {signal.get("rsi")}
Volume ratio: {signal.get("volume_ratio")}
RS rank: {signal.get("rs_rank")}
ATR: {signal.get("atr") or signal.get("atr_estimated")}
Support: {signal.get("support")}
Resistance: {signal.get("resistance")}
Breakout: {signal.get("breakout")}
Trend: {signal.get("trend")}
Technical reading: {signal.get("technical_reading")}

Approval rules:
- APPROVE only if the signal is suitable for a short-term momentum trade.
- REJECT if risk_level is HIGH.
- REJECT if confidence is below 80.
- REJECT if R:R is weak.
- REJECT if RSI is overheated.
- REJECT if volume confirmation is weak.
- REJECT if entry is too close to resistance.
- REJECT if stop loss is too far or illogical.

Arabic output:
Write arabic_summary and telegram_note in professional Arabic.
Keep them short and clear.
"""


def review_signal(client, signal):
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "You are a strict trading-signal validation engine. Return valid structured JSON only."
            },
            {
                "role": "user",
                "content": build_prompt(signal)
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "rased_signal_review",
                "strict": True,
                "schema": REVIEW_SCHEMA
            }
        }
    )

    content = response.choices[0].message.content
    return json.loads(content)


def main():
    print("=" * 60)
    print("🤖 راصد — OpenAI Signal Reviewer")
    print("=" * 60)

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY is missing")
        sys.exit(1)

    client = OpenAI()
    raw_data, signals = load_signals()

    reviewed = []

    for signal in sorted(signals, key=lambda x: x.get("score", 0), reverse=True):
        sym = signal.get("stock_symbol", signal.get("symbol", ""))
        print(f"🔎 Reviewing {sym}...")

        try:
            review = review_signal(client, signal)

            signal["ai_review"] = review
            signal["ai_decision"] = review["decision"]
            signal["ai_confidence"] = review["confidence"]
            signal["ai_risk_level"] = review["risk_level"]
            signal["ai_risk_score"] = review["risk_score"]
            signal["ai_reasons"] = review["main_reasons"]
            signal["ai_arabic_summary"] = review["arabic_summary"]
            signal["ai_telegram_note"] = review["telegram_note"]
            signal["ai_reviewed_at"] = datetime.now().isoformat()

            print(
                f"  {review['decision']} | "
                f"Confidence {review['confidence']} | "
                f"Risk {review['risk_level']}"
            )

        except Exception as e:
            signal["ai_decision"] = "REJECT"
            signal["ai_confidence"] = 0
            signal["ai_risk_level"] = "HIGH"
            signal["ai_reasons"] = [f"AI review failed: {str(e)}"]
            signal["ai_arabic_summary"] = ""
            signal["ai_telegram_note"] = ""
            print(f"  ❌ AI review failed for {sym}: {e}")

        reviewed.append(signal)

    output = {
        **raw_data,
        "signals": reviewed,
        "ai_reviewed": True,
        "ai_model": MODEL,
        "ai_reviewed_at": datetime.now().isoformat()
    }

    json.dump(output, open(SIGNALS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    ai_output = {
        "ai_model": MODEL,
        "reviewed_at": datetime.now().isoformat(),
        "signals": [
            {
                "stock_symbol": s.get("stock_symbol"),
                "stock_name": s.get("stock_name"),
                "decision": s.get("ai_decision"),
                "confidence": s.get("ai_confidence"),
                "risk_level": s.get("ai_risk_level"),
                "reasons": s.get("ai_reasons"),
                "arabic_summary": s.get("ai_arabic_summary")
            }
            for s in reviewed
        ]
    }

    json.dump(ai_output, open(AI_REVIEW_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    approved = [
        s for s in reviewed
        if s.get("ai_decision") == "APPROVE"
        and s.get("ai_confidence", 0) >= MIN_AI_CONFIDENCE
        and s.get("ai_risk_level") != "HIGH"
    ]

    print(f"\n✅ AI approved: {len(approved)}/{len(reviewed)}")
    sys.exit(0 if approved else 1)


if __name__ == "__main__":
    main()
