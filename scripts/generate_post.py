#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rased Auto Posting - Normal Signal Generator
مولّد صور إشارات راصد العادية (أثناء السوق)
تصميم: أزرق/رمادي — مضغوط — احترافي
"""

import sys
import io
import json
import os
from datetime import datetime
from pathlib import Path

# إصلاح ترميز الكونسول في ويندوز لعرض العربية بشكل صحيح
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("❌ خطأ: المكتبة Pillow غير مثبتة")
    print("💡 ثبّتها عبر: pip install Pillow")
    sys.exit(1)

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

# ═══════════════════════════════════════════════════════════════
# 🎨 إعدادات التصميم (مدمجة لضمان العمل الذاتي)
# ══════════════════════════════════════════════════════════════
COLORS = {
    "bg": "#0B1120",
    "card": "#151E32",
    "accent": "#3498DB",
    "gold": "#D4AF37",
    "green": "#2ECC71",
    "red": "#E74C3C",
    "white": "#FFFFFF",
    "gray": "#95A5A6",
    "border": "#2C3E50",
    "divider": "#1F2937"
}

FONT_SIZES = {
    "title": 36, "stock": 48, "label": 26, "value": 32,
    "price": 42, "footer": 20, "tiny": 18
}

BRANDING = {"name": "راصد", "channel": "@RasedSA"}
IMG_SIZE = (1080, 1350)
PADDING = 60


class RasedNormalGenerator:
    def __init__(self):
        self.data = None
        self.img = None
        self.draw = None
        self.fonts = {}
        self._load_fonts()

    def _load_fonts(self):
        base_dir = Path(__file__).parent.parent
        font_dir = base_dir / "assets" / "fonts"

        candidates = ["Cairo", "Tajawal", "Arial"]
        for name in candidates:
            try:
                bold = font_dir / f"{name}-Bold.ttf"
                reg = font_dir / f"{name}-Regular.ttf"
                if bold.exists() and reg.exists():
                    self.fonts = {
                        "title": ImageFont.truetype(bold, FONT_SIZES["title"]),
                        "stock": ImageFont.truetype(bold, FONT_SIZES["stock"]),
                        "label": ImageFont.truetype(reg,  FONT_SIZES["label"]),
                        "value": ImageFont.truetype(bold, FONT_SIZES["value"]),
                        "price": ImageFont.truetype(bold, FONT_SIZES["price"]),
                        "footer": ImageFont.truetype(reg, FONT_SIZES["footer"]),
                        "tiny":  ImageFont.truetype(reg,  FONT_SIZES["tiny"])
                    }
                    print(f"✅ تم تحميل خط: {name}")
                    return
            except Exception:
                continue

        print("⚠️ لم يتم العثور على خطوط عربية - استخدام النظام الافتراضي")
        self.fonts = {k: ImageFont.load_default() for k in FONT_SIZES}

    def load_data(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            return True
        except Exception as e:
            print(f"❌ خطأ في قراءة البيانات: {e}")
            return False

    def create_background(self):
        self.img = Image.new('RGB', IMG_SIZE, COLORS["bg"])
        self.draw = ImageDraw.Draw(self.img)
        for y in range(150):
            alpha = int(60 * (1 - y/150))
            self.draw.line([(0, y), (IMG_SIZE[0], y)], fill=(52, 152, 219, alpha))

    def draw_header(self):
        txt = ar(f"{BRANDING['name']} | إشارة اليوم")
        bbox = self.draw.textbbox((0, 0), txt, font=self.fonts["title"])
        x = (IMG_SIZE[0] - (bbox[2]-bbox[0])) // 2
        self.draw.text((x, 40), txt, font=self.fonts["title"], fill=COLORS["accent"])

        ly = 40 + bbox[3] + 15
        self.draw.line([(PADDING, ly), (IMG_SIZE[0]-PADDING, ly)], fill=COLORS["accent"], width=3)
        now = datetime.now().strftime("%Y/%m/%d - %H:%M")
        self.draw.text((PADDING, ly + 12), now, font=self.fonts["footer"], fill=COLORS["gray"])

    def draw_stock_info(self):
        if not self.data: return
        y = 160
        title = ar(f"{self.data.get('stock_name','')} — {self.data.get('stock_symbol','')}")
        bbox = self.draw.textbbox((0, 0), title, font=self.fonts["stock"])
        x = (IMG_SIZE[0] - (bbox[2]-bbox[0])) // 2
        self.draw.text((x, y), title, font=self.fonts["stock"], fill=COLORS["white"])

        sec = self.data.get('sector', '')
        if sec:
            st = ar(f"🏢 القطاع: {sec}")
            sb = self.draw.textbbox((0, 0), st, font=self.fonts["label"])
            sx = (IMG_SIZE[0] - (sb[2]-sb[0])) // 2
            self.draw.text((sx, y + 60), st, font=self.fonts["label"], fill=COLORS["gray"])

    def _draw_row(self, label, value, color, icon="", y=None):
        if y is None: y = self.cy
        h = 65
        self.draw.rectangle([(PADDING, y), (IMG_SIZE[0]-PADDING, y+h)], fill=COLORS["card"])
        self.draw.rectangle([(PADDING, y), (PADDING+6, y+h)], fill=color)
        self.draw.text((PADDING+20, y+18), ar(f"{icon} {label}"), font=self.fonts["label"], fill=COLORS["gray"])
        vb = self.draw.textbbox((0, 0), value, font=self.fonts["price"])
        vx = IMG_SIZE[0] - PADDING - 20 - (vb[2]-vb[0])
        self.draw.text((vx, y+18), value, font=self.fonts["price"], fill=color)
        self.draw.line([(PADDING, y+h), (IMG_SIZE[0]-PADDING, y+h)], fill=COLORS["divider"], width=1)
        return y + h + 8

    def draw_prices(self):
        if not self.data: return
        self.cy = 320
        self.cy = self._draw_row("السعر الحالي", f"{self.data.get('current_price',0)} ريال", COLORS["gold"], "📊", self.cy)
        self.cy = self._draw_row("نقطة الدخول", f"{self.data.get('entry_point', self.data.get('entry', 0))} ريال", COLORS["accent"], "🎯", self.cy)
        t1 = self.data.get('target1', 0); t1p = self.data.get('target1_percent', 0)
        self.cy = self._draw_row("الهدف الأول", f"{t1} ريال (+{t1p}%)", COLORS["green"], "🟢", self.cy)
        t2 = self.data.get('target2', 0); t2p = self.data.get('target2_percent', 0)
        if t2: self.cy = self._draw_row("الهدف الثاني", f"{t2} ريال (+{t2p}%)", COLORS["green"], "🟢", self.cy)
        sl = self.data.get('stop_loss', 0); slp = self.data.get('stop_loss_percent', 0)
        self.cy = self._draw_row("وقف الخسارة", f"{sl} ريال (-{slp}%)", COLORS["red"], "🔴", self.cy)

    def draw_analysis(self):
        if not self.data: return
        y = self.cy + 30
        sc = self.data.get('score', 0)
        rk = self.data.get('rs_rank', 0)
        self.draw.text((PADDING, y), f"🔢 Score: {sc}/100", font=self.fonts["label"], fill=COLORS["green"] if sc>=80 else COLORS["accent"])
        rb = self.draw.textbbox((0, 0), f" RS Rank: {rk}", font=self.fonts["label"])
        self.draw.text((IMG_SIZE[0]-PADDING-20-(rb[2]-rb[0]), y), f"📈 RS Rank: {rk}", font=self.fonts["label"], fill=COLORS["gold"])

        y += 40
        read = self.data.get('technical_reading', '')
        if read:
            self.draw.text((PADDING, y), ar("📌 قراءة فنية:"), font=self.fonts["label"], fill=COLORS["accent"])
            y += 32
            words = read.split(); line = ""
            for w in words:
                test = f"{line} {w}" if line else w
                if self.draw.textbbox((0, 0), ar(test), font=self.fonts["tiny"])[2] < IMG_SIZE[0]-PADDING*2:
                    line = test
                else:
                    if line:
                        self.draw.text((PADDING, y), ar(f"• {line}"), font=self.fonts["tiny"], fill=COLORS["gray"])
                        y += 26
                    line = w
            if line:
                self.draw.text((PADDING, y), ar(f"• {line}"), font=self.fonts["tiny"], fill=COLORS["gray"])

    def draw_footer(self):
        fy = IMG_SIZE[1] - 130
        self.draw.line([(PADDING, fy), (IMG_SIZE[0]-PADDING, fy)], fill=COLORS["border"], width=2)
        w = ar("⚠️ محتوى تعليمي وتحليلي فقط — لا يعد توصية استثمارية")
        wb = self.draw.textbbox((0, 0), w, font=self.fonts["footer"])
        wx = (IMG_SIZE[0] - (wb[2]-wb[0])) // 2
        self.draw.text((wx, fy+15), w, font=self.fonts["footer"], fill=COLORS["gray"])
        wm = ar(f"️ {BRANDING['name']} | {BRANDING['channel']}")
        wmb = self.draw.textbbox((0, 0), wm, font=self.fonts["label"])
        wmx = (IMG_SIZE[0] - (wmb[2]-wmb[0])) // 2
        self.draw.text((wmx, fy+50), wm, font=self.fonts["label"], fill=COLORS["accent"])

    def generate(self, inp, out):
        print("="*60)
        print(f"📊 {BRANDING['name']} — مولّد الإشارات العادية")
        print("="*60)
        if not self.load_data(inp): return False
        print("🎨 بدء إنشاء الصورة...")
        self.create_background()
        self.draw_header()
        self.draw_stock_info()
        self.draw_prices()
        self.draw_analysis()
        self.draw_footer()
        p = Path(out); p.parent.mkdir(parents=True, exist_ok=True)
        self.img.save(p, "PNG", quality=95)
        print(f"✅ تم الحفظ: {p.absolute()}")
        return True

def main():
    base = Path(__file__).parent.parent
    inp = sys.argv[1] if len(sys.argv) > 1 else str(base / "data/daily.json")
    out = sys.argv[2] if len(sys.argv) > 2 else str(base / "output.png")
    ok = RasedNormalGenerator().generate(inp, out)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
