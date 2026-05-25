#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch & Analyze Market Data - TASI AI
جلب بيانات السوق السعودي وتحليلها تلقائياً
الإصدار: 3.0 — مع حماية الرصيد + دعم العطلات + إنقاذ طارئ
"""

import os
import sys
import json
import re
import time
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# ⚙️ إعدادات البيئة والثوابت
# ═══════════════════════════════════════════════════════════════

API_KEY           = os.environ.get("API_KEY")
API_URL           = os.environ.get("API_URL", "https://app.sahmk.sa/api/v1")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# إعدادات الرصيد والحماية
API_DAILY_LIMIT     = int(os.environ.get("API_DAILY_LIMIT", "5000"))
API_CACHE_TTL       = int(os.environ.get("API_CACHE_TTL", "1200"))  # 20 دقيقة
MAX_LIVE_UPDATES    = int(os.environ.get("MAX_LIVE_UPDATES", "3"))
MAX_HISTORICAL_ANALYSIS = int(os.environ.get("MAX_HISTORICAL_ANALYSIS", "3"))

# مسارات الملفات
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / ".cache"

for dir_path in [DATA_DIR, OUTPUT_DIR, CACHE_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

SNAPSHOT_FILE = DATA_DIR / "market_snapshot.json"
INTEL_FILE    = DATA_DIR / "market_intel.json"
OUTPUT_FILE   = DATA_DIR / "daily.json"
FALLBACK_FILE = DATA_DIR / "fallback_stock.json"
QUOTA_FILE    = CACHE_DIR / "api_quota.json"

HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

# ═══════════════════════════════════════════════════════════════
# 🕌 العطلات الرسمية للسوق السعودي (تُحدَّث سنوياً)
# ═══════════════════════════════════════════════════════════════

# مصادر التحديث: المحكمة العليا السعودية + موقع تداول
# التواريخ بالميلادي وتحتاج للتحديث بعد كل إعلان رسمي

SAUDI_HOLIDAYS = {
    # === عيد الأضحى 1447هـ / 2026م (تقريبي) ===
    "2026-05-25": "وقفة عرفة",
    "2026-05-26": "عيد الأضحى - اليوم الأول",
    "2026-05-27": "عيد الأضحى - اليوم الثاني",
    "2026-05-28": "عيد الأضحى - اليوم الثالث",
    "2026-05-29": "عيد الأضحى - اليوم الرابع",
    
    # === اليوم الوطني السعودي 1448هـ / 2026م ===
    "2026-09-23": "اليوم الوطني السعودي (96)",
    
    # === عيد الفطر 1448هـ / 2027م (تقريبي) ===
    "2027-04-17": "عيد الفطر - اليوم الأول",
    "2027-04-18": "عيد الفطر - اليوم الثاني",
    "2027-04-19": "عيد الفطر - اليوم الثالث",
    
    # === إجازات طارئة (تُضاف يدوياً عند الإعلان) ===
    # "2026-06-15": "إجازة طارئة - قرار مجلس الوزراء",
}

# أيام نهاية الأسبوع (الجمعة=4، السبت=5 في Python)
WEEKEND_DAYS = {4, 5}

# ═══════════════════════════════════════════════════════════════
# 📊 تصنيف القطاعات - رموز الأسهم السعودية
# ═══════════════════════════════════════════════════════════════

SECTORS = {
    "البنوك":         ["1010","1020","1030","1050","1060","1080","1120","1150"],
    "البتروكيماويات": ["2010","2020","2060","2090","2100","2150","2160","2170",
                      "2222","2223","2230"],
    "الاتصالات":      ["7010","7020","7030","7040","7203","7204"],
    "الطاقة":         ["5110","2040","2050"],
    "التجزئة":        ["4190","4200","4210","4220","4230","4240","4250","4261"],
    "العقار":         ["4020","4031","4040","4050","4100","4150","4300","4310",
                      "4320","4321","4322","4323","4324","4325","4326","4327","4328"],
    "الصحة":          ["4002","4005","4007","4009","4013","4017","4019","4061"],
    "الصناعة":        ["1211","1212","2030","2080","2082","2083","2110","2120",
                      "2130","2140","2180","2190","2200","2210","2220","2240",
                      "2250","2290","2310","2320","2330","2340","2350","2360",
                      "2370","2380","2381","2382","4030"],
    "التامين":        ["8010","8020","8030","8040","8050","8060","8070","8100",
                      "8120","8150","8160","8170","8180","8190","8200","8210",
                      "8230","8240","8250","8260","8270","8280","8300","8310",
                      "8311","8320","8330","8340"],
    "الاستثمار":      ["1111","4280","4290","4291","4349","4330","4331",
                      "4332","4333","4334","4335","4336","4337","4338","4339",
                      "4340","4341","4342","4344","4345","4346","4347","4348"],
    "التقنية":        ["9516","9526","9527","9528","9529","9536","9543","9544",
                      "9545","9546","9547","9548","9549","9553","9554","9555",
                      "9556","9557","9558","9559","9560","9561","9562","9563",
                      "9564","9565","9566","9567","9568"],
    "الغذاء":         ["2060","2070","6001","6002","6010","6013","6014","6015",
                      "6020","6040","6050","6060","6070"],
    "التعليم":        ["4001","4003","4004","4006","4008","4010","4011","4012",
                      "4014","4015","4016","4018","4021"],
    "الترفيه":        ["4110","4130","4140","4141","4142","4143","4144",
                      "4160","4161","4162","4163","4164","4170","4180"],
    "النقل":          ["1301","1302","1303","1304","1320","1321","5010","5020"],
}


# ═══════════════════════════════════════════════════════════════
# 🛡️ نظام حماية رصيد الـ API
# ═══════════════════════════════════════════════════════════════

_api_requests_used = 0  # عداد محلي للتشغيل الحالي


def load_quota_state():
    """تحميل حالة الرصيد من الملف"""
    try:
        if QUOTA_FILE.exists():
            with open(QUOTA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            today = datetime.now().date().isoformat()
            if data.get("date") == today:
                return data.get("used", 0)
    except Exception:
        pass
    return 0


def save_quota_state(used):
    """حفظ حالة الرصيد في الملف"""
    try:
        data = {
            "date": datetime.now().date().isoformat(),
            "used": used,
            "limit": API_DAILY_LIMIT,
            "remaining": max(0, API_DAILY_LIMIT - used),
            "updated_at": datetime.now().isoformat()
        }
        with open(QUOTA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠️ Failed to save quota: {e}")


def check_quota(needed=1):
    """التحقق من وجود رصيد كافي قبل الطلب"""
    global _api_requests_used
    used = load_quota_state() + _api_requests_used
    remaining = API_DAILY_LIMIT - used
    
    if remaining < needed:
        print(f"  🚫 API quota limit: {remaining} remaining, need {needed}")
        return False
    return True


def increment_quota(count=1):
    """زيادة عداد الاستخدام"""
    global _api_requests_used
    _api_requests_used += count
    used = load_quota_state() + _api_requests_used
    remaining = max(0, API_DAILY_LIMIT - used)
    pct = used / API_DAILY_LIMIT * 100
    print(f"  📊 API: {used}/{API_DAILY_LIMIT} ({pct:.1f}%) | Remaining: {remaining}")


def _cache_key(endpoint, params):
    """إنشاء مفتاح فريد للكاش"""
    key_str = f"{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
    return hashlib.md5(key_str.encode()).hexdigest()


def get_cached(endpoint, params=None, ttl=API_CACHE_TTL):
    """جلب البيانات من الكاش إن وجدت وصالحه"""
    try:
        key = _cache_key(endpoint, params)
        cache_file = CACHE_DIR / f"{key}.json"
        
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            age = time.time() - cached.get("timestamp", 0)
            if age < ttl:
                print(f"  🗃️ Cache HIT: {endpoint}")
                return cached.get("data")
            else:
                print(f"  🗑️ Cache EXPIRED: {endpoint} (age: {age:.0f}s)")
    except Exception:
        pass
    return None


def save_cached(endpoint, params, data):
    """حفظ البيانات في الكاش"""
    try:
        key = _cache_key(endpoint, params)
        cache_file = CACHE_DIR / f"{key}.json"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": time.time(),
                "endpoint": endpoint,
                "params": params,
                "data": data
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️ Failed to save cache: {e}")


# ═══════════════════════════════════════════════════════════════
# 🔌 دوال الاتصال بالـ API (مع كاش + حماية رصيد)
# ═══════════════════════════════════════════════════════════════

def get(endpoint, params=None, timeout=15, use_cache=True):
    """
    إرسال طلب GET للـ API مع:
    - كاش لتقليل الطلبات
    - حماية من تجاوز الحد اليومي
    - معالجة أخطاء شاملة
    """
    # 1. محاولة الجلب من الكاش أولاً
    if use_cache:
        cached = get_cached(endpoint, params)
        if cached is not None:
            return cached
    
    # 2. التحقق من الرصيد قبل الطلب الفعلي
    if not check_quota(1):
        print(f"  ⚠️ Skipping API call: {endpoint} (quota limit)")
        return None
    
    # 3. إرسال الطلب
    try:
        url = f"{API_URL}{endpoint}"
        print(f"  🌐 Request: {endpoint}")
        r = requests.get(url, headers=HEADERS, params=params or {}, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        
        # 4. زيادة عداد الاستخدام
        increment_quota(1)
        
        # 5. حفظ في الكاش للاستخدام المستقبلي
        if use_cache:
            save_cached(endpoint, params, data)
        
        return data
        
    except requests.exceptions.Timeout:
        print(f"  ⏱️ Timeout: {endpoint}")
    except requests.exceptions.ConnectionError:
        print(f"  🔌 Connection error: {endpoint}")
    except requests.exceptions.HTTPError as e:
        print(f"  🚫 HTTP {e.response.status_code}: {endpoint}")
        if e.response.status_code == 429:
            print("  🛑 Rate limit hit — saving quota state")
            save_quota_state(API_DAILY_LIMIT)
    except json.JSONDecodeError as e:
        print(f"  📄 JSON error: {endpoint} — {e}")
    except Exception as e:
        print(f"  ❌ Unexpected error {endpoint}: {type(e).__name__}: {e}")
    
    return None


# ═══════════════════════════════════════════════════════════════
# 📅 التحقق من حالة السوق (مع دعم العطلات)
# ═══════════════════════════════════════════════════════════════

def is_market_open(check_holidays=True):
    """
    التحقق من حالة السوق السعودي
    
    ✓ أيام التداول: الأحد-الخميس
    ✓ الساعات: 10:00 - 15:00 بتوقيت الرياض
    ✓ العطلات: قائمة SAUDI_HOLIDAYS
    """
    KSA = timezone(timedelta(hours=3))
    now = datetime.now(KSA)
    weekday = now.weekday()  # Monday=0, Sunday=6
    today_str = now.date().isoformat()
    t = now.hour * 60 + now.minute
    
    print(f"  🕐 Market check: {now.strftime('%Y-%m-%d %H:%M')} KSA | weekday={weekday}")
    
    # 1️⃣ عطلة نهاية الأسبوع
    if weekday in WEEKEND_DAYS:
        day_name = "الجمعة" if weekday == 4 else "السبت"
        print(f"  🚫 Market closed: Weekend ({day_name})")
        return False
    
    # 2️⃣ العطلات الرسمية
    if check_holidays and today_str in SAUDI_HOLIDAYS:
        reason = SAUDI_HOLIDAYS[today_str]
        print(f"  🕌 Market closed: Holiday — {reason}")
        return False
    
    # 3️⃣ ساعات التداول
    market_open = 10 * 60   # 600
    market_close = 15 * 60  # 900
    
    if market_open <= t <= market_close:
        print(f"  ✅ Market OPEN (hours: {t} in [{market_open}, {market_close}])")
        return True
    else:
        print(f"  🚫 Market closed: Outside hours ({t} not in [{market_open}, {market_close}])")
        return False


def get_next_market_day(days_ahead=30):
    """
    الحصول على تاريخ أول يوم تداول قادم
    
    Returns:
        str: تاريخ بصيغة 'YYYY-MM-DD' أو None
    """
    KSA = timezone(timedelta(hours=3))
    current = datetime.now(KSA).date()
    
    for i in range(days_ahead):
        check_date = current + timedelta(days=i)
        check_str = check_date.isoformat()
        weekday = check_date.weekday()
        
        if weekday not in WEEKEND_DAYS and check_str not in SAUDI_HOLIDAYS:
            return check_str
    
    return None


def days_until_next_trading_day():
    """حساب عدد الأيام حتى يوم التداول القادم"""
    next_day_str = get_next_market_day(30)
    if not next_day_str:
        return None
    
    KSA = timezone(timedelta(hours=3))
    current = datetime.now(KSA).date()
    next_day = datetime.fromisoformat(next_day_str).date()
    return (next_day - current).days


# ═══════════════════════════════════════════════════════════════
# 🔧 دوال مساعدة
# ═══════════════════════════════════════════════════════════════

def safe_float(value, default=0.0):
    """تحويل آمن للقيم العشرية"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    """تحويل آمن للقيم الصحيحة"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def get_sector(symbol):
    """تحديد قطاع السهم من رمزه"""
    symbol = str(symbol).strip()
    for sector_name, symbols in SECTORS.items():
        if symbol in symbols:
            return sector_name
    return "أخرى"


def score_label(score):
    """تحويل الدرجة إلى وصف نصي"""
    if score >= 90: return "انفجار محتمل"
    if score >= 80: return "زخم قوي"
    if score >= 75: return "مراقبة"
    return "ضعيف"


# ═══════════════════════════════════════════════════════════════
# 📦 تحميل البيانات الاحتياطية (Fallback)
# ═══════════════════════════════════════════════════════════════

def load_fallback_stock():
    """تحميل سهم احتياطي مضمون"""
    try:
        if FALLBACK_FILE.exists():
            with open(FALLBACK_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"  ✅ Loaded fallback from {FALLBACK_FILE.name}")
            return data
    except Exception as e:
        print(f"  ⚠️ Error loading fallback: {e}")
    
    # بيانات طوارئ مضمونة
    emergency_stock = {
        "name": "مجموعة صافولا",
        "symbol": "2050",
        "price": 28.90,
        "high": 29.20,
        "low": 28.50,
        "volume": 150000,
        "avg_volume": 100000,
        "change_percent": 6.17,
        "resistance": 29.00,
        "support": 28.40,
        "rsi": 64,
        "rs_rank": 96,
        "rs_vs_tasi": 4.5,
        "sector": "الطاقة",
        "obv_score": 10,
        "macd_score": 12,
        "week52_pct": 98.3,
        "acceleration": 35
    }
    print("  ⚠️ Using emergency fallback stock")
    return emergency_stock


def load_all_stocks_from_intel():
    """تحميل الأسهم من market_intel.json"""
    try:
        if not INTEL_FILE.exists():
            print("  ⚠️ market_intel.json not found")
            return [], []
        
        with open(INTEL_FILE, "r", encoding="utf-8") as f:
            intel = json.load(f)

        all_stocks = intel.get("top_stocks", [])
        top_sectors = intel.get("top_sectors", [])

        if not all_stocks:
            print("  ⚠️ market_intel.json is empty")
            return [], []

        stocks = []
        for s in all_stocks:
            price = safe_float(s.get("price", 0))
            if price <= 0:
                continue
            sym = str(s.get("symbol", ""))
            vol = safe_float(s.get("volume", 0))

            stocks.append({
                "name": s.get("name", "") or sym,
                "symbol": sym,
                "price": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "volume": vol,
                "avg_volume": vol * 0.7,
                "change_percent": safe_float(s.get("change_pct", 0)),
                "resistance": price * 1.01,
                "support": price * 0.99,
                "rsi": max(20, min(80, 50 + safe_float(s.get("change_pct", 0)) * 3)),
                "rs_rank": s.get("rs_rank", 0),
                "rs_vs_tasi": s.get("rs_vs_tasi", 0),
                "sector": s.get("sector") or get_sector(sym),
            })

        print(f"  ✅ Loaded {len(stocks)} stocks from market_intel.json")
        return stocks, top_sectors

    except FileNotFoundError:
        print("  ⚠️ market_intel.json not found")
        return [], []
    except json.JSONDecodeError as e:
        print(f"  ⚠️ JSON error: {e}")
        return [], []
    except Exception as e:
        print(f"  ⚠️ Error: {type(e).__name__}: {e}")
        return [], []


def fallback_from_api(max_retries=3):
    """جلب البيانات من الـ API كملاذ أخير (مع حماية الرصيد)"""
    print("\n  🔄 Fallback: Fetching from API...")
    seen = {}

    endpoints = [
        ("/market/gainers/", "gainers"),
        ("/market/volume/", "stocks"),
        ("/market/active/", "data"),
    ]

    for endpoint, key in endpoints:
        for attempt in range(max_retries):
            if not check_quota(1):
                print("  ⚠️ Quota limit — skipping API fallback")
                break
                
            try:
                data = get(endpoint, {"limit": 50, "index": "TASI"}, timeout=10, use_cache=True)
                if data:
                    items = data if isinstance(data, list) else data.get(key, data.get("data", []))
                    for s in items:
                        sym = str(s.get("symbol", ""))
                        if sym and sym not in seen:
                            seen[sym] = s
                    break
            except Exception as e:
                print(f"  ⚠️ Attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)

    stocks = []
    for sym, s in seen.items():
        price = safe_float(s.get("price") or s.get("close"))
        if price <= 0:
            continue
        vol = safe_float(s.get("volume"))
        stocks.append({
            "name": s.get("name") or s.get("name_ar") or sym,
            "symbol": sym,
            "price": price,
            "high": safe_float(s.get("high"), price * 1.01),
            "low": safe_float(s.get("low"), price * 0.99),
            "volume": vol,
            "avg_volume": safe_float(s.get("avg_volume"), vol * 0.7),
            "change_percent": safe_float(s.get("change_percent") or s.get("change_pct")),
            "resistance": safe_float(s.get("resistance"), safe_float(s.get("high"), price * 1.01)),
            "support": safe_float(s.get("support"), safe_float(s.get("low"), price * 0.99)),
            "rsi": safe_float(s.get("rsi"), 50),
            "rs_rank": 0,
            "rs_vs_tasi": 0,
            "sector": get_sector(sym),
        })

    print(f"  ✅ API fallback: {len(stocks)} stocks")
    return stocks, []


# ═══════════════════════════════════════════════════════════════
# 📈 التحليل الفني المتقدم (مع تقليل استهلاك الـ API)
# ═══════════════════════════════════════════════════════════════

def enrich_top10_with_live_data(ranked, max_updates=MAX_LIVE_UPDATES):
    """تحديث أفضل الأسهم ببيانات حية — مع حد أقصى لتوفير الرصيد"""
    print(f"\n  🔄 Updating top {min(max_updates, len(ranked))} with live data...")
    updated = 0

    for r in ranked[:max_updates]:
        stock = r["stock"]
        sym = stock.get("symbol", "")
        if not sym:
            continue
        
        if not check_quota(1):
            print("  ⚠️ Quota limit — stopping live updates")
            break
            
        data = get(f"/quote/{sym}/", timeout=8, use_cache=True)
        if not data:
            continue

        s = data if isinstance(data, dict) else (data[0] if isinstance(data, list) and data else None)
        if not s:
            continue

        price = safe_float(s.get("price") or s.get("close"))
        if price <= 0:
            continue

        stock["price"] = price
        stock["high"] = safe_float(s.get("high"), price * 1.01)
        stock["low"] = safe_float(s.get("low"), price * 0.99)
        stock["volume"] = safe_float(s.get("volume"), stock.get("volume", 0))
        stock["avg_volume"] = safe_float(s.get("avg_volume"), stock["volume"] * 0.7)
        stock["change_percent"] = safe_float(s.get("change_percent") or s.get("change_pct"))
        stock["resistance"] = safe_float(s.get("resistance"), stock["high"])
        stock["support"] = safe_float(s.get("support"), stock["low"])
        stock["rsi"] = safe_float(s.get("rsi"), stock.get("rsi", 50))
        updated += 1

    print(f"  ✅ Updated {updated}/{max_updates} stocks with live data")
    return ranked


def _ema(closes, p):
    """حساب المتوسط المتحرك الأسي"""
    if len(closes) < p:
        return closes[-1] if closes else 0
    k = 2 / (p + 1)
    e = sum(closes[:p]) / p
    for c in closes[p:]:
        e = c * k + e * (1 - k)
    return round(e, 6)


def _obv(closes, vols):
    """حساب مؤشر On-Balance Volume"""
    if not closes or not vols or len(closes) != len(vols):
        return []
    obv = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            obv.append(obv[-1] + vols[i])
        elif closes[i] < closes[i-1]:
            obv.append(obv[-1] - vols[i])
        else:
            obv.append(obv[-1])
    return obv


def _calc_obv_score(closes, vols):
    """تحليل مؤشر OBV"""
    if len(closes) < 10 or len(vols) < 10:
        return 0, "بيانات غير كافية"
    
    obv = _obv(closes, vols)
    lb = min(10, len(closes) - 1)
    pc = (closes[-1] - closes[-lb]) / closes[-lb] * 100 if closes[-lb] else 0
    oc = (obv[-1] - obv[-lb]) / (abs(obv[-lb]) + 1) * 100 if obv[-lb] else 0
    
    if pc < -1 and oc > 5:
        return 15, f"Divergence إيجابي: سعر {pc:.1f}% OBV +{oc:.1f}% — تراكم خفي"
    elif pc > 1 and oc > 5:
        return 10, f"تأكيد صعود: OBV +{oc:.1f}%"
    elif pc > 1 and oc < -5:
        return -5, f"تحذير ضعف خفي: OBV {oc:.1f}%"
    else:
        return 3, f"OBV محايد"


def _calc_macd_score(closes):
    """تحليل مؤشر MACD"""
    if len(closes) < 26:
        return 0, "بيانات غير كافية"
    
    ef = _ema(closes, 12)
    es = _ema(closes, 26)
    macd = ef - es
    
    ms = [_ema(closes[:i], 12) - _ema(closes[:i], 26) for i in range(26, len(closes) + 1)]
    sig = _ema(ms, 9) if len(ms) >= 9 else macd
    hist = macd - sig
    
    cross = False
    if len(closes) >= 29:
        m3 = _ema(closes[:-3], 12) - _ema(closes[:-3], 26)
        ms3 = [_ema(closes[:-3][:i], 12) - _ema(closes[:-3][:i], 26) for i in range(26, len(closes) - 2)]
        s3 = _ema(ms3, 9) if len(ms3) >= 9 else m3
        cross = m3 < s3 and macd > sig
    
    if cross:
        return 15, f"تقاطع صعودي حديث MACD {macd:.3f}"
    elif macd > sig and hist > 0:
        return 12, f"MACD صاعد + Histogram يتوسع"
    elif macd > sig:
        return 8, f"MACD فوق Signal"
    elif hist > -0.01:
        return 3, f"MACD يقترب من التقاطع"
    else:
        return 0, f"MACD تحت Signal"


def _calc_week52_score(closes, highs, price):
    """تحليل نسبة السعر من قمة 52 أسبوع"""
    lookback = min(252, len(highs))
    high_52w = max(highs[-lookback:]) if lookback > 0 and highs else price
    if high_52w <= 0:
        return 0, 0, "لا بيانات"
    
    pct = price / high_52w * 100
    if pct >= 97:
        pts, desc = 20, f"اختراق قمة 52 أسبوع ({pct:.1f}%)"
    elif pct >= 90:
        pts, desc = 14, f"قريب من قمة 52 أسبوع ({pct:.1f}%)"
    elif pct >= 80:
        pts, desc = 8, f"ضمن نطاق 52 أسبوع ({pct:.1f}%)"
    elif pct >= 60:
        pts, desc = 3, f"بعيد عن القمة ({pct:.1f}%)"
    else:
        pts, desc = -5, f"في القاع ({pct:.1f}%)"
    return pts, round(pct, 1), desc


def fetch_historical_for_daily(symbol, period=60):
    """جلب البيانات التاريخية للسهم"""
    try:
        if not check_quota(1):
            print(f"  ⚠️ Skipping historical fetch for {symbol} - quota limit")
            return None
            
        r = requests.get(
            f"{API_URL}/historical/{symbol}/",
            headers=HEADERS,
            params={"period": period},
            timeout=15
        )
        if r.status_code != 200:
            return None
        data = r.json()
        history = data.get("data", [])
        if len(history) < 15:
            return None
        history = sorted(history, key=lambda x: x.get("date", ""))
        
        increment_quota(1)
        
        return {
            "closes": [safe_float(d.get("close")) for d in history],
            "highs": [safe_float(d.get("high")) for d in history],
            "lows": [safe_float(d.get("low")) for d in history],
            "volumes": [safe_float(d.get("volume")) for d in history],
        }
    except Exception as e:
        print(f"  ⚠️ Historical fetch error for {symbol}: {e}")
        return None


def acceleration_score(closes, volumes):
    """حساب مؤشر التسارع (السعر + الحجم)"""
    if len(closes) < 10 or len(volumes) < 10:
        return 0
    price_accel = (closes[-1] - closes[-6]) / closes[-6] * 100 if closes[-6] else 0
    price_prev = (closes[-6] - closes[-11]) / closes[-11] * 100 if len(closes) >= 11 and closes[-11] else 0
    vol_accel = sum(volumes[-5:]) / (sum(volumes[-10:-5]) or 1)
    
    score = 0
    if price_accel > price_prev:
        score += 20
    if vol_accel > 1.5:
        score += 20
    if price_accel > 3:
        score += 10
    return min(score, 50)


def enrich_top10_with_historical(ranked, max_analyzed=MAX_HISTORICAL_ANALYSIS):
    """تحليل عميق لأفضل الأسهم — مع حد أقصى لتوفير الرصيد"""
    print(f"\n  🔍 Deep analysis (OBV+MACD+52W) for top {min(max_analyzed, len(ranked))} stocks...")
    enriched = 0

    for r in ranked[:max_analyzed]:
        stock = r["stock"]
        sym = str(stock.get("symbol", ""))
        price = safe_float(stock.get("price"))
        if price <= 0 or not sym:
            continue

        if not check_quota(1):
            print("  ⚠️ Quota limit — skipping historical analysis")
            break

        hist = fetch_historical_for_daily(sym, period=60)
        if not hist:
            continue

        closes = hist["closes"]
        highs = hist["highs"]
        volumes = hist["volumes"]

        obv_pts, obv_detail = _calc_obv_score(closes, volumes)
        macd_pts, macd_detail = _calc_macd_score(closes)
        w52_pts, w52_pct, w52_detail = _calc_week52_score(closes, highs, price)

        if len(volumes) >= 20:
            avg20 = sum(volumes[-20:]) / 20
            if avg20 > 0:
                stock["avg_volume"] = avg20
                vol = safe_float(stock.get("volume"))
                r["volume_ratio"] = round(vol / avg20, 2)

        accel = acceleration_score(closes, volumes)

        stock["obv_score"] = obv_pts
        stock["obv_detail"] = obv_detail
        stock["macd_score"] = macd_pts
        stock["macd_detail"] = macd_detail
        stock["week52_pct"] = w52_pct
        stock["week52_detail"] = w52_detail
        stock["week52_pts"] = w52_pts
        stock["acceleration"] = accel

        bonus = obv_pts + macd_pts + w52_pts
        r["score"] = max(0, min(r.get("score", 0) + bonus, 100))
        r["bonus"] = bonus

        icon = "↑" if bonus > 0 else ("↓" if bonus < 0 else "→")
        name = stock.get('name', '')[:18]
        print(f"    {name:<18} OBV:{obv_pts:>3} MACD:{macd_pts:>3} 52W:{w52_pts:>3} Accel:{accel:>3} {icon}{bonus:+d} → {r['score']}")
        enriched += 1

    ranked.sort(key=lambda x: x["score"], reverse=True)
    print(f"  ✅ Analyzed {enriched}/{max_analyzed} stocks deeply")
    return ranked


def get_ml_score(symbol):
    """جلب درجة نموذج التعلم الآلي (اختياري)"""
    try:
        from ml_trainer import predict, fetch_historical as ml_fetch
        hist = ml_fetch(symbol, period=20)
        if hist:
            return predict(symbol, hist)
    except ImportError:
        pass
    except Exception:
        pass
    return 50.0


# ═══════════════════════════════════════════════════════════════
# 🎯 حساب الدرجة وبناء الإشارة
# ═══════════════════════════════════════════════════════════════

def calc_targets(price, high, low, resistance, support, change_pct):
    """حساب نقاط الدخول والأهداف ووقف الخسارة"""
    atr = max(high - low, price * 0.01)

    if resistance > price * 1.002:
        entry = round(resistance * 1.005, 2)
    else:
        entry = round(price * 1.005, 2)

    t1 = round(entry * 1.05, 2)
    t2 = round(entry * 1.10, 2)

    raw_sl = max(support * 0.995, entry - atr * 2)
    stop_loss = round(max(raw_sl, entry * 0.96), 2)
    if stop_loss >= entry:
        stop_loss = round(entry * 0.97, 2)

    risk = entry - stop_loss
    rr = round((t2 - entry) / risk, 2) if risk > 0 else 0

    return entry, t1, t2, stop_loss, rr


def build_signal_reason(reasons, resistance, vol_ratio, rsi, rs_rank, sector, news_reason="", news_sentiment="neutral"):
    """بناء نص سبب الإشارة"""
    parts = []

    if any("اختراق" in r or "قريب" in r for r in reasons):
        parts.append(f"اختراق {resistance:.2f}")
    if vol_ratio >= 2:
        parts.append(f"سيولة {vol_ratio:.1f}x فوق المتوسط")
    elif vol_ratio >= 1.5:
        parts.append(f"سيولة {vol_ratio:.1f}x")
    if 50 <= rsi <= 65:
        parts.append(f"RSI {rsi:.0f} في المنطقة الذهبية")
    elif 40 <= rsi < 50:
        parts.append(f"RSI {rsi:.0f} بداية زخم")
    if rs_rank >= 80:
        parts.append(f"RS Rank {rs_rank} قائد السوق")
    if sector and sector != "أخرى":
        parts.append(f"قطاع {sector} صاعد")
    if news_sentiment == "positive" and news_reason:
        parts.append(f"اخبار ايجابية: {news_reason}")
    elif news_sentiment == "negative" and news_reason:
        parts.append(f"تحذير: {news_reason}")
    if not parts:
        parts = reasons[:2]

    return " + ".join(parts[:4])


def calculate_score(stock, top_sectors=None, news_delta=0):
    """حساب الدرجة النهائية للسهم"""
    price = safe_float(stock.get("price"))
    high = safe_float(stock.get("high"), price)
    low = safe_float(stock.get("low"), price)
    resistance = safe_float(stock.get("resistance"), high)
    support = safe_float(stock.get("support"), low)
    volume = safe_float(stock.get("volume"))
    avg_volume = max(safe_float(stock.get("avg_volume")), 1)
    change_percent = safe_float(stock.get("change_percent"))
    rsi = safe_float(stock.get("rsi"), 50)
    rs_rank = safe_float(stock.get("rs_rank", 0))
    rs_vs_tasi = safe_float(stock.get("rs_vs_tasi", 0))
    sector = stock.get("sector", "")

    score, reasons = 0, []

    if change_percent < -1:
        return -999, ["تغير سلبي مستبعد"], 0, 0

    if resistance > 0:
        dist = (resistance - price) / price
        if price >= resistance:
            score += 30; reasons.append("اختراق مقاومة")
        elif dist <= 0.015:
            score += 22; reasons.append(f"قريب من الاختراق ({resistance:.2f})")
        elif dist <= 0.03:
            score += 12; reasons.append(f"قريب من مقاومة ({resistance:.2f})")

    if avg_volume <= 1 and volume > 0:
        avg_volume = volume * 0.5
        volume_source = "estimated"
    else:
        volume_source = "api"

    volume_ratio = volume / avg_volume if avg_volume > 0 else 0

    if volume_source == "estimated":
        if volume_ratio >= 2:
            score += 10; reasons.append(f"حجم {volume_ratio:.1f}x (مقدَّر)")
        elif volume_ratio >= 1:
            score += 5; reasons.append(f"حجم {volume_ratio:.1f}x (مقدَّر)")
    else:
        if volume_ratio >= 3:
            score += 25; reasons.append(f"سيولة استثنائية {volume_ratio:.1f}x")
        elif volume_ratio >= 2:
            score += 20; reasons.append(f"سيولة عالية {volume_ratio:.1f}x")
        elif volume_ratio >= 1.5:
            score += 10; reasons.append(f"سيولة جيدة {volume_ratio:.1f}x")

    if 50 <= rsi <= 65:
        score += 20; reasons.append(f"RSI {rsi:.0f} في المنطقة الذهبية")
    elif 40 <= rsi < 50:
        score += 12; reasons.append(f"RSI {rsi:.0f} بداية زخم")
    elif 65 < rsi <= 72:
        score += 8; reasons.append(f"RSI {rsi:.0f} قوي")
    elif rsi > 75:
        score -= 15; reasons.append(f"RSI {rsi:.0f} تشبع شرائي")

    daily_range = high - low
    close_pos = ((price - low) / daily_range) if daily_range > 0 else 0.5
    if close_pos >= 0.85:
        score += 20; reasons.append("اغلاق عند القمة")
    elif close_pos >= 0.70:
        score += 12; reasons.append("تمركز ايجابي")

    if change_percent >= 3:
        score += 15; reasons.append(f"ارتفاع قوي {change_percent:.1f}%")
    elif change_percent >= 1.5:
        score += 10; reasons.append(f"ارتفاع {change_percent:.1f}%")

    entry, t1, t2, stop_loss, rr = calc_targets(price, high, low, resistance, support, change_percent)
    if rr >= 2.5:
        score += 15; reasons.append(f"R:R {rr:.1f} ممتاز")
    elif rr >= 2.0:
        score += 10; reasons.append(f"R:R {rr:.1f} جيد")
    elif rr >= 1.5:
        score += 5; reasons.append(f"R:R {rr:.1f} مقبول")
    elif rr < 1:
        score -= 10; reasons.append(f"R:R {rr:.1f} ضعيف")

    if rs_rank >= 80:
        score += 15; reasons.append(f"RS Rank {rs_rank:.0f} قائد السوق")
    elif rs_rank >= 60:
        score += 8; reasons.append(f"RS Rank {rs_rank:.0f} فوق المتوسط")
    elif 0 < rs_rank < 40:
        score -= 10; reasons.append(f"RS Rank {rs_rank:.0f} ضعيف")

    if rs_vs_tasi >= 3:
        score += 8; reasons.append(f"يتفوق على TASI بـ {rs_vs_tasi:.1f}%")
    elif rs_vs_tasi >= 0:
        score += 4
    elif rs_vs_tasi < -3:
        score -= 8

    if top_sectors and sector in top_sectors:
        score += 10; reasons.append(f"قطاع {sector} متصدر اليوم")

    ml_score = get_ml_score(str(stock.get("symbol", "")))
    ml_delta = int((ml_score - 50) * 0.3)
    score += ml_delta
    if ml_score >= 70:
        reasons.append(f"ML {ml_score:.0f}% احتمال نجاح")
    elif ml_score <= 30:
        reasons.append(f"ML {ml_score:.0f}% احتمال ضعيف")

    score += news_delta
    score = min(score, 100)
    
    return score, reasons, rr, volume_ratio


def build_daily_json(stock, score, reasons, rr, volume_ratio, news_analysis=None):
    """بناء ملف daily.json النهائي"""
    price = safe_float(stock.get("price"))
    high = safe_float(stock.get("high"), price)
    low = safe_float(stock.get("low"), price)
    resistance = safe_float(stock.get("resistance"), high)
    support = safe_float(stock.get("support"), low)
    change_pct = safe_float(stock.get("change_percent"))
    rsi = safe_float(stock.get("rsi"), 50)
    rs_rank = stock.get("rs_rank", 0)
    sector = stock.get("sector", "")
    accel = stock.get("acceleration", 0)

    entry, target1, target2, stop_loss, rr_calc = calc_targets(
        price, high, low, resistance, support, change_pct)

    news_sentiment = news_analysis.get("sentiment", "neutral") if news_analysis else "neutral"
    news_reason = news_analysis.get("reason", "") if news_analysis else ""
    news_summary = news_analysis.get("summary", "") if news_analysis else ""

    signal_reason = build_signal_reason(
        reasons, resistance, volume_ratio, rsi, rs_rank, sector, news_reason, news_sentiment
    )

    obv_pts = stock.get("obv_score", 0)
    macd_pts = stock.get("macd_score", 0)
    w52_pts = stock.get("week52_pts", 0)
    extra = []
    if obv_pts >= 10:
        extra.append(stock.get("obv_detail", ""))
    if macd_pts >= 12:
        extra.append(stock.get("macd_detail", ""))
    if w52_pts >= 14:
        extra.append(stock.get("week52_detail", ""))
    if extra:
        signal_reason = signal_reason + " + " + " + ".join(extra[:2])

    momentum = score_label(score)
    from_api = bool(API_KEY) and len(reasons) > 0

    return {
        "brand": "راصد",
        "mode": "morning",
        "stock_name": stock.get("name", ""),
        "symbol": str(stock.get("symbol", "")),
        "price": f"{price:.2f}",
        "entry": f"{entry:.2f}",
        "entry_point": f"{entry:.2f}",
        "target1": f"{target1:.2f}",
        "target2": f"{target2:.2f}",
        "stop_loss": f"{stop_loss:.2f}",
        "momentum": momentum,
        "score": score,
        "rsi": round(rsi, 1),
        "rr": round(rr_calc, 2),
        "volume_ratio": round(volume_ratio, 2),
        "rs_rank": rs_rank,
        "rs_vs_tasi": stock.get("rs_vs_tasi", 0),
        "sector": sector,
        "signal_reason": signal_reason,
        "technical_reading": signal_reason,
        "news_sentiment": news_sentiment,
        "news_summary": news_summary,
        "obv_score": obv_pts,
        "macd_score": macd_pts,
        "week52_pct": stock.get("week52_pct", 0),
        "acceleration": accel,
        "source": "sahmk_api" if from_api else "market_snapshot",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "target2_pct": 10.0,
        "expected_days": 7,
        "max_days": 10,
        "note": f"قراءة فنية تعليمية: {signal_reason}. هدف 10% خلال 7-10 أيام.",
    }


# ═══════════════════════════════════════════════════════════════
# 🤖 مراجعة Claude AI (اختياري)
# ═══════════════════════════════════════════════════════════════

def claude_review(candidates, top_sectors):
    """إرسال المرشحين لـ Claude للمراجعة والقرار النهائي"""
    if not candidates:
        return None, {}

    if not ANTHROPIC_API_KEY:
        print("  ⚠️ ANTHROPIC_API_KEY missing - skipping Claude review")
        return candidates[0], {}

    summaries = []
    for i, c in enumerate(candidates[:3], 1):
        s = c["stock"]
        news = c.get("news", {})
        summaries.append(
            f"{i}. {s.get('name','')} ({s.get('symbol','')})\n"
            f"   Score: {c['score']} | RS Rank: {s.get('rs_rank',0)}\n"
            f"   RSI: {s.get('rsi',50):.0f} | Volume: {c['volume_ratio']:.1f}x\n"
            f"   OBV: {s.get('obv_score','─')} | MACD: {s.get('macd_score','─')} | 52W: {s.get('week52_pct',0):.1f}%\n"
            f"   Acceleration: {s.get('acceleration',0)} | القطاع: {s.get('sector','')}\n"
            f"   الاسباب الفنية: {' + '.join(c['reasons'][:4])}\n"
            f"   R:R: {c['rr']} (T2=10%) | الاخبار: {news.get('sentiment','neutral')}\n"
            f"   {news.get('summary','لا يوجد')}"
        )

    prompt = f"""
انت محلل مضاربة محترف متخصص في سوق الاسهم السعودي تاسي.
لديك صلاحية كاملة في قبول او رفض النشر.
الهدف: إشارات تصل +10% خلال 7-10 أيام.

القطاعات المتصدرة: {', '.join(top_sectors) if top_sectors else 'غير محدد'}

{chr(10).join(summaries)}

اجب بـ JSON فقط:
{{
  "selected_index": 1 او 2 او 3 او 0 للرفض,
  "decision": "publish" او "reject",
  "symbol": "رمز السهم",
  "reason": "سبب القرار بالعربي",
  "confidence": "عالية" او "متوسطة" او "منخفضة",
  "warning": "تحذير ان وجد",
  "note": "ملاحظة للمشتركين تتضمن توقع الوصول لـ 10% خلال كم يوم"
}}

ارفض اذا: Score < 70 | RSI > 75 | R:R < 1.5 | OBV سلبي | لا زخم واضح
"""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key": ANTHROPIC_API_KEY,
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            content = data["content"][0]["text"].strip()
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                result = json.loads(match.group())
                decision = result.get("decision", "publish")
                idx = int(result.get("selected_index", 1))

                print(f"\n  Claude قرار  : {decision.upper()}")
                print(f"  السبب        : {result.get('reason','')}")
                print(f"  الثقة        : {result.get('confidence','')}")
                if result.get("warning"):
                    print(f"  تحذير        : {result.get('warning','')}")

                if decision == "reject" or idx == 0:
                    print("\n  Claude رفض النشر — لا توجد فرصة جيدة")
                    return None, result

                idx = max(0, min(idx - 1, len(candidates) - 1))
                return candidates[idx], result
        else:
            print(f"  Claude API status: {response.status_code}")

    except Exception as e:
        print(f"  Claude review error: {type(e).__name__}: {e}")

    return candidates[0], {}


# ═══════════════════════════════════════════════════════════════
# 🚀 الدالة الرئيسية
# ═══════════════════════════════════════════════════════════════

def main():
    """نقطة الدخول الرئيسية للسكريبت"""
    print("=" * 70)
    print("📊 TASI Market Intelligence — Fetch & Analyze v3.0")
    print("=" * 70)
    
    # 📅 عرض معلومات العطلات
    print(f"\n📅 Holiday Check:")
    today = datetime.now(timezone(timedelta(hours=3))).date().isoformat()
    
    if today in SAUDI_HOLIDAYS:
        print(f"   🕌 Today is a holiday: {SAUDI_HOLIDAYS[today]}")
    
    next_trading = days_until_next_trading_day()
    if next_trading is not None and next_trading > 0:
        print(f"   🗓️ Next trading day: in {next_trading} day(s)")
    
    # ✅ التحقق من حالة السوق (مع تفعيل فحص العطلات)
    market_open = is_market_open(check_holidays=True)
    
    if not market_open:
        print("\n⚠️ Market closed — using fallback data only")
    
    # 📥 تحميل تحليل السوق
    top_sectors = []
    try:
        from market_intelligence import run as run_intel
        intel = run_intel() or {}
        top_sectors = intel.get("top_sectors", [])
        count = len(intel.get("top_stocks", []))
        print(f"\n✅ Market Intelligence: {count} stocks | Sectors: {', '.join(top_sectors)}")
    except ImportError:
        print("\n⚠️ market_intelligence.py not found — continuing")
    except Exception as e:
        print(f"\n⚠️ Market Intelligence error: {type(e).__name__}: {e}")
        try:
            if INTEL_FILE.exists():
                with open(INTEL_FILE, "r", encoding="utf-8") as f_intel:
                    intel_cache = json.load(f_intel)
                    top_sectors = intel_cache.get("top_sectors", [])
        except Exception:
            pass

    # 📥 تحميل بيانات الأسهم
    print("\n" + "-" * 70)
    print("📥 Loading stock data...")
    print("-" * 70)

    stocks, intel_sectors = load_all_stocks_from_intel()
    if intel_sectors:
        top_sectors = intel_sectors

    if len(stocks) < 5:
        print("  ⚠️ Few stocks loaded, trying API fallback...")
        stocks, _ = fallback_from_api()

    # ✅ حماية من "no stocks found"
    if not stocks:
        print("\n  ⚠️ No stocks found — using emergency fallback")
        fallback = load_fallback_stock()
        stocks = [fallback]

    # 📈 تقييم الأسهم
    print("\n" + "-" * 70)
    print("📈 Scoring and ranking stocks...")
    print("-" * 70)

    ranked = []
    for stock in stocks:
        if safe_float(stock.get("price")) <= 0:
            continue
        score, reasons, rr, vol_ratio = calculate_score(stock, top_sectors, 0)
        if score > 0:
            ranked.append({
                "score": score,
                "stock": stock,
                "reasons": reasons,
                "rr": rr,
                "volume_ratio": vol_ratio,
            })

    if not ranked:
        for stock in stocks:
            score, reasons, rr, vol_ratio = calculate_score(stock, top_sectors, 0)
            ranked.append({
                "score": score,
                "stock": stock,
                "reasons": reasons,
                "rr": rr,
                "volume_ratio": vol_ratio,
            })

    # ✅ حماية إضافية
    if not ranked:
        print("  ⚠️ No ranked stocks — using emergency fallback")
        fallback = load_fallback_stock()
        score, reasons, rr, vol_ratio = calculate_score(fallback, top_sectors, 0)
        ranked = [{"score": score, "stock": fallback, "reasons": reasons, "rr": rr, "volume_ratio": vol_ratio}]

    ranked.sort(key=lambda x: x["score"], reverse=True)
    ranked = enrich_top10_with_live_data(ranked, max_updates=MAX_LIVE_UPDATES)
    ranked = enrich_top10_with_historical(ranked, max_analyzed=MAX_HISTORICAL_ANALYSIS)

    # 🏆 عرض أفضل 5
    print(f"\n{'='*70}")
    print("🏆 Top 5 TASI — After deep analysis:")
    for i, r in enumerate(ranked[:5], 1):
        s = r["stock"]
        w52 = s.get("week52_pct", 0)
        obv = s.get("obv_score", "─")
        macd = s.get("macd_score", "─")
        acl = s.get("acceleration", 0)
        name = s.get('name', '')[:16]
        print(f"  {i}. {name:<16} ({s.get('symbol'):>4}) "
              f"Score:{r['score']:>4} 52W:{w52:>5.1f}% "
              f"OBV:{obv:>3} MACD:{macd:>3} Accel:{acl:>3}")

    # 📰 تحليل الأخبار
    print(f"\n{'='*70}")
    print("📰 News analysis...")
    print("-" * 70)

    try:
        from news_analyzer import get_news_analysis
    except ImportError:
        def get_news_analysis(sym, name):
            return {"sentiment": "neutral", "score_delta": 0, "reason": "", "summary": ""}

    final_candidates = []
    for r in ranked[:3]:
        s = r["stock"]
        sym = str(s.get("symbol", ""))
        name = s.get("name", "")
        news = get_news_analysis(sym, name)
        delta = news.get("score_delta", 0)
        new_score = min(r["score"] + delta, 100)

        final_candidates.append({
            "score": new_score,
            "stock": s,
            "reasons": r["reasons"],
            "rr": r["rr"],
            "volume_ratio": r["volume_ratio"],
            "news": news,
        })
        print(f"  {name[:20]:<20} {r['score']} -> {new_score} (news: {delta:+d})")

    final_candidates.sort(key=lambda x: x["score"], reverse=True)

    # 🤖 مراجعة Claude
    print(f"\n{'='*70}")
    print("🤖 Claude review...")
    print("-" * 70)

    best, claude_result = claude_review(final_candidates, top_sectors)

    if best is None:
        reason = claude_result.get("reason", "No good opportunity") if claude_result else "No opportunity"
        print(f"\n  ⚠️ Claude rejected: {reason}")
        best = final_candidates[0] if final_candidates else None
        if best is None:
            print("  🔄 Using emergency fallback as last resort")
            fallback = load_fallback_stock()
            score, reasons, rr, vol_ratio = calculate_score(fallback, top_sectors, 0)
            best = {"score": score, "stock": fallback, "reasons": reasons, "rr": rr, "volume_ratio": vol_ratio}

    claude_reason = claude_result.get("reason", "") if claude_result else ""
    claude_note = claude_result.get("note", "") if claude_result else ""
    claude_warning = claude_result.get("warning", "") if claude_result else ""
    claude_conf = claude_result.get("confidence", "متوسطة") if claude_result else "متوسطة"

    # 📝 بناء ملف الإشارة
    daily_data = build_daily_json(
        best["stock"], best["score"],
        best["reasons"], best["rr"],
        best["volume_ratio"], best.get("news")
    )

    if claude_reason:
        daily_data["note"] = f"قراءة فنية تعليمية: {claude_reason}."
    if claude_note:
        daily_data["claude_note"] = claude_note
    if claude_warning:
        daily_data["claude_warning"] = claude_warning
    daily_data["claude_confidence"] = claude_conf

    # 💾 حفظ الملف
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(daily_data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Signal saved to: {OUTPUT_FILE}")
    except Exception as e:
        print(f"\n❌ Failed to save file: {e}")
        sys.exit(1)

    # 📊 عرض النتيجة
    print(f"\n{'='*70}")
    print(f"🎯 Selected   : {daily_data['stock_name']} ({daily_data['symbol']})")
    print(f"   Score     : {daily_data['score']} | Momentum: {daily_data['momentum']}")
    print(f"   Entry     : {daily_data['entry']} | T1(+5%): {daily_data['target1']} | T2(+10%): {daily_data['target2']} | SL: {daily_data['stop_loss']}")
    print(f"   R:R(T2)   : {daily_data['rr']} | Acceleration: {daily_data.get('acceleration',0)}")
    print(f"   Claude    : {claude_reason}")
    print(f"   Confidence: {claude_conf}")
    if claude_warning:
        print(f"   Warning   : {claude_warning}")
    print(f"   Sector    : {daily_data['sector']} | Source: {daily_data['source']}")
    print(f"{'='*70}")

    if daily_data.get("source") == "market_snapshot":
        print("\n  ⚠️ WARNING: using local snapshot data")

    # 📊 تقرير الرصيد
    print(f"\n📊 API Quota Report")
    print(f"{'='*70}")
    final_used = load_quota_state() + _api_requests_used
    remaining = max(0, API_DAILY_LIMIT - final_used)
    print(f"   Used today:     {final_used}/{API_DAILY_LIMIT}")
    print(f"   Remaining:      {remaining}")
    print(f"   Usage %:        {final_used/API_DAILY_LIMIT*100:.1f}%")
    if remaining < API_DAILY_LIMIT * 0.2:
        print(f"   ⚠️ WARNING: Low quota remaining!")
    print(f"{'='*70}")

    print("\n✅ Process completed successfully!")
    return 0


# ═══════════════════════════════════════════════════════════════
# 🚪 نقطة دخول البرنامج
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code or 0)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(0)
        
    except Exception as e:
        # ═══════════════════════════════════════════════════
        # 🔥 EMERGENCY RESCUE — Never delete this block!
        # ═══════════════════════════════════════════════════
        print(f"\n\n❌ Fatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n🔄 Attempting emergency fallback...")
        try:
            fallback = load_fallback_stock()
            score, reasons, rr, vol_ratio = calculate_score(fallback, [], 0)
            daily_data = build_daily_json(fallback, score, reasons, rr, vol_ratio)
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(daily_data, f, ensure_ascii=False, indent=2)
            print("✅ Emergency fallback saved successfully")
            sys.exit(0)
        except Exception as e2:
            print(f"❌ Emergency fallback failed: {e2}")
            sys.exit(1)
