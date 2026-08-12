#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RASED Regime-Aware Signal Pipeline v10.1
========================================

الترتيب:
1) تحديد حالة السوق.
2) قراءة filter_profile الديناميكي.
3) فرض حدود دنيا ثابتة للجودة مع الحفاظ على أنواع env الصحيحة.
4) توليد الإشارات.
5) تشغيل RASED Signal Quality Gate v10.

أهم إصلاح:
MIN_SIGNAL_SCORE يجب أن يمر إلى generate_signal.py كعدد صحيح
مثل "81" وليس "81.0"، لأن generate_signal.py يستخدم int(...).
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Mapping


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

REGIME_FILE = DATA_DIR / "market_regime.json"

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


# ------------------------------------------------------------
# Environment variable types expected by downstream scripts
# ------------------------------------------------------------

INT_ENV_KEYS = {
    "MIN_SIGNAL_SCORE",
    "MIN_BACKTEST_TRADES",
    "MIN_BACKTEST_TRADES_FOR_HARD_REJECT",
    "QUALITY_MAX_SIGNALS",
    "QUALITY_BACKTEST_ZERO_REJECT_MIN_TRADES",
    "QUALITY_BACKTEST_HARD_MIN_TRADES",
}

BOOL_ENV_KEYS = set()


# ------------------------------------------------------------
# Permanent floors / ceilings
# ------------------------------------------------------------

QUALITY_DEFAULTS: Dict[str, object] = {
    # Technical engine floors
    "MIN_SIGNAL_SCORE": 80,
    "MIN_RR": 2.00,
    "MIN_VOLUME_RATIO": 1.00,
    "MAX_RSI": 72,
    "MAX_OVERBOUGHT_RSI": 70,
    "MIN_BACKTEST_WIN_RATE": 35,
    "MIN_BACKTEST_TRADES_FOR_HARD_REJECT": 4,

    # Independent Quality Gate
    "QUALITY_MIN_RASED_SCORE": 82,
    "QUALITY_MIN_TECHNICAL_SCORE": 80,
    "QUALITY_MIN_RR": 2.00,
    "QUALITY_MIN_VOLUME_RATIO": 1.15,
    "QUALITY_MAX_RSI": 70,
    "QUALITY_MAX_ATR_PCT": 8.0,
    "QUALITY_MIN_TP1_PCT": 4.0,
    "QUALITY_MIN_TP2_PCT": 6.0,
    "QUALITY_MAX_ENTRY_GAP_PCT": 3.0,

    # Backtest quality
    "QUALITY_BACKTEST_ZERO_REJECT_MIN_TRADES": 3,
    "QUALITY_BACKTEST_HARD_MIN_TRADES": 4,
    "QUALITY_BACKTEST_MIN_WIN_RATE": 35,

    # Chase protection
    "QUALITY_CHASE_RSI": 68,
    "QUALITY_CHASE_DAILY_CHANGE_PCT": 5.5,
    "QUALITY_CHASE_MIN_RR": 2.40,
    "QUALITY_CHASE_MIN_VOLUME_RATIO": 2.0,

    # Publish only the best few
    "QUALITY_MAX_SIGNALS": 3,
}


def fnum(
    value: object,
    default: float = 0.0,
) -> float:
    try:
        if value is None or value == "":
            return default

        return float(value)

    except Exception:
        return default


def format_env_value(
    key: str,
    value: object,
) -> str:
    """
    Preserve downstream type contracts.
    """
    if key in INT_ENV_KEYS:
        return str(
            int(round(fnum(value)))
        )

    if key in BOOL_ENV_KEYS:
        return (
            "true"
            if bool(value)
            else "false"
        )

    if isinstance(value, bool):
        return (
            "true"
            if value
            else "false"
        )

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if math.isfinite(value):
            return (
                f"{value:.10f}"
                .rstrip("0")
                .rstrip(".")
            )
        return str(value)

    return str(value)


def load_regime_payload() -> Dict[str, object]:
    if not REGIME_FILE.exists():
        raise RuntimeError(
            "market_regime.json غير موجود بعد تشغيل detector"
        )

    payload = json.loads(
        REGIME_FILE.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, dict):
        raise RuntimeError(
            "market_regime.json ليس JSON object صالحًا"
        )

    return payload


def load_profile() -> Dict[str, str]:
    payload = load_regime_payload()

    profile = payload.get(
        "filter_profile",
        {},
    )

    if not isinstance(profile, dict):
        raise RuntimeError(
            "filter_profile غير موجود في market_regime.json"
        )

    env: Dict[str, str] = {}

    for key, value in profile.items():
        env[str(key)] = format_env_value(
            str(key),
            value,
        )

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


def set_minimum(
    env: Dict[str, str],
    key: str,
    minimum: float,
) -> None:
    current = fnum(
        env.get(key),
        minimum,
    )

    env[key] = format_env_value(
        key,
        max(current, minimum),
    )


def set_maximum(
    env: Dict[str, str],
    key: str,
    maximum: float,
) -> None:
    current = fnum(
        env.get(key),
        maximum,
    )

    env[key] = format_env_value(
        key,
        min(current, maximum),
    )


def apply_quality_contract(
    profile: Mapping[str, str],
) -> Dict[str, str]:
    env = dict(profile)

    # Dynamic market regime may become stricter, never weaker.
    set_minimum(
        env,
        "MIN_SIGNAL_SCORE",
        fnum(QUALITY_DEFAULTS["MIN_SIGNAL_SCORE"]),
    )

    set_minimum(
        env,
        "MIN_RR",
        fnum(QUALITY_DEFAULTS["MIN_RR"]),
    )

    set_minimum(
        env,
        "MIN_VOLUME_RATIO",
        fnum(QUALITY_DEFAULTS["MIN_VOLUME_RATIO"]),
    )

    set_maximum(
        env,
        "MAX_RSI",
        fnum(QUALITY_DEFAULTS["MAX_RSI"]),
    )

    set_maximum(
        env,
        "MAX_OVERBOUGHT_RSI",
        fnum(QUALITY_DEFAULTS["MAX_OVERBOUGHT_RSI"]),
    )

    set_minimum(
        env,
        "MIN_BACKTEST_WIN_RATE",
        fnum(
            QUALITY_DEFAULTS[
                "MIN_BACKTEST_WIN_RATE"
            ]
        ),
    )

    # A hard-reject threshold above 4 would make the engine more
    # permissive. Cap it at 4.
    current_hard_reject = fnum(
        env.get(
            "MIN_BACKTEST_TRADES_FOR_HARD_REJECT"
        ),
        4,
    )

    env[
        "MIN_BACKTEST_TRADES_FOR_HARD_REJECT"
    ] = format_env_value(
        "MIN_BACKTEST_TRADES_FOR_HARD_REJECT",
        min(current_hard_reject, 4),
    )

    # Independent gate defaults.
    for key, value in QUALITY_DEFAULTS.items():
        if key not in env:
            env[key] = format_env_value(
                key,
                value,
            )

    # Final normalization prevents "81.0" for integer variables.
    for key in list(env):
        env[key] = format_env_value(
            key,
            env[key],
        )

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


def run_step(
    title: str,
    command: list[str],
    env: Dict[str, str] | None = None,
) -> int:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)

    code = run(
        command,
        env=env,
    )

    if code != 0:
        print(
            f"❌ Failed: {title} "
            f"(exit={code})"
        )

    return code


def print_profile(
    profile: Dict[str, str],
) -> None:
    print()
    print("=" * 72)
    print(
        "RASED — Regime-Aware Signal Pipeline v10.1"
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
        f"🧪 BACKTEST HARD REJECT="
        f"{profile.get('MIN_BACKTEST_WIN_RATE')}% "
        f"at "
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

    print(
        f"🛡 QUALITY_MAX_SIGNALS="
        f"{profile.get('QUALITY_MAX_SIGNALS')}"
    )

    print("=" * 72)


def main() -> int:
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # 1) Detect market regime
    # --------------------------------------------------------

    code = run_step(
        "1/3 Detect market regime",
        [
            sys.executable,
            str(DETECTOR),
        ],
    )

    if code != 0:
        return code

    # --------------------------------------------------------
    # 2) Load + enforce profile
    # --------------------------------------------------------

    try:
        profile = load_profile()
        profile = apply_quality_contract(
            profile
        )

    except Exception as exc:
        print(
            f"❌ Unable to build regime profile: {exc}"
        )
        return 1

    process_env = os.environ.copy()
    process_env.update(profile)

    print_profile(
        profile
    )

    # --------------------------------------------------------
    # 3) Generate signals
    # --------------------------------------------------------

    code = run_step(
        "2/3 Generate signals",
        [
            sys.executable,
            str(GENERATOR),
        ],
        env=process_env,
    )

    if code != 0:
        return code

    # --------------------------------------------------------
    # 4) Independent Quality Gate
    # --------------------------------------------------------

    if not QUALITY_GATE.exists():
        print(
            f"❌ Missing quality gate: {QUALITY_GATE}"
        )
        return 1

    code = run_step(
        "3/3 Apply RASED Quality Gate v10",
        [
            sys.executable,
            str(QUALITY_GATE),
        ],
        env=process_env,
    )

    if code != 0:
        return code

    print()
    print("=" * 72)
    print(
        "✅ RASED signal pipeline completed successfully"
    )
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())
