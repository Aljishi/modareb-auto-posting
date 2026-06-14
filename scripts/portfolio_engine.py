#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Portfolio Allocation Engine
ينتج توزيع محفظة مقترح من الإشارات المجازة أو إشارات اليوم.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VALIDATED_FILE = DATA_DIR / "validated_signals.json"
SIGNALS_FILE = DATA_DIR / "signals.json"
OUTPUT_FILE = DATA_DIR / "portfolio_allocation.json"

DEFAULT_CAPITAL = float(os.getenv("RASED_PORTFOLIO_CAPITAL", "500000"))
MAX_POSITION_PCT = float(os.getenv("RASED_MAX_POSITION_PCT", "35"))
MIN_CASH_PCT = float(os.getenv("RASED_MIN_CASH_PCT", "10"))


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


def extract_signals(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("validated_signals") or data.get("signals") or []
    return []


def signal_weight_score(sig: Dict[str, Any]) -> float:
    rased = fnum(sig.get("rased_score") or sig.get("score"), 0)
    rr = fnum(sig.get("rr") or sig.get("rr_ratio"), 0)
    bt = fnum(sig.get("backtest_win_rate"), 0)
    sector_bonus = fnum(sig.get("sector_strength_bonus"), 0)
    risk_penalty = abs(fnum(sig.get("stop_loss_percent") or sig.get("sl_pct"), 0))
    tier = str(sig.get("tier") or "").lower()
    tier_bonus = 15 if "platinum" in tier else 10 if "gold" in tier else 5 if "premium" in tier else 0
    raw = rased * 0.50 + min(rr * 20, 60) * 0.20 + bt * 0.15 + max(sector_bonus, 0) * 2 + tier_bonus - risk_penalty * 1.5
    return max(1.0, raw)


def build_portfolio(capital: float = DEFAULT_CAPITAL) -> Dict[str, Any]:
    data = load_json(VALIDATED_FILE, {})
    signals = extract_signals(data)
    source = str(VALIDATED_FILE)
    if not signals:
        data = load_json(SIGNALS_FILE, {})
        signals = extract_signals(data)
        source = str(SIGNALS_FILE)

    signals = sorted(signals, key=signal_weight_score, reverse=True)[:4]
    investable_pct = max(0.0, 100.0 - MIN_CASH_PCT)
    total_score = sum(signal_weight_score(s) for s in signals) or 1.0
    positions = []
    used_pct = 0.0

    for sig in signals:
        suggested_pct = signal_weight_score(sig) / total_score * investable_pct
        suggested_pct = min(MAX_POSITION_PCT, suggested_pct)
        amount = round(capital * suggested_pct / 100.0, 2)
        entry = fnum(sig.get("entry") or sig.get("entry_point"), 0)
        stop = fnum(sig.get("stop_loss"), 0)
        risk_amount = max(0.0, entry - stop)
        risk_pct_of_position = risk_amount / entry * 100 if entry > 0 else 0.0
        portfolio_risk_pct = suggested_pct * risk_pct_of_position / 100.0
        positions.append({
            "symbol": sig.get("symbol") or sig.get("stock_symbol"),
            "name": sig.get("name") or sig.get("stock_name"),
            "sector": sig.get("sector", ""),
            "tier": sig.get("tier", ""),
            "rased_score": sig.get("rased_score") or sig.get("score"),
            "entry": entry,
            "target1": sig.get("target1"),
            "target2": sig.get("target2"),
            "stop_loss": stop,
            "weight_pct": round(suggested_pct, 2),
            "amount_sar": amount,
            "position_risk_pct": round(risk_pct_of_position, 2),
            "portfolio_risk_pct": round(portfolio_risk_pct, 2),
        })
        used_pct += suggested_pct

    cash_pct = max(0.0, 100.0 - used_pct)
    sector_exposure: Dict[str, float] = {}
    for p in positions:
        sector = str(p.get("sector") or "غير محدد")
        sector_exposure[sector] = sector_exposure.get(sector, 0.0) + fnum(p.get("weight_pct"), 0.0)

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "capital_sar": round(capital, 2),
        "max_position_pct": MAX_POSITION_PCT,
        "min_cash_pct": MIN_CASH_PCT,
        "positions": positions,
        "cash": {"weight_pct": round(cash_pct, 2), "amount_sar": round(capital * cash_pct / 100.0, 2)},
        "sector_exposure": {k: round(v, 2) for k, v in sorted(sector_exposure.items(), key=lambda x: x[1], reverse=True)},
        "total_portfolio_risk_pct": round(sum(fnum(p.get("portfolio_risk_pct"), 0.0) for p in positions), 2),
        "note": "توزيع آلي مبني على جودة الإشارة وليس توصية شخصية. التزم بوقف الخسارة.",
    }
    write_json(OUTPUT_FILE, out)
    return out


def main() -> int:
    out = build_portfolio()
    print(f"✅ Portfolio allocation updated: {len(out.get('positions', []))} positions")
    print(f"📄 {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
