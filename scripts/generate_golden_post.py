#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, sys
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
BG = "#030303"
CARD = "#090D10"
CARD2 = "#101010"
GOLD = "#D8A928"
GOLD2 = "#F0CF67"
RED = "#EF3B2D"
GREEN = "#2ECC71"
WHITE = "#F8F8F8"
MUTED = "#A8A8A8"
LINE = "#443719"

DATA_FILE = Path("data/golden_signals.json")
OUT_FILE = "golden_output.png"


def ar(text):
    text = str(text)
    if arabic_reshaper and get_display:
        return get_display(arabic_reshaper.reshape(text))
    return text


def font(size, bold=False):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(p, size) if Path(p).exists() else ImageFont.load_default()


F_TITLE = font(74, True)
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


def rounded(draw, box, r, fill, outline=None, width=2):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def center_text(draw, xy, text, f, fill):
    bbox = draw.textbbox((0, 0), text, font=f)
    x = xy[0] - (bbox[2] - bbox[0]) / 2
    y = xy[1] - (bbox[3] - bbox[1]) / 2
    draw.text((x, y), text, font=f, fill=fill)


def get_signal():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_FILE
    data = json.load(open(source, encoding="utf-8"))
    if isinstance(data, list):
        return data[0]
    if isinstance(data, dict) and "signals" in data:
        return data["signals"][0]
    if isinstance(data, dict) and "golden_signals" in data:
        return data["golden_signals"][0]
    return data


def main():
    s = get_signal()

    symbol = s.get("stock_symbol") or s.get("symbol") or "----"
    name = s.get("stock_name") or s.get("name") or "السهم"
    entry = float(s.get("entry_point") or s.get("entry") or s.get("current_price") or 0)
    tp1 = float(s.get("target1") or s.get("tp1") or 0)
    tp2 = float(s.get("target2") or s.get("tp2") or 0)
    sl = float(s.get("stop_loss") or s.get("sl") or 0)

    score = int(float(s.get("rased_score") or s.get("score") or 96))
    confidence = int(float(s.get("ai_confidence") or s.get("confidence") or 94))
    risk = s.get("risk_level_ar") or "منخفضة جداً"
    holding = s.get("holding_period") or "3 - 7 أيام"
    signal_id = s.get("signal_id") or f"Signal #{datetime.now().strftime('%Y')}-{datetime.now().strftime('%j')}"

    tp1_pct = s.get("tp1_pct") or pct(tp1, entry)
    tp2_pct = s.get("tp2_pct") or pct(tp2, entry)
    sl_pct = s.get("sl_pct") or pct(sl, entry)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    rounded(d, (28, 28, W-28, H-28), 28, BG, GOLD, 3)

    # Header
    center_text(d, (W/2, 88), "♛  " + ar("الراصد"), F_TITLE, GOLD2)
    center_text(d, (W/2, 158), ar("الراصد الذكي للأسهم السعودية"), F_SUB, WHITE)

    rounded(d, (830, 55, 1015, 150), 16, "#4F3305", GOLD, 2)
    center_text(d, (922, 88), ar("الإشارة"), F_SM, WHITE)
    center_text(d, (922, 123), ar("الذهبية 💎"), F_SM, WHITE)

    # Stock title
    d.text((115, 240), str(symbol), font=F_BIG, fill=GOLD2)
    d.line((410, 245, 410, 320), fill=LINE, width=2)
    d.text((455, 245), ar(name), font=F_BIG, fill=WHITE)

    rounded(d, (875, 235, 985, 320), 12, "#090909", GOLD, 2)
    center_text(d, (930, 263), ar("تاسي"), F_SM, WHITE)
    center_text(d, (930, 295), "TASI", F_SM, GOLD2)

    # Price card
    rounded(d, (55, 365, 1025, 725), 18, CARD, GOLD, 2)
    rows = [
        ("↗", "سعر الدخول", entry, "", GOLD2),
        ("◎", "الهدف الأول", tp1, f"+{float(tp1_pct):.1f}%", GOLD2),
        ("◎", "الهدف الثاني", tp2, f"+{float(tp2_pct):.1f}%", GOLD2),
        ("🛡", "وقف الخسارة", sl, f"{float(sl_pct):.1f}%", RED),
    ]

    y = 420
    for icon, label, value, p, color in rows:
        d.ellipse((90, y-20, 150, y+40), fill="#111111", outline=color, width=3)
        center_text(d, (120, y+10), icon, F_TXT, WHITE)
        d.text((210, y-4), ar(label), font=F_TXT, fill=WHITE)
        d.text((555, y-12), money(value), font=F_MID, fill=color)
        d.text((735, y-3), ar("ريال"), font=F_SM, fill=WHITE)
        if p:
            rounded(d, (840, y-12, 980, y+38), 10, "#553C06" if color != RED else "#78160F", color, 1)
            center_text(d, (910, y+13), p, F_SM, WHITE)
        if y < 620:
            d.line((210, y+58, 985, y+58), fill=LINE, width=2)
        y += 75

    # Score panel
    rounded(d, (55, 755, 1025, 935), 18, CARD2, GOLD, 3)
    cols = [55, 300, 545, 790, 1025]
    labels = ["RASED SCORE™", "الثقة", "المخاطرة", "المدة المتوقعة"]
    values = [f"{score}/100", f"{confidence}%", risk, holding]
    colors = [GOLD2, GOLD2, GREEN, WHITE]

    for i in range(4):
        if i:
            d.line((cols[i], 790, cols[i], 910), fill=LINE, width=2)
        center_text(d, ((cols[i]+cols[i+1])/2, 800), ar(labels[i]), F_SM, WHITE)
        center_text(d, ((cols[i]+cols[i+1])/2, 865), ar(values[i]), F_MID, colors[i])

    # Platinum ribbon
    d.rectangle((150, 950, 930, 1015), fill=GOLD)
    center_text(d, (W/2, 982), "♛ PLATINUM SIGNAL ♛", F_MID, "#15100A")

    # Badges
    badges = [("📈", "زخم قوي"), ("💧", "سيولة عالية"), ("🛡", "إدارة مخاطر احترافية"), ("⭐", "مراجعة الذكاء الاصطناعي")]
    x_positions = [155, 400, 650, 900]
    for (ic, tx), x in zip(badges, x_positions):
        center_text(d, (x, 1065), ic, F_MID, GOLD2)
        center_text(d, (x, 1115), ar(tx), F_XS, GOLD2)

    # Footer
    rounded(d, (55, 1160, 1025, 1225), 14, CARD, GOLD, 1)
    d.text((95, 1178), ar(datetime.now().strftime("%Y/%m/%d")), font=F_SM, WHITE)
    d.text((390, 1178), datetime.now().strftime("%I:%M %p KSA"), font=F_SM, WHITE)
    d.text((690, 1178), signal_id, font=F_SM, GOLD2)

    rounded(d, (55, 1240, 1025, 1305), 14, CARD, GOLD, 1)
    d.text((95, 1255), "✈  t.me/RasedSA", font=F_MID, fill=GOLD2)
    d.text((640, 1266), "Powered by AI + Sahmk Data", font=F_SM, fill=GOLD2)

    center_text(d, (W/2, 1328), ar("تنبيه: ليست توصية استثمارية."), F_XS, GOLD2)

    out = sys.argv[2] if len(sys.argv) > 2 else OUT_FILE
    img.save(out, quality=95)
    print(f"✅ Golden post generated: {out}")


if __name__ == "__main__":
    main()