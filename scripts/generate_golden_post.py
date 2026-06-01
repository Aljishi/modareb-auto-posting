#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rased — Golden Signal Image Generator
Reads golden_signals.json from golden_signal_analysis.py output.
Cross-references daily.json for live prices/targets.
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

def ar(text):
    if not text or not _AR: return str(text)
    try: return get_display(arabic_reshaper.reshape(str(text)))
    except: return str(text)

C = {
    "bg": "#080D1A", "card": "#0F1525",
    "gold": "#D4AF37", "gold_light": "#F0D060",
    "green": "#2ECC71", "red": "#E74C3C",
    "white": "#FFFFFF", "gray": "#7B8BA4",
    "border": "#1A2540", "btn_bg": "#111827",
    "circle_bg": "#12192E", "badge_dark": "#1A0A00",
}
W, H = 1080, 1350
PAD = 55; ROW_H = 82; ROW_GAP = 7; BAR_W = 9
BRAND = {"name": "راصد", "subtitle": "تحليل ذكي معمق - 20 يوم تاريخي", "channel": "t.me/RasedSA"}


def load_golden(path):
    """Load first golden signal and enrich with price data if available."""
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    signals = raw if isinstance(raw, list) else raw.get("signals", [raw])
    if not signals: return None
    return signals[0]


def enrich_from_daily(signal):
    """
    golden_signal_analysis.py doesn't compute entry/target/stop.
    Pull the stock's current price from daily.json and calculate them.
    """
    sym      = signal.get("symbol", "")
    data_dir = Path(__file__).parent.parent / "data"
    daily    = data_dir / "daily.json"

    stock_price = None
    stock_name  = ""
    sector      = ""
    rsi_live    = None
    vol_live    = None

    if daily.exists():
        with open(daily, 'r', encoding='utf-8') as f:
            d = json.load(f)
        for s in d.get("stocks", []):
            if s.get("symbol") == sym:
                stock_price = float(s.get("current_price", 0))
                stock_name  = s.get("name", "")
                sector      = s.get("sector", "")
                rsi_live    = s.get("rsi")
                vol_live    = s.get("volume_ratio")
                break

    analysis   = signal.get("analysis", {})
    indicators = analysis.get("indicators", {})
    rsi   = rsi_live  or indicators.get("RSI", 0)
    vol   = vol_live  or indicators.get("volume_ratio", 0)
    score = analysis.get("score", 0)

    price = stock_price or 0
    entry = round(price * 1.01, 2) if price else 0
    t1    = round(price * 1.05, 2) if price else 0
    t2    = round(price * 1.10, 2) if price else 0
    sl    = round(price * 0.97, 2) if price else 0

    return {
        "stock_symbol":      sym,
        "stock_name":        stock_name,
        "sector":            sector,
        "current_price":     price,
        "entry_point":       entry,
        "target1":           t1,
        "target1_percent":   5.0,
        "target2":           t2,
        "target2_percent":   10.0,
        "stop_loss":         sl,
        "stop_loss_percent": 3.0,
        "rsi":               rsi,
        "volume_ratio":      vol,
        "score":             score,
        "technical_reading": " | ".join(analysis.get("conditions", [])[:3]),
        "type":              "إشارة ذهبية",
    }


class GoldenSignalGenerator:
    def __init__(self):
        self.data = None; self.img = None; self.draw = None; self.fonts = {}
        self._load_fonts()

    def _load_fonts(self):
        base = Path(__file__).parent.parent / "assets" / "fonts"
        for name in ["Cairo", "Tajawal"]:
            try:
                b = base / f"{name}-Bold.ttf"; r = base / f"{name}-Regular.ttf"
                if b.exists() and r.exists():
                    self.fonts = {
                        "brand": ImageFont.truetype(b,80), "subtitle": ImageFont.truetype(r,26),
                        "stock": ImageFont.truetype(b,48), "label":    ImageFont.truetype(r,28),
                        "value": ImageFont.truetype(b,36), "badge":    ImageFont.truetype(b,22),
                        "gbadge": ImageFont.truetype(b,24), "topbar":  ImageFont.truetype(r,22),
                        "metrics": ImageFont.truetype(r,26), "reading": ImageFont.truetype(r,20),
                        "footer": ImageFont.truetype(r,18), "btn":     ImageFont.truetype(b,22),
                    }
                    print(f"✅ خط: {name}"); return
            except: continue
        default = ImageFont.load_default()
        self.fonts = {k: default for k in ["brand","subtitle","stock","label","value","badge","gbadge","topbar","metrics","reading","footer","btn"]}

    def _tw(self,t,f): bb=self.draw.textbbox((0,0),t,font=f); return bb[2]-bb[0]
    def _th(self,t,f): bb=self.draw.textbbox((0,0),t,font=f); return bb[3]-bb[1]
    def _cx(self,t,f): return (W-self._tw(t,f))//2

    def _make_bg(self):
        self.img=Image.new("RGB",(W,H),C["bg"]); self.draw=ImageDraw.Draw(self.img)

    def _topbar(self):
        now=datetime.now(); ts=now.strftime("%I:%M م"); ds=now.strftime("%Y/%m/%d"); y=28
        self.draw.text((PAD,y), ts, font=self.fonts["topbar"], fill=C["gray"])
        self.draw.text((W-PAD-self._tw(ds,self.fonts["topbar"]),y), ds, font=self.fonts["topbar"], fill=C["gray"])
        badge=ar("★ اشارة ذهبية"); bw=self._tw(badge,self.fonts["gbadge"])+30; bx=(W-bw)//2; by=y-4
        self.draw.rounded_rectangle([(bx,by),(bx+bw,by+36)], radius=18, fill=C["gold"])
        self.draw.text(((W-self._tw(badge,self.fonts["gbadge"]))//2,by+7), badge, font=self.fonts["gbadge"], fill=C["badge_dark"])

    def _logo(self, cy=148):
        cx,r=W//2,58
        self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)], fill=C["circle_bg"], outline=C["gold"], width=4)
        bw,bg=11,5; tbw=3*bw+2*bg; bx0=cx-tbw//2
        for i,bh in enumerate([30,20,12]):
            bx=bx0+i*(bw+bg); self.draw.rectangle([(bx,cy+14-bh),(bx+bw,cy+14)], fill=C["gold"])
        ax,ay=cx+r-16,cy-r+14
        self.draw.line([(ax-12,ay+12),(ax,ay)], fill=C["gold"],width=3)
        self.draw.line([(ax-7,ay),(ax,ay)],     fill=C["gold"],width=3)
        self.draw.line([(ax,ay),(ax,ay+7)],     fill=C["gold"],width=3)

    def _brand(self, y0=220):
        brand=ar(BRAND["name"])
        self.draw.text((self._cx(brand,self.fonts["brand"]),y0), brand, font=self.fonts["brand"], fill=C["gold_light"])
        sub=ar(BRAND["subtitle"])
        self.draw.text((self._cx(sub,self.fonts["subtitle"]),y0+88), sub, font=self.fonts["subtitle"], fill=C["white"])

    def _divider(self, y):
        mid=W//2
        self.draw.line([(PAD,y),(mid-14,y)], fill=C["border"],width=1)
        self.draw.ellipse([(mid-7,y-7),(mid+7,y+7)], fill=C["gold"])
        self.draw.line([(mid+14,y),(W-PAD,y)], fill=C["border"],width=1)

    def _stock_box(self, y0=378):
        d=self.data; name=d.get("stock_name",""); sym=d.get("stock_symbol","")
        title=ar(f"{name} - {sym}"); tw=self._tw(title,self.fonts["stock"])
        box_w=min(tw+80,W-PAD*2); bx=(W-box_w)//2
        self.draw.rounded_rectangle([(bx,y0),(bx+box_w,y0+70)], radius=10, fill=C["card"], outline="#C8D0DC", width=2)
        tx=(W-tw)//2; ty=y0+(70-self._th(title,self.fonts["stock"]))//2
        self.draw.text((tx,ty), title, font=self.fonts["stock"], fill=C["white"])

    def _row(self,label,value,bar_color,y,badge=None):
        self.draw.rounded_rectangle([(PAD,y),(W-PAD,y+ROW_H)], radius=10, fill=C["card"])
        self.draw.rounded_rectangle([(PAD,y),(PAD+BAR_W,y+ROW_H)], radius=5, fill=bar_color)
        val_x=PAD+BAR_W+16
        if badge:
            bc=C["green"] if badge.startswith("+") else C["red"]
            bw=self._tw(badge,self.fonts["badge"])+22; bx=PAD+BAR_W+10; by=y+(ROW_H-28)//2
            self.draw.rounded_rectangle([(bx,by),(bx+bw,by+28)], radius=8, fill=bc)
            self.draw.text((bx+11,by+5), badge, font=self.fonts["badge"], fill=C["white"])
            val_x=bx+bw+14
        vy=y+(ROW_H-self._th(value,self.fonts["value"]))//2
        self.draw.text((val_x,vy), value, font=self.fonts["value"], fill=bar_color)
        lbl=ar(label); lw=self._tw(lbl,self.fonts["label"])
        self.draw.text((W-PAD-BAR_W-16-lw, y+(ROW_H-self._th(lbl,self.fonts["label"]))//2),
                       lbl, font=self.fonts["label"], fill=C["gray"])

    def _rows(self, y0=480):
        d=self.data
        def rial(v): return f"{v} ريال"
        y=y0
        self._row("السعر الحالي:", rial(d.get("current_price",0)), C["gold"],  y)
        y+=ROW_H+ROW_GAP
        self._row("نقطة الدخول:", rial(d.get("entry_point",0)),  C["gold"],  y)
        y+=ROW_H+ROW_GAP
        self._row("الهدف الاول:",  rial(d.get("target1",0)),      C["green"], y, badge="+5%")
        y+=ROW_H+ROW_GAP
        self._row("الهدف الثاني:", rial(d.get("target2",0)),      C["green"], y, badge="+10%")
        y+=ROW_H+ROW_GAP
        self._row("وقف الخسارة:", rial(d.get("stop_loss",0)),    C["red"],   y, badge="-3%")
        y+=ROW_H+ROW_GAP
        return y

    def _metrics(self, y):
        d=self.data; rsi=d.get("rsi",""); vol=d.get("volume_ratio",""); score=d.get("score","")
        self.draw.rounded_rectangle([(PAD,y),(W-PAD,y+52)], radius=8, fill=C["card"])
        segs=[s for s in [f"RSI  {rsi}" if rsi else "", f"Vol  {vol}x" if vol else "", f"Score  {score}" if score else ""] if s]
        if not segs: return y+62
        sw=(W-PAD*2)//len(segs)
        for i,seg in enumerate(segs):
            sx=PAD+i*sw; tw=self._tw(seg,self.fonts["metrics"])
            self.draw.text((sx+(sw-tw)//2,y+14), seg, font=self.fonts["metrics"], fill=C["white"])
            if i<len(segs)-1: self.draw.line([(sx+sw,y+10),(sx+sw,y+42)], fill=C["border"],width=1)
        return y+62

    def _reading(self, y, text):
        if not text: return y
        words=str(text).split(); max_w=W-PAD*2-30; lines,line=[],""
        for w in words:
            test=f"{line} {w}".strip()
            if self._tw(ar(test),self.fonts["reading"])<max_w: line=test
            else:
                if line: lines.append(line)
                line=w
        if line: lines.append(line)
        lh=26; box_h=len(lines)*lh+22
        self.draw.rounded_rectangle([(PAD,y),(W-PAD,y+box_h)], radius=8, fill=C["card"])
        ty=y+12
        for ln in lines:
            drawn=ar(ln)
            self.draw.text(((W-self._tw(drawn,self.fonts["reading"]))//2,ty), drawn, font=self.fonts["reading"], fill=C["gray"])
            ty+=lh
        return y+box_h+10

    def _footer(self, y):
        disc=ar("محتوى تعليمي وتحليلي فقط - لا يعد توصية استثمارية")
        self.draw.text(((W-self._tw(disc,self.fonts["footer"]))//2,y), disc, font=self.fonts["footer"], fill=C["gray"])
        btn_y=y+38; btn=BRAND["channel"]; bw=self._tw(btn,self.fonts["btn"])+64; bx=(W-bw)//2
        self.draw.rounded_rectangle([(bx,btn_y),(bx+bw,btn_y+46)], radius=23, fill=C["btn_bg"], outline=C["gold"], width=2)
        self.draw.text(((W-self._tw(btn,self.fonts["btn"]))//2,btn_y+11), btn, font=self.fonts["btn"], fill=C["gold"])

    def generate(self, inp, out):
        print("="*55); print("⭐ راصد — مولّد الإشارة الذهبية"); print("="*55)
        try:
            raw = load_golden(inp)
            self.data = enrich_from_daily(raw)
        except Exception as e:
            print(f"❌ {e}"); return False
        if not self.data: print("⚠️ لا توجد بيانات"); return False

        self._make_bg(); self._topbar(); self._logo(cy=148)
        self._brand(y0=220); self._divider(y=358)
        self._stock_box(y0=378); self._divider(y=462)
        y=self._rows(y0=480)
        y=self._metrics(y+10)
        reading=self.data.get("technical_reading","")
        y=self._reading(y+10, reading)
        self._footer(y+10)
        p=Path(out); p.parent.mkdir(parents=True,exist_ok=True)
        self.img.save(p,"PNG",quality=95)
        print(f"✅ تم الحفظ: {p.absolute()}")
        return True


def main():
    base=Path(__file__).parent.parent
    inp =sys.argv[1] if len(sys.argv)>1 else str(base/"data/golden_signals.json")
    out =sys.argv[2] if len(sys.argv)>2 else str(base/"golden_output.png")
    ok  =GoldenSignalGenerator().generate(inp,out)
    sys.exit(0 if ok else 1)

if __name__=="__main__": main()
