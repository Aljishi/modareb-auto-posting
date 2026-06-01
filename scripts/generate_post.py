#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rased — Daily Signal Image Generator
تصميم يطابق الصورة المرجعية: إطار ذهبي + أيقونات دائرية + اسم سهم ضخم
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

def ar(text):
    if not text or not _AR: return str(text)
    try: return get_display(arabic_reshaper.reshape(str(text)))
    except: return str(text)

# ── الألوان ─────────────────────────────────────────────────
C = {
    "bg":         "#0B0F1C",
    "card":       "#111827",
    "gold":       "#D4AF37",
    "gold_light": "#F0D060",
    "green":      "#2ECC71",
    "red":        "#E74C3C",
    "white":      "#FFFFFF",
    "gray":       "#8899AA",
    "border":     "#1E2D45",
    "btn_bg":     "#0D1628",
    "circle_bg":  "#161F30",
}

W, H    = 1080, 1200
PAD     = 48
ROW_H   = 74
ROW_GAP = 8
BORD    = 7    # إطار ذهبي
IR      = 21   # نصف قطر الأيقونة

BRAND = {"name": "راصد", "subtitle": "تحليل فني وتعليمي لسوق الاسهم السعودية", "channel": "t.me/RasedSA"}


def load_signal(path):
    raw = json.load(open(path, encoding='utf-8'))
    if "validated_signals" in raw:
        s = raw["validated_signals"]; return s[0] if s else None
    if "signals" in raw:
        s = raw["signals"]; return s[0] if s else None
    return raw

def get(d, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""): return v
    return default


class DailyGenerator:
    def __init__(self):
        self.data = None; self.img = None; self.draw = None; self.f = {}
        self._fonts()

    def _fonts(self):
        base = Path(__file__).parent.parent / "assets" / "fonts"
        for n in ["Cairo", "Tajawal"]:
            try:
                b = base / f"{n}-Bold.ttf"; r = base / f"{n}-Regular.ttf"
                if b.exists() and r.exists():
                    self.f = {
                        "brand":   ImageFont.truetype(b, 92),
                        "sub":     ImageFont.truetype(r, 27),
                        "stock":   ImageFont.truetype(b, 66),
                        "label":   ImageFont.truetype(r, 28),
                        "value":   ImageFont.truetype(b, 36),
                        "badge":   ImageFont.truetype(b, 22),
                        "topbar":  ImageFont.truetype(r, 22),
                        "metrics": ImageFont.truetype(r, 26),
                        "read":    ImageFont.truetype(r, 20),
                        "foot":    ImageFont.truetype(r, 18),
                        "btn":     ImageFont.truetype(b, 23),
                    }
                    print(f"✅ خط: {n}"); return
            except: continue
        d = ImageFont.load_default()
        self.f = {k: d for k in ["brand","sub","stock","label","value","badge","topbar","metrics","read","foot","btn"]}

    def _tw(self, t, f): bb = self.draw.textbbox((0,0),t,font=f); return bb[2]-bb[0]
    def _th(self, t, f): bb = self.draw.textbbox((0,0),t,font=f); return bb[3]-bb[1]
    def _cx(self, t, f): return (W - self._tw(t,f)) // 2

    # ── الخلفية والإطار ──────────────────────────────────────
    def _bg(self):
        self.img  = Image.new("RGB", (W,H), C["bg"])
        self.draw = ImageDraw.Draw(self.img)
        # إطار ذهبي مفرد
        self.draw.rectangle([(BORD,BORD),(W-BORD-1,H-BORD-1)],
                            fill=None, outline=C["gold"], width=2)

    # ── الشريط العلوي ────────────────────────────────────────
    def _topbar(self):
        now = datetime.now()
        ts  = now.strftime("%I:%M %p").replace("AM","ص").replace("PM","م")
        ds  = now.strftime("%Y/%m/%d")
        lb  = ar("وقت الاشارة")
        y   = 28
        self.draw.text((PAD+10, y), ts,  font=self.f["topbar"], fill="#88CC88")
        self.draw.text((self._cx(lb, self.f["topbar"]), y), lb, font=self.f["topbar"], fill=C["gray"])
        dw = self._tw(ds, self.f["topbar"])
        self.draw.text((W-PAD-10-dw, y), ds, font=self.f["topbar"], fill=C["gold"])
        # خط فاصل رفيع تحت الشريط العلوي
        self.draw.line([(PAD, y+28),(W-PAD, y+28)], fill=C["border"], width=1)

    # ── الشعار الدائري ───────────────────────────────────────
    def _logo(self, cy=155):
        cx = W//2; r = 58
        self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)], fill=C["circle_bg"], outline=C["gold"], width=4)
        bw,bg = 11,5; tbw = 3*bw+2*bg; bx0 = cx-tbw//2
        for i,bh in enumerate([30,20,12]):
            bx = bx0+i*(bw+bg)
            self.draw.rectangle([(bx,cy+14-bh),(bx+bw,cy+14)], fill=C["gold"])
        ax,ay = cx+r-16, cy-r+14
        self.draw.line([(ax-12,ay+12),(ax,ay)],  fill=C["gold"], width=3)
        self.draw.line([(ax-7,ay),(ax,ay)],       fill=C["gold"], width=3)
        self.draw.line([(ax,ay),(ax,ay+7)],       fill=C["gold"], width=3)

    # ── الاسم التجاري ────────────────────────────────────────
    def _brand(self, y0=228):
        brand = ar(BRAND["name"])
        self.draw.text((self._cx(brand,self.f["brand"]), y0), brand, font=self.f["brand"], fill=C["gold_light"])
        sub = ar(BRAND["subtitle"])
        self.draw.text((self._cx(sub,self.f["sub"]), y0+96), sub, font=self.f["sub"], fill=C["white"])

    # ── خط فاصل بنقطة ────────────────────────────────────────
    def _divider(self, y):
        mid = W//2
        self.draw.line([(PAD,y),(mid-12,y)],  fill=C["border"], width=1)
        self.draw.ellipse([(mid-7,y-7),(mid+7,y+7)], fill=C["gold"])
        self.draw.line([(mid+12,y),(W-PAD,y)], fill=C["border"], width=1)

    # ── اسم السهم (ضخم) ─────────────────────────────────────
    def _stock(self, y0):
        d    = self.data
        name = get(d,"stock_name","name")
        sym  = get(d,"stock_symbol","symbol")
        title = ar(f"{name} - {sym}")
        # تصغير الخط إذا كان الاسم طويلاً
        font  = self.f["stock"]
        while self._tw(title, font) > W - PAD*2 - 20:
            sz = font.size - 4
            if sz < 36: break
            try: font = ImageFont.truetype(font.path, sz)
            except: break
        tx = self._cx(title, font)
        self.draw.text((tx, y0), title, font=font, fill=C["white"])
        tw = self._tw(title, font)
        cx = W//2
        # خط تحت الاسم
        self.draw.line([(cx-tw//2, y0+font.size+6),(cx+tw//2, y0+font.size+6)],
                       fill=C["gold"], width=2)
        return y0 + font.size + 16

    # ── أيقونة دائرية (يمين الصف) ───────────────────────────
    def _icon(self, cx, cy, kind):
        r = IR
        if kind == "price":
            self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)], fill=C["circle_bg"], outline=C["gold"], width=2)
            bw,bg = 5,4; tb = 3*bw+2*bg; bx0 = cx-tb//2
            for i,bh in enumerate([10,14,18]):
                bx = bx0+i*(bw+bg)
                self.draw.rectangle([(bx,cy+8-bh),(bx+bw,cy+8)], fill=C["gold"])
        elif kind == "entry":
            self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)], fill=C["circle_bg"], outline=C["gold"], width=2)
            self.draw.ellipse([(cx-12,cy-12),(cx+12,cy+12)], fill=None, outline=C["gold"], width=1)
            self.draw.ellipse([(cx-5,cy-5),(cx+5,cy+5)], fill=C["gold"])
        elif kind == "target":
            self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)], fill=C["green"])
            self.draw.line([(cx-9,cy+1),(cx-3,cy+8)],   fill="#FFFFFF", width=3)
            self.draw.line([(cx-3,cy+8),(cx+10,cy-7)],  fill="#FFFFFF", width=3)
        elif kind == "stop":
            self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)], fill=C["red"])
            self.draw.line([(cx-8,cy-8),(cx+8,cy+8)], fill="#FFFFFF", width=3)
            self.draw.line([(cx-8,cy+8),(cx+8,cy-8)], fill="#FFFFFF", width=3)

    # ── صف بيانات ───────────────────────────────────────────
    def _row(self, label, value, bar_color, y, badge=None, icon_kind="price"):
        rx1, rx2 = PAD, W-PAD
        # خلفية الصف
        self.draw.rounded_rectangle([(rx1,y),(rx2,y+ROW_H)], radius=10, fill=C["card"])
        # شريط جانبي أيسر
        self.draw.rounded_rectangle([(rx1,y),(rx1+5,y+ROW_H)], radius=3, fill=bar_color)

        # أيقونة دائرية في أقصى اليمين
        icon_cx = rx2 - IR - 10
        icon_cy = y + ROW_H//2
        self._icon(icon_cx, icon_cy, icon_kind)

        # التسمية (يسار الأيقونة)
        lbl  = ar(label)
        lw   = self._tw(lbl, self.f["label"])
        lh   = self._th(lbl, self.f["label"])
        lx   = icon_cx - IR - 12 - lw
        ly   = y + (ROW_H - lh)//2
        lbl_color = bar_color if bar_color != C["gold"] else C["gray"]
        if icon_kind == "stop":
            lbl_color = C["red"]
        elif icon_kind in ("target",):
            lbl_color = C["gold"]
        elif icon_kind == "entry":
            lbl_color = C["gold"]
        else:
            lbl_color = C["gray"]
        self.draw.text((lx, ly), lbl, font=self.f["label"], fill=lbl_color)

        # شارة النسبة (أقصى اليسار)
        val_x = PAD + 8
        if badge:
            bc = C["green"] if badge.startswith("+") else C["red"]
            bw = self._tw(badge, self.f["badge"]) + 18
            bx = PAD + 8; by = y + (ROW_H-26)//2
            self.draw.rounded_rectangle([(bx,by),(bx+bw,by+26)], radius=7, fill=bc)
            self.draw.text((bx+9, by+4), badge, font=self.f["badge"], fill="#FFFFFF")
            val_x = bx + bw + 14

        # القيمة
        vh = self._th(value, self.f["value"])
        vy = y + (ROW_H - vh)//2
        self.draw.text((val_x, vy), value, font=self.f["value"], fill=bar_color)

    # ── صفوف البيانات الخمسة ─────────────────────────────────
    def _rows(self, y0):
        d = self.data
        price = str(get(d,"current_price","price",default="0"))
        entry = str(get(d,"entry_point","entry",default="0"))
        t1    = str(get(d,"target1",default=""))
        t1p   = get(d,"target1_percent",default="")
        t2    = str(get(d,"target2",default=""))
        t2p   = get(d,"target2_percent",default="")
        sl    = str(get(d,"stop_loss",default=""))
        slp   = get(d,"stop_loss_percent",default="")

        def r(v): return f"{v} ريال"
        y = y0
        self._row("السعر الحالي:", r(price), C["gold"],  y, icon_kind="price")
        y += ROW_H + ROW_GAP
        self._row("نقطة الدخول:", r(entry), C["gold"],  y, icon_kind="entry")
        y += ROW_H + ROW_GAP
        self._row("الهدف الاول:",  r(t1),   C["green"], y, badge=(f"+{t1p}%" if t1p else None), icon_kind="target")
        y += ROW_H + ROW_GAP
        self._row("الهدف الثاني:", r(t2),   C["green"], y, badge=(f"+{t2p}%" if t2p else None), icon_kind="target")
        y += ROW_H + ROW_GAP
        self._row("وقف الخسارة:", r(sl),   C["red"],   y, badge=(f"-{slp}%" if slp else None), icon_kind="stop")
        y += ROW_H + ROW_GAP
        return y

    # ── نص القراءة الفنية ────────────────────────────────────
    def _reading(self, y, text):
        if not text: return y
        words = str(text).split()
        max_w = W - PAD*2 - 30
        lines, line = [], ""
        for w in words:
            test = f"{line} {w}".strip()
            if self._tw(ar(test), self.f["read"]) < max_w: line = test
            else:
                if line: lines.append(line)
                line = w
        if line: lines.append(line)
        lh = 26; box_h = len(lines)*lh + 22
        self.draw.rounded_rectangle([(PAD,y),(W-PAD,y+box_h)], radius=8,
                                    fill=C["card"], outline=C["gold"], width=1)
        ty = y + 12
        for ln in lines:
            drawn = ar(ln)
            self.draw.text(((W-self._tw(drawn,self.f["read"]))//2, ty),
                           drawn, font=self.f["read"], fill=C["gray"])
            ty += lh
        return y + box_h + 12

    # ── التذييل ──────────────────────────────────────────────
    def _footer(self, y):
        disc = ar("محتوى تعليمي وتحليلي فقط - لا يعد توصية استثمارية")
        self.draw.text(((W-self._tw(disc,self.f["foot"]))//2, y),
                       disc, font=self.f["foot"], fill=C["gray"])
        _y  = y + 36
        btn = BRAND["channel"]
        bw  = self._tw(btn, self.f["btn"]) + 60
        bx  = (W-bw)//2
        self.draw.rounded_rectangle([(bx,_y),(bx+bw,_y+44)],
                                    radius=22, fill=C["btn_bg"], outline=C["gold"], width=2)
        self.draw.text(((W-self._tw(btn,self.f["btn"]))//2, _y+10),
                       btn, font=self.f["btn"], fill=C["gold"])

    # ── التوليد الرئيسي ──────────────────────────────────────
    def generate(self, inp, out):
        print("="*55); print("📊 راصد — مولّد الإشارة اليومية"); print("="*55)
        try: self.data = load_signal(inp)
        except Exception as e: print(f"❌ {e}"); return False
        if not self.data: print("⚠️ لا توجد إشارات"); return False

        self._bg()
        self._topbar()
        self._logo(cy=158)
        self._brand(y0=232)
        self._divider(y=372)
        y_after = self._stock(y0=394)
        self._divider(y=y_after + 8)
        y = self._rows(y0=y_after + 32)
        reading = (self.data.get("technical_reading") or
                   self.data.get("signal_reason") or "")
        y = self._reading(y + 10, reading)
        self._divider(y + 8)
        self._footer(y + 22)

        p = Path(out); p.parent.mkdir(parents=True, exist_ok=True)
        self.img.save(p, "PNG", quality=95)
        print(f"✅ تم الحفظ: {p.absolute()}")
        return True


def main():
    base = Path(__file__).parent.parent
    inp  = sys.argv[1] if len(sys.argv) > 1 else str(base/"data/daily.json")
    out  = sys.argv[2] if len(sys.argv) > 2 else str(base/"output.png")
    sys.exit(0 if DailyGenerator().generate(inp, out) else 1)

if __name__ == "__main__": main()
