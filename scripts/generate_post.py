#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راصد | Rased
Normal signal image generator - clean Arabic layout.
Output: output.png

Required:
Pillow
arabic-reshaper
python-bidi
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
except Exception:
    arabic_reshaper = None
    get_display = None


W, H = 1080, 1080

BRAND_NAME = "راصد"
BRAND_SUBTITLE = "تحليل فني وتعليمي لسوق الأسهم السعودية"
CHANNEL = "t.me/Rased_Smart"

COLORS = {
    "bg": "#07101E",
    "panel": "#0B1626",
    "row": "#101B2C",
    "row_border": "#2A3548",
    "gold": "#D4AF37",
    "gold2": "#F2C94C",
    "white": "#F5F7FB",
    "muted": "#A8B2C3",
    "green": "#18D26B",
    "red": "#FF4D68",
    "line": "#334156",
}


def ar(text):
    text = "" if text is None else str(text)
    if arabic_reshaper and get_display:
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            return text
    return text


def load_font(size, bold=False):
    base = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    names = [
        "Tajawal-Bold.ttf" if bold else "Tajawal-Regular.ttf",
        "Cairo-Bold.ttf" if bold else "Cairo-Regular.ttf",
        "NotoSansArabic-Bold.ttf" if bold else "NotoSansArabic-Regular.ttf",
        "NotoNaskhArabic-Bold.ttf" if bold else "NotoNaskhArabic-Regular.ttf",
    ]
    for name in names:
        p = base / name
        if p.exists():
            return ImageFont.truetype(str(p), size)

    system_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    ]
    for p in system_fonts:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


F = {
    "top": load_font(26, True),
    "brand": load_font(86, True),
    "subtitle": load_font(30, False),
    "stock": load_font(58, True),
    "label": load_font(33, True),
    "value": load_font(35, True),
    "percent": load_font(28, True),
    "note": load_font(25, False),
    "footer": load_font(23, False),
    "channel": load_font(27, True),
}


def size(draw, text, font):
    box = draw.textbbox((0, 0), str(text), font=font)
    return box[2] - box[0], box[3] - box[1]


def text_center(draw, y, text, font, fill):
    txt = ar(text)
    tw, th = size(draw, txt, font)
    draw.text(((W - tw) / 2, y), txt, font=font, fill=fill)
    return y + th


def text_right(draw, x_right, y, text, font, fill):
    txt = ar(text)
    tw, _ = size(draw, txt, font)
    draw.text((x_right - tw, y), txt, font=font, fill=fill)


def rr(draw, xy, r, fill=None, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def val(data, *keys, default=""):
    for k in keys:
        if k in data and data[k] not in ("", None):
            return data[k]
    return default


def money(v):
    try:
        return f"{float(v):.2f} ريال"
    except Exception:
        return f"{v} ريال"


def pct(entry, target):
    try:
        entry = float(entry)
        target = float(target)
        if entry == 0:
            return ""
        return f"{((target - entry) / entry) * 100:+.1f}%"
    except Exception:
        return ""


def norm_pct(raw, entry=None, target=None):
    raw = "" if raw is None else str(raw).strip()
    if raw:
        raw = raw.replace("%", "")
        if not raw.startswith(("+", "-")):
            raw = "+" + raw
        return raw + "%"
    return pct(entry, target)


def wrap(draw, text, font, max_width, max_lines=2):
    words = str(text).replace("\n", " ").split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if size(draw, ar(trial), font)[0] <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def logo(draw, cx, cy):
    gold = COLORS["gold2"]
    r = 58
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=gold, width=3)
    for x, y, bw, bh in [(cx - 31, cy + 24, 13, 27), (cx - 10, cy + 24, 13, 42), (cx + 11, cy + 24, 13, 57)]:
        draw.rectangle((x, y - bh, x + bw, y), fill=gold)
    draw.line((cx - 40, cy + 21, cx - 5, cy + 1, cx + 39, cy - 43), fill=gold, width=6)
    draw.polygon([(cx + 39, cy - 43), (cx + 16, cy - 36), (cx + 34, cy - 18)], fill=gold)


def divider(draw, y, x1=210, x2=870):
    mid = W // 2
    draw.line((x1, y, mid - 18, y), fill=COLORS["gold"], width=2)
    draw.line((mid + 18, y, x2, y), fill=COLORS["gold"], width=2)
    draw.ellipse((mid - 8, y - 8, mid + 8, y + 8), fill=COLORS["gold2"])


def row(draw, y, label, amount, color, icon, percent=""):
    x1, x2, h = 62, 1018, 72
    rr(draw, (x1, y, x2, y + h), 16, fill=COLORS["row"], outline=COLORS["row_border"], width=2)

    if percent:
        draw.line((245, y + 10, 245, y + h - 10), fill=COLORS["line"], width=2)
        pcolor = COLORS["green"] if percent.startswith("+") else COLORS["red"]
        draw.text((105, y + 20), percent, font=F["percent"], fill=pcolor)

    icx, icy = 970, y + h // 2
    draw.ellipse((icx - 25, icy - 25, icx + 25, icy + 25), outline=color, width=3)
    iw, ih = size(draw, icon, F["label"])
    draw.text((icx - iw / 2, icy - ih / 2 - 2), icon, font=F["label"], fill=color)

    text_right(draw, 915, y + 18, label, F["label"], color)

    amount_txt = ar(amount)
    aw, _ = size(draw, amount_txt, F["value"])
    draw.text((440 - aw / 2, y + 18), amount_txt, font=F["value"], fill=color)


def generate(input_path="data/daily.json", output_path="output.png"):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    rr(draw, (34, 28, W - 34, H - 28), 34, fill=COLORS["panel"], outline=COLORS["gold2"], width=3)

    now = datetime.now()
    time_txt = now.strftime("%I:%M م").lstrip("0")
    date_txt = now.strftime("%Y/%m/%d")

    draw.text((92, 68), ar(time_txt), font=F["top"], fill=COLORS["green"])
    draw_text = ar("وقت الإشارة")
    tw, _ = size(draw, draw_text, F["top"])
    draw.text(((W - tw) / 2, 68), draw_text, font=F["top"], fill=COLORS["muted"])
    dw, _ = size(draw, date_txt, F["top"])
    draw.text((W - 92 - dw, 68), date_txt, font=F["top"], fill=COLORS["gold2"])
    draw.line((70, 116, 1010, 116), fill=COLORS["gold"], width=1)

    logo(draw, W // 2, 185)
    text_center(draw, 265, BRAND_NAME, F["brand"], COLORS["gold2"])
    text_center(draw, 365, BRAND_SUBTITLE, F["subtitle"], COLORS["white"])
    divider(draw, 430)

    symbol = val(data, "stock_symbol", "symbol", default="")
    name = val(data, "stock_name", "name", default="")
    title = f"{name} - {symbol}".strip(" -")

    text_center(draw, 462, title, F["stock"], COLORS["white"])
    divider(draw, 535)

    price = val(data, "current_price", "price", default="0")
    entry = val(data, "entry_point", "entry", default=price)
    t1 = val(data, "target1", "target_1", default="")
    t2 = val(data, "target2", "target_2", default="")
    sl = val(data, "stop_loss", "sl", default="")

    t1p = norm_pct(val(data, "target1_percent", "target_1_percent", default=""), entry, t1)
    t2p = norm_pct(val(data, "target2_percent", "target_2_percent", default=""), entry, t2)
    slp = norm_pct(val(data, "stop_loss_percent", "sl_percent", default=""), entry, sl)

    y = 560
    row(draw, y, "السعر الحالي:", money(price), COLORS["white"], "◔")
    y += 78
    row(draw, y, "نقطة الدخول:", money(entry), COLORS["gold2"], "◎")
    y += 78
    row(draw, y, "الهدف الأول:", money(t1), COLORS["green"], "◎", t1p)
    y += 78
    row(draw, y, "الهدف الثاني:", money(t2), COLORS["green"], "◎", t2p)
    y += 78
    row(draw, y, "وقف الخسارة:", money(sl), COLORS["red"], "×", slp)

    note = (
        val(data, "technical_reading", default="")
        or val(data, "signal_reason", default="")
        or val(data, "note", default="")
        or "قراءة فنية تعليمية: قريب من اختراق مقاومة + حجم تداول أعلى من المتوسط + RSI صحي للزخم"
    )

    note_y = 962
    rr(draw, (62, note_y, 1018, note_y + 66), 14, fill=COLORS["row"], outline=COLORS["gold2"], width=2)
    lines = wrap(draw, note, F["note"], 880, max_lines=2)
    ty = note_y + 12
    for line in lines:
        txt = ar(line)
        lw, _ = size(draw, txt, F["note"])
        draw.text(((W - lw) / 2, ty), txt, font=F["note"], fill=COLORS["white"])
        ty += 28

    divider(draw, 1045, 260, 820)

    footer = ar("محتوى تعليمي وتحليلي فقط - لا يعد توصية استثمارية")
    fw, _ = size(draw, footer, F["footer"])
    draw.text(((W - fw) / 2, 1060), footer, font=F["footer"], fill=COLORS["muted"])

    ch_w, _ = size(draw, CHANNEL, F["channel"])
    rr(draw, ((W - ch_w - 92) / 2, 1090, (W + ch_w + 92) / 2, 1132), 20, fill=COLORS["panel"], outline=COLORS["gold2"], width=2)
    draw.text(((W - ch_w) / 2, 1097), CHANNEL, font=F["channel"], fill=COLORS["gold2"])

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG", quality=95)
    print(f"✅ Normal post generated: {output_path}")


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
