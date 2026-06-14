#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Self-Learning Engine
يتعلم من سجل الأداء المنشور ويحوّل النتائج إلى تعديلات صغيرة على Score الإشارة.

الملفات:
- input : data/signal_performance.csv, data/published_signals.csv
- output: data/self_learning_weights.json

ملاحظة مهمة:
هذا المحرك لا يغيّر منطق الإشارة الأساسي. فقط يعطي bonus/penalty محدود حتى لا يصبح النظام متساهلاً.
"""

from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WEIGHTS_FILE = DATA_DIR / "self_learning_weights.json"
PERFORMANCE_FILE = DATA_DIR / "signal_performance.csv"
PUBLISHED_FILE = DATA_DIR / "published_signals.csv"

MIN_BUCKET_TRADES = int(os.getenv("SELF_LEARNING_MIN_BUCKET_TRADES", "4"))
MAX_LEARNING_BONUS = int(os.getenv("MAX_SELF_LEARNING_BONUS", "6"))
DEFAULT_WIN_RATE = 55.0


def fnum(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", "").strip()
        return float(value)
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


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def normalize_symbol(row: Dict[str, Any]) -> str:
    return str(row.get("symbol") or row.get("stock_symbol") or row.get("Symbol") or "").strip()


def normalize_outcome(row: Dict[str, Any]) -> str:
    raw = str(row.get("outcome") or row.get("status") or row.get("result") or row.get("final_status") or "").strip().lower()
    if any(x in raw for x in ["win", "tp1", "tp2", "target", "success", "hit_target", "ربح", "نجاح", "هدف"]):
        return "WIN"
    if any(x in raw for x in ["loss", "sl", "stop", "failed", "خسارة", "وقف"]):
        return "LOSS"
    if any(x in raw for x in ["partial", "open", "مفتوحة", "جزئي"]):
        return "PARTIAL"
    pnl = fnum(row.get("pnl_pct") or row.get("return_pct") or row.get("performance_pct"), math.nan)
    if not math.isnan(pnl):
        if pnl > 0:
            return "WIN"
        if pnl < 0:
            return "LOSS"
    return "UNKNOWN"


def bucket_rsi(rsi: float) -> str:
    if rsi < 45:
        return "rsi_lt_45"
    if rsi < 52:
        return "rsi_45_52"
    if rsi <= 64:
        return "rsi_52_64"
    if rsi <= 72:
        return "rsi_64_72"
    return "rsi_gt_72"


def bucket_volume(vr: float) -> str:
    if vr < 1:
        return "vol_lt_1x"
    if vr < 1.5:
        return "vol_1_1_5x"
    if vr < 2.5:
        return "vol_1_5_2_5x"
    return "vol_gt_2_5x"


def bucket_rr(rr: float) -> str:
    if rr < 1.7:
        return "rr_lt_1_7"
    if rr < 2.2:
        return "rr_1_7_2_2"
    if rr < 3.0:
        return "rr_2_2_3_0"
    return "rr_gt_3"


def score_bucket(records: Iterable[Tuple[str, float]]) -> Dict[str, Any]:
    rows = list(records)
    total = len(rows)
    wins = sum(1 for outcome, _ in rows if outcome == "WIN")
    losses = sum(1 for outcome, _ in rows if outcome == "LOSS")
    avg_pnl = mean([p for _, p in rows]) if rows else 0.0
    win_rate = wins / total * 100 if total else 0.0
    if total < MIN_BUCKET_TRADES:
        adjustment = 0
        grade = "عينة صغيرة"
    else:
        edge = win_rate - DEFAULT_WIN_RATE
        adjustment = int(round(edge / 8.0))
        if avg_pnl > 1.5:
            adjustment += 1
        elif avg_pnl < -1.0:
            adjustment -= 1
        adjustment = max(-MAX_LEARNING_BONUS, min(MAX_LEARNING_BONUS, adjustment))
        grade = "قوي" if adjustment >= 3 else "جيد" if adjustment > 0 else "ضعيف" if adjustment < 0 else "محايد"
    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 2),
        "avg_pnl_pct": round(avg_pnl, 2),
        "adjustment": adjustment,
        "grade": grade,
    }


def build_learning_model() -> Dict[str, Any]:
    rows = read_csv(PERFORMANCE_FILE)
    buckets: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    symbols: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    sectors: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    total_known = 0

    for row in rows:
        outcome = normalize_outcome(row)
        if outcome == "UNKNOWN":
            continue
        pnl = fnum(row.get("pnl_pct") or row.get("return_pct") or row.get("performance_pct"), 0.0)
        total_known += 1
        symbol = normalize_symbol(row)
        sector = str(row.get("sector") or row.get("sector_name") or "").strip()
        rsi = fnum(row.get("rsi"), 0.0)
        vr = fnum(row.get("volume_ratio"), 0.0)
        rr = fnum(row.get("rr") or row.get("rr_ratio"), 0.0)
        if symbol:
            symbols[symbol].append((outcome, pnl))
        if sector:
            sectors[sector].append((outcome, pnl))
        if rsi:
            buckets[bucket_rsi(rsi)].append((outcome, pnl))
        if vr:
            buckets[bucket_volume(vr)].append((outcome, pnl))
        if rr:
            buckets[bucket_rr(rr)].append((outcome, pnl))

    model = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": str(PERFORMANCE_FILE),
        "total_known_outcomes": total_known,
        "max_learning_bonus": MAX_LEARNING_BONUS,
        "min_bucket_trades": MIN_BUCKET_TRADES,
        "buckets": {k: score_bucket(v) for k, v in sorted(buckets.items())},
        "symbols": {k: score_bucket(v) for k, v in sorted(symbols.items())},
        "sectors": {k: score_bucket(v) for k, v in sorted(sectors.items())},
    }
    write_json(WEIGHTS_FILE, model)
    return model


def load_learning_model() -> Dict[str, Any]:
    model = load_json(WEIGHTS_FILE, {})
    if not model:
        model = build_learning_model()
    return model


def get_learning_adjustment(signal: Dict[str, Any], model: Dict[str, Any] | None = None) -> Dict[str, Any]:
    model = model or load_learning_model()
    adjustments: List[int] = []
    notes: List[str] = []

    symbol = str(signal.get("symbol") or signal.get("stock_symbol") or "").strip()
    sector = str(signal.get("sector") or "").strip()
    rsi = fnum(signal.get("rsi"), 0.0)
    vr = fnum(signal.get("volume_ratio"), 0.0)
    rr = fnum(signal.get("rr") or signal.get("rr_ratio"), 0.0)

    checks = []
    if symbol:
        checks.append(("symbols", symbol, "رمز"))
    if sector:
        checks.append(("sectors", sector, "قطاع"))
    if rsi:
        checks.append(("buckets", bucket_rsi(rsi), "RSI"))
    if vr:
        checks.append(("buckets", bucket_volume(vr), "Volume"))
    if rr:
        checks.append(("buckets", bucket_rr(rr), "R:R"))

    for group, key, label in checks:
        item = model.get(group, {}).get(key)
        if not item:
            continue
        adj = int(item.get("adjustment", 0))
        if adj == 0:
            continue
        adjustments.append(adj)
        notes.append(f"{label} {key}: {adj:+d} ({item.get('win_rate', 0)}%)")

    if not adjustments:
        final_adj = 0
    else:
        final_adj = int(round(sum(adjustments) / len(adjustments)))
        final_adj = max(-MAX_LEARNING_BONUS, min(MAX_LEARNING_BONUS, final_adj))

    return {
        "available": bool(model.get("total_known_outcomes", 0)),
        "bonus": final_adj,
        "notes": notes[:5],
        "model_generated_at": model.get("generated_at"),
        "known_outcomes": model.get("total_known_outcomes", 0),
    }


def main() -> int:
    model = build_learning_model()
    print(f"✅ Self-learning model updated: {model.get('total_known_outcomes', 0)} known outcomes")
    print(f"📄 {WEIGHTS_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
