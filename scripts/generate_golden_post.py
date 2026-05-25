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
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError as e:
    print(f"❌ خطأ: {e}")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# 🎨 استيراد الإعدادات المركزية
# ══════════════════════════════════════════════════════════════
try:
    from config import BRAND, COLORS, FONT_SIZES, IMG_SIZE, PADDING, BRANDING
except ImportError:
    print("⚠️ تحذير: config.py غير موجود - استخدام إعدادات افتراضية")
    COLORS = {
        "bg": "#1A0F0A",
        "card": "#2D1F1A",
        "accent": "#FFD700",
        "gold": "#FFD700",
        "green": "#2ECC71",
        "red": "#E74C3C",
        "white": "#FFF8DC",
        "gray": "#B8A898",
        "border": "#FFD700"
    }
    FONT_SIZES = {
        "title": 40, "stock": 52, "label": 28, "value": 32,
        "price": 36, "footer": 20, "badge": 26
    }
    BRANDING = {"name": "راصد", "channel": "@RasedSA", "slogan": "عينك على الفرص"}
    IMG_SIZE = (1080, 1350)  # ✅ تم الإصلاح: نسبة 4:5
    PADDING = 60


def ar(text):
    """معالجة النصوص العربية"""
    if not text:
        return ""
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except:
        return str(text)


class GoldenSignalGenerator:
    """مولّد الإشارات الذهبية"""

    def __init__(self, data_file):
        self.data_file = Path(data_file)
        self.data = None
        self.img = None
        self.draw = None
        self.fonts = {}
        self._load_fonts()

    def _load_fonts(self):
        base_dir = Path(__file__).parent.parent
        font_dir = base_dir / "assets" / "fonts"
        
        for name in ["Cairo", "Tajawal", "Arial"]:
            try:
                bold = font_dir / f"{name}-Bold.ttf"
                reg = font_dir / f"{name}-Regular.ttf"
                if bold.exists() and reg.exists():
                    self.fonts = {
                        "title": ImageFont.truetype(bold, FONT_SIZES["title"]),
                        "stock": ImageFont.truetype(bold, FONT_SIZES["stock"]),
                        "label": ImageFont.truetype(reg, FONT_SIZES["label"]),
                        "value": ImageFont.truetype(bold, FONT_SIZES["value"]),
                        "price": ImageFont.truetype(bold, FONT_SIZES["price"]),
                        "footer": ImageFont.truetype(reg, FONT_SIZES["footer"]),
                        "badge": ImageFont.truetype(bold, FONT_SIZES["badge"])
                    }
                    print(f"✅ تم تحميل خط: {name}")
                    return
            except:
                continue
        
        print("⚠️ استخدام الخط الافتراضي")
        self.fonts = {k: ImageFont.load_default() for k in FONT_SIZES}

    def load_data(self):
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            return True
        except Exception as e:
            print(f"❌ خطأ: {e}")
            return False

    def create_background(self):
        self.img = Image.new('RGB', IMG_SIZE, COLORS["bg"])
        self.draw = ImageDraw.Draw(self.img)
        
        # توهج ذهبي
        for y in range(250):
            alpha = int(100 * (1 - y/250))
            self.draw.line([(0, y), (IMG_SIZE[0], y)], fill=(255, 215, 0, alpha))
        
        # إطار ذهبي
        self.draw.rectangle([(0, 0), IMG_SIZE], outline=COLORS["gold"], width=12)
        self.draw.rectangle(
            [(22, 22), (IMG_SIZE[0] - 22, IMG_SIZE[1] - 22)],
            outline=COLORS["gray"], width=2
        )
        
        # زوايا مزخرفة
        corner = 70
        corners = [
            [(PADDING, PADDING), (PADDING + corner, PADDING + corner)],
            [(IMG_SIZE[0] - PADDING - corner, PADDING), (IMG_SIZE[0] - PADDING, PADDING + corner)],
            [(PADDING, IMG_SIZE[1] - PADDING - corner), (PADDING + corner, IMG_SIZE[1] - PADDING)],
            [(IMG_SIZE[0] - PADDING - corner, IMG_SIZE[1] - PADDING - corner), 
             (IMG_SIZE[0] - PADDING, IMG_SIZE[1] - PADDING)]
        ]
        for (x1, y1), (x2, y2) in corners:
            self.draw.rectangle([(x1, y1), (x2, y2)], outline=COLORS["gold"], width=3)

    def draw_header(self):
        # شارة ذهبية
        badge = ar("✨ إشارة ذهبية مميزة ✨")
        bb = self.draw.textbbox((0, 0), badge, font=self.fonts["badge"])
        bw = bb[2] - bb[0]
        bh = bb[3] - bb[1]
        bx = (IMG_SIZE[0] - bw) // 2
        
        self.draw.rounded_rectangle(
            [(bx - 20, 40), (bx + bw + 20, 40 + bh + 15)],
            radius=25, fill=COLORS["gold"]
        )
        self.draw.text((bx, 45), badge, font=self.fonts["badge"], fill="#000000")
        
        # العنوان
        title = ar(f"{BRANDING['name']} | إشارة اليوم")
        tb = self.draw.textbbox((0, 0), title, font=self.fonts["title"])
        tx = (IMG_SIZE[0] - (tb[2] - tb[0])) // 2
        self.draw.text((tx, 130), title, font=self.fonts["title"], fill=COLORS["gold"])
        
        # خط فاصل
        ly = 130 + tb[3] + 20
        self.draw.line([(PADDING, ly), (IMG_SIZE[0] - PADDING, ly)], 
                      fill=COLORS["gold"], width=3)
        
        # التاريخ
        now = datetime.now().strftime("%Y/%m/%d - %H:%M")
        self.draw.text((PADDING, ly + 15), ar(now), 
                      font=self.fonts["footer"], fill=COLORS["gray"])

    def draw_stock_info(self):
        if not self.data:
            return
        
        y = 260
        name = ar(self.data.get('stock_name', ''))
        symbol = self.data.get('stock_symbol', '')
        title = ar(f"{name} — {symbol}")
        
        tb = self.draw.textbbox((0, 0), title, font=self.fonts["stock"])
        tx = (IMG_SIZE[0] - (tb[2] - tb[0])) // 2
        self.draw.text((tx, y), title, font=self.fonts["stock"], fill=COLORS["white"])
        
        sector = ar(self.data.get('sector', ''))
        if sector:
            st = ar(f"🏢 القطاع: {sector}")
            sb = self.draw.textbbox((0, 0), st, font=self.fonts["label"])
            self.draw.text(((IMG_SIZE[0] - (sb[2] - sb[0])) // 2, y + 65), 
                          st, font=self.fonts["label"], fill=COLORS["gray"])

    def _draw_price_box(self, label, value, color, icon=""):
        y = self.current_y
        
        # بطاقة كبيرة
        self.draw.rounded_rectangle(
            [(PADDING, y), (IMG_SIZE[0] - PADDING, y + 85)],
            radius=15, fill=COLORS["card"]
        )
        
        # حدود ذهبية
        self.draw.rounded_rectangle(
            [(PADDING + 2, y + 2), (IMG_SIZE[0] - PADDING - 2, y + 83)],
            radius=13, outline=color, width=2
        )
        
        # أيقونة جانبية
        self.draw.text((PADDING + 25, y + 25), ar(icon), 
                      font=self.fonts["value"], fill=color)
        
        # التسمية
        self.draw.text((PADDING + 60, y + 20), ar(label), 
                      font=self.fonts["label"], fill=COLORS["gray"])
        
        # القيمة
        vb = self.draw.textbbox((0, 0), ar(str(value)), font=self.fonts["price"])
        self.draw.text((IMG_SIZE[0] - PADDING - 30 - (vb[2] - vb[0]), y + 25), 
                      ar(str(value)), font=self.fonts["price"], fill=color)
        
        self.current_y += 97

    def draw_prices(self):
        if not self.data:
            return
        
        self.current_y = 420
        
        self._draw_price_box("السعر الحالي", 
                            f"{self.data.get('current_price', 0)} ريال", 
                            COLORS["gold"], "📊")
        
        self._draw_price_box("نقطة الدخول", 
                            f"{self.data.get('entry_point', 0)} ريال", 
                            COLORS["accent"], "🎯")
        
        t1 = self.data.get('target1', 0)
        t1_pct = self.data.get('target1_percent', 0)
        self._draw_price_box("الهدف الأول", 
                            f"{t1} ريال (+{t1_pct}%)", 
                            COLORS["green"], "🟢")
        
        t2 = self.data.get('target2', 0)
        t2_pct = self.data.get('target2_percent', 0)
        if t2:
            self._draw_price_box("الهدف الثاني", 
                                f"{t2} ريال (+{t2_pct}%)", 
                                COLORS["green"], "🟢")
        
        sl = self.data.get('stop_loss', 0)
        sl_pct = self.data.get('stop_loss_percent', 0)
        self._draw_price_box("وقف الخسارة", 
                            f"{sl} ريال (-{sl_pct}%)", 
                            COLORS["red"], "🔴")

    def draw_footer(self):
        fy = IMG_SIZE[1] - 140
        
        self.draw.line([(PADDING, fy), (IMG_SIZE[0] - PADDING, fy)], 
                      fill=COLORS["gray"], width=2)
        
        warning = ar("⚠️ محتوى تعليمي وتحليلي فقط — لا يعد توصية استثمارية")
        wb = self.draw.textbbox((0, 0), warning, font=self.fonts["footer"])
        self.draw.text(((IMG_SIZE[0] - (wb[2] - wb[0])) // 2, fy + 15), 
                      warning, font=self.fonts["footer"], fill=COLORS["gray"])
        
        wm = ar(f"👁️ {BRANDING['name']} | {BRANDING.get('channel', '@RasedSA')}")
        wmb = self.draw.textbbox((0, 0), wm, font=self.fonts["label"])
        self.draw.text(((IMG_SIZE[0] - (wmb[2] - wmb[0])) // 2, fy + 55), 
                      wm, font=self.fonts["label"], fill=COLORS["gold"])

    def generate(self, output_path):
        print(ar("🎨 بدء التصميم الذهبي..."))
        
        if not self.load_data():
            return False
        
        self.create_background()
        self.draw_header()
        self.draw_stock_info()
        self.draw_prices()
        self.draw_footer()
        
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.img.save(out, "PNG", quality=95)
        
        print(ar(f"✅ ذهبية: {out.absolute()}"))
        return True


def main():
    base = Path(__file__).parent.parent
    inp = sys.argv[1] if len(sys.argv) > 1 else str(base / "data" / "golden_signal.json")
    out = sys.argv[2] if len(sys.argv) > 2 else str(base / "output_golden.png")
    
    ok = GoldenSignalGenerator(inp).generate(out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
