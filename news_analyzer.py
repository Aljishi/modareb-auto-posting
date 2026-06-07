import os
import json
import re
import requests
from datetime import datetime, timezone, timedelta

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_API_URL    = "https://api.anthropic.com/v1/messages"
NEWS_FILE         = "data/news_cache.json"

KSA = timezone(timedelta(hours=3))

NEUTRAL_RESULT = {
    "sentiment":   "neutral",
    "score_delta": 0,
    "reason":      "لا توجد اخبار حديثة",
    "summary":     "",
    "news_count":  0,
}


def safe_get(url, headers=None, timeout=10):
    try:
        r = requests.get(url, headers=headers or {}, timeout=timeout)
        if r.status_code == 200 and r.text:
            return r.text
    except Exception as e:
        print(f"  fetch error {url[:50]}: {e}")
    return None


def is_arabic(text):
    return any(c in text for c in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي")


def extract_news_from_html(html, patterns):
    """✅ إصلاح: دالة موحدة تستخرج الأخبار وتتحقق من صحتها"""
    if not html:
        return []
    news = []
    seen = set()
    for pattern in patterns:
        for m in re.findall(pattern, html, re.IGNORECASE | re.DOTALL):
            text = re.sub(r'<[^>]+>', '', m).strip()
            text = re.sub(r'\s+', ' ', text)
            if len(text) > 15 and is_arabic(text) and text not in seen:
                seen.add(text)
                news.append(text)
    return news[:5]


def fetch_tadawul_disclosures(symbol):
    url = (
        "https://www.saudiexchange.sa/wps/portal/saudiexchange/"
        "newsandreports/company-announcements"
        f"?companySymbol={symbol}"
    )
    headers = {
        "User-Agent":      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "Accept":          "text/html,application/xhtml+xml",
        "Accept-Language": "ar,en;q=0.9",
    }
    html = safe_get(url, headers)
    patterns = [
        r'class="announcement-title[^"]*"[^>]*>([^<]+)<',
        r'<td[^>]*class="[^"]*title[^"]*"[^>]*>([^<]{15,200})<',
        r'<h\d[^>]*>([^<]{20,200})</h\d>',
    ]
    result = extract_news_from_html(html, patterns)
    print(f"  تداول: {len(result)} خبر")
    return result


def fetch_argaam_news(symbol):
    url = f"https://www.argaam.com/ar/stocks/stockdetail/newslist/{symbol}"
    headers = {
        "User-Agent":      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "Accept":          "text/html",
        "Accept-Language": "ar",
        "Referer":         "https://www.argaam.com/",
    }
    html = safe_get(url, headers)
    patterns = [
        r'class="news-title[^"]*"[^>]*>([^<]+)<',
        r'class="article-title[^"]*"[^>]*>([^<]+)<',
        r'"title"\s*:\s*"([^"]{20,200})"',
    ]
    result = extract_news_from_html(html, patterns)
    print(f"  أرقام: {len(result)} خبر")
    return result


def fetch_mubasher_news(symbol):
    url = f"https://www.mubasher.info/countries/sa/stocks/{symbol}/news"
    headers = {
        "User-Agent":      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        "Accept":          "text/html",
        "Accept-Language": "ar",
    }
    html = safe_get(url, headers)
    patterns = [
        r'class="[^"]*news[^"]*title[^"]*"[^>]*>([^<]+)<',
        r'class="[^"]*headline[^"]*"[^>]*>([^<]+)<',
        r'"headline"\s*:\s*"([^"]{20,200})"',
    ]
    result = extract_news_from_html(html, patterns)
    print(f"  مباشر: {len(result)} خبر")
    return result


def analyze_with_claude(symbol, stock_name, news_items):
    """✅ إصلاح: معالجة أفضل للحالات الفارغة وأخطاء API"""
    if not news_items:
        return NEUTRAL_RESULT.copy()

    if not ANTHROPIC_API_KEY:
        print("  ANTHROPIC_API_KEY missing — تخطي تحليل الاخبار")
        return NEUTRAL_RESULT.copy()

    news_text = "\n".join([f"- {n}" for n in news_items])

    prompt = f"""انت محلل مالي متخصص في سوق الاسهم السعودي.

السهم: {stock_name} ({symbol})

الاخبار والافصاحات الاخيرة:
{news_text}

حلل هذه الاخبار واجب بـ JSON فقط بهذا الشكل بالضبط:
{{
  "sentiment": "positive" او "negative" او "neutral",
  "score_delta": رقم بين -15 و 15,
  "reason": "جملة واحدة عربية تشرح سبب التقييم",
  "summary": "ملخص عربي قصير للاخبار المؤثرة"
}}

قواعد:
- positive و score_delta موجب (+5 الى +15): اخبار ارباح، توزيعات، عقود، توسع
- negative و score_delta سالب (-5 الى -15): خسائر، غرامات، مشاكل تنظيمية
- neutral و score_delta صفر: اخبار عامة لا تؤثر على السعر
- اجب بـ JSON فقط بدون اي نص اضافي"""

    try:
        response = requests.post(
            CLAUDE_API_URL,
            headers={
                "Content-Type":      "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key":         ANTHROPIC_API_KEY,
            },
            json={
                "model":      "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "messages":   [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if response.status_code == 200:
            data    = response.json()
            content = data["content"][0]["text"].strip()
            # ✅ إصلاح: تنظيف backticks قبل parse
            content = re.sub(r'```json|```', '', content).strip()
            match   = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                result = json.loads(match.group())
                result["score_delta"] = max(-15, min(15, int(result.get("score_delta", 0))))
                # ✅ إصلاح: تحقق من وجود الحقول الأساسية
                result.setdefault("sentiment",   "neutral")
                result.setdefault("reason",      "")
                result.setdefault("summary",     "")
                return result
            else:
                print("  Claude: لم يرجع JSON صحيح — محايد")
        else:
            print(f"  Claude news API status: {response.status_code}")

    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
    except Exception as e:
        print(f"  Claude API error: {e}")

    # ✅ إصلاح: دائماً يرجع neutral عند الفشل بدل None
    return {
        "sentiment":   "neutral",
        "score_delta": 0,
        "reason":      "تعذر تحليل الاخبار",
        "summary":     "",
    }


def get_news_analysis(symbol, stock_name):
    print(f"  جلب اخبار {stock_name} ({symbol})...")

    # ✅ إصلاح: كل مصدر مستقل — إذا فشل أحدهم لا يوقف الباقين
    news = []
    try:
        news += fetch_tadawul_disclosures(symbol)
    except Exception as e:
        print(f"  تداول error: {e}")

    if len(news) < 3:
        try:
            news += fetch_argaam_news(symbol)
        except Exception as e:
            print(f"  أرقام error: {e}")

    if len(news) < 3:
        try:
            news += fetch_mubasher_news(symbol)
        except Exception as e:
            print(f"  مباشر error: {e}")

    # إزالة المكررات
    seen, unique = set(), []
    for n in news:
        key = n[:50]
        if key not in seen:
            seen.add(key)
            unique.append(n)

    print(f"  إجمالي أخبار فريدة: {len(unique)}")

    # ✅ إصلاح: إذا لا أخبار نرجع neutral فوراً بدون Claude call
    if not unique:
        result = NEUTRAL_RESULT.copy()
        result["news_count"] = 0
        _save_cache(symbol, result)
        return result

    analysis = analyze_with_claude(symbol, stock_name, unique[:5])
    analysis["news_count"] = len(unique)
    analysis["news_items"] = unique[:3]

    sentiment_ar = {
        "positive": "ايجابي",
        "negative": "سلبي",
        "neutral":  "محايد",
    }.get(analysis.get("sentiment", "neutral"), "محايد")

    delta = analysis.get("score_delta", 0)
    sign  = "+" if delta >= 0 else ""
    print(f"  الاخبار: {sentiment_ar} | Score: {sign}{delta}")
    if analysis.get("reason"):
        print(f"  السبب: {analysis['reason']}")

    _save_cache(symbol, analysis)
    return analysis


def _save_cache(symbol, analysis):
    """✅ إصلاح: حفظ منفصل مع معالجة الخطأ"""
    try:
        cache = {
            "symbol":       symbol,
            "generated_at": datetime.now(KSA).strftime("%Y-%m-%d %H:%M"),
            "analysis":     analysis,
        }
        with open(NEWS_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  cache save error: {e}")


if __name__ == "__main__":
    import sys
    sym  = sys.argv[1] if len(sys.argv) > 1 else "2222"
    name = sys.argv[2] if len(sys.argv) > 2 else "اختبار"
    result = get_news_analysis(sym, name)
    print(json.dumps(result, ensure_ascii=False, indent=2))
