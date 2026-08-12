#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RASED Sector Rotation Engine v2.0
=================================

يبني قراءة يومية لدوران القطاعات من:
- data/daily.json
- data/signals.json

التحسينات:
- توحيد القطاع عبر RASED Sector Master حتى لا يدخل تصنيف مزود خاطئ
  في Sector Bonus أو التقرير.
- استخدام الحركة الموزونة بالسيولة بدل المتوسط البسيط فقط.
- استخدام اتساع القطاع، السيولة، وجودة الإشارات.
- إبقاء all_sectors و top_sectors ليتوافق مع التقارير الحالية.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List

try:
    from sector_master import normalize_stock_sector, resolve_sector
except ImportError:
    from scripts.sector_master import normalize_stock_sector, resolve_sector


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

DAILY_FILE = DATA_DIR / "daily.json"
SIGNALS_FILE = DATA_DIR / "signals.json"
OUTPUT_FILE = DATA_DIR / "sector_rotation.json"

ENGINE_VERSION = "rased_sector_rotation_v2_0"


def fnum(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None or value == "":
            return default

        if isinstance(value, str):
            value = (
                value
                .replace(",", "")
                .replace("%", "")
                .strip()
            )

        return float(value)

    except Exception:
        return default


def clamp(
    value: float,
    low: float,
    high: float,
) -> float:
    return max(
        low,
        min(value, high),
    )


def load_json(
    path: Path,
    default: Any,
) -> Any:
    try:
        if path.exists():
            return json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

    except Exception as exc:
        print(
            f"⚠️ Unable to read {path.name}: {exc}"
        )

    return default


def write_json(
    path: Path,
    data: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def stock_change(
    stock: Dict[str, Any],
) -> float:
    return fnum(
        stock.get("change_percent")
        or stock.get("change_pct")
        or stock.get("pct_change")
    )


def stock_value(
    stock: Dict[str, Any],
) -> float:
    direct = fnum(
        stock.get("value")
        or stock.get("turnover")
    )

    if direct > 0:
        return direct

    price = fnum(
        stock.get("current_price")
        or stock.get("price")
        or stock.get("close")
    )

    volume = fnum(
        stock.get("volume")
    )

    return max(
        0.0,
        price * volume,
    )


def classify(
    score: float,
) -> str:
    if score >= 82:
        return "قيادة قوية"

    if score >= 68:
        return "قوي"

    if score >= 55:
        return "محايد إيجابي"

    if score >= 42:
        return "محايد"

    return "ضعيف"


def signal_rows(
    signals_data: Any,
) -> List[Dict[str, Any]]:
    if isinstance(signals_data, list):
        return [
            item
            for item in signals_data
            if isinstance(item, dict)
        ]

    if isinstance(signals_data, dict):
        rows = signals_data.get(
            "signals",
            [],
        )

        if isinstance(rows, list):
            return [
                item
                for item in rows
                if isinstance(item, dict)
            ]

    return []


def build_sector_rotation() -> Dict[str, Any]:
    daily = load_json(
        DAILY_FILE,
        {},
    )

    signals_data = load_json(
        SIGNALS_FILE,
        {},
    )

    raw_stocks = (
        daily.get("stocks", [])
        if isinstance(daily, dict)
        else []
    )

    stocks = [
        normalize_stock_sector(stock)
        for stock in raw_stocks
        if isinstance(stock, dict)
    ]

    signals = signal_rows(
        signals_data
    )

    groups: Dict[str, List[Dict[str, Any]]] = {}

    for stock in stocks:
        sector = str(
            stock.get("sector")
            or ""
        ).strip()

        if not sector or sector == "غير مصنف":
            continue

        groups.setdefault(
            sector,
            [],
        ).append(
            stock
        )

    # Signal context by corrected sector.
    sector_signal_count: Dict[str, int] = {}
    sector_signal_scores: Dict[str, List[float]] = {}

    for signal in signals:
        symbol = (
            signal.get("symbol")
            or signal.get("stock_symbol")
            or ""
        )

        sector = resolve_sector(
            symbol,
            signal.get("sector")
            or signal.get("sector_name")
            or "",
        )

        if not sector or sector == "غير مصنف":
            continue

        sector_signal_count[sector] = (
            sector_signal_count.get(
                sector,
                0,
            )
            + 1
        )

        sector_signal_scores.setdefault(
            sector,
            [],
        ).append(
            fnum(
                signal.get("rased_score")
                or signal.get("score")
            )
        )

    sector_values: Dict[str, float] = {}

    for sector, items in groups.items():
        sector_values[sector] = sum(
            stock_value(item)
            for item in items
        )

    total_market_value = (
        sum(sector_values.values())
        or 1.0
    )

    max_sector_value = (
        max(sector_values.values())
        if sector_values
        else 1.0
    ) or 1.0

    sectors: List[Dict[str, Any]] = []

    for sector, items in groups.items():
        changes = [
            stock_change(item)
            for item in items
        ]

        total_value = sector_values.get(
            sector,
            0.0,
        )

        advancing = sum(
            1
            for change in changes
            if change > 0
        )

        declining = sum(
            1
            for change in changes
            if change < 0
        )

        unchanged = (
            len(items)
            - advancing
            - declining
        )

        advance_ratio = (
            advancing / len(items)
            if items
            else 0.0
        )

        avg_change = (
            mean(changes)
            if changes
            else 0.0
        )

        median_change = (
            median(changes)
            if changes
            else 0.0
        )

        weighted_change = 0.0

        if total_value > 0:
            weighted_change = (
                sum(
                    stock_change(item)
                    * stock_value(item)
                    for item in items
                )
                / total_value
            )

        liquidity_share = (
            total_value
            / total_market_value
        )

        # Components 0..100
        momentum_component = clamp(
            50
            + weighted_change * 12,
            0,
            100,
        )

        breadth_component = (
            advance_ratio * 100
        )

        relative_liquidity_component = clamp(
            total_value
            / max_sector_value
            * 100,
            0,
            100,
        )

        signal_count = (
            sector_signal_count.get(
                sector,
                0,
            )
        )

        signal_scores = (
            sector_signal_scores.get(
                sector,
                [],
            )
        )

        avg_signal_score = (
            mean(signal_scores)
            if signal_scores
            else 0.0
        )

        # Signal component is intentionally capped so signals do not
        # dominate actual market participation.
        if signal_count <= 0:
            signal_component = 40.0
        else:
            signal_component = clamp(
                45
                + signal_count * 7
                + max(
                    0.0,
                    avg_signal_score - 80,
                )
                * 0.6,
                0,
                100,
            )

        rotation_score = (
            momentum_component * 0.38
            + breadth_component * 0.30
            + relative_liquidity_component * 0.22
            + signal_component * 0.10
        )

        sectors.append(
            {
                "sector": sector,
                "members": len(items),
                "advancing": advancing,
                "declining": declining,
                "unchanged": unchanged,
                "advancing_ratio": round(
                    advance_ratio,
                    3,
                ),
                "advance_ratio": round(
                    advance_ratio,
                    3,
                ),
                "avg_change_pct": round(
                    avg_change,
                    2,
                ),
                "median_change_pct": round(
                    median_change,
                    2,
                ),
                "liquidity_weighted_change_pct": round(
                    weighted_change,
                    2,
                ),
                "total_value": round(
                    total_value,
                    2,
                ),
                "liquidity_share_pct": round(
                    liquidity_share * 100,
                    2,
                ),
                "signal_count": signal_count,
                "avg_signal_score": round(
                    avg_signal_score,
                    1,
                ),
                "components": {
                    "momentum": round(
                        momentum_component,
                        1,
                    ),
                    "breadth": round(
                        breadth_component,
                        1,
                    ),
                    "relative_liquidity": round(
                        relative_liquidity_component,
                        1,
                    ),
                    "signals": round(
                        signal_component,
                        1,
                    ),
                },
                "rotation_score": round(
                    rotation_score,
                    1,
                ),
                "grade": classify(
                    rotation_score
                ),
            }
        )

    sectors.sort(
        key=lambda item: (
            fnum(
                item.get(
                    "rotation_score"
                )
            ),
            fnum(
                item.get(
                    "liquidity_weighted_change_pct"
                )
            ),
            fnum(
                item.get(
                    "total_value"
                )
            ),
        ),
        reverse=True,
    )

    result = {
        "engine_version": ENGINE_VERSION,
        "generated_at": (
            datetime.now()
            .isoformat(
                timespec="seconds"
            )
        ),
        "stocks_used": len(stocks),
        "sectors_count": len(sectors),
        "top_sectors": sectors[:6],
        "all_sectors": sectors,
        "methodology": {
            "momentum_weight": 0.38,
            "breadth_weight": 0.30,
            "relative_liquidity_weight": 0.22,
            "signal_context_weight": 0.10,
            "sector_source": (
                "RASED Sector Master + provider sector"
            ),
        },
    }

    return result


def main() -> int:
    result = build_sector_rotation()

    write_json(
        OUTPUT_FILE,
        result,
    )

    print(
        "✅ Sector rotation updated: "
        f"{result.get('sectors_count', 0)} sectors"
    )

    for row in result.get(
        "top_sectors",
        [],
    ):
        print(
            f"• {row.get('sector')}: "
            f"{row.get('rotation_score')}/100 | "
            f"{row.get('grade')} | "
            f"weighted "
            f"{row.get('liquidity_weighted_change_pct'):+.2f}% | "
            f"breadth "
            f"{fnum(row.get('advance_ratio')) * 100:.0f}%"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
