#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
راصد — جلب بيانات السوق
UPGRADE:
- يُضيف حقل data_source: 'api' | 'scrape' | 'fallback'
- Fallback لا يُشغّل النشر (generate_signal.py سيرفضه)
- sector يُملأ من القاموس إذا فات الـ API
- RSI يُحسب من change_percent عند غيابه
- حُذف التعديل العشوائي على الأسعار
"""

import json
import os
import sys
import requests
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
import re

SECTOR_MAP = {
    "2222": "الطاقة",           "2010": "البتروكيماويات",  "2350": "البتروكيماويات",
    "2380": "البتروكيماويات",   "2050": "الاستهلاكية",     "4002": "إنتاج الأغذية",
    "1120": "المصارف",          "1180": "المصارف",          "1150": "المصارف",
    "1060": "المصارف",          "1020": "المصارف",          "1050": "المصارف",
    "1140": "المصارف",          "1010": "المصارف",          "1211": "التأمين",
    "4030": "الاستثمار",        "4280": "الاستثمار",        "4130": "الاستثمار",
    "4110": "اللوجستيات",       "7010": "الاتصالات",        "7030": "الاتصالات",
    "7202": "التقنية",          "6017": "التقنية",           "6018": "الترفيه",
    "4190": "التجزئة",          "4240": "التجزئة",          "4250": "العقارات",
    "5110": "الطاقة",           "2090": "الكيماويات",        "2230": "الكيماويات",
    "3008": "الاستثمار",        "1303": "الصناعات",          "1820": "الاستثمار",
    "1831": "الموارد البشرية",  "1834": "الموارد البشرية",  "4061": "الاستثمار",
    "6015": "المطاعم",          "7205": "الخدمات",           "2030": "الصناعات",
    "2020": "الصناعات",         "2060": "الصناعات",          "2280": "الكيماويات",
    "4001": "العقارات",         "4003": "التجزئة",
}


class MarketIntelligence:
    def __init__(self):
        self.api_key  = os.environ.get("API_KEY", "")
        self.api_url  = os.environ.get("API_URL", "https://www.sahmk.sa/api/v1")
        self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session  = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept":     "application/json, text/html",
        })

    def _rsi_estimate(self, change_pct) -> float:
        return round(min(75.0, max(28.0, 50.0 + float(change_pct or 0) * 3)), 2)

    def _sector(self, symbol, api_sector="") -> str:
        if api_sector and str(api_sector).strip():
            return str(api_sector).strip()
        return SECTOR_MAP.get(str(symbol), "متعدد")

    def fetch_from_sahmk_api(self):
        if not self.api_key:
            return None
        print("📡 Fetching from Sahmk API...")
        headers = {
            "User-Agent":    "Mozilla/5.0",
            "Accept":        "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key":     self.api_key,
        }
        endpoints = [
            ("market/volume/",  30, 2.5),
            ("market/gainers/", 20, 2.0),
            ("market/losers/",  20, 1.8),
        ]
        all_items, seen = [], set()
        for endpoint, limit, src_vol in endpoints:
            url = f"{self.api_url}/{endpoint}"
            try:
                resp = self.session.get(url, headers=headers,
                                        params={"apikey": self.api_key, "limit": limit}, timeout=10)
                if resp.status_code == 200:
                    raw   = resp.json()
                    items = raw if isinstance(raw, list) else raw.get("data", raw.get("stocks", []))
                    for item in items:
                        sym = item.get("symbol", item.get("ticker", ""))
                        if sym and sym not in seen:
                            item["_src_vol"] = src_vol
                            all_items.append(item)
                            seen.add(sym)
                    print(f"   ✅ {endpoint}: {len(items)} أسهم")
                elif resp.status_code == 404:
                    print(f"   ⚠️ {endpoint}: 404")
                else:
                    print(f"   ❌ {endpoint}: HTTP {resp.status_code}")
            except Exception as e:
                print(f"   ❌ {endpoint}: {e}")

        if all_items:
            stocks = self._normalize(all_items, "api")
            if stocks:
                print(f"✅ Sahmk API: {len(stocks)} سهم")
                return stocks
        return None

    def fetch_from_argaam(self):
        print("📰 Fetching from Argaam...")
        try:
            resp = self.session.get("https://www.argaam.com/ar/market", timeout=15)
            if resp.status_code != 200:
                return None
            soup, stocks = BeautifulSoup(resp.text, "html.parser"), []
            for row in soup.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                try:
                    symbol = cells[0].get_text(strip=True)
                    name   = cells[1].get_text(strip=True)
                    price  = float(re.sub(r"[^\d.]", "", cells[2].get_text()) or 0)
                    change = float(re.sub(r"[^\d.-]", "", cells[3].get_text()) or 0)
                    if symbol and price > 0:
                        stocks.append({
                            "symbol":         symbol,
                            "name":           name,
                            "sector":         self._sector(symbol),
                            "current_price":  price,
                            "change_percent": change,
                            "rsi":            self._rsi_estimate(change),
                            "volume_ratio":   round(1.0 + abs(change) / 10, 2),
                            "rs_rank":        round(min(100, max(0, 50 + change * 2)), 1),
                            "timestamp":      datetime.now().isoformat(),
                            "data_source":    "scrape",
                        })
                except Exception:
                    continue
            if stocks:
                print(f"✅ Argaam: {len(stocks)} stocks")
                return stocks
        except Exception as e:
            print(f"❌ Argaam: {e}")
        return None

    def get_fallback_data(self):
        """بيانات احتياطية — data_source=fallback → لن يتم النشر"""
        print("⚠️  FALLBACK data — posting will be BLOCKED by generate_signal.py")
        return [
            {"symbol": "2222", "name": "أرامكو السعودية",    "sector": "الطاقة",        "current_price": 30.85, "change_percent": 1.2,  "rsi": 58.3, "volume_ratio": 1.80, "rs_rank": 72},
            {"symbol": "1120", "name": "مصرف الراجحي",       "sector": "المصارف",        "current_price": 86.40, "change_percent": 0.8,  "rsi": 61.2, "volume_ratio": 1.50, "rs_rank": 68},
            {"symbol": "2010", "name": "سابك",               "sector": "البتروكيماويات", "current_price": 94.20, "change_percent": -0.3, "rsi": 47.8, "volume_ratio": 1.10, "rs_rank": 55},
            {"symbol": "2050", "name": "صافولا",             "sector": "الاستهلاكية",    "current_price": 27.15, "change_percent": 2.4,  "rsi": 64.5, "volume_ratio": 2.30, "rs_rank": 81},
            {"symbol": "1180", "name": "البنك الأهلي",       "sector": "المصارف",        "current_price": 42.80, "change_percent": 1.1,  "rsi": 59.7, "volume_ratio": 1.60, "rs_rank": 70},
            {"symbol": "2380", "name": "رابغ للتكرير",       "sector": "البتروكيماويات", "current_price": 18.45, "change_percent": 3.2,  "rsi": 68.1, "volume_ratio": 2.80, "rs_rank": 85},
            {"symbol": "4002", "name": "المراعي",            "sector": "إنتاج الأغذية", "current_price": 55.30, "change_percent": 0.5,  "rsi": 53.2, "volume_ratio": 1.30, "rs_rank": 62},
            {"symbol": "7010", "name": "الاتصالات السعودية", "sector": "الاتصالات",      "current_price": 38.90, "change_percent": -0.8, "rsi": 44.6, "volume_ratio": 0.90, "rs_rank": 48},
            {"symbol": "4030", "name": "أسترا الصناعية",     "sector": "الاستثمار",      "current_price": 22.60, "change_percent": 1.8,  "rsi": 62.4, "volume_ratio": 2.10, "rs_rank": 76},
            {"symbol": "1010", "name": "بنك الرياض",         "sector": "المصارف",        "current_price": 31.25, "change_percent": 0.3,  "rsi": 51.8, "volume_ratio": 1.20, "rs_rank": 58},
        ]

    def _normalize(self, items: list, source: str) -> list:
        stocks = []
        for item in items:
            try:
                sym    = item.get("symbol", "")
                change = float(item.get("change_percent", item.get("changePercent", 0)) or 0)
                price  = float(item.get("price", item.get("current_price", 0)) or 0)
                rsi_raw = item.get("rsi") or item.get("RSI")
                rsi     = float(rsi_raw) if rsi_raw else self._rsi_estimate(change)
                stocks.append({
                    "symbol":         sym,
                    "name":           item.get("name", ""),
                    "sector":         self._sector(sym, item.get("sector", item.get("sector_name", ""))),
                    "current_price":  price,
                    "change_percent": change,
                    "rsi":            round(rsi, 2),
                    "volume_ratio":   float(item.get("_src_vol", item.get("volume_ratio", 1.0))),
                    "rs_rank":        float(item.get("rs_rank", 50)),
                    "timestamp":      datetime.now().isoformat(),
                    "data_source":    source,
                })
            except Exception:
                continue
        return stocks

    def run(self):
        print("=" * 60)
        print("🧠 راصد — جلب بيانات السوق")
        print("=" * 60)

        stocks, source = None, "fallback"

        if self.api_key:
            stocks = self.fetch_from_sahmk_api()
            if stocks:
                source = "api"

        if not stocks:
            stocks = self.fetch_from_argaam()
            if stocks:
                source = "scrape"

        if not stocks:
            stocks = self.get_fallback_data()
            source = "fallback"

        for s in stocks:
            if not s.get("sector", "").strip():
                s["sector"] = self._sector(s.get("symbol", ""))
            s["data_source"] = source

        output = {
            "stocks":        stocks,
            "timestamp":     datetime.now().isoformat(),
            "timezone":      "Asia/Riyadh",
            "market_status": "open",
            "total_stocks":  len(stocks),
            "data_source":   source,
        }

        daily_file = self.data_dir / "daily.json"
        with open(daily_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        positive = sum(1 for s in stocks if s.get("change_percent", 0) > 0)
        negative = sum(1 for s in stocks if s.get("change_percent", 0) < 0)
        print(f"\n✅ إجمالي: {len(stocks)} سهم | مصدر: {source}")
        print(f"📈 موجب: {positive}   📉 سالب: {negative}")

        if source == "fallback":
            print("🚫 تحذير: بيانات fallback — لن يتم النشر")
            return 1

        print(f"💾 محفوظ في: {daily_file}")
        return 0


def main():
    sys.exit(MarketIntelligence().run())

if __name__ == "__main__":
    main()
