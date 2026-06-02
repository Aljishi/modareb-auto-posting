#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
راصد — تحليل كلود العميق
يستدعي Claude API لتحليل الإشارة وإضافة قراءة فنية حقيقية
"""

import os, sys, json, requests, time
from pathlib import Path

CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL   = "claude-opus-4-6"
DATA_DIR       = Path(__file__).parent.parent / "data"


def build_prompt(signal: dict) -> str:
    name   = signal.get("stock_name",  signal.get("name",   ""))
    sym    = signal.get("stock_symbol", signal.get("symbol", ""))
    price  = signal.get("current_price", 0)
    change = signal.get("change_percent", 0)
    volume = signal.get("volume", 0)
    rsi    = signal.get("rsi", 50)
    score  = signal.get("score", 0)
    entry  = signal.get("entry_point", 0)
    t1     = signal.get("target1", 0)
    t2     = signal.get("target2", 0)
    sl     = signal.get("stop_loss", 0)

    return f"""أنت محلل مالي متخصص في سوق الأسهم السعودي (تاسي).

لديك البيانات التالية لسهم تم اختياره كإشارة تداول تعليمية:

الرمز: {sym}
الاسم: {name}
السعر الحالي: {price:.2f} ريال
التغيير اليوم: {change:+.2f}%
حجم التداول: {volume:,}
RSI التقديري: {rsi:.1f}
درجة الإشارة: {score}/100
نقطة الدخول: {entry:.2f}
الهدف الأول: {t1:.2f}
الهدف الثاني: {t2:.2f}
وقف الخسارة: {sl:.2f}

المطلوب: تحليل موضوعي ومختصر. أجب بـ JSON فقط بدون أي نص خارجه:

{{
  "sector": "القطاع الذي تنتمي إليه الشركة",
  "company_summary": "وصف مختصر للشركة في جملة واحدة",
  "signal_reason": "سبب قوة الإشارة بناءً على البيانات المتاحة",
  "technical_reading": "قراءة فنية موجزة للصورة (15 كلمة كحد أقصى)",
  "risk_level": "منخفض أو متوسط أو مرتفع",
  "confidence_label": "ضعيفة أو متوسطة أو جيدة أو عالية أو عالية جداً",
  "key_insight": "أهم ملاحظة للمتداول في جملة واحدة",
  "emoji": "🟢 أو 🟡 أو 🔴"
}}

ملاحظة: هذا تحليل تعليمي فقط وليس توصية استثمارية."""


def call_claude(prompt: str) -> dict:
    """استدعاء Claude API وإعادة JSON"""
    if not CLAUDE_API_KEY:
        print("⚠️ ANTHROPIC_API_KEY غير موجود — تخطي تحليل كلود")
        return {}

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      CLAUDE_MODEL,
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data    = resp.json()
        content = data["content"][0]["text"].strip()

        # تنظيف إذا جاء محاطاً بـ ```json
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())

    except json.JSONDecodeError as e:
        print(f"⚠️ Claude أعاد نصاً غير JSON: {e}")
        return {}
    except Exception as e:
        print(f"⚠️ خطأ في Claude API: {e}")
        return {}


def enrich_signal(signal: dict) -> dict:
    """إضافة تحليل Claude للإشارة"""
    print("🤖 جاري تحليل الإشارة بواسطة Claude...")

    prompt   = build_prompt(signal)
    analysis = call_claude(prompt)

    if not analysis:
        print("⚠️ لا يوجد تحليل كلود — سيُستخدم التحليل الأساسي")
        return signal

    # إضافة نتائج كلود للإشارة
    signal["sector"]            = analysis.get("sector",           signal.get("sector", ""))
    signal["company_summary"]   = analysis.get("company_summary",  "")
    signal["signal_reason"]     = analysis.get("signal_reason",    "")
    signal["technical_reading"] = analysis.get("technical_reading","")
    signal["risk_level"]        = analysis.get("risk_level",       "متوسط")
    signal["confidence"]        = analysis.get("confidence_label", "جيدة")
    signal["key_insight"]       = analysis.get("key_insight",      "")
    signal["emoji"]             = analysis.get("emoji",            "🟡")
    signal["claude_analyzed"]   = True

    name = signal.get("stock_name", signal.get("name", ""))
    sym  = signal.get("stock_symbol", signal.get("symbol", ""))
    print(f"✅ تحليل كلود مكتمل لـ {name} ({sym})")
    print(f"   📊 القطاع: {signal['sector']}")
    print(f"   🎯 الثقة: {signal['confidence']} {signal['emoji']}")
    print(f"   📝 القراءة: {signal['technical_reading']}")
    print(f"   💡 الملاحظة: {signal['key_insight']}")

    return signal


def analyze_signals(signals: list) -> list:
    """تحليل قائمة الإشارات — نحلل الأعلى score فقط لتوفير وقت API"""
    if not signals:
        return signals

    # ترتيب حسب الـ score
    sorted_sigs = sorted(signals, key=lambda x: x.get("score", 0), reverse=True)

    enriched = []
    for i, sig in enumerate(sorted_sigs):
        if i == 0:
            # الإشارة الأولى — تحليل كامل بكلود
            enriched.append(enrich_signal(sig))
        else:
            # باقي الإشارات — بدون كلود (توفير)
            enriched.append(sig)
        time.sleep(0.5)  # تجنب rate limiting

    return enriched


def main():
    print("="*60)
    print("🤖 راصد — تحليل Claude العميق")
    print("="*60)

    # قراءة الإشارات
    sig_file = DATA_DIR / "signals.json"
    if not sig_file.exists():
        print("❌ signals.json غير موجود"); sys.exit(1)

    raw     = json.load(open(sig_file, encoding="utf-8"))
    signals = raw.get("signals", raw if isinstance(raw, list) else [raw])

    if not signals:
        print("❌ لا توجد إشارات"); sys.exit(1)

    print(f"📊 عدد الإشارات: {len(signals)}")

    # تحليل بكلود
    enriched = analyze_signals(signals)

    # حفظ النتيجة
    out = {"signals": enriched, "claude_analyzed": True,
           "timestamp": __import__("datetime").datetime.now().isoformat()}
    out_file = DATA_DIR / "signals.json"
    json.dump(out, open(out_file, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n✅ {len(enriched)} إشارة محللة ومحفوظة")


if __name__ == "__main__":
    main()
