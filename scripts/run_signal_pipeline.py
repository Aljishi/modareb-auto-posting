#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Regime-Aware Signal Pipeline v10

الترتيب:
1. تحديد حالة السوق.
2. تحميل الفلاتر الديناميكية.
3. فرض حدود دنيا للجودة لا يستطيع Market Regime تخفيفها.
4. توليد الإشارات.
5. تشغيل RASED Quality Gate v10.

الهدف:
تظل الفلاتر ديناميكية حسب السوق،
لكن لا يُسمح لأي وضع سوق بخفض جودة راصد
إلى مستويات تناقض سياسة إدارة المخاطر.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

REGIME_FILE = DATA / "market_regime.json"

DETECTOR = (
    ROOT
    / "scripts"
    / "market_regime_detector.py"
)

GENERATOR = (
    ROOT
    / "scripts"
    / "generate_signal.py"
)

QUALITY_GATE = (
    ROOT
    / "scripts"
    / "signal_quality_gate.py"
)


# ============================================================
# Hard quality floors
# ============================================================

QUALITY_FLOORS = {
    # المحرك الفني
    "MIN_SIGNAL_SCORE": "80",

    # لا نسمح لـ Market Regime بخفض R:R عن 2
    "MIN_RR": "2.00",

    # الحد الأدنى المقبول للسيولة
    "MIN_VOLUME_RATIO": "1.00",

    # حماية من المطاردة
    "MAX_RSI": "72",
    "MAX_OVERBOUGHT_RSI": "70",

    # الباك تست
    "MIN_BACKTEST_WIN_RATE": "35",
    "MIN_BACKTEST_TRADES_FOR_HARD_REJECT": "4",

    # Quality Gate
    "QUALITY_MIN_RASED_SCORE": "82",
    "QUALITY_MIN_TECHNICAL_SCORE": "80",
    "QUALITY_MIN_RR": "2.00",
    "QUALITY_MIN_VOLUME_RATIO": "1.15",
    "QUALITY_MAX_RSI": "70",
    "QUALITY_MAX_ATR_PCT": "8.0",
    "QUALITY_MIN_TP1_PCT": "4.0",
    "QUALITY_MIN_TP2_PCT": "6.0",

    # Backtest quality
    "QUALITY_BACKTEST_ZERO_REJECT_MIN_TRADES": "3",
    "QUALITY_BACKTEST_HARD_MIN_TRADES": "4",
    "QUALITY_BACKTEST_MIN_WIN_RATE": "35",

    # Chase protection
    "QUALITY_CHASE_RSI": "68",
    "QUALITY_CHASE_DAILY_CHANGE_PCT": "5.5",
    "QUALITY_CHASE_MIN_RR": "2.40",
    "QUALITY_CHASE_MIN_VOLUME_RATIO": "2.0",

    # لا نحتاج كمية كبيرة من الإشارات
    "QUALITY_MAX_SIGNALS": "3",
}


def fnum(
    value: object,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except Exception:
        return default


def load_profile() -> Dict[str, str]:
    if not REGIME_FILE.exists():
        raise RuntimeError(
            "market_regime.json غير موجود"
        )

    payload = json.loads(
        REGIME_FILE.read_text(
            encoding="utf-8"
        )
    )

    profile = payload.get(
        "filter_profile",
        {},
    )

    if not isinstance(profile, dict):
        raise RuntimeError(
            "filter_profile غير موجود "
            "في market_regime.json"
        )

    env: Dict[str, str] = {}

    for key, value in profile.items():
        env[str(key)] = str(value)

    env["MARKET_REGIME"] = str(
        payload.get(
            "regime",
            "NORMAL",
        )
    )

    env["MARKET_REGIME_AR"] = str(
        payload.get(
            "regime_ar",
            "طبيعي",
        )
    )

    return env


def enforce_minimum(
    env: Dict[str, str],
    key: str,
    minimum: float,
) -> None:
    current = fnum(
        env.get(key),
        minimum,
    )

    env[key] = str(
        max(current, minimum)
    )


def enforce_maximum(
    env: Dict[str, str],
    key: str,
    maximum: float,
) -> None:
    current = fnum(
        env.get(key),
        maximum,
    )

    env[key] = str(
        min(current, maximum)
    )


def apply_quality_floors(
    profile: Dict[str, str],
) -> Dict[str, str]:
    env = dict(profile)

    # --------------------------------------------------------
    # Dynamic filters may become stricter,
    # but never weaker than these floors.
    # --------------------------------------------------------

    enforce_minimum(
        env,
        "MIN_SIGNAL_SCORE",
        80,
    )

    enforce_minimum(
        env,
        "MIN_RR",
        2.00,
    )

    enforce_minimum(
        env,
        "MIN_VOLUME_RATIO",
        1.00,
    )

    enforce_maximum(
        env,
        "MAX_RSI",
        72,
    )

    enforce_maximum(
        env,
        "MAX_OVERBOUGHT_RSI",
        70,
    )

    enforce_minimum(
        env,
        "MIN_BACKTEST_WIN_RATE",
        35,
    )

    # هنا نريد 4 تحديداً إذا كان النظام أكثر تساهلاً
    existing_bt_trades = int(
        fnum(
            env.get(
                "MIN_BACKTEST_TRADES_FOR_HARD_REJECT"
            ),
            4,
        )
    )

    env[
        "MIN_BACKTEST_TRADES_FOR_HARD_REJECT"
    ] = str(
        min(existing_bt_trades, 4)
    )

    # --------------------------------------------------------
    # Independent Quality Gate settings
    # --------------------------------------------------------

    for key, value in QUALITY_FLOORS.items():
        if key not in env:
            env[key] = value

    return env


def run(
    command: list[str],
    env: Dict[str, str] | None = None,
) -> int:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
    )

    return int(
        completed.returncode
    )


def print_profile(
    profile: Dict[str, str],
) -> None:
    print("=" * 72)
    print(
        "راصد — Regime-Aware Signal Pipeline v10"
    )
    print("=" * 72)

    print(
        f"📊 MARKET_REGIME="
        f"{profile.get('MARKET_REGIME')}"
    )

    print(
        f"🎯 MIN_SIGNAL_SCORE="
        f"{profile.get('MIN_SIGNAL_SCORE')}"
    )

    print(
        f"⚖️ MIN_RR="
        f"{profile.get('MIN_RR')}"
    )

    print(
        f"💧 MIN_VOLUME_RATIO="
        f"{profile.get('MIN_VOLUME_RATIO')}"
    )

    print(
        f"📉 RSI="
        f"{profile.get('MIN_RSI', 'default')}"
        f".."
        f"{profile.get('MAX_RSI')}"
    )

    print(
        f"🔥 MAX_OVERBOUGHT_RSI="
        f"{profile.get('MAX_OVERBOUGHT_RSI')}"
    )

    print(
        f"🧪 BACKTEST="
        f"{profile.get('MIN_BACKTEST_WIN_RATE')}% "
        f"/ "
        f"{profile.get('MIN_BACKTEST_TRADES_FOR_HARD_REJECT')} "
        f"trades"
    )

    print(
        f"🛡 QUALITY_MIN_RASED_SCORE="
        f"{profile.get('QUALITY_MIN_RASED_SCORE')}"
    )

    print(
        f"🛡 QUALITY_MIN_RR="
        f"{profile.get('QUALITY_MIN_RR')}"
    )

    print(
        f"🛡 QUALITY_MAX_RSI="
        f"{profile.get('QUALITY_MAX_RSI')}"
    )

    print("=" * 72)


def main() -> int:
    DATA.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # 1. Detect market regime
    # --------------------------------------------------------

    detector_code = run(
        [
            sys.executable,
            str(DETECTOR),
        ]
    )

    if detector_code != 0:
        print(
            "❌ فشل تحديد حالة السوق"
        )

        return detector_code

    # --------------------------------------------------------
    # 2. Load dynamic profile
    # --------------------------------------------------------

    profile = load_profile()

    # --------------------------------------------------------
    # 3. Apply permanent RASED quality floors
    # --------------------------------------------------------

    profile = apply_quality_floors(
        profile
    )

    process_env = os.environ.copy()
    process_env.update(profile)

    print_profile(
        profile
    )

    # --------------------------------------------------------
    # 4. Generate signals
    # --------------------------------------------------------

    generator_code = run(
        [
            sys.executable,
            str(GENERATOR),
        ],
        env=process_env,
    )

    if generator_code != 0:
        print(
            "❌ فشل توليد الإشارات"
        )

        return generator_code

    # --------------------------------------------------------
    # 5. Independent quality gate
    # --------------------------------------------------------

    quality_code = run(
        [
            sys.executable,
            str(QUALITY_GATE),
        ],
        env=process_env,
    )

    if quality_code != 0:
        print(
            "❌ فشلت بوابة جودة الإشارات"
        )

        return quality_code

    print("=" * 72)
    print(
        "✅ اكتمل توليد وفحص إشارات راصد V10"
    )
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())