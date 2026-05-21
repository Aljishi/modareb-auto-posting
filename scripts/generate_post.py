#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rased Auto Posting - Normal Signal Generator
مولّد صور إشارات راصد العادية (أثناء السوق)
تصميم: أزرق/رمادي — مضغوط — احترافي
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
    print("💡 ثبّتها عبر: pip install Pillow")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# 🎨 ألوان التصميم العادي
# ═══════════════════════════════════════════════════════════════
NORMAL_COLORS = {
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

# ═══════════════════════════════════════════════════════════════
# 🔤 إعدادات الخطوط
# ═══════════════════════════════════════════════════════════════
FONTS = {
    "path": "assets/fonts",
    "sizes": {
        "title": 36,
        "stock": 48,
        "label": 26,
        "value": 32,
        "price": 42,
        "footer": 20,
        "tiny": 18
    }
}

# ═══════════════════════════════════════════════════════════════
# 🏷️ الهوية
# ═══════════════════════════════════════════════════════════════
BRANDING = {
    "name": "راصد",
    "channel": "@RasedSA",
    "watermark": "بواسطة راصد | عينك على الفرص"
}

# ═══════════════════════════════════════════════════════════════
# 📐 أبعاد الصورة
# ═══════════════════════════════════════════════════════════════
IMG_WIDTH = 1080
IMG_HEIGHT = 1350
PADDING = 60


class RasedNormalGenerator:
    """مولّد صور الإشارات العادية"""

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
                        Path(f"C:/Windows/Fonts/{file_prefix}-Bold.ttf"),
                        Path(f"/usr/share/fonts/{file_prefix}-Bold.ttf"),
                    ],
                    "Regular": [
                        font_dir / f"{file_prefix}-Regular.ttf",
                        font_dir / f"{font_name}-Regular.ttf",
                        Path(f"C:/Windows/Fonts/{file_prefix}-Regular.ttf"),
                        Path(f"/usr/share/fonts/{file_prefix}-Regular.ttf"),
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
                        "tiny": ImageFont.truetype(light_found or reg_found, sizes["tiny"])
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
                    "tiny": ImageFont.truetype("arial.ttf", sizes["tiny"])
                }
                print("✅ تم استخدام Arial")
            except:
                self.fonts = {k: ImageFont.load_default() for k in sizes.keys()}
                print("❌ استخدام الخط الافتراضي")

    def load_data(self, file_path):
        """تحميل البيانات من ملف JSON"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            return True
        except FileNotFoundError:
            print(f"❌ الملف غير موجود: {file_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ خطأ في تنسيق JSON: {e}")
            return False
        except Exception as e:
            print(f"❌ خطأ غير متوقع: {e}")
            return False

    def create_background(self):
        """إنشاء الخلفية الداكنة مع تدرج خفيف"""
        self.img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), NORMAL_COLORS["bg"])
        self.draw = ImageDraw.Draw(self.img)
        
        for y in range(150):
            alpha = int(60 * (1 - y/150))
            color = (52, 152, 219, alpha)
            self.draw.line([(0, y), (IMG_WIDTH, y)], fill=color)

    def draw_header(self):
        """رسم الرأس"""
        header = f"{BRANDING['name']} | إشارة اليوم"
        bbox = self.draw.textbbox((0, 0), header, font=self.fonts["title"])
        w = bbox[2] - bbox[0]
        x = (IMG_WIDTH - w) // 2
        
        self.draw.text((x, 40), header, 
                      font=self.fonts["title"], fill=NORMAL_COLORS["accent"])
        
        line_y = 40 + bbox[3] + 15
        self.draw.line([(PADDING, line_y), (IMG_WIDTH-PADDING, line_y)], 
                      fill=NORMAL_COLORS["accent"], width=3)
        
        now = datetime.now().strftime("%Y/%m/%d - %H:%M")
        self.draw.text((PADDING, line_y + 12), now, 
                      font=self.fonts["footer"], fill=NORMAL_COLORS["gray"])

    def draw_stock_info(self):
        """رسم معلومات السهم"""
        if not self.data:
            return
        
        y = 160
        name = self.data.get('stock_name', '')
        symbol = self.data.get('stock_symbol', '')
        title = f"{name} — {symbol}"
        
        bbox = self.draw.textbbox((0, 0), title, font=self.fonts["stock"])
        w = bbox[2] - bbox[0]
        x = (IMG_WIDTH - w) // 2
        
        self.draw.text((x, y), title, 
                      font=self.fonts["stock"], fill=NORMAL_COLORS["white"])
        
        sector = self.data.get('sector', '')
        if sector:
            sector_text = f"🏢 القطاع: {sector}"
            bbox_sec = self.draw.textbbox((0, 0), sector_text, font=self.fonts["label"])
            w_sec = bbox_sec[2] - bbox_sec[0]
            self.draw.text(((IMG_WIDTH - w_sec)//2, y + 60), 
                          sector_text, font=self.fonts["label"], 
                          fill=NORMAL_COLORS["gray"])

    def _draw_price_row(self, label, value, color, icon="", y_start=None):
        """رسم صف سعر واحد"""
        if y_start is None:
            y_start = self.current_y
        
        row_height = 65
        
        self.draw.rectangle(
            [(PADDING, y_start), (IMG_WIDTH-PADDING, y_start + row_height)],
            fill=NORMAL_COLORS["card"]
        )
        
        self.draw.rectangle(
            [(PADDING, y_start), (PADDING+6, y_start + row_height)],
            fill=color
        )
        
        label_text = f"{icon} {label}"
        self.draw.text((PADDING + 20, y_start + 18), 
                      label_text, font=self.fonts["label"], 
                      fill=NORMAL_COLORS["gray"])
        
        val_text = f"{value}"
        bbox_val = self.draw.textbbox((0, 0), val_text, font=self.fonts["price"])
        w_val = bbox_val[2] - bbox_val[0]
        x_val = IMG_WIDTH - PADDING - 20 - w_val
        
        self.draw.text((x_val, y_start + 18), 
                      val_text, font=self.fonts["price"], 
                      fill=color)
        
        if y_start < (IMG_HEIGHT - 200):
            self.draw.line(
                [(PADDING, y_start + row_height), (IMG_WIDTH-PADDING, y_start + row_height)], 
                fill=NORMAL_COLORS["divider"], width=1
            )
        
        return y_start + row_height + 8

    def draw_prices(self):
        """رسم جدول الأسعار"""
        if not self.data:
            return
        
        self.current_y = 320
        
        current = self.data.get('current_price', 0)
        self.current_y = self._draw_price_row(
            "السعر الحالي", f"{current} ريال", 
            NORMAL_COLORS["gold"], "📊", self.current_y
        )
        
        entry = self.data.get('entry_point', 0)
        self.current_y = self._draw_price_row(
            "نقطة الدخول", f"{entry} ريال", 
            NORMAL_COLORS["accent"], "🎯", self.current_y
        )
        
        t1 = self.data.get('target1', 0)
        t1_pct = self.data.get('target1_percent', 0)
        self.current_y = self._draw_price_row(
            "الهدف الأول", f"{t1} ريال (+{t1_pct}%)", 
            NORMAL_COLORS["green"], "🟢", self.current_y
        )
        
        t2 = self.data.get('target2', 0)
        t2_pct = self.data.get('target2_percent', 0)
        if t2:
            self.current_y = self._draw_price_row(
                "الهدف الثاني", f"{t2} ريال (+{t2_pct}%)", 
                NORMAL_COLORS["green"], "🟢", self.current_y
            )
        
        sl = self.data.get('stop_loss', 0)
        sl_pct = self.data.get('stop_loss_percent', 0)
        self.current_y = self._draw_price_row(
            "وقف الخسارة", f"{sl} ريال (-{sl_pct}%)", 
            NORMAL_COLORS["red"], "🔴", self.current_y
        )

    def draw_analysis(self):
        """رسم المؤشرات الفنية"""
        if not self.data:
            return
        
        y = self.current_y + 30
        
        score = self.data.get('score', 0)
        rs_rank = self.data.get('rs_rank', 0)
        
        score_color = NORMAL_COLORS["green"] if score >= 80 else NORMAL_COLORS["accent"]
        score_text = f"🔢 Score: {score}/100"
        self.draw.text((PADDING, y), score_text, 
                      font=self.fonts["label"], fill=score_color)
        
        rank_text = f"📈 RS Rank: {rs_rank}"
        bbox_rank = self.draw.textbbox((0, 0), rank_text, font=self.fonts["label"])
        rank_x = IMG_WIDTH - PADDING - 20 - (bbox_rank[2] - bbox_rank[0])
        self.draw.text((rank_x, y), rank_text, 
                      font=self.fonts["label"], fill=NORMAL_COLORS["gold"])
        
        y += 40
        reading = self.data.get('technical_reading', '')
        if reading:
            self.draw.text((PADDING, y), "📌 قراءة فنية:", 
                          font=self.fonts["label"], fill=NORMAL_COLORS["accent"])
            y += 32
            
            words = reading.split()
            line = ""
            max_width = IMG_WIDTH - (PADDING * 2)
            
            for word in words:
                test_line = line + " " + word if line else word
                bbox = self.draw.textbbox((0, 0), test_line, font=self.fonts["tiny"])
                if bbox[2] < max_width:
                    line = test_line
                else:
                    if line:
                        self.draw.text((PADDING, y), f"• {line}", 
                                      font=self.fonts["tiny"], 
                                      fill=NORMAL_COLORS["gray"])
                        y += 26
                    line = word
            
            if line:
                self.draw.text((PADDING, y), f"• {line}", 
                              font=self.fonts["tiny"], 
                              fill=NORMAL_COLORS["gray"])

    def draw_footer(self):
        """رسم التذييل"""
        footer_y = IMG_HEIGHT - 130
        
        self.draw.line([(PADDING, footer_y), (IMG_WIDTH-PADDING, footer_y)], 
                      fill=NORMAL_COLORS["border"], width=2)
        
        warning = "⚠️ محتوى تعليمي وتحليلي فقط — لا يعد توصية استثمارية"
        bbox_w = self.draw.textbbox((0, 0), warning, font=self.fonts["footer"])
        w_w = bbox_w[2] - bbox_w[0]
        self.draw.text(((IMG_WIDTH - w_w)//2, footer_y + 15), 
                      warning, font=self.fonts["footer"], 
                      fill=NORMAL_COLORS["gray"])
        
        watermark = f"👁️ {BRANDING['name']} | {BRANDING['channel']}"
        bbox_wm = self.draw.textbbox((0, 0), watermark, font=self.fonts["label"])
        w_wm = bbox_wm[2] - bbox_wm[0]
        self.draw.text(((IMG_WIDTH - w_wm)//2, footer_y + 50), 
                      watermark, font=self.fonts["label"], 
                      fill=NORMAL_COLORS["accent"])

    def generate(self, input_file, output_file):
        """التنفيذ الكامل"""
        try:
            print("=" * 60)
            print(f"📊 {BRANDING['name']} — مولّد الإشارات العادية")
            print("=" * 60)
            
            if not self.load_data(input_file):
                return False
            
            print("🎨 بدء إنشاء الصورة...")
            
            self.create_background()
            self.draw_header()
            self.draw_stock_info()
            self.draw_prices()
            self.draw_analysis()
            self.draw_footer()
            
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            self.img.save(output_path, "PNG", quality=95)
            
            print(f"✅ تم حفظ الصورة: {output_path.absolute()}")
            return True
            
        except Exception as e:
            print(f"❌ خطأ غير متوقع: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """الدالة الرئيسية"""
    base_dir = Path(__file__).parent.parent
    input_default = base_dir / "data" / "daily.json"
    output_default = base_dir / "output.png"
    
    input_file = sys.argv[1] if len(sys.argv) > 1 else str(input_default)
    output_file = sys.argv[2] if len(sys.argv) > 2 else str(output_default)
    
    generator = RasedNormalGenerator()
    success = generator.generate(input_file, output_file)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
