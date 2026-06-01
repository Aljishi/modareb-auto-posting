#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate post image from validated signals
Usage: python scripts/generate_post.py <input_json> <output_png>
"""

import json
import sys
import os
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import arabic_reshaper
from bidi.algorithm import get_display

def get_arabic_text(text):
    """Reshape Arabic text for correct display in PIL"""
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

def generate_image(signal_data, output_path):
    """Generate a dark-themed trading signal image"""
    # Create dark background
    width, height = 900, 980
    img = Image.new('RGB', (width, height), color='#0f172a')
    draw = ImageDraw.Draw(img)
    
    # Load fonts (using default or system fonts if custom not available)
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 40)
        font_body = ImageFont.truetype("arial.ttf", 30)
        font_small = ImageFont.truetype("arial.ttf", 24)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Colors
    color_white = '#ffffff'
    color_green = '#10b981'
    color_red = '#ef4444'
    color_gray = '#94a3b8'
    color_gold = '#fbbf24'

    # Header
    draw.text((50, 50), get_arabic_text("إشارة تداول - راصد"), fill=color_gold, font=font_title)
    
    # Stock Info
    y_pos = 150
    symbol = signal_data.get('symbol', '')
    name = signal_data.get('name', '')
    sector = signal_data.get('sector', '')
    
    draw.text((50, y_pos), get_arabic_text(f"{name} ({symbol})"), fill=color_white, font=font_body)
    y_pos += 50
    draw.text((50, y_pos), get_arabic_text(f"القطاع: {sector}"), fill=color_gray, font=font_small)
    
    # Prices
    y_pos += 80
    current_price = signal_data.get('current_price', 0)
    entry = signal_data.get('entry_point', 0)
    target1 = signal_data.get('target1', 0)
    target2 = signal_data.get('target2', 0)
    stop_loss = signal_data.get('stop_loss', 0)
    
    draw.text((50, y_pos), get_arabic_text(f"السعر الحالي: {current_price:.2f} ريال"), fill=color_white, font=font_body)
    y_pos += 50
    draw.text((50, y_pos), get_arabic_text(f"نقطة الدخول: {entry:.2f} ريال"), fill=color_green, font=font_body)
    
    y_pos += 60
    draw.text((50, y_pos), get_arabic_text(f"الهدف الأول: {target1:.2f} ريال (+{((target1-current_price)/current_price*100):.1f}%)"), fill=color_green, font=font_small)
    y_pos += 40
    draw.text((50, y_pos), get_arabic_text(f"الهدف الثاني: {target2:.2f} ريال (+{((target2-current_price)/current_price*100):.1f}%)"), fill=color_green, font=font_small)
    
    y_pos += 60
    draw.text((50, y_pos), get_arabic_text(f"وقف الخسارة: {stop_loss:.2f} ريال ({((stop_loss-current_price)/current_price*100):.1f}%)"), fill=color_red, font=font_small)
    
    # Indicators
    y_pos += 80
    score = signal_data.get('score', 0)
    rsi = signal_data.get('rsi', 0)
    confidence = signal_data.get('confidence', 'متوسطة')
    
    draw.text((50, y_pos), get_arabic_text(f"النتيجة: {score}/100 | RSI: {rsi:.1f}"), fill=color_white, font=font_small)
    y_pos += 40
    draw.text((50, y_pos), get_arabic_text(f"مستوى الثقة: {confidence}"), fill=color_gold, font=font_small)
    
    # Footer
    footer_text = "محتوى تعليمي وتحليلي فقط — لا يعد توصية استثمارية"
    draw.text((50, height - 50), get_arabic_text(footer_text), fill=color_gray, font=font_small)
    
    # Save
    img.save(output_path)
    print(f"✅ Image saved to {output_path}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_post.py <input_json> <output_png>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        sys.exit(1)
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Get first valid signal
    signals = data.get('validated_signals', data.get('signals', []))
    
    if not signals:
        print("⚠️ No signals found in input file")
        sys.exit(0)
    
    signal = signals[0]
    generate_image(signal, output_file)

if __name__ == "__main__":
    main()

