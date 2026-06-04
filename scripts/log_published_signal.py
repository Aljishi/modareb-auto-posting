#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("data")
PUBLISHED_FILE = DATA_DIR / "published_signals.csv"
VALIDATED_FILE = DATA_DIR / "validated_signals.json"
GOLDEN_FILE = DATA_DIR / "golden_signals.json"

FIELDS = [
    "signal_id", "signal_type", "symbol", "name", "published_at",
    "entry", "target1", "target2", "stop_loss",
    "target1_percent", "target2_percent", "stop_loss_percent",
    "rased_score", "confidence", "risk_level", "tier",
    "expected_holding_period", "max_holding_days",
    "status", "result", "closed_at",
    "days_to_tp1", "days_to_tp2", "highest_price", "lowest_price",
    "source_file"
]


def fnum(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(str(v).replace(",", "").replace("%", "").strip())
    except Exception:
        return default


def load_existing_ids():
    if not PUBLISHED_FILE.exists():
        return set()

    ids = set()
    with open(PUBLISHED_FILE, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("signal_id"):
                ids.add(row["signal_id"])

    return ids


def append_rows(rows):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    exists = PUBLISHED_FILE.exists()

    with open(PUBLISHED_FILE, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)

        if not exists:
            writer.writeheader()

        for row in rows:
            writer.writerow(row)


def extract_signals(path):
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        if "validated_signals" in data:
            return data["validated_signals"]
        if "signals" in data:
            return data["signals"]
        if "golden_signals" in data:
            return data["golden_signals"]

    return []


def build_row(signal, signal_type, source_file):
    symbol = str(signal.get("stock_symbol") or signal.get("symbol") or "").strip()
    name = signal.get("stock_name") or signal.get("name") or symbol

    now = datetime.now().isoformat(timespec="seconds")

    signal_id = signal.get("signal_id")
    if not signal_id:
        signal_id = f"{signal_type}-{datetime.now().strftime('%Y%m%d-%H%M')}-{symbol}"

    return {
        "signal_id": signal_id,
        "signal_type": signal_type,
        "symbol": symbol,
        "name": name,
        "published_at": now,

        "entry": fnum(signal.get("entry_point") or signal.get("entry")),
        "target1": fnum(signal.get("target1") or signal.get("tp1")),
        "target2": fnum(signal.get("target2") or signal.get("tp2")),
        "stop_loss": fnum(signal.get("stop_loss") or signal.get("sl")),

        "target1_percent": fnum(signal.get("target1_percent") or signal.get("tp1_pct")),
        "target2_percent": fnum(signal.get("target2_percent") or signal.get("tp2_pct")),
        "stop_loss_percent": fnum(signal.get("stop_loss_percent") or signal.get("sl_pct")),

        "rased_score": fnum(signal.get("rased_score") or signal.get("score")),
        "confidence": signal.get("ai_confidence") or signal.get("confidence") or "",
        "risk_level": signal.get("risk_level_ar") or signal.get("risk_level") or "",
        "tier": signal.get("tier") or "",

        "expected_holding_period": signal.get("expected_holding_period") or signal.get("holding_period") or "1-7 أيام",
        "max_holding_days": int(fnum(signal.get("max_holding_days"), 7)),

        "status": "OPEN",
        "result": "",
        "closed_at": "",
        "days_to_tp1": "",
        "days_to_tp2": "",
        "highest_price": "",
        "lowest_price": "",
        "source_file": source_file,
    }


def main():
    existing_ids = load_existing_ids()
    rows_to_add = []

    normal_signals = extract_signals(VALIDATED_FILE)
    for sig in normal_signals:
        row = build_row(sig, "NORMAL", str(VALIDATED_FILE))
        if row["signal_id"] not in existing_ids and row["symbol"]:
            rows_to_add.append(row)
            existing_ids.add(row["signal_id"])

    golden_signals = extract_signals(GOLDEN_FILE)
    for sig in golden_signals:
        row = build_row(sig, "GOLDEN", str(GOLDEN_FILE))
        if row["signal_id"] not in existing_ids and row["symbol"]:
            rows_to_add.append(row)
            existing_ids.add(row["signal_id"])

    if not rows_to_add:
        print("ℹ️ No new published signals to log.")
        return 0

    append_rows(rows_to_add)
    print(f"✅ Logged {len(rows_to_add)} published signal(s) to {PUBLISHED_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())