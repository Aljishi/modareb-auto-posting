#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Sector Rotation Engine
يبني قراءة يومية لدوران القطاعات من daily.json و signals.json.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DAILY_FILE = DATA_DIR / "daily.json"
SIGNALS_FILE = DATA_DIR / "signals.json"
OUTPUT_FILE = DATA_DIR / "sector_rotation.json"


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace(",", "").replace("%", "").strip()
        return float(x)
    except Exception:
        return default


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def classify(score: float) -> str:
    if score >= 85:
        return "قيادة قوية"
    if score >= 70:
        return "قوي"
    if score >= 55:
        return "محايد إيجابي"
    if score >= 40:
        return "محايد"
    return "ضعيف"


def build_sector_rotation() -> Dict[str, Any]:
    daily = load_json(DAILY_FILE, {})
    signals_data = load_json(SIGNALS_FILE, {})
    stocks = daily.get("stocks", []) if isinstance(daily, dict) else []
    signals = signals_data.get("signals", []) if isinstance(signals_data, dict) else []

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for s in stocks:
        sector = str(s.get("sector") or s.get("sector_name") or "").strip()
        if sector:
            groups.setdefault(sector, []).append(s)

    sector_signal_count: Dict[str, int] = {}
    sector_signal_score: Dict[str, List[float]] = {}
    for sig in signals:
        sector = str(sig.get("sector") or "").strip()
        if not sector:
            continue
        sector_signal_count[sector] = sector_signal_count.get(sector, 0) + 1
        sector_signal_score.setdefault(sector, []).append(fnum(sig.get("rased_score") or sig.get("score"), 0))

    sectors = []
    max_value = 1.0
    temp_values = []
    for items in groups.values():
        total_value = sum((fnum(x.get("value") or x.get("turnover")) or fnum(x.get("current_price") or x.get("price")) * fnum(x.get("volume"))) for x in items)
        temp_values.append(total_value)
    if temp_values:
        max_value = max(temp_values) or 1.0

    for sector, items in groups.items():
        changes = [fnum(x.get("change_percent")) for x in items]
        values = [(fnum(x.get("value") or x.get("turnover")) or fnum(x.get("current_price") or x.get("price")) * fnum(x.get("volume"))) for x in items]
        avg_change = mean(changes) if changes else 0.0
        advancing_ratio = sum(1 for c in changes if c > 0) / len(changes) if changes else 0.0
        total_value = sum(values)
        liquidity_score = min(100.0, total_value / max_value * 100.0)
        signal_score = mean(sector_signal_score.get(sector, [0])) if sector_signal_score.get(sector) else 0.0
        momentum_score = max(0.0, min(100.0, 50 + avg_change * 18))
        breadth_score = advancing_ratio * 100
        rotation_score = round(momentum_score * 0.35 + breadth_score * 0.25 + liquidity_score * 0.20 + signal_score * 0.20, 1)
        sectors.append({
            "sector": sector,
            "rotation_score": rotation_score,
            "grade": classify(rotation_score),
            "avg_change_pct": round(avg_change, 2),
            "advancing_ratio": round(advancing_ratio, 2),
            "total_value": round(total_value, 2),
            "stocks_count": len(items),
            "signals_count": sector_signal_count.get(sector, 0),
            "avg_signal_score": round(signal_score, 1),
        })

    sectors.sort(key=lambda x: x.get("rotation_score", 0), reverse=True)
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "top_sectors": sectors[:10],
        "all_sectors": sectors,
        "method": "momentum 35% + breadth 25% + liquidity 20% + signal quality 20%",
    }
    write_json(OUTPUT_FILE, out)
    return out


def main() -> int:
    out = build_sector_rotation()
    print(f"✅ Sector rotation updated: {len(out.get('all_sectors', []))} sectors")
    print(f"📄 {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
