#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد | Rased
Normal daily signal image generator.
Design: matches the attached normal signal style.
Output: output.png
"""

import io
import json
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_OK = True
except Exception:
    ARABIC_OK = False


# =========================
# Canvas / Brand
# =========================

W, H = 1080, 1080

BRAND_NAME = "راصد"
BRAND_SUBTITLE = "تحليل فني وتعليمي لسوق الأسهم السعودية"
CHANNEL = "t.me/Rased_Smart"

COLORS = {
    "bg": "#07101E",
    "panel": "#0B1626",
    "row": "#101B2C",
    "row_border": "#263247",
    "gold": "#D4AF37",
    "gold2": "#F2C94C",
    "white": "#F4F6FA",
    "muted": "#9AA6B8",
    "green": "#19D36B",
    "red": "#FF4D68",
    "dark": "#060B14",
}


def rtl(text):
    text = "" if text is None else str(text)
    if not ARABIC_OK:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def load_font(size, bold=False):
    base = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    candidates = [
        "Tajawal-Bold.ttf" if bold else "Tajawal-Regular.ttf",
        "Cairo-Bold.ttf" if bold else "Cairo-Regular.ttf",
        "Arial-Bold.ttf" if bold else "Arial-Regular.ttf",
    ]

    for name in candidates:
        p = base / name
        if p.exists():
            return ImageFont.truetype(str(p), size)

    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass

    return ImageFont.load_default()


FONTS = {
    "top": load_font(26, True),
    "brand": load_font(90, True),
    "subtitle": load_font(31, False),
    "stock": load_font(62, True),
    "label": load_font(34, True),
    "value": load_font(36, True),
    "percent": load_font(27, True),
    "note": load_font(23, False),
    "footer": load_font(23, False),
    "channel": load_font(26, True),
}


def text_size(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def center_text(draw, y, text, font, fill):
    text = rtl(text)
    tw, th = text_size(draw, text, font)
    draw.text(((W - tw) / 2, y), text, font=font, fill=fill)
    return y + th


def rounded(draw, xy, r, fill=None, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def pct_from(entry, target):
    try:
        entry = float(entry)
        target = float(target)
        if entry == 0:
            return ""
        return f"{((target - entry) / entry) * 100:+.1f}%"
    except Exception:
        return ""


def value(data, *keys, default=""):
    for k in keys:
        if k in data and data[k] not in [None, ""]:
            return data[k]
    return default


def draw_logo(draw, cx, cy):
    gold = COLORS["gold2"]
    r = 62
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=gold, width=3)

    # bars
    bars = [(cx - 31, cy + 26, 13, 28), (cx - 11, cy + 26, 13, 42), (cx + 9, cy + 26, 13, 56)]
    for x, y, bw, bh in bars:
        draw.rectangle((x, y - bh, x + bw, y), fill=gold)

    # arrow
    draw.line((cx - 39, cy + 22, cx - 5, cy + 2, cx + 39, cy - 45), fill=gold, width=6)
    draw.polygon([(cx + 39, cy - 45), (cx + 16, cy - 37), (cx + 34, cy - 18)], fill=gold)


def draw_line_with_dot(draw, y, x1=170, x2=910):
    mid = W // 2
    draw.line((x1, y, mid - 16, y), fill=COLORS["gold"], width=2)
    draw.line((mid + 16, y, x2, y), fill=COLORS["gold"], width=2)
    draw.ellipse((mid - 7, y - 7, mid + 7, y + 7), fill=COLORS["gold2"])


def draw_row(draw, y, label, amount, color, icon="◎", pct=""):
    x1, x2 = 62, 1018
    h = 76
    rounded(draw, (x1, y, x2, y + h), 16, fill=COLORS["row"], outline=COLORS["row_border"], width=2)

    # left percent area
    if pct:
        draw.line((250, y + 9, 250, y + h - 9), fill="#1D2A3F", width=2)
        pct_fill = COLORS["green"] if pct.startswith("+") else COLORS["red"]
        draw.text((110, y + 23), pct, font=FONTS["percent"], fill=pct_fill)

    # right icon circle
    icx, icy = 970, y + h // 2
    draw.ellipse((icx - 24, icy - 24, icx + 24, icy + 24), outline=color, width=3)
    iw, ih = text_size(draw, icon, FONTS["label"])
    draw.text((icx - iw / 2, icy - ih / 2 - 1), icon, font=FONTS["label"], fill=color)

    # Arabic label on right
    label_txt = rtl(label)
    lw, lh = text_size(draw, label_txt, FONTS["label"])
    draw.text((920 - lw, y + 20), label_txt, font=FONTS["label"], fill=color)

    # amount in center-left
    amount_txt = rtl(amount)
    aw, ah = text_size(draw, amount_txt, FONTS["value"])
    draw.text((410 - aw / 2, y + 20), amount_txt, font=FONTS["value"], fill=color)


def wrap_arabic(draw, text, font, max_width):
    words = str(text).split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        if text_size(draw, rtl(test), font)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines[:2]


def generate(input_path="data/daily.json", output_path="output.png"):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    # Main panel: normal signal style
    panel = (42, 68, 1038, 1018)
    rounded(draw, panel, 26, fill=COLORS["panel"], outline=COLORS["gold"], width=3)

    # Top bar
    now = datetime.now()
    time_txt = now.strftime("%I:%M م").lstrip("0")
    date_txt = now.strftime("%Y/%m/%d")
    draw.text((92, 100), rtl(time_txt), font=FONTS["top"], fill=COLORS["green"])

    badge_txt = rtl("وقت الإشارة")
    bw, bh = text_size(draw, badge_txt, FONTS["top"])
    draw.text(((W - bw) / 2, 100), badge_txt, font=FONTS["top"], fill=COLORS["muted"])

    dw, dh = text_size(draw, date_txt, FONTS["top"])
    draw.text((W - 92 - dw, 100), date_txt, font=FONTS["top"], fill=COLORS["gold2"])
    draw.line((80, 145, 1000, 145), fill=COLORS["gold"], width=1)

    # Logo and brand
    draw_logo(draw, W // 2, 220)
    center_text(draw, 292, BRAND_NAME, FONTS["brand"], COLORS["gold2"])
    center_text(draw, 397, BRAND_SUBTITLE, FONTS["subtitle"], COLORS["white"])
    draw_line_with_dot(draw, 468, 225, 855)

    # Stock name
    symbol = value(data, "stock_symbol", "symbol", default="")
    name = value(data, "stock_name", "name", default="")
    stock_title = f"{name} - {symbol}".strip(" -")
    center_text(draw, 506, stock_title, FONTS["stock"], COLORS["white"])
    draw_line_with_dot(draw, 590, 235, 845)

    # Values
    price = value(data, "current_price", "price", default="0")
    entry = value(data, "entry_point", "entry", default=price)
    t1 = value(data, "target1", "target_1", default="")
    t2 = value(data, "target2", "target_2", default="")
    sl = value(data, "stop_loss", "sl", default="")

    t1p = str(value(data, "target1_percent", "target_1_percent", default="")).replace("%", "")
    t2p = str(value(data, "target2_percent", "target_2_percent", default="")).replace("%", "")
    slp = str(value(data, "stop_loss_percent", "sl_percent", default="")).replace("%", "")

    t1p = f"+{t1p}%" if t1p and not t1p.startswith(("+", "-")) else (f"{t1p}%" if t1p and not t1p.endswith("%") else t1p)
    t2p = f"+{t2p}%" if t2p and not t2p.startswith(("+", "-")) else (f"{t2p}%" if t2p and not t2p.endswith("%") else t2p)
    slp = f"-{slp}%" if slp and not slp.startswith(("+", "-")) else (f"{slp}%" if slp and not slp.endswith("%") else slp)

    if not t1p:
        t1p = pct_from(entry, t1)
    if not t2p:
        t2p = pct_from(entry, t2)
    if not slp:
        slp = pct_from(entry, sl)

    y = 625
    draw_row(draw, y, "السعر الحالي:", f"{price} ريال", COLORS["white"], icon="◔", pct="")
    y += 84
    draw_row(draw, y, "نقطة الدخول:", f"{entry} ريال", COLORS["gold2"], icon="◎", pct="")
    y += 84
    draw_row(draw, y, "الهدف الأول:", f"{t1} ريال", COLORS["green"], icon="◎", pct=t1p)
    y += 84
    draw_row(draw, y, "الهدف الثاني:", f"{t2} ريال", COLORS["green"], icon="◎", pct=t2p)
    y += 84
    draw_row(draw, y, "وقف الخسارة:", f"{sl} ريال", COLORS["red"], icon="×", pct=slp)

    # Technical reading
    note = (
        value(data, "technical_reading", default="")
        or value(data, "signal_reason", default="")
        or value(data, "note", default="")
        or "قراءة فنية تعليمية: قريب من اختراق مقاومة + حجم تداول أعلى من المتوسط + RSI صحي للزخم"
    )

    note_box = (62, 956 - 96, 1018, 956)
    rounded(draw, note_box, 12, fill=COLORS["row"], outline=COLORS["gold"], width=2)
    lines = wrap_arabic(draw, note, FONTS["note"], 860)
    ty = note_box[1] + 22
    for line in lines:
        line = rtl(line)
        lw, lh = text_size(draw, line, FONTS["note"])
        draw.text(((W - lw) / 2, ty), line, font=FONTS["note"], fill=COLORS["muted"])
        ty += 30

    # Footer
    draw.line((160, 965, 920, 965), fill=COLORS["gold"], width=2)
    disclaimer = rtl("محتوى تعليمي وتحليلي فقط - لا يعد توصية استثمارية")
    dw, dh = text_size(draw, disclaimer, FONTS["footer"])
    draw.text(((W - dw) / 2, 984), disclaimer, font=FONTS["footer"], fill=COLORS["muted"])

    ch_w, ch_h = text_size(draw, CHANNEL, FONTS["channel"])
    bx1, by1, bx2, by2 = (W - ch_w - 80) / 2, 1014, (W + ch_w + 80) / 2, 1060
    rounded(draw, (bx1, by1, bx2, by2), 22, fill=COLORS["panel"], outline=COLORS["gold"], width=2)
    draw.text(((W - ch_w) / 2, 1024), CHANNEL, font=FONTS["channel"], fill=COLORS["gold2"])

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG", quality=95)
    print(f"✅ تم إنشاء التصميم العادي باسم راصد: {output_path}")


def main():
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    base = Path(__file__).resolve().parent.parent
    input_path = sys.argv[1] if len(sys.argv) > 1 else str(base / "data" / "daily.json")
    output_path = sys.argv[2] if len(sys.argv) > 2 else str(base / "output.png")
    generate(input_path, output_path)


if __name__ == "__main__":
    main()
