#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

DAILY_FILE = DATA / "daily.json"
OUT_FILE = DATA / "data_quality.json"

# القائمة الحالية تحتوي عادةً على 18 سهمًا.
# نستخدم 15 لتوفير هامش مؤقت عند تعذر جلب سهم أو سهمين.
MIN_STOCKS = 15
MIN_VALID_RATIO = 0.70


def fnum(x, default=0.0):
    try:
        if x is None or x == "":
            return default

        if isinstance(x, str):
            x = x.replace(",", "").replace("%", "").strip()

        return float(x)
    except Exception:
        return default


def main():
    DATA.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now().isoformat(timespec="seconds")

    if not DAILY_FILE.exists():
        out = {
            "status": "FAIL",
            "score": 0,
            "total_stocks": 0,
            "valid_stocks": 0,
            "invalid_stocks": [],
            "reason": "daily.json غير موجود",
            "generated_at": generated_at,
        }

        OUT_FILE.write_text(
            json.dumps(out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print("❌ Data quality failed: daily.json missing")
        return 1

    try:
        data = json.loads(DAILY_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        out = {
            "status": "FAIL",
            "score": 0,
            "total_stocks": 0,
            "valid_stocks": 0,
            "invalid_stocks": [],
            "reason": f"تعذر قراءة daily.json: {e}",
            "generated_at": generated_at,
        }

        OUT_FILE.write_text(
            json.dumps(out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print("❌ Data quality failed: invalid JSON")
        return 1

    stocks = data.get("stocks", []) if isinstance(data, dict) else []

    if not isinstance(stocks, list):
        stocks = []

    total = len(stocks)
    valid = 0
    issues = []

    for stock in stocks:
        if not isinstance(stock, dict):
            issues.append("INVALID_RECORD")
            continue

        symbol = str(stock.get("symbol", "")).strip()

        price = fnum(
            stock.get("current_price")
            or stock.get("price")
            or stock.get("close")
        )

        volume = fnum(stock.get("volume"))

        value = fnum(
            stock.get("value")
            or stock.get("turnover")
            or stock.get("traded_value")
        )

        if value <= 0 and price > 0 and volume > 0:
            value = price * volume

        if symbol and price > 0 and volume > 0 and value > 0:
            valid += 1
        else:
            issues.append(symbol or "UNKNOWN")

    valid_ratio = valid / total if total else 0
    score = round(valid_ratio * 100, 1)

    status = "PASS"
    reason = "جودة البيانات مقبولة"

    if total < MIN_STOCKS:
        status = "FAIL"
        reason = f"عدد الأسهم المفحوصة قليل: {total}/{MIN_STOCKS}"

    elif valid_ratio < MIN_VALID_RATIO:
        status = "FAIL"
        reason = f"نسبة البيانات الصالحة منخفضة: {score}%"

    out = {
        "status": status,
        "score": score,
        "total_stocks": total,
        "valid_stocks": valid,
        "invalid_stocks": issues[:30],
        "minimum_required_stocks": MIN_STOCKS,
        "minimum_valid_ratio": MIN_VALID_RATIO,
        "reason": reason,
        "generated_at": generated_at,
    }

    OUT_FILE.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    icon = "✅" if status == "PASS" else "❌"

    print(
        f"{icon} Data Quality: {score}% "
        f"— صالح {valid}/{total} — {reason}"
    )

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())