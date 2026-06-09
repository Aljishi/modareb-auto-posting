#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, sys, math
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None
    get_display = None

W, H = 1080, 1350
BG = "#050A12"
CARD = "#0B1420"
CARD2 = "#0F1B2A"
GREEN = "#2ECC71"
RED = "#EF3B2D"
WHITE = "#F4F6F8"
MUTED = "#AAB2BD"
LINE = "#263544"
GOLD = "#D8B64C"

DATA_FILE = Path("data/validated_signals.json")
OUT_FILE = "output.png"


def ar(text):
    text = str(text)
    if arabic_reshaper and get_display:
        return get_display(arabic_reshaper.reshape(text))
    return text


def font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


F_TITLE = font(70, True)
F_SUB = font(30)
F_BIG = font(76, True)
F_MID = font(42, True)
F_TXT = font(34)
F_SM = font(25)
F_XS = font(22)


def pct(a, b):
    try:
        return ((float(a) - float(b)) / float(b)) * 100
    except Exception:
        return 0


def money(v):
    try:
        return f"{float(v):.2f}"
    except Exception:
        return str(v)


def as_int(v, default=0):
    try:
        if isinstance(v, str):
            v = v.replace("%", "").strip()
        return int(float(v))
    except Exception:
        return default


def get_signal():
    if len(sys.argv) > 1:
        source = Path(sys.argv[1])
    else:
        source = DATA_FILE

    data = json.load(open(source, encoding="utf-8"))

    if isinstance(data, dict) and "validated_signals" in data:
        return data["validated_signals"][0]
    if isinstance(data, dict) and "signals" in data:
        return data["signals"][0]
    if isinstance(data, list):
        return data[0]
    return data


def rounded(draw, box, r, fill, outline=None, width=2):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def center_text(draw, xy, text, f, fill):
    bbox = draw.textbbox((0, 0), text, font=f)
    x = xy[0] - (bbox[2] - bbox[0]) / 2
    y = xy[1] - (bbox[3] - bbox[1]) / 2
    draw.text((x, y), text, font=f, fill=fill)


def main():
    s = get_signal()

    symbol = s.get("stock_symbol") or s.get("symbol") or "----"
    name = s.get("stock_name") or s.get("name") or "السهم"
    entry = float(s.get("entry_point") or s.get("entry") or s.get("current_price") or 0)
    tp1 = float(s.get("target1") or s.get("tp1") or 0)
    tp2 = float(s.get("target2") or s.get("tp2") or 0)
    sl = float(s.get("stop_loss") or s.get("sl") or 0)

    score = as_int(s.get("rased_score") or s.get("score") or 88, 88)
    confidence = as_int(s.get("ai_confidence") or s.get("confidence") or s.get("rased_score") or 89, 89)
    tier = s.get("tier") or "Standard"
    tier_emoji = s.get("tier_emoji") or "✅"
    risk = s.get("risk_level_ar") or s.get("ai_risk_level") or "منخفضة"
    holding = s.get("holding_period") or "1 - 7 أيام"
    signal_id = s.get("signal_id") or f"Signal #{datetime.now().strftime('%Y')}-{datetime.now().strftime('%j')}"
    fundamental_bonus = as_int(s.get("fundamental_bonus") or 0, 0)
    fundamental_grade = s.get("fundamental_grade") or "محايد"

    tp1_pct = s.get("tp1_pct") or pct(tp1, entry)
    tp2_pct = s.get("tp2_pct") or pct(tp2, entry)
    sl_pct = s.get("sl_pct") or pct(sl, entry)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    rounded(d, (28, 28, W-28, H-28), 28, BG, "#46515E", 2)

    # Header
    d.ellipse((55, 60, 145, 150), fill="#081923", outline=GREEN, width=2)
    d.rectangle((83, 115, 96, 138), fill=GREEN)
    d.rectangle((103, 95, 116, 138), fill=GREEN)
    d.rectangle((123, 75, 136, 138), fill=GREEN)

    d.text((170, 55), ar("الراصد"), font=F_TITLE, fill=WHITE)
    d.text((172, 137), ar("الراصد الذكي للأسهم السعودية"), font=F_SUB, fill=MUTED)

    rounded(d, (740, 58, 1015, 135), 16, "#0A5E29", GREEN, 2)
    center_text(d, (877, 96), ar(f"{tier} {tier_emoji}"), F_MID, WHITE)

    # Stock card
    rounded(d, (55, 185, 1025, 575), 18, CARD, "#334253", 2)
    d.text((95, 230), str(symbol), font=F_BIG, fill=WHITE)
    d.line((395, 230, 395, 315), fill=LINE, width=2)
    d.text((450, 230), ar(name), font=F_BIG, fill=WHITE)

    rounded(d, (865, 230, 980, 315), 12, "#081923", GREEN, 2)
    center_text(d, (922, 257), ar("تاسي"), F_SM, WHITE)
    center_text(d, (922, 292), "TASI", F_SM, GREEN)

    rows = [
        ("↗", "سعر الدخول", entry, "", GREEN),
        ("◎", "الهدف الأول", tp1, f"+{float(tp1_pct):.1f}%", GREEN),
        ("◎", "الهدف الثاني", tp2, f"+{float(tp2_pct):.1f}%", GREEN),
        ("🛡", "وقف الخسارة", sl, f"{float(sl_pct):.1f}%", RED),
    ]

    y = 350
    for icon, label, value, p, color in rows:
        d.ellipse((85, y-20, 145, y+40), fill="#07131E", outline=color, width=3)
        center_text(d, (115, y+10), icon, F_TXT, WHITE)
        d.text((190, y-5), ar(label), font=F_TXT, fill=WHITE)
        d.text((455, y-12), money(value), font=F_MID, fill=color)
        d.text((630, y-3), ar("ريال"), font=F_SM, fill=WHITE)
        if p:
            rounded(d, (840, y-12, 980, y+38), 10, "#0D642E" if color == GREEN else "#78160F", color, 1)
            center_text(d, (910, y+13), p, F_SM, WHITE)
        y += 70

    # Score panel
    rounded(d, (55, 600, 1025, 790), 18, CARD2, "#334253", 2)
    cols = [55, 300, 545, 790, 1025]
    labels = ["RASED SCORE™", "الثقة", "المخاطرة", "المدة المتوقعة"]
    values = [f"{score}/100", f"{confidence}%", risk, holding]
    colors = [GREEN, GREEN, GREEN, WHITE]

    for i in range(4):
        if i:
            d.line((cols[i], 625, cols[i], 765), fill=LINE, width=2)
        center_text(d, ((cols[i]+cols[i+1])/2, 635), ar(labels[i]), F_SM, WHITE)
        center_text(d, ((cols[i]+cols[i+1])/2, 710), ar(values[i]), F_MID, colors[i])

    # Badges
    rounded(d, (55, 815, 1025, 915), 18, CARD, "#334253", 2)
    fundamental_badge = f"أساسيات {fundamental_grade}" if fundamental_bonus != 0 else "فلتر أساسي"
    badges = [("↗", "زخم إيجابي"), ("💧", "سيولة جيدة"), ("◆", fundamental_badge)]
    bx = [190, 540, 850]
    for (ic, tx), x in zip(badges, bx):
        center_text(d, (x-55, 865), ic, F_MID, GREEN)
        center_text(d, (x+60, 865), ar(tx), F_SM, WHITE)

    # Footer
    rounded(d, (55, 940, 1025, 1025), 18, CARD, "#334253", 2)
    d.text((95, 968), ar(datetime.now().strftime("%Y/%m/%d")), font=F_SM, fill=WHITE)
    d.text((405, 968), datetime.now().strftime("%I:%M %p KSA"), font=F_SM, fill=WHITE)
    d.text((700, 968), signal_id, font=F_SM, fill=GREEN)

    rounded(d, (55, 1050, 1025, 1135), 18, CARD, "#334253", 2)
    d.text((95, 1075), "✈  t.me/RasedSA", font=F_MID, fill=GREEN)
    ai_label = "AI + Sahmk Starter Data" if s.get("ai_available") is True else "Sahmk Starter Data"
    d.text((655, 1083), ai_label, font=F_SM, fill=MUTED)

    center_text(d, (W/2, 1195), ar("تنبيه: ليست توصية استثمارية."), F_SM, MUTED)

    out = sys.argv[2] if len(sys.argv) > 2 else OUT_FILE
    img.save(out, quality=95)
    print(f"✅ Premium post generated: {out}")


if __name__ == "__main__":
    main()
