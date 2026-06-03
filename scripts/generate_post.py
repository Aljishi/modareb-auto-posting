#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""راصد — توليد صورة Premium للإشارة اليومية."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw, ImageFont

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_AR = True
except Exception:
    HAS_AR = False

W, H = 1080, 1080
BG = "#0A0E1A"
CARD = "#111827"
CARD2 = "#0F172A"
GOLD = "#D4AF37"
GOLD2 = "#F5D060"
WHITE = "#FFFFFF"
GRAY = "#9CA3AF"
GREEN = "#22C55E"
RED = "#EF4444"
BLUE = "#38BDF8"
BORDER = "#26364F"

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets"


def ar(text: Any) -> str:
    s = str(text)
    if HAS_AR:
        try:
            return get_display(arabic_reshaper.reshape(s))
        except Exception:
            return s
    return s


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace("%", "").replace(",", "").strip()
        return float(x)
    except Exception:
        return default


def safe_int_percent(*values: Any, default: int = 0) -> int:
    for v in values:
        try:
            n = fnum(v, None)
            if n is not None:
                return int(round(n))
        except Exception:
            pass
    return default


def load_signal(path: str) -> Optional[Dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if "validated_signals" in raw:
        sigs = raw.get("validated_signals", [])
        return sigs[0] if sigs else None
    if "signals" in raw:
        sigs = raw.get("signals", [])
        return sigs[0] if sigs else None
    return raw if isinstance(raw, dict) else None


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = []
    if bold:
        candidates += [ASSET_DIR / "Tajawal-Bold.ttf", ASSET_DIR / "Cairo-Bold.ttf"]
    else:
        candidates += [ASSET_DIR / "Tajawal-Regular.ttf", ASSET_DIR / "Cairo-Regular.ttf"]
    # fallback: original project sometimes stores fonts directly under assets
    candidates += [ASSET_DIR / "Tajawal-Bold.ttf", ASSET_DIR / "Tajawal-Regular.ttf"]
    for p in candidates:
        try:
            if p.exists():
                return ImageFont.truetype(str(p), size)
        except Exception:
            pass
    return ImageFont.load_default()


def text_w(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0]


def center(draw, y, text, fnt, fill=WHITE):
    x = (W - text_w(draw, text, fnt)) // 2
    draw.text((x, y), text, font=fnt, fill=fill)


def rounded(draw, xy, fill, outline=None, width=1, radius=26):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def row(draw, y, label, value, pct_text=None, icon="", value_color=WHITE):
    x1, x2 = 70, W - 70
    rounded(draw, (x1, y, x2, y + 90), CARD, BORDER, 1, 18)
    draw.text((x1 + 28, y + 28), icon, font=font(28), fill=GOLD2)
    draw.text((x1 + 78, y + 30), ar(label), font=font(25, False), fill=GRAY)
    val = ar(value)
    fval = font(34)
    vx = x2 - 40 - text_w(draw, val, fval)
    draw.text((vx, y + 23), val, font=fval, fill=value_color)
    if pct_text:
        fp = font(25)
        draw.text((vx - text_w(draw, pct_text, fp) - 18, y + 31), pct_text, font=fp, fill=value_color)


def build_image(signal: Dict[str, Any], out_path: str):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Outer premium border
    draw.rectangle((16, 16, W - 16, H - 16), outline=GOLD, width=3)
    draw.rectangle((26, 26, W - 26, H - 26), outline="#3B2F12", width=1)

    # Header
    tier = signal.get("tier", "Premium")
    tier_emoji = signal.get("tier_emoji", "⭐")
    center(draw, 52, f"{tier_emoji} RASED {tier.upper()} SIGNAL", font(42), GOLD2)
    center(draw, 110, ar("إشارة تداول احترافية"), font(27, False), GRAY)

    # Stock card
    rounded(draw, (70, 165, W - 70, 270), CARD2, GOLD, 2, 22)
    sym = signal.get("stock_symbol", signal.get("symbol", ""))
    name = signal.get("stock_name", signal.get("name", ""))
    center(draw, 190, ar(f"{sym} | {name}"), font(43), WHITE)
    sector = signal.get("sector", "")
    if sector:
        center(draw, 238, ar(sector), font(22, False), GRAY)

    # Trade rows
    y = 315
    row(draw, y, "نقطة الدخول", f"{fnum(signal.get('entry_point', signal.get('entry'))):.2f} ريال", icon="💰", value_color=WHITE)
    y += 106
    row(draw, y, "الهدف الأول", f"{fnum(signal.get('target1')):.2f} ريال", f"+{fnum(signal.get('target1_percent')):.2f}%", icon="🎯", value_color=GREEN)
    y += 106
    row(draw, y, "الهدف الثاني", f"{fnum(signal.get('target2')):.2f} ريال", f"+{fnum(signal.get('target2_percent')):.2f}%", icon="🎯", value_color=GREEN)
    y += 106
    row(draw, y, "وقف الخسارة", f"{fnum(signal.get('stop_loss')):.2f} ريال", f"-{fnum(signal.get('stop_loss_percent')):.2f}%", icon="🛑", value_color=RED)

    # Score panel
    y = 750
    rounded(draw, (70, y, W - 70, y + 175), CARD2, BORDER, 1, 24)
    score = fnum(signal.get("rased_score"), fnum(signal.get("score"), 0))
    confidence = safe_int_percent(signal.get("ai_confidence"), signal.get("confidence"), default=int(round(score)))
    risk = signal.get("risk_level", "متوسط")
    risk_emoji = signal.get("risk_emoji", "🟡")

    draw.text((105, y + 28), "RASED SCORE™", font(28), GOLD2)
    draw.text((105, y + 70), f"{score:.1f} / 100", font(42), WHITE)

    draw.text((430, y + 28), ar("الثقة"), font(26, False), GRAY)
    draw.text((430, y + 70), f"{confidence}%", font(42), BLUE)

    draw.text((690, y + 28), ar("المخاطرة"), font(26, False), GRAY)
    draw.text((690, y + 70), ar(f"{risk_emoji} {risk}"), font(36), GREEN if risk == "منخفض" else GOLD2)

    # Holding period
    rounded(draw, (170, 945, W - 170, 1005), "#0B1220", GOLD, 1, 30)
    center(draw, 959, ar("⏳ مدة الصفقة المتوقعة: 1–7 أيام"), font(27), WHITE)

    # Footer
    now = datetime.now().strftime("%Y-%m-%d | %I:%M %p KSA").replace("AM", "ص").replace("PM", "م")
    center(draw, 1024, now, font(20, False), GRAY)

    img.save(out_path, quality=95)
    print(f"✅ Premium post image saved: {out_path}")


def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "validated_signals.json")
    output_path = sys.argv[2] if len(sys.argv) > 2 else "output.png"
    signal = load_signal(input_path)
    if not signal:
        print("❌ لا توجد إشارة لتوليد الصورة")
        sys.exit(1)
    build_image(signal, output_path)


if __name__ == "__main__":
    main()
