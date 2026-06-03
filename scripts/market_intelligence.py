#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
راصد — جلب بيانات السوق الحقيقي فقط
Production-grade guardrails:
- لا يوجد fallback ولا mock ولا random.
- يوقف المسار إذا لم تتوفر بيانات كافية.
- يوحد الحقول المطلوبة لمحرك الإشارة.
- يحفظ snapshot تاريخي محلي لاستخدام ATR/الدعم/المقاومة لاحقاً.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DAILY_FILE = DATA_DIR / "daily.json"
HISTORY_FILE = DATA_DIR / "market_history.json"

MIN_VALID_STOCKS = int(os.environ.get("MIN_VALID_STOCKS", "15"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "15"))

SECTOR_MAP = {
    "2222": "الطاقة", "2010": "المواد الأساسية", "2350": "المواد الأساسية", "2380": "الطاقة",
    "1120": "المصارف", "1180": "المصارف", "1150": "المصارف", "1060": "المصارف", "1020": "المصارف", "1050": "المصارف", "1140": "المصارف", "1010": "المصارف",
    "4030": "النقل", "4110": "النقل", "7010": "الاتصالات", "7030": "الاتصالات", "7202": "التقنية", "7203": "التقنية", "7205": "التقنية",
    "6015": "الخدمات الاستهلاكية", "6018": "الخدمات الاستهلاكية", "4190": "تجزئة", "4001": "الرعاية الصحية", "4002": "الرعاية الصحية", "4003": "الرعاية الصحية",
    "2200": "المواد الأساسية", "1301": "السلع الرأسمالية", "1302": "السلع الرأسمالية", "1303": "السلع الرأسمالية", "2280": "إنتاج الأغذية", "2286": "إنتاج الأغذية",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        return float(value)
    except Exception:
        return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return int(float(value))
    except Exception:
        return default


def pick(d: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


class MarketIntelligence:
    def __init__(self) -> None:
        self.api_key = os.environ.get("API_KEY", "").strip()
        self.api_url = os.environ.get("API_URL", "https://www.sahmk.sa/api/v1").rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "RasedBot/1.0 (+github-actions)",
            "Accept": "application/json",
        })
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        url = f"{self.api_url}/{endpoint.strip('/')}"
        params = dict(params or {})
        if self.api_key:
            params.setdefault("apikey", self.api_key)
        try:
            r = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                print(f"⚠️ API {r.status_code}: {endpoint}")
                return None
            return r.json()
        except Exception as exc:
            print(f"⚠️ API request failed {endpoint}: {exc}")
            return None

    def _extract_items(self, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("data", "results", "stocks", "items", "quotes", "gainers", "active"):
            val = payload.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
            if isinstance(val, dict):
                nested = self._extract_items(val)
                if nested:
                    return nested
        return []

    def normalize_stock(self, raw: Dict[str, Any], source_endpoint: str) -> Optional[Dict[str, Any]]:
        symbol = str(pick(raw, ["symbol", "ticker", "code", "company_symbol", "stock_symbol"], "")).strip()
        if not symbol:
            return None
        name = str(pick(raw, ["name", "company_name", "companyName", "arabic_name", "short_name"], symbol)).strip()
        sector = str(pick(raw, ["sector", "sector_name", "sectorName"], SECTOR_MAP.get(symbol, ""))).strip()

        price = to_float(pick(raw, ["current_price", "price", "last_price", "last", "close", "lastTradePrice"]), 0)
        prev_close = to_float(pick(raw, ["previous_close", "prev_close", "previousClose", "prevClose", "yesterday_close"]), 0)
        change_pct = to_float(pick(raw, ["change_percent", "change_percentage", "percent_change", "changePercent", "pct_change"]), 0)
        change = to_float(pick(raw, ["change", "price_change", "net_change", "change_value"]), 0)

        high = to_float(pick(raw, ["high", "day_high", "high_price", "highPrice"]), 0)
        low = to_float(pick(raw, ["low", "day_low", "low_price", "lowPrice"]), 0)
        open_price = to_float(pick(raw, ["open", "open_price", "openPrice"]), 0)
        volume = to_int(pick(raw, ["volume", "traded_volume", "tradedVolume", "qty", "quantity"]), 0)
        value = to_float(pick(raw, ["value", "traded_value", "tradedValue", "turnover"]), 0)

        if price <= 0:
            return None
        if prev_close <= 0 and change_pct != 0:
            prev_close = price / (1 + change_pct / 100.0)
        if change_pct == 0 and prev_close > 0:
            change_pct = ((price / prev_close) - 1) * 100
        if change == 0 and prev_close > 0:
            change = price - prev_close

        # لا نعتبر السهم صالحاً للإشارات الاحترافية بدون OHLC وحجم.
        has_ohlc = high > 0 and low > 0 and open_price > 0 and prev_close > 0 and high >= low
        has_liquidity = volume > 0 or value > 0

        return {
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "current_price": round(price, 4),
            "change_percent": round(change_pct, 4),
            "change": round(change, 4),
            "volume": volume,
            "value": round(value, 2),
            "high": round(high, 4),
            "low": round(low, 4),
            "open": round(open_price, 4),
            "previous_close": round(prev_close, 4),
            "rsi": to_float(pick(raw, ["rsi", "RSI"]), 0),
            "volume_ratio": to_float(pick(raw, ["volume_ratio", "volumeRatio", "relative_volume"]), 0),
            "rs_rank": to_float(pick(raw, ["rs_rank", "rsRank", "RS_Rank", "relative_strength_rank"]), 0),
            "timestamp": now_iso(),
            "data_source": "api",
            "source_endpoint": source_endpoint,
            "has_real_ohlc": has_ohlc,
            "has_real_liquidity": has_liquidity,
            "quality_flags": [],
        }

    def fetch_candidates(self) -> List[Dict[str, Any]]:
        endpoints: List[Tuple[str, Dict[str, Any]]] = [
            ("market/gainers", {"limit": 50}),
            ("market/volume", {"limit": 50}),
            ("market/active", {"limit": 50}),
            ("market/quotes", {"limit": 250}),
            ("stocks", {"limit": 250}),
        ]
        seen = set()
        out: List[Dict[str, Any]] = []
        for endpoint, params in endpoints:
            payload = self._request(endpoint, params)
            items = self._extract_items(payload)
            if not items:
                print(f"⚠️ {endpoint}: لا توجد بيانات قابلة للقراءة")
                continue
            print(f"✅ {endpoint}: {len(items)} سجل")
            for raw in items:
                stock = self.normalize_stock(raw, endpoint)
                if not stock or stock["symbol"] in seen:
                    continue
                seen.add(stock["symbol"])
                out.append(stock)
            time.sleep(0.2)
        return out

    def load_history(self) -> Dict[str, List[Dict[str, Any]]]:
        if not HISTORY_FILE.exists():
            return {}
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_history_snapshot(self, stocks: List[Dict[str, Any]]) -> None:
        history = self.load_history()
        today = datetime.now().strftime("%Y-%m-%d")
        for s in stocks:
            if not s.get("has_real_ohlc"):
                continue
            sym = s["symbol"]
            row = {
                "date": today,
                "open": s["open"],
                "high": s["high"],
                "low": s["low"],
                "close": s["current_price"],
                "previous_close": s["previous_close"],
                "volume": s["volume"],
                "value": s["value"],
            }
            arr = history.setdefault(sym, [])
            arr = [x for x in arr if x.get("date") != today]
            arr.append(row)
            arr.sort(key=lambda x: x.get("date", ""))
            history[sym] = arr[-260:]
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    def run(self) -> int:
        print("=" * 60)
        print("🧠 راصد — جلب بيانات السوق الحقيقي فقط")
        print("=" * 60)
        if not self.api_key:
            print("❌ API_KEY غير موجود. تم إيقاف النشر بدلاً من استخدام fallback.")
            return 1

        stocks = self.fetch_candidates()
        valid = [s for s in stocks if s.get("has_real_ohlc") and s.get("has_real_liquidity")]

        if len(valid) < MIN_VALID_STOCKS:
            print(f"❌ بيانات غير كافية: {len(valid)} سهم صالح فقط، المطلوب {MIN_VALID_STOCKS} على الأقل")
            output = {
                "stocks": valid,
                "timestamp": now_iso(),
                "timezone": "Asia/Riyadh",
                "market_status": "open",
                "total_stocks": len(valid),
                "data_source": "api",
                "quality_status": "blocked_insufficient_real_data",
                "blocked_reason": f"valid_stocks {len(valid)} < {MIN_VALID_STOCKS}",
            }
            DAILY_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1

        self.save_history_snapshot(valid)
        output = {
            "stocks": valid,
            "timestamp": now_iso(),
            "timezone": "Asia/Riyadh",
            "market_status": "open",
            "total_stocks": len(valid),
            "data_source": "api",
            "quality_status": "real_api_data",
        }
        DAILY_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ تم حفظ {len(valid)} سهم ببيانات OHLC وحجم حقيقية")
        return 0


if __name__ == "__main__":
    sys.exit(MarketIntelligence().run())
