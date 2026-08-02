#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد — Regime-Aware Signal Pipeline

يشغّل market_regime_detector.py أولًا، ثم يقرأ ملف الفلاتر الناتج
ويشغّل generate_signal.py بالحدود المناسبة لحالة السوق الحالية.

بهذا تصبح Market Regime Detection طبقة تسبق تحليل الأسهم فعلًا.
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
DETECTOR = ROOT / "scripts" / "market_regime_detector.py"
GENERATOR = ROOT / "scripts" / "generate_signal.py"


def load_profile() -> Dict[str, str]:
    payload = json.loads(REGIME_FILE.read_text(encoding="utf-8"))
    profile = payload.get("filter_profile", {})
    if not isinstance(profile, dict):
        raise RuntimeError("filter_profile غير موجود في market_regime.json")

    env: Dict[str, str] = {}
    for key, value in profile.items():
        env[str(key)] = str(value)

    env["MARKET_REGIME"] = str(payload.get("regime", "NORMAL"))
    env["MARKET_REGIME_AR"] = str(payload.get("regime_ar", "طبيعي"))
    return env


def run(command: list[str], env: Dict[str, str] | None = None) -> int:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)

    detector_code = run([sys.executable, str(DETECTOR)])
    if detector_code != 0:
        print("❌ فشل تحديد حالة السوق")
        return detector_code

    profile = load_profile()
    process_env = os.environ.copy()
    process_env.update(profile)

    print("=" * 68)
    print("راصد — Regime-Aware Signal Pipeline")
    print("=" * 68)
    print(f"📊 MARKET_REGIME={profile['MARKET_REGIME']}")
    print(f"🎯 MIN_SIGNAL_SCORE={profile.get('MIN_SIGNAL_SCORE')}")
    print(f"⚖️ MIN_RR={profile.get('MIN_RR')}")
    print(f"💧 MIN_VOLUME_RATIO={profile.get('MIN_VOLUME_RATIO')}")
    print(f"📉 RSI={profile.get('MIN_RSI')}..{profile.get('MAX_RSI')}")

    return run(
        [sys.executable, str(GENERATOR)],
        env=process_env,
    )


if __name__ == "__main__":
    sys.exit(main())
