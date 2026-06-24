#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

DAILY_FILE = DATA / "daily.json"
OUT_FILE = DATA / "data_quality.json"

MIN_STOCKS = 25
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
    DATA.mkdir(exist_ok=True)

    if not DAILY_FILE.exists():
        out = {
            "status": "FAIL",
            "score": 0,
            "reason": "daily.json غير موجود",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
        OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print("❌ Data quality failed: daily.json missing")
        return 1

    try:
        data = json.loads(DAILY_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        out = {
            "status": "FAIL",
            "score": 0,
            "reason": f"تعذر قراءة daily.json: {e}",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
        OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print("❌ Data quality failed: invalid JSON")
        return 1

    stocks = data.get("stocks", []) if isinstance(data, dict) else []
    total = len(stocks)

    valid = 0
    issues = []

    for s in stocks:
        symbol = str(s.get("symbol", "")).strip()
        price = fnum(s.get("current_price") or s.get("price"))
        volume = fnum(s.get("volume"))
        value = fnum(s.get("value") or s.get("turnover")) or price * volume

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
        "reason": reason,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'✅' if status == 'PASS' else '❌'} Data Quality: {score}% — {reason}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())