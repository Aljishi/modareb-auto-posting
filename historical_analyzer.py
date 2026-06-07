#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Historical Analyzer - Golden Signal Generator
تحليل تاريخي للأسهم لتوليد إشارات ذهبية قبل افتتاح السوق
يعتمد على: OBV + MACD + 52 Week High + Acceleration
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get("API_KEY")
API_URL = os.environ.get("API_URL", "https://app.sahmk.sa/api/v1")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

OUTPUT_FILE = "data/golden_signal.json"
INTEL_FILE = "data/market_intel.json"

# ══════════════════════════════════════════════════════════════
# ✅ قائمة ثابتة من أهم 80 سهم في تاسي
# لا تعتمد على gainers/volume — تعمل قبل افتتاح السوق
# ══════════════════════════════════════════════════════════════
TASI_WATCHLIST = [
    # البنوك
    "1010","1020","1030","1050","1060","1080","1120","1150",
    # البتروكيماويات
    "2010","2020","2060","2090","2100","2150","2160","2170","2222","2223","2230",
    # الاتصالات
    "7010","7020","7030","7040","7203","7204",
    # الطاقة
    "5110","2040","2050",
    # التجزئة
    "4190","4200","4210","4220","4230","4240","4250","4261",
    # التقنية
    "9516","9526","9527","9528","9529","9536","9543","9544",
    "9545","9546","9547","9548","9553","9554","9555","9556",
    # الصحة
    "4002","4005","4007","4009","4013","4017","4019","4061",
    # الصناعة
    "1211","2030","2080","2110","2120","2130","2220","2250","2290","2310","2360","2380",
    # الغذاء
    "6001","6010","6013","6020","6040","6050",
    # العقار
    "4020","4031","4040","4100","4320","4321",
    # النقل والاستثمار
    "4280","5010","5020",
]

SECTORS = {
    "البنوك": ["1010","1020","1030","1050","1060","1080","1120","1150"],
    "البتروكيماويات": ["2010","2020","2060","2090","2100","2150","2160","2170","2222","2223","2230"],
    "الاتصالات": ["7010","7020","7030","7040","7203","7204"],
    "الطاقة": ["5110","2040","2050"],
    "التجزئة": ["4190","4200","4210","4220","4230","4240","4250","4261"],
    "العقار": ["4020","4031","4040","4050","4100","4150","4300","4320","4321","4322","4323","4324"],
    "الصحة": ["4002","4005","4007","4009","4013","4017","4019","4061"],
    "الصناعة": ["1211","1212","2030","2080","2082","2083","2110","2120","2130","2140","2180",
    "2190","2200","2210","2220","2240","2250","2290","2310","2320","2330","2340",
    "2350","2360","2370","2380","2381","2382"],
    "التأمين": ["8010","8020","8030","8040","8050","8060","8070","8100","8120","8150","8160",
    "8170","8180","8190","8200","8210","8230","8240","8250","8260","8270","8280",
    "8300","8310","8311","8320","8330","8340"],
    "الاستثمار": ["1111","4280","4290","4310","4349","4330","4331","4332","4333","4334","4335",
    "4336","4337","4338","4339","4340","4341","4342","4344","4345","4346","4347","4348"],
    "التقنية": ["9516","9526","9527","9528","9529","9536","9543","9544","9545","9546","9547",
    "9548","9549","9553","9554","9555","9556","9557","9558","9559","9560","9561",
    "9562","9563","9564","9565","9566","9567","9568"],
    "الغذاء": ["2060","2070","6001","6002","6010","6013","6014","6015","6020","6040","6050","6060","6070"],
}

def safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def get_sector(symbol):
    for sector_name, symbols in SECTORS.items():
        if str(symbol) in symbols:
            return sector_name
    return "أخرى"

def get(endpoint, params=None, timeout=10):
    """طلب API مع معالجة الأخطاء"""
    try:
        r = requests.get(
            f"{API_URL}{endpoint}",
            headers=HEADERS,
            params=params or {},
            timeout=timeout
        )
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            print(f"⚠️ 429 Rate Limit: {endpoint}")
            return None
        else:
            print(f"❌ {r.status_code}: {endpoint}")
            return None
    except Exception as e:
        print(f"⚠️ Error {endpoint}: {e}")
        return None

def fetch_historical(symbol, period=60):
    """جلب البيانات التاريخية للسهم"""
    data = get(f"/historical/{symbol}/", {"period": period})
    if not data:
        return None
    
    history = data if isinstance(data, list) else data.get("data", [])
    if len(history) < 20:
        return None
    
    # ترتيب حسب التاريخ
    history = sorted(history, key=lambda x: x.get("date", ""))
    
    return {
        "dates": [d.get("date") for d in history],
        "closes": [safe_float(d.get("close")) for d in history],
        "highs": [safe_float(d.get("high")) for d in history],
        "lows": [safe_float(d.get("low")) for d in history],
        "volumes": [safe_float(d.get("volume")) for d in history],
    }

def calc_ema(closes, period):
    """حساب المتوسط المتحرك الأسي"""
    if len(closes) < period:
        return closes[-1] if closes else 0
    
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    
    for close in closes[period:]:
        ema = close * k + ema * (1 - k)
    
    return ema

def calc_macd(closes):
    """حساب MACD"""
    if len(closes) < 26:
        return 0, 0, 0
    
    ema12 = calc_ema(closes, 12)
    ema26 = calc_ema(closes, 26)
    macd_line = ema12 - ema26
    
    # Signal line (EMA 9 للـ MACD)
    macd_values = []
    for i in range(26, len(closes) + 1):
        e12 = calc_ema(closes[:i], 12)
        e26 = calc_ema(closes[:i], 26)
        macd_values.append(e12 - e26)
    
    signal_line = calc_ema(macd_values, 9) if len(macd_values) >= 9 else macd_line
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

def calc_obv(closes, volumes):
    """حساب OBV (On-Balance Volume)"""
    obv = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i-1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    return obv

def calc_obv_score(closes, volumes):
    """حساب نقاط OBV"""
    if len(closes) < 10:
        return 0, "بيانات غير كافية"
    
    obv = calc_obv(closes, volumes)
    lookback = min(10, len(closes) - 1)
    
    # نسبة تغير السعر
    price_change = (closes[-1] - closes[-lookback]) / closes[-lookback] * 100 if closes[-lookback] else 0
    # نسبة تغير OBV
    obv_change = (obv[-1] - obv[-lookback]) / (abs(obv[-lookback]) + 1) * 100 if obv[-lookback] else 0
    
    if price_change < -1 and obv_change > 5:
        return 15, f"Divergence إيجابي: سعر {price_change:.1f}% OBV +{obv_change:.1f}% — تراكم خفي"
    elif price_change > 1 and obv_change > 5:
        return 10, f"تأكيد صعود: OBV +{obv_change:.1f}%"
    elif price_change > 1 and obv_change < -5:
        return -5, f"تحذير ضعف خفي: OBV {obv_change:.1f}%"
    else:
        return 3, f"OBV محايد"

def calc_week52_score(highs, price):
    """حساب نقاط قمة 52 أسبوع"""
    lookback = min(252, len(highs))
    high_52w = max(highs[-lookback:]) if lookback > 0 and highs else price
    
    if high_52w <= 0:
        return 0, 0, "لا بيانات"
    
    pct = price / high_52w * 100
    
    if pct >= 97:
        pts = 20
        desc = f"اختراق قمة 52 أسبوع ({pct:.1f}%)"
    elif pct >= 90:
        pts = 14
        desc = f"قريب من قمة 52 أسبوع ({pct:.1f}%)"
    elif pct >= 80:
        pts = 8
        desc = f"ضمن نطاق 52 أسبوع ({pct:.1f}%)"
    elif pct >= 60:
        pts = 3
        desc = f"بعيد عن القمة ({pct:.1f}%)"
    else:
        pts = -5
        desc = f"في القاع ({pct:.1f}%)"
    
    return pts, round(pct, 1), desc

def calc_acceleration(closes, volumes):
    """حساب تسارع السعر والحجم"""
    if len(closes) < 11 or len(volumes) < 11:
        return 0
    
    # تسارع السعر (آخر 5 أيام vs 5 أيام قبلها)
    price_accel = (closes[-1] - closes[-6]) / closes[-6] * 100 if closes[-6] else 0
    price_prev = (closes[-6] - closes[-11]) / closes[-11] * 100 if closes[-11] else 0
    
    # تسارع الحجم
    vol_recent = sum(volumes[-5:]) / 5
    vol_prev = sum(volumes[-10:-5]) / 5
    vol_accel = vol_recent / vol_prev if vol_prev > 0 else 0
    
    score = 0
    if price_accel > price_prev:
        score += 20
    if vol_accel > 1.5:
        score += 20
    if price_accel > 3:
        score += 10
    
    return min(score, 50)

def analyze_stock(symbol):
    """تحليل سهم واحد"""
    print(f"\n📊 {symbol}...")
    
    # جلب البيانات الحالية
    quote = get(f"/quote/{symbol}/", timeout=8)
    if not quote:
        return None
    
    stock = quote if isinstance(quote, dict) else (quote[0] if isinstance(quote, list) and quote else None)
    if not stock:
        return None
    
    price = safe_float(stock.get("price") or stock.get("close"))
    if price <= 0:
        return None
    
    # جلب البيانات التاريخية
    hist = fetch_historical(symbol, period=60)
    if not hist:
        return None
    
    closes = hist["closes"]
    highs = hist["highs"]
    volumes = hist["volumes"]
    
    # الحسابات الفنية
    macd_line, signal_line, histogram = calc_macd(closes)
    obv_pts, obv_detail = calc_obv_score(closes, volumes)
    week52_pts, week52_pct, week52_detail = calc_week52_score(highs, price)
    acceleration = calc_acceleration(closes, volumes)
    
    # RSI (مبسط)
    rsi = safe_float(stock.get("rsi"), 50)
    
    # حساب النقاط الأساسية
    score = 50  # نقطة بداية
    
    # MACD
    if macd_line > signal_line and histogram > 0:
        score += 15
    elif macd_line > signal_line:
        score += 8
    
    # OBV
    score += obv_pts
    
    # 52 Week
    score += week52_pts
    
    # Acceleration
    score += min(acceleration, 20)
    
    # RSI (النطاق الذهبي)
    if 40 <= rsi <= 70:
        score += 10
    elif rsi < 40:
        score += 5
    elif rsi > 75:
        score -= 10
    
    # الحجم
    volume = safe_float(stock.get("volume", 0))
    avg_volume = safe_float(stock.get("avg_volume", 0))
    if avg_volume > 0:
        vol_ratio = volume / avg_volume
        if vol_ratio >= 2:
            score += 15
        elif vol_ratio >= 1.5:
            score += 8
    
    score = max(0, min(score, 100))
    
    return {
        "stock": stock,
        "symbol": symbol,
        "name": stock.get("name") or stock.get("name_ar") or symbol,
        "price": price,
        "sector": get_sector(symbol),
        "score": score,
        "rsi": rsi,
        "macd_line": round(macd_line, 4),
        "signal_line": round(signal_line, 4),
        "histogram": round(histogram, 4),
        "obv_score": obv_pts,
        "obv_detail": obv_detail,
        "week52_pts": week52_pts,
        "week52_pct": week52_pct,
        "week52_detail": week52_detail,
        "acceleration": acceleration,
        "volume_ratio": round(volume / avg_volume, 2) if avg_volume > 0 else 0,
    }

def run():
    """التنفيذ الرئيسي"""
    print("=" * 60)
    print("🏆 Historical Analyzer — الإشارة الذهبية")
    print("=" * 60)
    print(f"📋 قائمة المراقبة: {len(TASI_WATCHLIST)} سهم")
    
    if not API_KEY:
        print("⚠️ API_KEY غير موجود — استخدام وضع محدود")
    
    results = []
    
    # تحليل جميع الأسهم في القائمة
    for i, symbol in enumerate(TASI_WATCHLIST, 1):
        print(f"\n[{i}/{len(TASI_WATCHLIST)}] {symbol}")
        
        try:
            result = analyze_stock(symbol)
            if result:
                results.append(result)
                print(f"  Score: {result['score']} | OBV: {result['obv_score']} | "
                      f"52W: {result['week52_pct']}% | Accel: {result['acceleration']}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    if not results:
        print("\n❌ لم يتم تحليل أي سهم")
        return {}
    
    # ترتيب حسب النقاط
    results.sort(key=lambda x: x["score"], reverse=True)
    
    # عرض أفضل 10
    print("\n" + "=" * 60)
    print("🏆 أفضل 10 أسهم:")
    print("=" * 60)
    for i, r in enumerate(results[:10], 1):
        print(f"{i:2}. {r['name']:<20} ({r['symbol']}) Score: {r['score']:>3} "
              f"OBV: {r['obv_score']:>3} 52W: {r['week52_pct']:>5.1f}% Accel: {r['acceleration']:>3}")
    
    # اختيار الأفضل كإشارة ذهبية
    best = results[0]
    
    # حساب الأهداف ووقف الخسارة
    entry = round(best["price"] * 1.005, 2)
    target1 = round(entry * 1.05, 2)
    target2 = round(entry * 1.12, 2)  # 12% للإشارة الذهبية
    stop_loss = round(entry * 0.96, 2)
    rr = round((target2 - entry) / (entry - stop_loss), 2)
    
    # بناء البيانات النهائية
    output = {
        "type": "إشارة ذهبية",
        "signal_type": "Golden",
        "brand": "راصد",
        "mode": "golden",
        "stock_name": best["name"],
        "symbol": best["symbol"],
        "stock_symbol": best["symbol"],
        "sector": best["sector"],
        "current_price": best["price"],
        "entry_point": entry,
        "target1": target1,
        "target2": target2,
        "stop_loss": stop_loss,
        "target1_percent": 5.0,
        "target2_percent": 12.0,
        "stop_loss_percent": 4.0,
        "timeframe": "7-10 أيام (هدف 12%)",
        "score": best["score"],
        "rsi": best["rsi"],
        "rs_rank": 0,  # سيتم حسابه لاحقاً
        "rr": rr,
        "volume_ratio": best["volume_ratio"],
        "acceleration": best["acceleration"],
        "obv_score": best["obv_score"],
        "obv_detail": best["obv_detail"],
        "macd_line": best["macd_line"],
        "signal_line": best["signal_line"],
        "histogram": best["histogram"],
        "week52_pct": best["week52_pct"],
        "week52_detail": best["week52_detail"],
        "technical_reading": (
            f"OBV: {best['obv_detail']} + "
            f"52W: {best['week52_detail']} + "
            f"تسارع: {best['acceleration']} + "
            f"RSI: {best['rsi']:.0f}"
        ),
        "confidence": "عالية" if best["score"] >= 70 else "متوسطة",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note": f"إشارة ذهبية قبل السوق — تحليل {len(results)} سهم من قائمة المراقبة",
    }
    
    # حفظ البيانات
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    # كتابة النسخة نفسها في daily.json حتى تتمكن should_post.py من قراءتها
    with open("data/daily.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print(f"✅ الإشارة الذهبية: {best['name']} ({best['symbol']})")
    print(f"   Score: {best['score']} | Entry: {entry} | T2: {target2} | SL: {stop_loss}")
    print(f"   تم الحفظ في: {OUTPUT_FILE}")
    print("=" * 60)
    
    return output

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n⚠️ تم الإيقاف")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
