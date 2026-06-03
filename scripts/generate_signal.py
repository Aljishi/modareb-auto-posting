#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
راصد — توليد الإشارات
UPGRADE: أهداف مبنية على ATR + فلتر بيانات حقيقية + مؤشرات إضافية
"""

import json
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# ── حدود جودة البيانات ────────────────────────────────────────────────────────
MIN_REAL_VOLUME_RATIO = 1.2  # volume_ratio أقل من هذا = بيانات وهمية على الأرجح
UNIFORM_VOL_SUSPECT   = True  # كل الأسهم بنفس volume_ratio = fallback data

# ── معاملات الإشارة ───────────────────────────────────────────────────────────
MIN_SCORE    = 70
ATR_MULT_T1  = 2.0   # الهدف الأول  = entry + 2 × ATR_estimated
ATR_MULT_T2  = 3.5   # الهدف الثاني = entry + 3.5 × ATR_estimated
ATR_MULT_SL  = 1.0   # وقف الخسارة  = entry − 1 × ATR_estimated
MIN_RR       = 2.0   # نسبة مخاطرة/عائد لا تقل عن 2:1


def check_data_quality(stocks: list) -> dict:
    """
    تحقق من جودة مصدر البيانات قبل توليد الإشارات.
    إذا كان fallback/mock → لا نشر.
    """
    if not stocks:
        return {"ok": False, "reason": "لا توجد أسهم في daily.json"}

    # علامة صريحة من market_intelligence.py
    # (أضفناها في النسخة المحسّنة من market_intelligence)

    # فحص: هل كل volume_ratio متطابقة؟ (علامة fallback)
    vols = [s.get("volume_ratio", 0) for s in stocks]
    if len(set(vols)) == 1 and vols[0] in (1.0, 2.5):
        return {"ok": False,
                "reason": f"volume_ratio موحدة ({vols[0]}) — بيانات fallback/mock"}

    # فحص: هل يوجد قيم سعر = 0؟
    zero_price = sum(1 for s in stocks if s.get("current_price", 0) == 0)
    if zero_price > len(stocks) * 0.5:
        return {"ok": False,
                "reason": f"{zero_price}/{len(stocks)} سهم بسعر صفر"}

    # فحص: هل القطاعات كلها فارغة؟ (علامة ضعيفة لكن مفيدة)
    empty_sector = sum(1 for s in stocks if not s.get("sector", "").strip())
    sector_warning = ""
    if empty_sector == len(stocks):
        sector_warning = " | ⚠️ القطاعات فارغة"

    return {"ok": True, "warning": sector_warning}


def estimate_atr(price: float, rsi: float, change_pct: float) -> float:
    """
    تقدير ATR بدون بيانات تاريخية.
    منطق: تقلب السهم ∝ حجم الحركة اليومية + RSI (إشارة تقلب).
    أفضل من نسبة ثابتة 5% للجميع.
    """
    # التقلب الأساسي: نسبة مئوية من السعر بناءً على RSI
    # RSI عالٍ (>65) = سهم متحرك = ATR أكبر
    # RSI منخفض (<45) = سهم هادئ = ATR أصغر
    if rsi >= 65:
        base_pct = 0.025   # 2.5%
    elif rsi >= 55:
        base_pct = 0.018   # 1.8%
    elif rsi >= 45:
        base_pct = 0.013   # 1.3%
    else:
        base_pct = 0.010   # 1.0%

    # تعديل بناءً على الحركة اليومية الفعلية
    daily_move = abs(change_pct) / 100
    atr_estimate = price * max(base_pct, daily_move * 1.5)

    return round(atr_estimate, 4)


def calculate_targets(price: float, rsi: float, change_pct: float) -> dict:
    """
    حساب نقطة الدخول، الأهداف، ووقف الخسارة بناءً على ATR المُقدَّر.
    أفضل بكثير من نسب ثابتة × السعر.
    """
    atr   = estimate_atr(price, rsi, change_pct)
    entry = round(price * 1.005, 2)  # دخول طفيف فوق السعر الحالي (0.5%)

    t1 = round(entry + ATR_MULT_T1 * atr, 2)
    t2 = round(entry + ATR_MULT_T2 * atr, 2)
    sl = round(entry - ATR_MULT_SL * atr, 2)

    # نسب مئوية حقيقية
    t1p = round((t1 - entry) / entry * 100, 1)
    t2p = round((t2 - entry) / entry * 100, 1)
    slp = round((entry - sl) / entry * 100, 1)
    rr  = round(t2p / slp, 1) if slp > 0 else 0

    return {
        "entry":   entry,
        "t1":      t1,   "t1p":  t1p,
        "t2":      t2,   "t2p":  t2p,
        "sl":      sl,   "slp":  slp,
        "rr":      rr,
        "atr_est": round(atr, 3),
    }


def calculate_score(stock: dict) -> tuple:
    """
    نظام نقاط محسّن بـ 6 أبعاد بدلاً من 4.
    يعيد (score, reasons)
    """
    score   = 0
    reasons = []

    rsi = stock.get("rsi", 50)
    vol = stock.get("volume_ratio", 1.0)
    chg = stock.get("change_percent", 0)
    rs  = stock.get("rs_rank", 50)

    # ── 1. RSI (25 نقطة) ─────────────────────────────────────────────────────
    if 52 <= rsi <= 65:
        score += 25
        reasons.append(f"RSI ذهبي {rsi:.0f}")
    elif 45 <= rsi < 52 or 65 < rsi <= 72:
        score += 16
        reasons.append(f"RSI مقبول {rsi:.0f}")
    elif 38 <= rsi < 45:
        score += 8
    # RSI فوق 72 أو دون 38 = صفر (مبالغة)

    # ── 2. حجم التداول (25 نقطة) ─────────────────────────────────────────────
    if vol >= 3.0:
        score += 25
        reasons.append(f"حجم قوي جداً {vol:.1f}x")
    elif vol >= 2.0:
        score += 20
        reasons.append(f"حجم قوي {vol:.1f}x")
    elif vol >= 1.5:
        score += 14
        reasons.append(f"حجم فوق المتوسط {vol:.1f}x")
    elif vol >= 1.2:
        score += 8
    # دون 1.2x = صفر

    # ── 3. الزخم اليومي (20 نقطة) ────────────────────────────────────────────
    if 1.5 <= chg <= 6.0:
        score += 20
        reasons.append(f"زخم صحي +{chg:.1f}%")
    elif 0.5 <= chg < 1.5:
        score += 14
    elif 6.0 < chg <= 9.5:
        score += 10           # ارتفاع مبالغ فيه
    elif -1.0 <= chg < 0.5:
        score += 6
    # دون -1% = صفر

    # ── 4. القوة النسبية RS Rank (20 نقطة) ───────────────────────────────────
    if rs >= 85:
        score += 20
        reasons.append(f"RS قوة عالية {rs:.0f}")
    elif rs >= 70:
        score += 14
        reasons.append(f"RS فوق المتوسط {rs:.0f}")
    elif rs >= 55:
        score += 8
    # دون 55 = صفر

    # ── 5. تناسق RSI + حجم (10 نقطات إضافية) ────────────────────────────────
    if 52 <= rsi <= 65 and vol >= 2.0:
        score += 10
        reasons.append("تناسق RSI + حجم")

    # ── 6. فلتر خاص: RSI عالٍ جداً = خصم ───────────────────────────────────
    if rsi > 75:
        score = max(0, score - 20)
        reasons.append(f"⚠️ RSI مرتفع جداً ({rsi:.0f}) — خصم")

    return min(score, 100), reasons


def build_signal_text(reasons: list) -> str:
    """بناء نص القراءة التقنية من أسباب الإشارة"""
    return " | ".join(reasons[:3]) if reasons else ""


def main():
    print("=" * 60)
    print("🎯 راصد — توليد الإشارات (محسّن)")
    print("=" * 60)

    daily_file = DATA_DIR / "daily.json"
    if not daily_file.exists():
        print("❌ daily.json غير موجود")
        sys.exit(1)

    with open(daily_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    stocks = data.get("stocks", [])

    # ── فحص جودة البيانات أولاً ──────────────────────────────────────────────
    quality = check_data_quality(stocks)
    if not quality["ok"]:
        print(f"🚫 بيانات غير موثوقة: {quality['reason']}")
        print("🚫 لن يتم توليد إشارات من بيانات وهمية")
        # حفظ ملف فارغ لمنع استخدام إشارات قديمة
        out = {"signals": [], "generated_at": datetime.now().isoformat(),
               "total": 0, "blocked_reason": quality["reason"]}
        with open(DATA_DIR / "signals.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        sys.exit(1)

    if quality.get("warning"):
        print(f"⚠️ تحذير جودة البيانات:{quality['warning']}")

    print(f"✅ بيانات موثوقة: {len(stocks)} سهم")

    # ── توليد الإشارات ────────────────────────────────────────────────────────
    signals = []

    for stock in stocks:
        price = float(stock.get("current_price", 0))
        if price <= 0:
            continue

        score, reasons = calculate_score(stock)
        if score < MIN_SCORE:
            continue

        rsi = stock.get("rsi", 50)
        chg = stock.get("change_percent", 0)

        # أهداف مبنية على ATR
        tgt = calculate_targets(price, rsi, chg)

        # تحقق R:R قبل قبول الإشارة
        if tgt["rr"] < MIN_RR:
            print(f"  ⚠️ {stock.get('symbol')}: R:R={tgt['rr']} ضعيف — تجاوز")
            continue

        if score >= 85:
            confidence, emoji, level = "عالية جداً", "🟢", "golden"
        elif score >= 75:
            confidence, emoji, level = "عالية",      "🟡", "high"
        else:
            confidence, emoji, level = "متوسطة",     "🔵", "medium"

        sig = {
            "stock_symbol":       stock.get("symbol", ""),
            "stock_name":         stock.get("name",   ""),
            "sector":             stock.get("sector", ""),
            "current_price":      price,
            "entry_point":        tgt["entry"],
            "target1":            tgt["t1"],
            "target1_percent":    tgt["t1p"],
            "target2":            tgt["t2"],
            "target2_percent":    tgt["t2p"],
            "stop_loss":          tgt["sl"],
            "stop_loss_percent":  tgt["slp"],
            "rr":                 tgt["rr"],
            "atr_estimated":      tgt["atr_est"],
            "rsi":                stock.get("rsi", 50),
            "volume_ratio":       stock.get("volume_ratio", 1.0),
            "rs_rank":            stock.get("rs_rank", 50),
            "score":              score,
            "technical_reading":  build_signal_text(reasons),
            "confidence":         confidence,
            "emoji":              emoji,
            "level":              level,
            "generated_at":       datetime.now().isoformat(),
            # ── حقل مهم: مصدر البيانات ──────────────────────────────────
            "data_source":        data.get("data_source", "unknown"),
        }
        signals.append(sig)
        print(f"  🎯 {stock.get('symbol'):6} | Score {score:3} | "
              f"R:R {tgt['rr']} | ATR≈{tgt['atr_est']} | {confidence}")

    # ترتيب حسب النتيجة
    signals.sort(key=lambda x: x["score"], reverse=True)

    output = {
        "signals":        signals,
        "generated_at":   datetime.now().isoformat(),
        "total":          len(signals),
        "data_source":    data.get("data_source", "unknown"),
        "total_screened": len(stocks),
    }

    out_file = DATA_DIR / "signals.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(signals)}/{len(stocks)} إشارة مقبولة")
    sys.exit(0 if signals else 1)


if __name__ == "__main__":
    main()
