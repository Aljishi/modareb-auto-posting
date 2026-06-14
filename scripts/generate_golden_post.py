#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Generate a simple golden signal image for Telegram."""

import json
import sys
from pathlib import Path
from typing import Any, Dict

from PIL import Image, ImageDraw, ImageFont


def fnum(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        if isinstance(x, str):
            x = x.replace("%", "").replace(",", "").strip()
        return float(x)
    except Exception:
        return default


def load_signal(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data[0] if data else {}
    signals = data.get("golden_signals") or data.get("signals") or []
    return signals[0] if signals else data


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def text(draw, xy, content, size=32, fill=(30, 30, 30), bold=False):
    draw.text(xy, str(content), font=font(size, bold), fill=fill)


def main() -> int:
    in_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/golden_signals.json")
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("golden_output.png")

    s = load_signal(in_path)
    if not s:
        print("No golden signal to draw")
        return 0

    status = str(s.get("status", "PREMARKET")).upper()
    title = s.get("golden_title") or ("🌟 تأكيد الإشارة الذهبية" if status == "CONFIRMED" else "👑 الإشارة الذهبية قبل الافتتاح")
    name = s.get("stock_name") or s.get("name") or s.get("symbol")
    symbol = s.get("symbol") or s.get("stock_symbol") or ""

    img = Image.new("RGB", (1080, 1350), (250, 246, 236))
    d = ImageDraw.Draw(img)

    # Header
    d.rounded_rectangle((60, 50, 1020, 220), radius=30, fill=(33, 37, 41))
    text(d, (100, 85), title, 44, (255, 215, 90), True)
    text(d, (100, 150), f"{name} ({symbol})", 38, (255, 255, 255), True)

    y = 280
    if status == "CANCELLED":
        d.rounded_rectangle((60, y, 1020, y + 260), radius=25, fill=(255, 235, 235))
        text(d, (100, y + 40), "⚠️ تم إلغاء / عدم تأكيد الذهبية", 40, (160, 30, 30), True)
        reason = s.get("confirmation_reason") or s.get("key_insight") or "لم تعد شروط الذهبية مكتملة."
        text(d, (100, y + 115), reason[:90], 30, (90, 40, 40), False)
        y += 320
    else:
        rows = [
            ("نقطة الدخول", s.get("entry") or s.get("entry_point")),
            ("الهدف الأول", f"{s.get('target1')}  (+{s.get('target1_percent') or s.get('tp1_pct')}%)"),
            ("الهدف الثاني", f"{s.get('target2')}  (+{s.get('target2_percent') or s.get('tp2_pct')}%)"),
            ("وقف الخسارة", f"{s.get('stop_loss')}  ({s.get('sl_pct') or '-' + str(s.get('stop_loss_percent', ''))}%)"),
        ]
        for label, value in rows:
            d.rounded_rectangle((60, y, 1020, y + 95), radius=20, fill=(255, 255, 255))
            text(d, (95, y + 22), label, 30, (80, 80, 80), True)
            text(d, (500, y + 22), value, 32, (20, 90, 60), True)
            y += 115

    d.rounded_rectangle((60, y, 1020, y + 230), radius=25, fill=(255, 255, 255))
    text(d, (95, y + 30), "RASED SCORE™", 34, (80, 80, 80), True)
    text(d, (620, y + 25), f"{s.get('rased_score') or s.get('score')} / 100", 42, (205, 150, 20), True)
    text(d, (95, y + 95), f"RSI: {s.get('rsi')} | Volume: {s.get('volume_ratio')}x | R:R: {s.get('rr') or s.get('rr_ratio')}", 29, (40, 40, 40), False)
    text(d, (95, y + 145), f"ATR: {s.get('atr_pct')}% | الحالة: {s.get('confirmation_status') or status}", 29, (40, 40, 40), False)
    y += 280

    d.rounded_rectangle((60, y, 1020, y + 250), radius=25, fill=(245, 240, 220))
    text(d, (95, y + 30), "ملخص راصد", 34, (80, 70, 40), True)
    summary = s.get("key_insight") or s.get("signal_reason") or "إشارة ذهبية آلية خاضعة لإدارة المخاطر."
    text(d, (95, y + 95), summary[:100], 28, (60, 60, 60), False)
    text(d, (95, y + 160), "محتوى تعليمي آلي وليس توصية استثمارية.", 26, (120, 70, 30), False)

    img.save(out_path)
    print(f"✅ Golden image saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
