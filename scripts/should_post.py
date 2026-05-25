import json
import sys
from datetime import datetime

DATA_FILE   = "data/daily.json"
GOLDEN_FILE = "data/golden_signal.json"

# ─── معايير الإشارة اليومية (هدف ثانٍ 10% خلال 10 أيام) ────
MIN_SCORE        = 78
MIN_RSI          = 42
MAX_RSI          = 68
MIN_VOLUME_RATIO = 1.5   # مرن بسبب مشكلة API
MIN_RR           = 2.0   # R:R محسوب على T2 (10%)

# ─── معايير الإشارة الذهبية (قبل السوق) ────────────────────
GOLDEN_MIN_SCORE = 50
GOLDEN_RSI_MIN   = 35
GOLDEN_RSI_MAX   = 75
GOLDEN_MIN_RR    = 1.5


def check_golden(data):
    """معايير الإشارة الذهبية قبل السوق"""
    score  = data.get("score", 0)
    rsi    = data.get("rsi", 50)
    rr     = data.get("rr", 0)
    # FIX: check both key names for compatibility
    symbol = data.get("stock_symbol", data.get("symbol", ""))
    name   = data.get("stock_name", "")
    stype  = data.get("signal_type", "")
    t2_pct = data.get("target2_pct", 0)
    accel  = data.get("acceleration", 0)

    fails = []
    if score < GOLDEN_MIN_SCORE:
        fails.append(f"Score {score} < {GOLDEN_MIN_SCORE}")
    if not (GOLDEN_RSI_MIN <= rsi <= GOLDEN_RSI_MAX):
        fails.append(f"RSI {rsi:.0f} خارج النطاق ({GOLDEN_RSI_MIN}-{GOLDEN_RSI_MAX})")
    if rr < GOLDEN_MIN_RR:
        fails.append(f"R:R {rr:.1f} < {GOLDEN_MIN_RR}")

    print(f"\n{'='*55}")
    print(f"فحص الإشارة الذهبية: {name} ({symbol})")
    print(f"النوع: {stype}")
    print(f"{'='*55}")
    print(f"  Score     : {score:>5}  {'OK' if score >= GOLDEN_MIN_SCORE else 'X'} (min {GOLDEN_MIN_SCORE})")
    print(f"  RSI       : {rsi:>5.0f}  {'OK' if GOLDEN_RSI_MIN <= rsi <= GOLDEN_RSI_MAX else 'X'} ({GOLDEN_RSI_MIN}-{GOLDEN_RSI_MAX})")
    print(f"  R:R       : {rr:>5.1f}  {'OK' if rr >= GOLDEN_MIN_RR else 'X'} (min {GOLDEN_MIN_RR})")
    print(f"  هدف ثانٍ : {t2_pct:>4.0f}%  {'OK' if t2_pct >= 10 else '─'}")
    print(f"  تسارع     : {accel:>5}  {'قوي' if accel >= 30 else 'متوسط' if accel >= 15 else 'عادي'}")
    print(f"  Volume    : تُتجاهل للإشارة الذهبية (بيانات تاريخية)")

    if fails:
        print(f"\nالإشارة الذهبية لا تستوفي المعايير:")
        for f in fails:
            print(f"   - {f}")
        print(f"\nتم تخطي النشر\n")
        return False

    print(f"\nالإشارة الذهبية تستوفي المعايير — سيتم النشر!\n")
    return True


def check_daily(data):
    """معايير الإشارة اليومية — هدف ثانٍ 10% خلال 10 أيام"""
    score        = data.get("score", 0)
    rsi          = data.get("rsi", 50)
    volume_ratio = data.get("volume_ratio", 0)
    rr           = data.get("rr", 0)
    # FIX: check both key names for compatibility
    symbol       = data.get("stock_symbol", data.get("symbol", ""))
    name         = data.get("stock_name", "")
    t2_pct       = data.get("target2_pct", 0)
    accel        = data.get("acceleration", 0)

    fails = []

    if score < MIN_SCORE:
        fails.append(f"Score {score} < {MIN_SCORE}")
    if not (MIN_RSI <= rsi <= MAX_RSI):
        fails.append(f"RSI {rsi:.0f} خارج النطاق ({MIN_RSI}-{MAX_RSI})")
    if rr < MIN_RR:
        if score >= 85 and rr >= 1.5:
            print(f"  ** R:R {rr:.1f} مقبول لـ Score {score}")
        else:
            fails.append(f"R:R {rr:.1f} < {MIN_RR}")
    if volume_ratio < MIN_VOLUME_RATIO:
        if score >= 85 and volume_ratio == 0.0:
            print(f"  ** Volume = 0 (مشكلة API) — مقبول لـ Score {score}")
        else:
            fails.append(f"Volume {volume_ratio:.1f}x < {MIN_VOLUME_RATIO}x")
    if t2_pct > 0 and t2_pct < 10:
        fails.append(f"هدف ثانٍ {t2_pct:.1f}% < 10%")

    print(f"\n{'='*55}")
    print(f"فحص جودة الاشارة: {name} ({symbol})")
    print(f"{'='*55}")
    print(f"  Score     : {score:>5}  {'OK' if score >= MIN_SCORE else 'X'} (min {MIN_SCORE})")
    print(f"  RSI       : {rsi:>5.0f}  {'OK' if MIN_RSI <= rsi <= MAX_RSI else 'X'} ({MIN_RSI}-{MAX_RSI})")
    print(f"  R:R       : {rr:>5.1f}  {'OK' if rr >= MIN_RR else 'X'} (min {MIN_RR} — T2 10%)")
    vol_ok = volume_ratio >= MIN_VOLUME_RATIO or (score >= 85 and volume_ratio == 0.0)
    print(f"  Volume    : {volume_ratio:>4.1f}x  {'OK' if vol_ok else 'X'} (min {MIN_VOLUME_RATIO}x)")
    print(f"  هدف ثانٍ : {t2_pct:>4.0f}%  {'OK' if t2_pct >= 10 else '─'} (min 10%)")
    print(f"  تسارع     : {accel:>5}  {'قوي' if accel >= 30 else 'متوسط' if accel >= 15 else 'عادي'}")

    if fails:
        print(f"\nالاشارة لا تستوفي المعايير:")
        for f in fails:
            print(f"   - {f}")
        print(f"\nتم تخطي النشر اليوم\n")
        return False

    print(f"\nالاشارة تستوفي جميع المعايير — سيتم النشر!\n")
    return True


if __name__ == "__main__":
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"خطا في قراءة {DATA_FILE}: {e}")
        sys.exit(1)

    generated_at = data.get("generated_at", "")
    today = datetime.now().strftime("%Y-%m-%d")
    if not generated_at.startswith(today):
        print(f"البيانات قديمة ({generated_at or 'غير محدد'}) — تم الانتهاء")
        sys.exit(1)

    # ─── FIX: حارس النشر المزدوج ────────────────────────────
    # منع النشر أكثر من مرة في نفس اليوم للإشارة نفسها.
    # بعد النشر الناجح تكتب السكريبت الأخرى "posted_today": true
    # في daily.json — إذا وُجدت نتوقف هنا مباشرةً.
    if data.get("posted_today") is True:
        symbol = data.get("stock_symbol", data.get("symbol", ""))
        print(f"تم النشر مسبقاً اليوم ({symbol}) — تم تخطي النشر")
        sys.exit(1)
    # ────────────────────────────────────────────────────────

    signal_type = data.get("type", "")
    is_golden   = signal_type == "اشارة ذهبية"

    if is_golden:
        print("  نوع الإشارة: ذهبية — تطبيق معايير ما قبل السوق")
        passed = check_golden(data)
    else:
        print("  نوع الإشارة: يومية — هدف ثانٍ 10% خلال 10 أيام")
        passed = check_daily(data)

    sys.exit(0 if passed else 1)
