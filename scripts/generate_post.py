#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rased Auto Posting - Normal Signal Generator
مولّد صور إشارات راصد العادية (أثناء السوق)
"""

import sys
import io
import json
from datetime import datetime
from pathlib import Path

# إصلاح ترميز الكونسول في ويندوز
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    from PIL import Image, ImageDraw, ImageFont
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError as e:
    print(f"❌ خطأ: مكتبة مفقودة - {e}")
    print("💡 ثبّتها عبر: pip install -r requirements.txt")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
#  استيراد الإعدادات المركزية من config.py
# ══════════════════════════════════════════════════════════════
try:
    from config import BRAND, COLORS, FONT_SIZES, IMG_SIZE, PADDING, BRANDING
except ImportError:
    print("⚠️ تحذير: config.py غير موجود - استخدام إعدادات افتراضية")
    COLORS = {
        "bg": "#07101E",
        "card": "#0B1420",
        "accent": "#2563EB",
        "gold": "#F59E0B",
        "green": "#10B981",
        "red": "#EF4444",
        "white": "#FFFFFF",
        "gray": "#9CA3AF",
        "border": "#1E293B"
    }
    FONT_SIZES = {
        "title": 40, "stock": 52, "label": 28, "value": 32,
        "price": 36, "footer": 20, "tiny": 18
    }
    BRANDING = {"name": "راصد", "channel": "@RasedSA", "slogan": "عينك على الفرص"}
    IMG_SIZE = (1080, 1350)  # ✅ تم الإصلاح: نسبة 4:5
    PADDING = 60


def ar(text):
    """معالجة النصوص العربية للعرض الصحيح"""
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except:
        return str(text)


class SignalImageGenerator:
    """مولّد صور الإشارات العادية"""

    def __init__(self, data_file):
        self.data_file = Path(data_file)
        self.data = None
        self.img = None
        self.draw = None
        self.fonts = {}
        self._load_fonts()

    def _load_fonts(self):
        """تحميل الخطوط مع fallback ذكي"""
        base_dir = Path(__file__).parent.parent
        font_dir = base_dir / "assets" / "fonts"
        
        for name in ["Cairo", "Tajawal", "Arial"]:
            try:
                bold_path = font_dir / f"{name}-Bold.ttf"
                reg_path = font_dir / f"{name}-Regular.ttf"
                
                if bold_path.exists() and reg_path.exists():
                    self.fonts = {
                        "title": ImageFont.truetype(bold_path, FONT_SIZES["title"]),
                        "stock": ImageFont.truetype(bold_path, FONT_SIZES["stock"]),
                        "label": ImageFont.truetype(reg_path, FONT_SIZES["label"]),
                        "value": ImageFont.truetype(bold_path, FONT_SIZES["value"]),
                        "price": ImageFont.truetype(bold_path, FONT_SIZES["price"]),
                        "footer": ImageFont.truetype(reg_path, FONT_SIZES["footer"]),
                        "tiny": ImageFont.truetype(reg_path, FONT_SIZES["tiny"])
                    }
                    print(f"✅ تم تحميل خط: {name}")
                    return
            except Exception as e:
                continue
        
        print("⚠️ لم يتم العثور على خطوط عربية - استخدام الافتراضي")
        self.fonts = {k: ImageFont.load_default() for k in FONT_SIZES}

    def load_data(self):
        """تحميل البيانات من JSON"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            return True
        except Exception as e:
            print(f"❌ خطأ في قراءة البيانات: {e}")
            return False

    def create_background(self):
        """إنشاء الخلفية مع التدرج"""
        self.img = Image.new('RGB', IMG_SIZE, COLORS["bg"])
        self.draw = ImageDraw.Draw(self.img)
        
        # تدرج علوي خفيف
        for y in range(200):
            alpha = int(80 * (1 - y/200))
            self.draw.line([(0, y), (IMG_SIZE[0], y)], fill=(37, 99, 235, alpha))

    def draw_header(self):
        """رسم الرأس مع الشعار"""
        # الشعار الدائري
        logo_x = IMG_SIZE[0] // 2
        logo_y = 50
        logo_radius = 45
        
        # دائرة الشعار
        self.draw.ellipse(
            [(logo_x - logo_radius, logo_y), 
             (logo_x + logo_radius, logo_y + logo_radius * 2)],
            outline=COLORS["gold"],
            width=4
        )
        
        # نص الشعار داخل الدائرة
        self.draw.text(
            (logo_x - 20, logo_y + 15),
            ar("ر"),
            font=self.fonts["title"],
            fill=COLORS["gold"]
        )
        
        # العنوان
        title = ar(f"{BRANDING['name']} | إشارة اليوم")
        bbox = self.draw.textbbox((0, 0), title, font=self.fonts["title"])
        title_x = (IMG_SIZE[0] - (bbox[2] - bbox[0])) // 2
        self.draw.text((title_x, 150), title, font=self.fonts["title"], fill=COLORS["white"])
        
        # خط فاصل
        line_y = 150 + bbox[3] + 15
        self.draw.line([(PADDING, line_y), (IMG_SIZE[0] - PADDING, line_y)], 
                      fill=COLORS["accent"], width=3)
        
        # التاريخ
        now = datetime.now().strftime("%Y/%m/%d - %H:%M")
        self.draw.text((PADDING, line_y + 12), ar(now), 
                      font=self.fonts["footer"], fill=COLORS["gray"])

    def draw_stock_info(self):
        """معلومات السهم"""
        if not self.data:
            return
        
        y = 240
        name = ar(self.data.get('stock_name', ''))
        symbol = self.data.get('stock_symbol', '')
        title = ar(f"{name} — {symbol}")
        
        bbox = self.draw.textbbox((0, 0), title, font=self.fonts["stock"])
        x = (IMG_SIZE[0] - (bbox[2] - bbox[0])) // 2
        self.draw.text((x, y), title, font=self.fonts["stock"], fill=COLORS["white"])
        
        # القطاع
        sector = ar(self.data.get('sector', ''))
        if sector:
            sector_text = ar(f"🏢 القطاع: {sector}")
            sb = self.draw.textbbox((0, 0), sector_text, font=self.fonts["label"])
            sx = (IMG_SIZE[0] - (sb[2] - sb[0])) // 2
            self.draw.text((sx, y + 65), sector_text, 
                          font=self.fonts["label"], fill=COLORS["gray"])

    def _draw_price_row(self, label, value, color, icon="", y=None):
        """رسم صف سعر واحد"""
        if y is None:
            y = self.current_y
        
        row_height = 75
        card_x1 = PADDING
        card_y1 = y
        card_x2 = IMG_SIZE[0] - PADDING
        card_y2 = y + row_height
        
        # خلفية البطاقة
        self.draw.rounded_rectangle(
            [(card_x1, card_y1), (card_x2, card_y2)],
            radius=12,
            fill=COLORS["card"]
        )
        
        # شريط ملون على اليسار
        self.draw.rectangle(
            [(card_x1, card_y1 + 10), (card_x1 + 8, card_y2 - 10)],
            fill=color
        )
        
        # الأيقونة والتسمية
        label_text = ar(f"{icon} {label}")
        self.draw.text((card_x1 + 25, card_y1 + 22), 
                      label_text, font=self.fonts["label"], fill=COLORS["gray"])
        
        # القيمة (يمين)
        val_text = ar(str(value))
        vb = self.draw.textbbox((0, 0), val_text, font=self.fonts["price"])
        val_x = card_x2 - 25 - (vb[2] - vb[0])
        self.draw.text((val_x, card_y1 + 22), 
                      val_text, font=self.fonts["price"], fill=color)
        
        return y + row_height + 12

    def draw_prices(self):
        """رسم جدول الأسعار"""
        if not self.data:
            return
        
        self.current_y = 380
        
        # السعر الحالي (مميز)
        current = f"{self.data.get('current_price', 0)} ريال"
        self.current_y = self._draw_price_row(
            "السعر الحالي", current, COLORS["gold"], "📊", self.current_y
        )
        
        # نقطة الدخول
        entry = f"{self.data.get('entry_point', 0)} ريال"
        self.current_y = self._draw_price_row(
            "نقطة الدخول", entry, COLORS["accent"], "🎯", self.current_y
        )
        
        # الهدف الأول
        t1 = self.data.get('target1', 0)
        t1_pct = self.data.get('target1_percent', 0)
        t1_text = f"{t1} ريال (+{t1_pct}%)"
        self.current_y = self._draw_price_row(
            "الهدف الأول", t1_text, COLORS["green"], "🟢", self.current_y
        )
        
        # الهدف الثاني
        t2 = self.data.get('target2', 0)
        t2_pct = self.data.get('target2_percent', 0)
        if t2:
            t2_text = f"{t2} ريال (+{t2_pct}%)"
            self.current_y = self._draw_price_row(
                "الهدف الثاني", t2_text, COLORS["green"], "🟢", self.current_y
            )
        
        # وقف الخسارة
        sl = self.data.get('stop_loss', 0)
        sl_pct = self.data.get('stop_loss_percent', 0)
        sl_text = f"{sl} ريال (-{sl_pct}%)"
        self.current_y = self._draw_price_row(
            "وقف الخسارة", sl_text, COLORS["red"], "🔴", self.current_y
        )

    def draw_analysis(self):
        """المؤشرات الفنية"""
        if not self.data:
            return
        
        y = self.current_y + 35
        
        # Score
        score = self.data.get('score', 0)
        score_color = COLORS["green"] if score >= 80 else COLORS["accent"]
        score_text = ar(f"🔢 Score: {score}/100")
        self.draw.text((PADDING, y), score_text, 
                      font=self.fonts["label"], fill=score_color)
        
        # RS Rank
        rs_rank = self.data.get('rs_rank', 0)
        rank_text = ar(f"📈 RS Rank: {rs_rank}")
        rb = self.draw.textbbox((0, 0), rank_text, font=self.fonts["label"])
        rank_x = IMG_SIZE[0] - PADDING - 25 - (rb[2] - rb[0])
        self.draw.text((rank_x, y), rank_text, 
                      font=self.fonts["label"], fill=COLORS["gold"])
        
        # القراءة الفنية
        y += 45
        reading = ar(self.data.get('technical_reading', ''))
        if reading:
            self.draw.text((PADDING, y), ar("📌 قراءة فنية:"), 
                          font=self.fonts["label"], fill=COLORS["accent"])
            y += 35
            
            # تقسيم النص الطويل
            words = reading.split()
            line = ""
            max_width = IMG_SIZE[0] - (PADDING * 2)
            
            for word in words:
                test = f"{line} {word}" if line else word
                tb = self.draw.textbbox((0, 0), test, font=self.fonts["tiny"])
                if tb[2] < max_width:
                    line = test
                else:
                    if line:
                        self.draw.text((PADDING, y), ar(f"• {line}"), 
                                      font=self.fonts["tiny"], fill=COLORS["gray"])
                        y += 28
                    line = word
            
            if line:
                self.draw.text((PADDING, y), ar(f"• {line}"), 
                              font=self.fonts["tiny"], fill=COLORS["gray"])

    def draw_footer(self):
        """التذييل"""
        footer_y = IMG_SIZE[1] - 140
        
        # خط فاصل
        self.draw.line([(PADDING, footer_y), (IMG_SIZE[0] - PADDING, footer_y)], 
                      fill=COLORS["border"], width=2)
        
        # التحذير
        warning = ar("⚠️ محتوى تعليمي وتحليلي فقط — لا يعد توصية استثمارية")
        wb = self.draw.textbbox((0, 0), warning, font=self.fonts["footer"])
        wx = (IMG_SIZE[0] - (wb[2] - wb[0])) // 2
        self.draw.text((wx, footer_y + 15), warning, 
                      font=self.fonts["footer"], fill=COLORS["gray"])
        
        # العلامة المائية
        watermark = ar(f"👁️ {BRANDING['name']} | {BRANDING.get('channel', '@RasedSA')}")
        wmb = self.draw.textbbox((0, 0), watermark, font=self.fonts["label"])
        wmx = (IMG_SIZE[0] - (wmb[2] - wmb[0])) // 2
        self.draw.text((wmx, footer_y + 50), watermark, 
                      font=self.fonts["label"], fill=COLORS["accent"])

    def generate(self, output_path):
        """التنفيذ الكامل"""
        print("=" * 60)
        print(ar(f"📊 {BRANDING['name']} — مولّد الإشارات العادية"))
        print("=" * 60)
        
        if not self.load_data():
            return False
        
        print(ar("🎨 بدء إنشاء الصورة..."))
        
        self.create_background()
        self.draw_header()
        self.draw_stock_info()
        self.draw_prices()
        self.draw_analysis()
        self.draw_footer()
        
        # الحفظ
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.img.save(out, "PNG", quality=95)
        
        print(ar(f"✅ تم الحفظ: {out.absolute()}"))
        return True


def main():
    base_dir = Path(__file__).parent.parent
    input_file = sys.argv[1] if len(sys.argv) > 1 else str(base_dir / "data" / "daily.json")
    output_file = sys.argv[2] if len(sys.argv) > 2 else str(base_dir / "output.png")
    
    generator = SignalImageGenerator(input_file)
    success = generator.generate(output_file)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
