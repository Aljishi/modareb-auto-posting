"""
log_signal.py — يسجل الإشارة في السجل التاريخي
"""

import json
import csv
import os
from datetime import datetime

DATA_FILE = "data/daily.json"
LOG_FILE  = "data/signals_log.csv"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

file_exists = os.path.exists(LOG_FILE)

# FIX: check both key names for compatibility
symbol = data.get("stock_symbol", data.get("symbol", ""))

row = {
    "date":         datetime.now().strftime("%Y-%m-%d"),
    "time":         datetime.now().strftime("%H:%M"),
    "signal_type":  data.get("type", "يومية"),
    "stock_name":   data.get("stock_name", ""),
    "symbol":       symbol,
    "sector":       data.get("sector", ""),
    "price":        data.get("price", data.get("current_price", "")),
    "entry":        data.get("entry", data.get("entry_point", "")),
    "target1":      data.get("target1", ""),
    "target2":      data.get("target2", ""),
    "stop_loss":    data.get("stop_loss", ""),
    "rsi":          data.get("rsi", ""),
    "volume_ratio": data.get("volume_ratio", ""),
    "score":        data.get("score", ""),
    "rr":           data.get("rr", ""),
    "momentum":     data.get("momentum", ""),
    "rs_rank":      data.get("rs_rank", ""),
    "source":       data.get("source", ""),
    "status":       "open",
    "close_price":  "",
    "close_date":   "",
    "result":       "",
}

with open(LOG_FILE, "a", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=row.keys())
    if not file_exists:
        writer.writeheader()
    writer.writerow(row)

print(f"✅ إشارة {data.get('stock_name')} ({symbol}) سُجّلت")
print(f"   النوع  : {row['signal_type']}")
print(f"   القطاع : {row['sector']}")
print(f"   Score  : {row['score']} | R:R: {row['rr']}")

# ─── FIX: حارس النشر المزدوج ────────────────────────────────
# كتابة علامة "posted_today" في daily.json حتى تمنع should_post.py
# من السماح بنشر ثانٍ في نفس اليوم لنفس الإشارة.
try:
    data["posted_today"] = True
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("🔒 تم تسجيل posted_today=True في daily.json")
except Exception as e:
    print(f"⚠️ تعذّر كتابة posted_today: {e}")
# ────────────────────────────────────────────────────────────
