#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rased Auto Posting - Golden Signal Generator
مولّد إشارات راصد الذهبية المميزة (تصميم خاص)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("❌ خطأ: المكتبة Pillow غير مثبتة")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# 🎨 إعدادات التصميم الذهبي
# ═══════════════════════════════════════════════════════════════
GOLDEN_COLORS = {
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

FONTS = {
    "sizes": {
        "title": 36,
        "stock": 48,
        "label": 26,
        "value": 32,
        "price": 42,
        "footer": 20,
        "badge": 24
    }
}

BRANDING = {
    "name": "راصد",
    "channel": "@RasedSA"
}

IMG_WIDTH = 1080
IMG_HEIGHT = 1350
PADDING = 60
BORDER_WIDTH = 12


class RasedGoldenGenerator:
    """مولّد الصور الذهبية"""

    def __init__(self):
        self.data = None
        self.img = None
        self.draw = None
        self.fonts = {}
        self._load_fonts()

    def _load_fonts(self):
        """تحميل الخطوط العربية مع fallback ذكي"""
        sizes = FONTS["sizes"]
        base_dir = Path(__file__).parent.parent
        font_dir = base_dir / "assets" / "fonts"
        
        font_candidates = [
            ("Cairo", "Cairo"),
            ("Tajawal", "Tajawal"),
            ("Arial", "arial"),
        ]
        
        fonts_loaded = False
        
        for font_name, file_prefix in font_candidates:
            try:
                font_paths = {
                    "Bold": [
                        font_dir / f"{file_prefix}-Bold.ttf",
                        font_dir / f"{font_name}-Bold.ttf",
                    ],
                    "Regular": [
                        font_dir / f"{file_prefix}-Regular.ttf",
                        font_dir / f"{font_name}-Regular.ttf",
                    ],
                    "Light": [
                        font_dir / f"{file_prefix}-Light.ttf",
                        font_dir / f"{font_name}-Light.ttf",
                    ],
                }
                
                bold_found = None
                reg_found = None
                light_found = None
                
                for bold_path in font_paths["Bold"]:
                    if bold_path.exists():
                        bold_found = bold_path
                        break
                
                for reg_path in font_paths["Regular"]:
                    if reg_path.exists():
                        reg_found = reg_path
                        break
                
                for light_path in font_paths["Light"]:
                    if light_path.exists():
                        light_found = light_path
                        break
                
                if bold_found and reg_found:
                    self.fonts = {
                        "title": ImageFont.truetype(bold_found, sizes["title"]),
                        "stock": ImageFont.truetype(bold_found, sizes["stock"]),
                        "label": ImageFont.truetype(reg_found, sizes["label"]),
                        "value": ImageFont.truetype(bold_found, sizes["value"]),
                        "price": ImageFont.truetype(bold_found, sizes["price"]),
                        "footer": ImageFont.truetype(reg_found, sizes["footer"]),
                        "badge": ImageFont.truetype(bold_found, sizes["badge"])
                    }
                    print(f"✅ تم تحميل خط: {font_name}")
                    fonts_loaded = True
                    break
                    
            except Exception as e:
                print(f"⚠️ فشل تحميل {font_name}: {e}")
                continue
        
        if not fonts_loaded:
            print("⚠️ لم يتم العثور على خطوط عربية - استخدام Arial")
            try:
                self.fonts = {
                    "title": ImageFont.truetype("arial.ttf", sizes["title"]),
                    "stock": ImageFont.truetype("arialbd.ttf", sizes["stock"]),
                    "label": ImageFont.truetype("arial.ttf", sizes["label"]),
                    "value": ImageFont.truetype("arialbd.ttf", sizes["value"]),
                    "price": ImageFont.truetype("arialbd.ttf", sizes["price"]),
                    "footer": ImageFont.truetype("arial.ttf", sizes["footer"]),
                    "badge": ImageFont.truetype("arialbd.ttf", sizes["badge"])
                }
                print("✅ تم استخدام Arial")
            except:
                self.fonts = {k: ImageFont.load_default() for k in sizes.keys()}
                print("❌ استخدام الخط الافتراضي")

    def load_data(self, file_path):
        """تحميل البيانات"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            return True
        except Exception as e:
            print(f"❌ خطأ في قراءة الملف {file_path}: {e}")
            return False

    def create_base(self):
        """إنشاء الخلفية"""
        self.img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), GOLDEN_COLORS["bg"])
        self.draw = ImageDraw.Draw(self.img)
        
        for y in range(200):
            alpha = int(80 * (1 - y/200))
            color = (255, 215, 0, alpha)
            self.draw.line([(0, y), (IMG_WIDTH, y)], fill=color)

    def draw_frame(self):
        """رسم الإطار الذهبي"""
        self.draw.rectangle(
            [(0, 0), (IMG_WIDTH, IMG_HEIGHT)],
            outline=GOLDEN_COLORS["border"],
            width=BORDER_WIDTH
        )
        self.draw.rectangle(
            [(BORDER_WIDTH + 10, BORDER_WIDTH + 10), 
             (IMG_WIDTH - BORDER_WIDTH - 10, IMG_HEIGHT - BORDER_WIDTH - 10)],
            outline=GOLDEN_COLORS["gray"],
            width=2
        )

    def draw_header(self):
        """رسم الرأس"""
        badge_text = "✨ إشارة ذهبية مميزة ✨"
        bbox = self.draw.textbbox((0, 0), badge_text, font=self.fonts["badge"])
        badge_w = bbox[2] - bbox[0]
        badge_h = bbox[3] - bbox[1]
        badge_x = (IMG_WIDTH - badge_w) // 2
        badge_y = 40
        
        self.draw.rounded_rectangle(
            [(badge_x - 15, badge_y), (badge_x + badge_w + 15, badge_y + badge_h + 10)],
            radius=20,
            fill=GOLDEN_COLORS["accent"]
        )
        
        self.draw.text((badge_x, badge_y + 5), badge_text, 
                      font=self.fonts["badge"], fill="#000000")

        header_text = f"{BRANDING['name']} | إشارة اليوم"
        bbox_h = self.draw.textbbox((0, 0), header_text, font=self.fonts["title"])
        w_h = bbox_h[2] - bbox_h[0]
        x_h = (IMG_WIDTH - w_h) // 2
        
        self.draw.text((x_h, badge_y + 80), header_text, 
                      font=self.fonts["title"], fill=GOLDEN_COLORS["accent"])
        
        line_y = badge_y + 80 + 50
        self.draw.line([(PADDING, line_y), (IMG_WIDTH-PADDING, line_y)], 
                      fill=GOLDEN_COLORS["accent"], width=3)
        
        now = datetime.now().strftime("%Y/%m/%d - %H:%M")
        self.draw.text((PADDING, line_y + 15), now, 
                      font=self.fonts["footer"], fill=GOLDEN_COLORS["gray"])

    def draw_stock_info(self):
        """معلومات السهم"""
        if not self.data:
            return
        
        y_start = 260
        symbol = self.data.get('stock_symbol', '')
        name = self.data.get('stock_name', '')
        title_text = f"{name} — {symbol}"
        
        bbox = self.draw.textbbox((0, 0), title_text, font=self.fonts["stock"])
        w = bbox[2] - bbox[0]
        x = (IMG_WIDTH - w) // 2
        
        self.draw.text((x, y_start), title_text, 
                      font=self.fonts["stock"], fill=GOLDEN_COLORS["white"])
        
        sector = self.data.get('sector', '')
        if sector:
            sector_text = f"القطاع: {sector}"
            bbox_sec = self.draw.textbbox((0, 0), sector_text, font=self.fonts["label"])
            w_sec = bbox_sec[2] - bbox_sec[0]
            self.draw.text(((IMG_WIDTH-w_sec)//2, y_start + 60), 
                          sector_text, font=self.fonts["label"], fill=GOLDEN_COLORS["gray"])

    def draw_price_row(self, label, value, color, icon=""):
        """رسم صف سعر"""
        start_y = self.current_y
        
        self.draw.rounded_rectangle(
            [(PADDING, start_y), (IMG_WIDTH-PADDING, start_y + 80)],
            radius=15,
            fill=GOLDEN_COLORS["card"]
        )
        
        self.draw.rectangle(
            [(PADDING, start_y), (PADDING+10, start_y + 80)],
            fill=color
        )
        
        label_text = f"{icon} {label}"
        self.draw.text((PADDING + 30, start_y + 20), 
                      label_text, font=self.fonts["label"], fill=GOLDEN_COLORS["gray"])
        
        val_text = f"{value}"
        bbox_val = self.draw.textbbox((0, 0), val_text, font=self.fonts["price"])
        w_val = bbox_val[2] - bbox_val[0]
        x_val = IMG_WIDTH - PADDING - 30 - w_val
        
        self.draw.text((x_val, start_y + 20), 
                      val_text, font=self.fonts["price"], fill=color)
        
        self.current_y += 95

    def draw_prices(self):
        """رسم الأسعار"""
        if not self.data:
            return
        
        self.current_y = 420
        
        current = self.data.get('current_price', 0)
        self.draw_price_row("السعر الحالي", f"{current} ريال", GOLDEN_COLORS["accent"], "📊")
        
        entry = self.data.get('entry_point', 0)
        self.draw_price_row("نقطة الدخول", f"{entry} ريال", GOLDEN_COLORS["accent"], "🎯")
        
        t1 = self.data.get('target1', 0)
        t1_pct = self.data.get('target1_percent', 0)
        self.draw_price_row("الهدف الأول", f"{t1} ريال (+{t1_pct}%)", GOLDEN_COLORS["green"], "🟢")
        
        t2 = self.data.get('target2', 0)
        t2_pct = self.data.get('target2_percent', 0)
        if t2:
            self.draw_price_row("الهدف الثاني", f"{t2} ريال (+{t2_pct}%)", GOLDEN_COLORS["green"], "🟢")
        
        sl = self.data.get('stop_loss', 0)
        sl_pct = self.data.get('stop_loss_percent', 0)
        self.draw_price_row("وقف الخسارة", f"{sl} ريال (-{sl_pct}%)", GOLDEN_COLORS["red"], "")

    def draw_footer(self):
        """التذييل"""
        footer_y = IMG_HEIGHT - 140
        
        self.draw.line([(PADDING, footer_y), (IMG_WIDTH-PADDING, footer_y)], 
                      fill=GOLDEN_COLORS["gray"], width=2)
        
        warning = "⚠️ محتوى تعليمي وتحليلي فقط — لا يعد توصية استثمارية"
        bbox_w = self.draw.textbbox((0, 0), warning, font=self.fonts["footer"])
        w_w = bbox_w[2] - bbox_w[0]
        self.draw.text(((IMG_WIDTH-w_w)//2, footer_y + 15), 
                      warning, font=self.fonts["footer"], fill=GOLDEN_COLORS["gray"])
        
        watermark = f"👁️ {BRANDING['name']} | {BRANDING['channel']}"
        bbox_wm = self.draw.textbbox((0, 0), watermark, font=self.fonts["label"])
        w_wm = bbox_wm[2] - bbox_wm[0]
        self.draw.text(((IMG_WIDTH-w_wm)//2, footer_y + 55), 
                      watermark, font=self.fonts["label"], fill=GOLDEN_COLORS["accent"])

    def generate(self, input_file, output_file):
        """التنفيذ الكامل"""
        if not self.load_data(input_file):
            return False
            
        print("🎨 بدء رسم التصميم الذهبي...")
        self.create_base()
        self.draw_frame()
        self.draw_header()
        self.draw_stock_info()
        self.draw_prices()
        self.draw_footer()
        
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        self.img.save(output_file, "PNG", quality=95)
        print(f"✅ تم حفظ الصورة الذهبية: {output_file}")
        return True


def main():
    """الدالة الرئيسية"""
    base_dir = Path(__file__).parent.parent
    
    input_default = base_dir / "data" / "golden_signal.json"
    output_default = base_dir / "output_golden.png"
    
    input_file = sys.argv[1] if len(sys.argv) > 1 else str(input_default)
    output_file = sys.argv[2] if len(sys.argv) > 2 else str(output_default)
    
    generator = RasedGoldenGenerator()
    generator.generate(input_file, output_file)


if __name__ == "__main__":
    main()
