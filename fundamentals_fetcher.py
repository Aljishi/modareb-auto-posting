"""
fundamentals_fetcher.py
=======================
يجلب ويحدّث البيانات الأساسية لأسهم تاسي:
  - من sahmk.sa API (ما هو متاح)
  - يدمجها مع fundamentals.json الموجود
  - يحسب fundamental_score لكل سهم

يُشغَّل أسبوعياً من weekly-report job.
"""

import os
import json
import requests
from datetime import datetime

API_KEY   = os.environ.get("API_KEY")
API_URL   = os.environ.get("API_URL", "https://app.sahmk.sa/api/v1")
HEADERS   = {"X-API-Key": API_KEY} if API_KEY else {}
FUND_FILE = "data/fundamentals.json"


def safe_float(v, default=0.0):
    try: return float(v)
    except: return default


def get(endpoint, params=None):
    try:
        r = requests.get(f"{API_URL}{endpoint}", headers=HEADERS,
                         params=params or {}, timeout=15)
        if r.status_code == 200: return r.json()
    except Exception as e:
        print(f"  error {endpoint}: {e}")
    return None


def load_fundamentals():
    try:
        with open(FUND_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"stocks": {}, "sector_pe": {}, "updated_at": ""}


def try_fetch_from_api(symbol):
    """يحاول جلب P/E وEPS من sahmk.sa إذا كانت متاحة"""
    data = get(f"/quote/{symbol}/")
    if not data:
        return None
    s = data if isinstance(data, dict) else (data[0] if isinstance(data, list) and data else None)
    if not s:
        return None
    result = {}
    pe  = safe_float(s.get("pe") or s.get("p_e") or s.get("pe_ratio"))
    eps = safe_float(s.get("eps") or s.get("earnings_per_share"))
    div = safe_float(s.get("dividend_yield") or s.get("div_yield"))
    if pe  > 0: result["pe"]        = round(pe, 2)
    if eps > 0: result["eps"]       = round(eps, 2)
    if div > 0: result["div_yield"] = round(div, 2)
    return result if result else None


def calc_fundamental_score(stock_data, sector):
    """
    نقطة الأساسيات من 0-25:
    P/E vs القطاع → +10
    نمو الأرباح   → +8
    ROE            → +4
    الديون         → +3
    """
    if not stock_data:
        return 0, "لا بيانات أساسية"

    score   = 0
    details = []
    fundamentals   = load_fundamentals()
    sector_avg_pe  = fundamentals.get("sector_pe", {}).get(sector, 20.0)

    pe         = stock_data.get("pe", 0)
    rev_growth = stock_data.get("rev_growth", 0)
    roe        = stock_data.get("roe", 0)
    debt_eq    = stock_data.get("debt_eq", 999)
    div_yield  = stock_data.get("div_yield", 0)

    # P/E مقارنة بالقطاع
    if pe > 0 and sector_avg_pe > 0:
        ratio = pe / sector_avg_pe
        if ratio <= 0.7:
            score += 10; details.append(f"P/E {pe:.1f} رخيص ({ratio:.0%} من القطاع)")
        elif ratio <= 0.9:
            score += 7;  details.append(f"P/E {pe:.1f} أقل من القطاع")
        elif ratio <= 1.1:
            score += 4;  details.append(f"P/E {pe:.1f} عادل")
        elif ratio > 1.5:
            score -= 3;  details.append(f"P/E {pe:.1f} مرتفع")

    # نمو الإيرادات
    if rev_growth > 20:
        score += 8; details.append(f"نمو إيرادات قوي +{rev_growth:.1f}%")
    elif rev_growth > 10:
        score += 6; details.append(f"نمو إيرادات جيد +{rev_growth:.1f}%")
    elif rev_growth > 0:
        score += 3; details.append(f"نمو إيرادات +{rev_growth:.1f}%")
    elif rev_growth < -10:
        score -= 5; details.append(f"تراجع إيرادات {rev_growth:.1f}%")

    # ROE
    if roe > 20:
        score += 4; details.append(f"ROE {roe:.1f}% ممتاز")
    elif roe > 12:
        score += 2; details.append(f"ROE {roe:.1f}%")
    elif roe < 5:
        score -= 3

    # الديون
    if debt_eq < 0.3:
        score += 3; details.append("ديون منخفضة")
    elif debt_eq > 1.5:
        score -= 2; details.append("ديون مرتفعة")

    # توزيعات
    if div_yield > 4:
        score += 3; details.append(f"عائد {div_yield:.1f}%")
    elif div_yield > 2:
        score += 1

    return max(0, min(score, 25)), " + ".join(details) if details else "تحليل أساسي"


def get_fundamental_data(symbol, sector=""):
    """الواجهة الرئيسية — تُستدعى من fetch_api_data.py"""
    fundamentals = load_fundamentals()
    stock_data   = fundamentals.get("stocks", {}).get(str(symbol))
    if not stock_data:
        api_data = try_fetch_from_api(str(symbol))
        if api_data:
            stock_data = api_data
    score, detail = calc_fundamental_score(stock_data, sector)
    return score, detail, stock_data


def update_from_api():
    """يُشغَّل أسبوعياً لتحديث الأرقام من API"""
    fundamentals = load_fundamentals()
    stocks_data  = fundamentals.get("stocks", {})
    updated = 0
    print(f"\n{'='*55}\nتحديث البيانات الأساسية\n{'='*55}")
    for symbol in list(stocks_data.keys()):
        api_data = try_fetch_from_api(symbol)
        if api_data:
            stocks_data[symbol].update(api_data)
            updated += 1
    fundamentals["stocks"]     = stocks_data
    fundamentals["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(FUND_FILE, "w", encoding="utf-8") as f:
        json.dump(fundamentals, f, ensure_ascii=False, indent=2)
    print(f"  تم تحديث {updated} سهم | إجمالي: {len(stocks_data)}")


def generate_report():
    """تقرير الأسهم الأفضل أساسياً"""
    fundamentals = load_fundamentals()
    results = []
    sector_map = {
        "البنوك":["1010","1020","1030","1050","1060","1080","1120","1150"],
        "البتروكيماويات":["2010","2020","2060","2222","2223","2230"],
        "الاتصالات":["7010","7020","7030"],
        "التقنية":["9516","9526","9527"],
    }
    for sym, data in fundamentals.get("stocks", {}).items():
        sector = next((s for s,syms in sector_map.items() if sym in syms), "")
        score, detail, _ = calc_fundamental_score(data, sector)
        results.append({"symbol":sym,"name":data.get("name",sym),"score":score,
                        "pe":data.get("pe",0),"roe":data.get("roe",0),
                        "growth":data.get("rev_growth",0)})
    results.sort(key=lambda x: x["score"], reverse=True)
    print(f"\n{'='*60}\nأفضل الأسهم أساسياً\n{'='*60}")
    print(f"  {'السهم':<20} {'Score':>5} {'P/E':>6} {'ROE':>6} {'نمو':>7}")
    print("-"*52)
    for r in results[:15]:
        print(f"  {r['name'][:20]:<20} {r['score']:>5} "
              f"{r['pe']:>5.1f} {r['roe']:>5.1f}% {r['growth']:>+6.1f}%")
    return results


if __name__ == "__main__":
    update_from_api()
    generate_report()
