#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rased Auto Posting - Golden Signal Generator
مولّد إشارات راصد الذهبية المميزة
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
    print("❌ Pillow غير مثبتة"); sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# 🔤 إصلاح العربية — reshaping + bidi للعرض الصحيح في Pillow
# ═══════════════════════════════════════════════════════════════
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _ARABIC_OK = True
except ImportError:
    _ARABIC_OK = False
    print("⚠️ arabic-reshaper / python-bidi غير مثبتة — الخط العربي قد لا يظهر صحيحاً")
    print("💡 ثبّتها عبر: pip install arabic-reshaper python-bidi")

def ar(text):
    """إصلاح النص العربي لعرضه صحيحاً في Pillow (تشكيل الحروف + اتجاه RTL)."""
    if not text or not _ARABIC_OK:
        return str(text)
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)

COLORS = {"bg":"#1A0F0A","card":"#2D1F1A","gold":"#FFD700","green":"#2ECC71","red":"#E74C3C","white":"#FFF8DC","gray":"#B8A898","border":"#FFD700"}
SIZES  = {"title":36,"stock":48,"label":26,"value":32,"price":42,"footer":20,"badge":24}
BRAND  = {"name":"راصد","chan":"@RasedSA"}
SZ = (1080, 1350); PAD = 60

class GoldenGen:
    def __init__(self):
        self.data=None; self.img=None; self.draw=None; self.f={}
        self._fonts()

    def _fonts(self):
        d = Path(__file__).parent.parent / "assets/fonts"
        for n in ["Cairo", "Tajawal", "Arial"]:
            try:
                b, r = d/f"{n}-Bold.ttf", d/f"{n}-Regular.ttf"
                if b.exists() and r.exists():
                    self.f = {k: ImageFont.truetype(b if k != "footer" else r, SIZES[k]) for k in SIZES}
                    print(f"✅ خط: {n}"); return
            except: pass
        print("⚠️ خط افتراضي"); self.f = {k: ImageFont.load_default() for k in SIZES}

    def load(self, p):
        try:
            with open(p, 'r', encoding='utf-8') as f: self.data = json.load(f)
            return True
        except Exception as e: print(f"❌ {e}"); return False

    def bg(self):
        self.img = Image.new('RGB', SZ, COLORS["bg"]); self.draw = ImageDraw.Draw(self.img)
        for y in range(200): self.draw.line([(0,y),(SZ[0],y)], fill=(255,215,0,int(80*(1-y/200))))
        self.draw.rectangle([(0,0),SZ], outline=COLORS["border"], width=12)
        self.draw.rectangle([(22,22),(SZ[0]-22,SZ[1]-22)], outline=COLORS["gray"], width=2)

    def head(self):
        t = ar("✨ إشارة ذهبية مميزة ✨")
        b = self.draw.textbbox((0,0), t, font=self.f["badge"])
        x = (SZ[0]-(b[2]-b[0]))//2; y = 40
        self.draw.rounded_rectangle([(x-15,y),(x+(b[2]-b[0])+15,y+(b[3]-b[1])+10)], radius=20, fill=COLORS["gold"])
        self.draw.text((x,y+5), t, font=self.f["badge"], fill="#000")
        h = ar(f"{BRAND['name']} | إشارة اليوم")
        hb = self.draw.textbbox((0,0), h, font=self.f["title"])
        hx = (SZ[0]-(hb[2]-hb[0]))//2
        self.draw.text((hx,y+80), h, font=self.f["title"], fill=COLORS["gold"])
        ly = y+130
        self.draw.line([(PAD,ly),(SZ[0]-PAD,ly)], fill=COLORS["gold"], width=3)
        self.draw.text((PAD,ly+12), datetime.now().strftime("%Y/%m/%d - %H:%M"), font=self.f["footer"], fill=COLORS["gray"])

    def stock(self):
        if not self.data: return
        y = 260
        t = ar(f"{self.data.get('stock_name','')} — {self.data.get('stock_symbol','')}")
        b = self.draw.textbbox((0,0), t, font=self.f["stock"]); x = (SZ[0]-(b[2]-b[0]))//2
        self.draw.text((x,y), t, font=self.f["stock"], fill=COLORS["white"])
        s = self.data.get('sector','')
        if s:
            sb = self.draw.textbbox((0,0), ar(f"القطاع: {s}"), font=self.f["label"])
            self.draw.text(((SZ[0]-(sb[2]-sb[0]))//2, y+60), ar(f"🏢 القطاع: {s}"), font=self.f["label"], fill=COLORS["gray"])

    def row(self, l, v, c, ic="", y=None):
        if y is None: y = self.cy
        self.draw.rounded_rectangle([(PAD,y),(SZ[0]-PAD,y+80)], radius=15, fill=COLORS["card"])
        self.draw.rectangle([(PAD,y),(PAD+10,y+80)], fill=c)
        self.draw.text((PAD+30,y+20), ar(f"{ic} {l}"), font=self.f["label"], fill=COLORS["gray"])
        vb = self.draw.textbbox((0,0), v, font=self.f["price"])
        self.draw.text((SZ[0]-PAD-30-(vb[2]-vb[0]),y+20), v, font=self.f["price"], fill=c)
        self.cy += 95

    def prices(self):
        if not self.data: return
        self.cy = 420
        self.row("السعر الحالي", f"{self.data.get('current_price',0)} ريال", COLORS["gold"], "📊")
        self.row("نقطة الدخول", f"{self.data.get('entry_point',0)} ريال", COLORS["gold"], "")
        self.row("الهدف الأول",  f"{self.data.get('target1',0)} ريال (+{self.data.get('target1_percent',0)}%)", COLORS["green"], "")
        t2 = self.data.get('target2', 0)
        if t2: self.row("الهدف الثاني", f"{t2} ريال (+{self.data.get('target2_percent',0)}%)", COLORS["green"], "🟢")
        self.row("وقف الخسارة", f"{self.data.get('stop_loss',0)} ريال (-{self.data.get('stop_loss_percent',0)}%)", COLORS["red"], "")

    def foot(self):
        fy = SZ[1]-140
        self.draw.line([(PAD,fy),(SZ[0]-PAD,fy)], fill=COLORS["gray"], width=2)
        w = ar("⚠️ محتوى تعليمي وتحليلي فقط — لا يعد توصية استثمارية")
        wb = self.draw.textbbox((0,0), w, font=self.f["footer"])
        self.draw.text(((SZ[0]-(wb[2]-wb[0]))//2, fy+15), w, font=self.f["footer"], fill=COLORS["gray"])
        wm = ar(f"👁️ {BRAND['name']} | {BRAND['chan']}")
        wmb = self.draw.textbbox((0,0), wm, font=self.f["label"])
        self.draw.text(((SZ[0]-(wmb[2]-wmb[0]))//2, fy+55), wm, font=self.f["label"], fill=COLORS["gold"])

    def run(self, inp, out):
        print("🎨 بدء التصميم الذهبي...")
        if not self.load(inp): return False
        self.bg(); self.head(); self.stock(); self.prices(); self.foot()
        p = Path(out); p.parent.mkdir(parents=True, exist_ok=True)
        self.img.save(p, "PNG", quality=95)
        print(f"✅ ذهبية: {p.absolute()}"); return True

def main():
    b = Path(__file__).parent.parent
    inp = sys.argv[1] if len(sys.argv) > 1 else str(b / "data/golden_signal.json")
    out = sys.argv[2] if len(sys.argv) > 2 else str(b / "output_golden.png")
    ok = GoldenGen().run(inp, out)
    sys.exit(0 if ok else 1)

if __name__ == "__main__": main()
