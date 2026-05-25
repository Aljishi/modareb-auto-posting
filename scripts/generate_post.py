#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rased Auto Posting - Daily Signal Image Generator
تصميم الإشارة اليومية — يطابق التصميم المرجعي
"""

import sys
import io
import json
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("❌ Pillow غير مثبتة — pip install Pillow")
    sys.exit(1)

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _AR = True
except ImportError:
    _AR = False
    print("⚠️ arabic-reshaper/python-bidi غير مثبتة")

def ar(text):
    """إصلاح النص العربي لعرضه صحيحاً في Pillow"""
    if not text or not _AR:
        return str(text)
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)

# ═══════════════════════════════════════════════════════════
# 🎨 الألوان
# ═══════════════════════════════════════════════════════════
C = {
    "bg":         "#080D1A",
    "card":       "#0F1525",
    "gold":       "#D4AF37",
    "gold_light": "#F0D060",
    "green":      "#2ECC71",
    "red":        "#E74C3C",
    "white":      "#FFFFFF",
    "gray":       "#7B8BA4",
    "border":     "#1A2540",
    "btn_bg":     "#111827",
    "circle_bg":  "#12192E",
}

W, H    = 1080, 1350
PAD     = 55
ROW_H   = 82
ROW_GAP = 7
BAR_W   = 9

BRAND = {
    "name":     "راصد",
    "subtitle": "تحليل فني وتعليمي لسوق الاسهم السعودية",
    "channel":  "t.me/RasedSA",
}


class DailySignalGenerator:

    def __init__(self):
        self.data  = None
        self.img   = None
        self.draw  = None
        self.fonts = {}
        self._load_fonts()

    def _load_fonts(self):
        base = Path(__file__).parent.parent / "assets" / "fonts"
        for name in ["Cairo", "Tajawal", "Arial"]:
            try:
                b = base / f"{name}-Bold.ttf"
                r = base / f"{name}-Regular.ttf"
                if b.exists() and r.exists():
                    self.fonts = {
                        "brand":    ImageFont.truetype(b, 80),
                        "subtitle": ImageFont.truetype(r, 26),
                        "stock":    ImageFont.truetype(b, 50),
                        "label":    ImageFont.truetype(r, 28),
                        "value":    ImageFont.truetype(b, 36),
                        "badge":    ImageFont.truetype(b, 22),
                        "topbar":   ImageFont.truetype(r, 22),
                        "reading":  ImageFont.truetype(r, 20),
                        "footer":   ImageFont.truetype(r, 18),
                        "btn":      ImageFont.truetype(b, 22),
                    }
                    print(f"✅ تم تحميل خط: {name}")
                    return
            except Exception:
                continue
        print("⚠️ استخدام الخط الافتراضي")
        default = ImageFont.load_default()
        self.fonts = {k: default for k in
                      ["brand","subtitle","stock","label","value","badge",
                       "topbar","reading","footer","btn"]}

    def _tw(self, text, font):
        bb = self.draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]

    def _th(self, text, font):
        bb = self.draw.textbbox((0, 0), text, font=font)
        return bb[3] - bb[1]

    def _cx(self, text, font):
        return (W - self._tw(text, font)) // 2

    def load_data(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            return True
        except Exception as e:
            print(f"❌ خطأ في قراءة البيانات: {e}")
            return False

    def _make_bg(self):
        self.img  = Image.new("RGB", (W, H), C["bg"])
        self.draw = ImageDraw.Draw(self.img)

    def _draw_topbar(self):
        now      = datetime.now()
        time_str = now.strftime("%I:%M م")
        date_str = now.strftime("%Y/%m/%d")
        label    = ar("وقت الاشارة")
        y = 34
        self.draw.text((PAD, y), time_str,
                       font=self.fonts["topbar"], fill=C["gray"])
        lx = self._cx(label, self.fonts["topbar"])
        self.draw.text((lx, y), label,
                       font=self.fonts["topbar"], fill=C["gray"])
        dw = self._tw(date_str, self.fonts["topbar"])
        self.draw.text((W - PAD - dw, y), date_str,
                       font=self.fonts["topbar"], fill=C["gray"])

    def _draw_logo(self, cy=155):
        cx, r = W // 2, 58
        self.draw.ellipse(
            [(cx-r, cy-r), (cx+r, cy+r)],
            fill=C["circle_bg"], outline=C["gold"], width=4
        )
        bw, bgap = 11, 5
        total_bw = 3 * bw + 2 * bgap
        bx0      = cx - total_bw // 2
        for i, bh in enumerate([30, 20, 12]):
            bx = bx0 + i * (bw + bgap)
            self.draw.rectangle(
                [(bx, cy + 14 - bh), (bx + bw, cy + 14)],
                fill=C["gold"]
            )
        ax, ay = cx + r - 16, cy - r + 14
        self.draw.line([(ax-12, ay+12), (ax, ay)],   fill=C["gold"], width=3)
        self.draw.line([(ax-7,  ay),    (ax, ay)],   fill=C["gold"], width=3)
        self.draw.line([(ax,    ay),    (ax, ay+7)], fill=C["gold"], width=3)

    def _draw_brand(self, y0=228):
        brand = ar(BRAND["name"])
        self.draw.text((self._cx(brand, self.fonts["brand"]), y0),
                       brand, font=self.fonts["brand"], fill=C["gold_light"])
        sub = ar(BRAND["subtitle"])
        self.draw.text((self._cx(sub, self.fonts["subtitle"]), y0 + 88),
                       sub, font=self.fonts["subtitle"], fill=C["white"])

    def _draw_dot_divider(self, y):
        mid = W // 2
        self.draw.line([(PAD, y), (mid - 14, y)],     fill=C["border"], width=1)
        self.draw.ellipse([(mid-7, y-7), (mid+7, y+7)], fill=C["gold"])
        self.draw.line([(mid + 14, y), (W - PAD, y)], fill=C["border"], width=1)

    def _draw_stock(self, y0=400):
        if not self.data: return
        name  = self.data.get("stock_name", "")
        sym   = self.data.get("stock_symbol", self.data.get("symbol", ""))
        title = ar(f"{name} - {sym}")
        self.draw.text((self._cx(title, self.fonts["stock"]), y0),
                       title, font=self.fonts["stock"], fill=C["white"])
        tw = self._tw(title, self.fonts["stock"])
        cx = W // 2
        self.draw.line(
            [(cx - tw//2, y0 + 60), (cx + tw//2, y0 + 60)],
            fill=C["gold"], width=2
        )

    def _draw_row(self, label, value, bar_color, y, badge=None):
        self.draw.rounded_rectangle(
            [(PAD, y), (W - PAD, y + ROW_H)],
            radius=10, fill=C["card"]
        )
        self.draw.rounded_rectangle(
            [(PAD, y), (PAD + BAR_W, y + ROW_H)],
            radius=5, fill=bar_color
        )
        val_x = PAD + BAR_W + 16
        if badge:
            badge_color = C["green"] if badge.startswith("+") else C["red"]
            bw = self._tw(badge, self.fonts["badge"]) + 22
            bx = PAD + BAR_W + 10
            by = y + (ROW_H - 28) // 2
            self.draw.rounded_rectangle(
                [(bx, by), (bx + bw, by + 28)],
                radius=8, fill=badge_color
            )
            self.draw.text((bx + 11, by + 5), badge,
                           font=self.fonts["badge"], fill=C["white"])
            val_x = bx + bw + 14
        vy = y + (ROW_H - self._th(value, self.fonts["value"])) // 2
        self.draw.text((val_x, vy), value,
                       font=self.fonts["value"], fill=bar_color)
        lbl = ar(label)
        lw  = self._tw(lbl, self.fonts["label"])
        lx  = W - PAD - BAR_W - 16 - lw
        ly  = y + (ROW_H - self._th(lbl, self.fonts["label"])) // 2
        self.draw.text((lx, ly), lbl,
                       font=self.fonts["label"], fill=C["gray"])

    def _draw_data_rows(self, y0=490):
        if not self.data: return y0
        d     = self.data
        price = str(d.get("current_price", d.get("price", "0")))
        entry = str(d.get("entry_point",  d.get("entry",  "0")))
        t1    = str(d.get("target1",  ""))
        t1p   = d.get("target1_percent", "")
        t2    = str(d.get("target2",  ""))
        t2p   = d.get("target2_percent", "")
        sl    = str(d.get("stop_loss", ""))
        slp   = d.get("stop_loss_percent", "")

        def rial(v): return f"{v} ريال"

        y = y0
        self._draw_row("السعر الحالي:", rial(price), C["gold"],  y)
        y += ROW_H + ROW_GAP
        self._draw_row("نقطة الدخول:", rial(entry), C["gold"],  y)
        y += ROW_H + ROW_GAP
        self._draw_row("الهدف الاول:",  rial(t1),   C["green"], y,
                       badge=(f"+{t1p}%" if t1p else None))
        y += ROW_H + ROW_GAP
        self._draw_row("الهدف الثاني:", rial(t2),   C["green"], y,
                       badge=(f"+{t2p}%" if t2p else None))
        y += ROW_H + ROW_GAP
        self._draw_row("وقف الخسارة:", rial(sl),   C["red"],   y,
                       badge=(f"-{slp}%" if slp else None))
        y += ROW_H + ROW_GAP
        return y

    def _draw_reading(self, y, text):
        if not text: return y
        words  = str(text).split()
        max_w  = W - PAD * 2 - 30
        lines, line = [], ""
        for w in words:
            test = f"{line} {w}".strip()
            if self._tw(ar(test), self.fonts["reading"]) < max_w:
                line = test
            else:
                if line: lines.append(line)
                line = w
        if line: lines.append(line)
        lh    = 26
        box_h = len(lines) * lh + 22
        self.draw.rounded_rectangle(
            [(PAD, y), (W - PAD, y + box_h)],
            radius=8, fill=C["card"]
        )
        ty = y + 12
        for ln in lines:
            drawn = ar(ln)
            self.draw.text(((W - self._tw(drawn, self.fonts["reading"])) // 2, ty),
                           drawn, font=self.fonts["reading"], fill=C["gray"])
            ty += lh
        return y + box_h + 10

    def _draw_footer(self, y):
        disc = ar("محتوى تعليمي وتحليلي فقط - لا يعد توصية استثمارية")
        self.draw.text(((W - self._tw(disc, self.fonts["footer"])) // 2, y),
                       disc, font=self.fonts["footer"], fill=C["gray"])
        btn_y = y + 38
        btn   = BRAND["channel"]
        bw    = self._tw(btn, self.fonts["btn"]) + 64
        bx    = (W - bw) // 2
        self.draw.rounded_rectangle(
            [(bx, btn_y), (bx + bw, btn_y + 46)],
            radius=23, fill=C["btn_bg"], outline=C["gold"], width=2
        )
        self.draw.text(
            ((W - self._tw(btn, self.fonts["btn"])) // 2, btn_y + 11),
            btn, font=self.fonts["btn"], fill=C["gold"]
        )

    def generate(self, inp, out):
        print("=" * 55)
        print("📊 راصد — مولّد الإشارة اليومية")
        print("=" * 55)
        if not self.load_data(inp): return False
        print("🎨 بدء التصميم...")
        self._make_bg()
        self._draw_topbar()
        self._draw_logo(cy=155)
        self._draw_brand(y0=228)
        self._draw_dot_divider(y=368)
        self._draw_stock(y0=392)
        self._draw_dot_divider(y=468)
        y = self._draw_data_rows(y0=490)
        reading = (self.data.get("technical_reading") or
                   self.data.get("signal_reason") or
                   self.data.get("note") or "")
        y = self._draw_reading(y + 12, reading)
        self._draw_footer(y + 10)
        p = Path(out)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.img.save(p, "PNG", quality=95)
        print(f"✅ تم الحفظ: {p.absolute()}")
        return True


def main():
    base = Path(__file__).parent.parent
    inp  = sys.argv[1] if len(sys.argv) > 1 else str(base / "data/daily.json")
    out  = sys.argv[2] if len(sys.argv) > 2 else str(base / "output.png")
    ok   = DailySignalGenerator().generate(inp, out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
