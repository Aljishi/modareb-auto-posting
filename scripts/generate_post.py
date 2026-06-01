#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rased — Daily Signal Image Generator
Reads validated_signals.json or signals.json (new pipeline)
Falls back to flat daily.json format (old pipeline)
Design matches the reference image.
"""

import sys, io, json
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("❌ Pillow غير مثبتة"); sys.exit(1)

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _AR = True
except ImportError:
    _AR = False
    print("⚠️ arabic-reshaper/python-bidi غير مثبتة")

def ar(text):
    if not text or not _AR:
        return str(text)
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)

C = {
    "bg": "#080D1A", "card": "#0F1525",
    "gold": "#D4AF37", "gold_light": "#F0D060",
    "green": "#2ECC71", "red": "#E74C3C",
    "white": "#FFFFFF", "gray": "#7B8BA4",
    "border": "#1A2540", "btn_bg": "#111827", "circle_bg": "#12192E",
}
W, H = 1080, 1350
PAD = 55; ROW_H = 82; ROW_GAP = 7; BAR_W = 9
BRAND = {"name": "راصد", "subtitle": "تحليل فني وتعليمي لسوق الاسهم السعودية", "channel": "t.me/RasedSA"}


def load_signal(path):
    """Load signal from any pipeline format."""
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    # New pipeline: {validated_signals: [...]}
    if "validated_signals" in raw:
        sigs = raw["validated_signals"]
        return sigs[0] if sigs else None
    # New pipeline: {signals: [...]}
    if "signals" in raw:
        sigs = raw["signals"]
        return sigs[0] if sigs else None
    # Old flat format
    return raw


def get(d, *keys, default=""):
    """Try multiple key names, return first match."""
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default


class DailySignalGenerator:
    def __init__(self):
        self.data = None; self.img = None; self.draw = None; self.fonts = {}
        self._load_fonts()

    def _load_fonts(self):
        base = Path(__file__).parent.parent / "assets" / "fonts"
        for name in ["Cairo", "Tajawal"]:
            try:
                b = base / f"{name}-Bold.ttf"
                r = base / f"{name}-Regular.ttf"
                if b.exists() and r.exists():
                    self.fonts = {
                        "brand": ImageFont.truetype(b, 80), "subtitle": ImageFont.truetype(r, 26),
                        "stock": ImageFont.truetype(b, 50), "label":    ImageFont.truetype(r, 28),
                        "value": ImageFont.truetype(b, 36), "badge":    ImageFont.truetype(b, 22),
                        "topbar": ImageFont.truetype(r, 22), "reading": ImageFont.truetype(r, 20),
                        "footer": ImageFont.truetype(r, 18), "btn":     ImageFont.truetype(b, 22),
                    }
                    print(f"✅ خط: {name}"); return
            except Exception:
                continue
        default = ImageFont.load_default()
        self.fonts = {k: default for k in ["brand","subtitle","stock","label","value","badge","topbar","reading","footer","btn"]}

    def _tw(self, t, f):
        bb = self.draw.textbbox((0,0),t,font=f); return bb[2]-bb[0]
    def _th(self, t, f):
        bb = self.draw.textbbox((0,0),t,font=f); return bb[3]-bb[1]
    def _cx(self, t, f): return (W - self._tw(t,f)) // 2

    def _make_bg(self):
        self.img = Image.new("RGB",(W,H),C["bg"]); self.draw = ImageDraw.Draw(self.img)

    def _topbar(self):
        now = datetime.now()
        ts  = now.strftime("%I:%M م"); ds = now.strftime("%Y/%m/%d"); lb = ar("وقت الاشارة")
        y = 34
        self.draw.text((PAD,y), ts, font=self.fonts["topbar"], fill=C["gray"])
        self.draw.text((self._cx(lb,self.fonts["topbar"]),y), lb, font=self.fonts["topbar"], fill=C["gray"])
        self.draw.text((W-PAD-self._tw(ds,self.fonts["topbar"]),y), ds, font=self.fonts["topbar"], fill=C["gray"])

    def _logo(self, cy=155):
        cx, r = W//2, 58
        self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)], fill=C["circle_bg"], outline=C["gold"], width=4)
        bw, bg = 11, 5; tbw = 3*bw+2*bg; bx0 = cx-tbw//2
        for i, bh in enumerate([30,20,12]):
            bx = bx0+i*(bw+bg)
            self.draw.rectangle([(bx,cy+14-bh),(bx+bw,cy+14)], fill=C["gold"])
        ax, ay = cx+r-16, cy-r+14
        self.draw.line([(ax-12,ay+12),(ax,ay)], fill=C["gold"], width=3)
        self.draw.line([(ax-7,ay),(ax,ay)],     fill=C["gold"], width=3)
        self.draw.line([(ax,ay),(ax,ay+7)],     fill=C["gold"], width=3)

    def _brand(self, y0=228):
        brand = ar(BRAND["name"])
        self.draw.text((self._cx(brand,self.fonts["brand"]),y0), brand, font=self.fonts["brand"], fill=C["gold_light"])
        sub = ar(BRAND["subtitle"])
        self.draw.text((self._cx(sub,self.fonts["subtitle"]),y0+88), sub, font=self.fonts["subtitle"], fill=C["white"])

    def _divider(self, y):
        mid = W//2
        self.draw.line([(PAD,y),(mid-14,y)], fill=C["border"], width=1)
        self.draw.ellipse([(mid-7,y-7),(mid+7,y+7)], fill=C["gold"])
        self.draw.line([(mid+14,y),(W-PAD,y)], fill=C["border"], width=1)

    def _stock(self, y0=400):
        d = self.data
        name  = get(d, "stock_name", "name")
        sym   = get(d, "stock_symbol", "symbol")
        title = ar(f"{name} - {sym}")
        self.draw.text((self._cx(title,self.fonts["stock"]),y0), title, font=self.fonts["stock"], fill=C["white"])
        tw = self._tw(title,self.fonts["stock"]); cx = W//2
        self.draw.line([(cx-tw//2,y0+60),(cx+tw//2,y0+60)], fill=C["gold"], width=2)

    def _row(self, label, value, bar_color, y, badge=None):
        self.draw.rounded_rectangle([(PAD,y),(W-PAD,y+ROW_H)], radius=10, fill=C["card"])
        self.draw.rounded_rectangle([(PAD,y),(PAD+BAR_W,y+ROW_H)], radius=5, fill=bar_color)
        val_x = PAD+BAR_W+16
        if badge:
            bc = C["green"] if badge.startswith("+") else C["red"]
            bw = self._tw(badge,self.fonts["badge"])+22
            bx = PAD+BAR_W+10; by = y+(ROW_H-28)//2
            self.draw.rounded_rectangle([(bx,by),(bx+bw,by+28)], radius=8, fill=bc)
            self.draw.text((bx+11,by+5), badge, font=self.fonts["badge"], fill=C["white"])
            val_x = bx+bw+14
        vy = y+(ROW_H-self._th(value,self.fonts["value"]))//2
        self.draw.text((val_x,vy), value, font=self.fonts["value"], fill=bar_color)
        lbl = ar(label); lw = self._tw(lbl,self.fonts["label"])
        self.draw.text((W-PAD-BAR_W-16-lw, y+(ROW_H-self._th(lbl,self.fonts["label"]))//2),
                       lbl, font=self.fonts["label"], fill=C["gray"])

    def _rows(self, y0=490):
        d = self.data
        price = str(get(d,"current_price","price", default="0"))
        entry = str(get(d,"entry_point","entry",  default="0"))
        t1    = str(get(d,"target1",              default=""))
        t1p   = get(d,"target1_percent",           default="")
        t2    = str(get(d,"target2",              default=""))
        t2p   = get(d,"target2_percent",           default="")
        sl    = str(get(d,"stop_loss",            default=""))
        slp   = get(d,"stop_loss_percent",         default="")

        def rial(v): return f"{v} ريال"
        y = y0
        self._row("السعر الحالي:", rial(price), C["gold"],  y)
        y += ROW_H+ROW_GAP
        self._row("نقطة الدخول:", rial(entry), C["gold"],  y)
        y += ROW_H+ROW_GAP
        self._row("الهدف الاول:",  rial(t1),   C["green"], y, badge=(f"+{t1p}%" if t1p else None))
        y += ROW_H+ROW_GAP
        self._row("الهدف الثاني:", rial(t2),   C["green"], y, badge=(f"+{t2p}%" if t2p else None))
        y += ROW_H+ROW_GAP
        self._row("وقف الخسارة:", rial(sl),   C["red"],   y, badge=(f"-{slp}%" if slp else None))
        y += ROW_H+ROW_GAP
        return y

    def _reading(self, y, text):
        if not text: return y
        words = str(text).split(); max_w = W-PAD*2-30
        lines, line = [], ""
        for w in words:
            test = f"{line} {w}".strip()
            if self._tw(ar(test),self.fonts["reading"]) < max_w: line = test
            else:
                if line: lines.append(line)
                line = w
        if line: lines.append(line)
        lh = 26; box_h = len(lines)*lh+22
        self.draw.rounded_rectangle([(PAD,y),(W-PAD,y+box_h)], radius=8, fill=C["card"])
        ty = y+12
        for ln in lines:
            drawn = ar(ln)
            self.draw.text(((W-self._tw(drawn,self.fonts["reading"]))//2,ty), drawn, font=self.fonts["reading"], fill=C["gray"])
            ty += lh
        return y+box_h+10

    def _footer(self, y):
        disc = ar("محتوى تعليمي وتحليلي فقط - لا يعد توصية استثمارية")
        self.draw.text(((W-self._tw(disc,self.fonts["footer"]))//2,y), disc, font=self.fonts["footer"], fill=C["gray"])
        btn_y = y+38; btn = BRAND["channel"]
        bw = self._tw(btn,self.fonts["btn"])+64; bx = (W-bw)//2
        self.draw.rounded_rectangle([(bx,btn_y),(bx+bw,btn_y+46)], radius=23, fill=C["btn_bg"], outline=C["gold"], width=2)
        self.draw.text(((W-self._tw(btn,self.fonts["btn"]))//2,btn_y+11), btn, font=self.fonts["btn"], fill=C["gold"])

    def generate(self, inp, out):
        print("="*55); print("📊 راصد — مولّد الإشارة اليومية"); print("="*55)
        try:
            self.data = load_signal(inp)
        except Exception as e:
            print(f"❌ {e}"); return False
        if not self.data:
            print("⚠️ لا توجد إشارات"); return False

        self._make_bg(); self._topbar(); self._logo(cy=155)
        self._brand(y0=228); self._divider(y=368)
        self._stock(y0=392); self._divider(y=468)
        y = self._rows(y0=490)
        reading = (self.data.get("technical_reading") or self.data.get("signal_reason") or "")
        y = self._reading(y+12, reading)
        self._footer(y+10)
        p = Path(out); p.parent.mkdir(parents=True, exist_ok=True)
        self.img.save(p,"PNG",quality=95)
        print(f"✅ تم الحفظ: {p.absolute()}")
        return True


def main():
    base = Path(__file__).parent.parent
    inp  = sys.argv[1] if len(sys.argv) > 1 else str(base/"data/daily.json")
    out  = sys.argv[2] if len(sys.argv) > 2 else str(base/"output.png")
    ok   = DailySignalGenerator().generate(inp, out)
    sys.exit(0 if ok else 1)

if __name__ == "__main__": main()
