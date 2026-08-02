#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Market Regime Detector v1

يقرأ بيانات السوق المجمعة من data/daily.json ويصنف البيئة الحالية إلى:
- STRONG: سوق قوي واسع الصعود.
- NORMAL: سوق طبيعي انتقائي.
- SIDEWAYS: سوق عرضي منخفض الزخم.
- WEAK: سوق ضعيف يحتاج حماية أعلى.
- HIGH_VOLATILITY: تذبذب مرتفع واتساع غير مستقر.

ينتج:
- data/market_regime.json
- data/market_regime.env

ملف env يُستخدم بواسطة run_signal_pipeline.py لضبط فلاتر محرك الإشارات
قبل تحليل الأسهم، وليس بعد توليد الإشارة فقط.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

DAILY_FILE = DATA / "daily.json"
OUT_FILE = DATA / "market_regime.json"
ENV_FILE = DATA / "market_regime.env"

MIN_SAMPLE = int(os.getenv("REGIME_MIN_SAMPLE", "15"))

STRONG_AVG_CHANGE = float(os.getenv("REGIME_STRONG_AVG_CHANGE", "0.80"))
STRONG_ADVANCE_RATIO = float(os.getenv("REGIME_STRONG_ADVANCE_RATIO", "0.65"))

WEAK_AVG_CHANGE = float(os.getenv("REGIME_WEAK_AVG_CHANGE", "-0.50"))
WEAK_ADVANCE_RATIO = float(os.getenv("REGIME_WEAK_ADVANCE_RATIO", "0.35"))

SIDEWAYS_ABS_AVG = float(os.getenv("REGIME_SIDEWAYS_ABS_AVG", "0.25"))
SIDEWAYS_BREADTH_LOW = float(os.getenv("REGIME_SIDEWAYS_BREADTH_LOW", "0.42"))
SIDEWAYS_BREADTH_HIGH = float(os.getenv("REGIME_SIDEWAYS_BREADTH_HIGH", "0.58"))

HIGH_VOL_DISPERSION = float(os.getenv("REGIME_HIGH_VOL_DISPERSION", "3.00"))
HIGH_VOL_EXTREME_RATIO = float(os.getenv("REGIME_HIGH_VOL_EXTREME_RATIO", "0.20"))


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def fnum(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"⚠️ تعذر قراءة {path.name}: {exc}")
    return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(path)


def get_stocks(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        rows = payload.get("stocks", [])
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def market_summary_change(payload: Any) -> Optional[float]:
    if not isinstance(payload, dict):
        return None

    summary = payload.get("market_summary", {})
    if not isinstance(summary, dict):
        return None

    candidates = (
        summary.get("change_percent"),
        summary.get("change_pct"),
        summary.get("percent_change"),
        summary.get("index_change_percent"),
    )

    for value in candidates:
        parsed = fnum(value, None)
        if parsed is not None and -20 <= parsed <= 20:
            return parsed

    nested = summary.get("data")
    if isinstance(nested, dict):
        for key in (
            "change_percent",
            "change_pct",
            "percent_change",
            "index_change_percent",
        ):
            parsed = fnum(nested.get(key), None)
            if parsed is not None and -20 <= parsed <= 20:
                return parsed

    return None


def filter_profile(regime: str) -> Dict[str, Any]:
    profiles = {
        "STRONG": {
            "MIN_SIGNAL_SCORE": 77,
            "MIN_RR": 1.70,
            "MIN_VOLUME_RATIO": 0.80,
            "MIN_VALUE_SAR": 300000,
            "MIN_RSI": 38,
            "MAX_RSI": 76,
            "MAX_ENTRY_GAP_PCT": 5.5,
            "MIN_TP1_PCT_NORMAL": 3.25,
            "MAX_CANDIDATES": 50,
        },
        "NORMAL": {
            "MIN_SIGNAL_SCORE": 80,
            "MIN_RR": 1.80,
            "MIN_VOLUME_RATIO": 0.85,
            "MIN_VALUE_SAR": 300000,
            "MIN_RSI": 38,
            "MAX_RSI": 74,
            "MAX_ENTRY_GAP_PCT": 5.0,
            "MIN_TP1_PCT_NORMAL": 3.25,
            "MAX_CANDIDATES": 50,
        },
        "SIDEWAYS": {
            "MIN_SIGNAL_SCORE": 81,
            "MIN_RR": 1.90,
            "MIN_VOLUME_RATIO": 0.95,
            "MIN_VALUE_SAR": 400000,
            "MIN_RSI": 42,
            "MAX_RSI": 70,
            "MAX_ENTRY_GAP_PCT": 4.5,
            "MIN_TP1_PCT_NORMAL": 3.50,
            "MAX_CANDIDATES": 45,
        },
        "WEAK": {
            "MIN_SIGNAL_SCORE": 83,
            "MIN_RR": 2.00,
            "MIN_VOLUME_RATIO": 1.00,
            "MIN_VALUE_SAR": 500000,
            "MIN_RSI": 45,
            "MAX_RSI": 68,
            "MAX_ENTRY_GAP_PCT": 4.0,
            "MIN_TP1_PCT_NORMAL": 4.00,
            "MAX_CANDIDATES": 40,
        },
        "HIGH_VOLATILITY": {
            "MIN_SIGNAL_SCORE": 84,
            "MIN_RR": 2.10,
            "MIN_VOLUME_RATIO": 1.10,
            "MIN_VALUE_SAR": 600000,
            "MIN_RSI": 45,
            "MAX_RSI": 66,
            "MAX_ENTRY_GAP_PCT": 3.5,
            "MIN_TP1_PCT_NORMAL": 4.00,
            "MAX_CANDIDATES": 35,
        },
    }
    return profiles[regime]


def detect() -> Dict[str, Any]:
    payload = read_json(DAILY_FILE, {})
    stocks = get_stocks(payload)

    changes: List[float] = []
    advances = 0
    declines = 0
    unchanged = 0
    extreme = 0

    for stock in stocks:
        raw = (
            stock.get("change_percent")
            if "change_percent" in stock
            else stock.get("change_pct")
        )
        change = fnum(raw, None)
        if change is None or change < -20 or change > 20:
            continue

        changes.append(change)

        if change > 0.05:
            advances += 1
        elif change < -0.05:
            declines += 1
        else:
            unchanged += 1

        if abs(change) >= 5.0:
            extreme += 1

    sample = len(changes)
    index_change = market_summary_change(payload)

    if sample < MIN_SAMPLE:
        regime = "NORMAL"
        avg_change = 0.0
        median_change = 0.0
        dispersion = 0.0
        advance_ratio = 0.0
        decline_ratio = 0.0
        extreme_ratio = 0.0
        reason = (
            f"العينة غير كافية ({sample}/{MIN_SAMPLE})؛ "
            "تم تطبيق ملف السوق الطبيعي احترازيًا"
        )
    else:
        avg_change = sum(changes) / sample
        median_change = statistics.median(changes)
        dispersion = statistics.pstdev(changes) if sample > 1 else 0.0
        advance_ratio = advances / sample
        decline_ratio = declines / sample
        extreme_ratio = extreme / sample

        if (
            dispersion >= HIGH_VOL_DISPERSION
            or extreme_ratio >= HIGH_VOL_EXTREME_RATIO
        ):
            regime = "HIGH_VOLATILITY"
            reason = (
                f"تشتت مرتفع {dispersion:.2f} ونسبة تحركات حادة "
                f"{extreme_ratio * 100:.1f}%"
            )
        elif (
            avg_change >= STRONG_AVG_CHANGE
            and advance_ratio >= STRONG_ADVANCE_RATIO
            and (index_change is None or index_change > -0.25)
        ):
            regime = "STRONG"
            reason = (
                f"متوسط السوق {avg_change:.2f}% ونسبة الصعود "
                f"{advance_ratio * 100:.1f}%"
            )
        elif (
            avg_change <= WEAK_AVG_CHANGE
            or advance_ratio <= WEAK_ADVANCE_RATIO
            or (index_change is not None and index_change <= -0.75)
        ):
            regime = "WEAK"
            reason = (
                f"متوسط السوق {avg_change:.2f}% ونسبة الصعود "
                f"{advance_ratio * 100:.1f}%"
            )
        elif (
            abs(avg_change) <= SIDEWAYS_ABS_AVG
            and SIDEWAYS_BREADTH_LOW <= advance_ratio <= SIDEWAYS_BREADTH_HIGH
        ):
            regime = "SIDEWAYS"
            reason = (
                f"متوسط قريب من الصفر {avg_change:.2f}% واتساع متوازن "
                f"{advance_ratio * 100:.1f}%"
            )
        else:
            regime = "NORMAL"
            reason = (
                f"متوسط السوق {avg_change:.2f}% ونسبة الصعود "
                f"{advance_ratio * 100:.1f}%"
            )

    labels = {
        "STRONG": ("قوي", "شهية مخاطرة مرتفعة"),
        "NORMAL": ("طبيعي", "انتقائي"),
        "SIDEWAYS": ("عرضي", "اختراقات مؤكدة فقط"),
        "WEAK": ("ضعيف", "حماية رأس المال"),
        "HIGH_VOLATILITY": ("عالي التذبذب", "تشدد مرتفع"),
    }

    profile = filter_profile(regime)
    regime_ar, posture = labels[regime]

    return {
        "status": "PASS",
        "engine": "rased_market_regime_v1",
        "regime": regime,
        "regime_ar": regime_ar,
        "posture": posture,
        "reason": reason,
        "sample_size": sample,
        "minimum_sample": MIN_SAMPLE,
        "average_change_pct": round(avg_change, 3),
        "median_change_pct": round(median_change, 3),
        "index_change_pct": (
            round(index_change, 3) if index_change is not None else None
        ),
        "advance_ratio": round(advance_ratio, 4),
        "decline_ratio": round(decline_ratio, 4),
        "unchanged_ratio": (
            round(unchanged / sample, 4) if sample else 0.0
        ),
        "dispersion": round(dispersion, 3),
        "extreme_move_ratio": round(extreme_ratio, 4),
        "advancing_stocks": advances,
        "declining_stocks": declines,
        "unchanged_stocks": unchanged,
        "filter_profile": profile,
        "daily_generated_at": (
            payload.get("generated_at") if isinstance(payload, dict) else None
        ),
        "generated_at": now_iso(),
    }


def save_env(result: Dict[str, Any]) -> None:
    profile = result["filter_profile"]
    lines = [
        f"MARKET_REGIME={result['regime']}",
        f"MARKET_REGIME_AR={result['regime_ar']}",
    ]
    for key, value in profile.items():
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)

    result = detect()
    write_json(OUT_FILE, result)
    save_env(result)

    print("=" * 68)
    print("راصد — Market Regime Detector")
    print("=" * 68)
    print(f"📊 الحالة: {result['regime_ar']} ({result['regime']})")
    print(f"📈 متوسط التغير: {result['average_change_pct']}%")
    print(f"🟢 نسبة الصعود: {result['advance_ratio'] * 100:.1f}%")
    print(f"⚡ التشتت: {result['dispersion']}")
    print(f"🎯 MIN_SIGNAL_SCORE: {result['filter_profile']['MIN_SIGNAL_SCORE']}")
    print(f"📝 السبب: {result['reason']}")
    print(f"✅ Saved: {OUT_FILE}")
    print(f"✅ Saved: {ENV_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
