#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
راصد — الإشارة اليومية
تصميم مطابق للمرجع: سطر واحد لكل صف (تسمية | قيمة | شارة)
"""
import sys, io, json
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from PIL import Image, ImageDraw, ImageFont
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _AR = True
except:
    _AR = False

def ar(t):
    if not t or not _AR: return str(t)
    try: return get_display(arabic_reshaper.reshape(str(t)))
    except: return str(t)

# ── ألوان ────────────────────────────────────────────────────
BG      = "#0B0F1C"
CARD    = "#111827"
GOLD    = "#D4AF37"
GOLD_L  = "#F5D060"
GREEN   = "#27AE60"
RED     = "#E74C3C"
WHITE   = "#FFFFFF"
GRAY    = "#8899AA"
BORDER  = "#1E2D45"
BTN_BG  = "#0D1628"
CIRC    = "#161F30"

# ── ثوابت التخطيط ────────────────────────────────────────────
W       = 1080
H       = 1080
PAD     = 40        # هامش الصفوف من الحافة
ROW_H   = 76        # ارتفاع الصف
GAP     = 8         # المسافة بين الصفوف
IR      = 22        # نصف قطر الأيقونة
BH      = 34        # ارتفاع الشارة
BORD    = 5         # إطار الصورة

BRAND = {"name":"الراصد","sub":"تحليل فني وتعليمي لسوق الاسهم السعودية","ch":"t.me/RasedSA"}

def load(path):
    raw = json.load(open(path, encoding='utf-8'))
    if "validated_signals" in raw: s=raw["validated_signals"]; return s[0] if s else None
    if "signals" in raw: s=raw["signals"]; return s[0] if s else None
    return raw

def _g(d,*k,df=""):
    for i in k:
        v=d.get(i)
        if v not in (None,""): return v
    return df


class Post:
    def __init__(self):
        self.d=None; self.img=None; self.draw=None; self.f={}
        self._fonts()

    def _fonts(self):
        base = Path(__file__).parent.parent/"assets"/"fonts"
        for n in ["Cairo","Tajawal"]:
            try:
                b=base/f"{n}-Bold.ttf"; r=base/f"{n}-Regular.ttf"
                if not(b.exists() and r.exists()): continue
                self.f = {
                    "brand": ImageFont.truetype(b, 58),
                    "sub":   ImageFont.truetype(r, 22),
                    "s72":   ImageFont.truetype(b, 58),
                    "s56":   ImageFont.truetype(b, 46),
                    "s44":   ImageFont.truetype(b, 36),
                    "s34":   ImageFont.truetype(b, 28),
                    "lbl":   ImageFont.truetype(r, 26),
                    "val":   ImageFont.truetype(b, 32),
                    "bdg":   ImageFont.truetype(b, 22),
                    "top":   ImageFont.truetype(r, 20),
                    "rd":    ImageFont.truetype(r, 18),
                    "ft":    ImageFont.truetype(r, 16),
                    "btn":   ImageFont.truetype(b, 20),
                }
                print(f"✅ {n}"); return
            except: continue
        df=ImageFont.load_default()
        self.f={k:df for k in["brand","sub","s72","s56","s44","s34","lbl","val","bdg","top","rd","ft","btn"]}

    def tw(self,t,f): bb=self.draw.textbbox((0,0),t,font=f); return bb[2]-bb[0]
    def th(self,t,f): bb=self.draw.textbbox((0,0),t,font=f); return bb[3]-bb[1]
    def cx(self,t,f): return (W-self.tw(t,f))//2

    def sf(self,txt):
        for k in["s72","s56","s44","s34"]:
            f=self.f[k]
            if self.tw(txt,f) <= W-PAD*2-20: return f
        return self.f["s34"]


    def _islamic_box(self, x1, y1, x2, y2):
        """إطار إسلامي مزخرف: خطان + زخارف في الزوايا ومنتصف الأضلاع"""
        w = x2 - x1; h = y2 - y1
        cx = (x1+x2)//2; cy = (y1+y2)//2

        # ── الإطار الخارجي ──
        self.draw.rectangle([(x1,y1),(x2,y2)], fill=None, outline=GOLD, width=2)

        # ── الإطار الداخلي (4px للداخل) ──
        self.draw.rectangle([(x1+5,y1+5),(x2-5,y2-5)], fill=None, outline=GOLD, width=1)

        # ── زخرفة الزوايا (معين صغير داخل كل زاوية) ──
        d = 8   # نصف حجم المعين
        for (cx_, cy_) in [(x1,y1),(x2,y1),(x1,y2),(x2,y2)]:
            pts = [(cx_,cy_-d),(cx_+d,cy_),(cx_,cy_+d),(cx_-d,cy_)]
            self.draw.polygon(pts, fill=GOLD)

        # ── زخرفة منتصف الأضلاع (معين صغير في منتصف كل ضلع) ──
        dm = 6
        for (mx, my) in [(cx,y1),(cx,y2),(x1,cy),(x2,cy)]:
            pts = [(mx,my-dm),(mx+dm,my),(mx,my+dm),(mx-dm,my)]
            self.draw.polygon(pts, fill=GOLD)

        # ── خطوط الزخرفة من الزوايا الداخلية ──
        ofs = 18
        # أعلى يسار
        self.draw.line([(x1,y1+ofs),(x1+ofs,y1)], fill=GOLD, width=1)
        # أعلى يمين
        self.draw.line([(x2,y1+ofs),(x2-ofs,y1)], fill=GOLD, width=1)
        # أسفل يسار
        self.draw.line([(x1,y2-ofs),(x1+ofs,y2)], fill=GOLD, width=1)
        # أسفل يمين
        self.draw.line([(x2,y2-ofs),(x2-ofs,y2)], fill=GOLD, width=1)
    def bg(self):
        self.img=Image.new("RGB",(W,H),BG)
        self.draw=ImageDraw.Draw(self.img)
        self.draw.rectangle([(BORD,BORD),(W-BORD-1,H-BORD-1)],fill=None,outline=GOLD,width=2)

    def topbar(self):
        now=datetime.now()
        ts=now.strftime("%I:%M %p").replace("AM","ص").replace("PM","م")
        ds=now.strftime("%Y/%m/%d")
        lb=ar("وقت الاشارة"); y=28
        self.draw.text((PAD,y),ts,font=self.f["top"],fill="#77BB77")
        self.draw.text((self.cx(lb,self.f["top"]),y),lb,font=self.f["top"],fill=GRAY)
        self.draw.text((W-PAD-self.tw(ds,self.f["top"]),y),ds,font=self.f["top"],fill=GOLD)
        self.draw.line([(PAD,y+26),(W-PAD,y+26)],fill=BORDER,width=1)

    def logo(self,cy):
        cx,r=W//2,54
        self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)],fill=CIRC,outline=GOLD,width=4)
        bw,bg=11,5; tbw=3*bw+2*bg; bx0=cx-tbw//2
        for i,bh in enumerate([28,20,13]):
            bx=bx0+i*(bw+bg)
            self.draw.rectangle([(bx,cy+12-bh),(bx+bw,cy+12)],fill=GOLD)
        ax,ay=cx+r-16,cy-r+14
        self.draw.line([(ax-12,ay+12),(ax,ay)],fill=GOLD,width=3)
        self.draw.line([(ax-7,ay),(ax,ay)],fill=GOLD,width=3)
        self.draw.line([(ax,ay),(ax,ay+7)],fill=GOLD,width=3)

    def brand(self,y0):
        b=ar(BRAND["name"])
        self.draw.text((self.cx(b,self.f["brand"]),y0),b,font=self.f["brand"],fill=GOLD_L)
        s=ar(BRAND["sub"])
        self.draw.text((self.cx(s,self.f["sub"]),y0+90),s,font=self.f["sub"],fill=WHITE)

    def div(self,y):
        m=W//2
        self.draw.line([(PAD,y),(m-12,y)],fill=BORDER,width=1)
        self.draw.ellipse([(m-6,y-6),(m+6,y+6)],fill=GOLD)
        self.draw.line([(m+12,y),(W-PAD,y)],fill=BORDER,width=1)

    def stock(self,y0):
        name=_g(self.d,"stock_name","name")
        sym =_g(self.d,"stock_symbol","symbol")
        t   =ar(f"{name} - {sym}")
        f   =self.sf(t)
        tw  =self.tw(t,f)
        # صندوق مؤطر مثل الإشارة الذهبية
        # المربع بالعرض الكامل → النص متوسط داخله
        bx  = PAD
        bw  = W - PAD*2
        bh  = 66
        self.draw.rounded_rectangle(
            [(bx,y0),(bx+bw,y0+bh)], radius=0,
            fill=CARD
        )
        self._islamic_box(bx, y0, bx+bw, y0+bh)
        th = self.th(t,f)
        # توسيط أفقي وعمودي
        self.draw.text(((W-tw)//2, y0+(bh-th)//2), t, font=f, fill=WHITE)

    def icon(self,cx,cy,k):
        r=IR
        if k=="price":
            self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)],fill=CIRC,outline=GOLD,width=2)
            bw,bg=5,4; tbw=3*bw+2*bg; bx0=cx-tbw//2
            for i,bh in enumerate([10,14,18]):
                bx=bx0+i*(bw+bg)
                self.draw.rectangle([(bx,cy+9-bh),(bx+bw,cy+9)],fill=GOLD)
        elif k=="entry":
            self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)],fill=CIRC,outline=GOLD,width=2)
            self.draw.ellipse([(cx-12,cy-12),(cx+12,cy+12)],fill=None,outline=GOLD,width=1)
            self.draw.ellipse([(cx-5,cy-5),(cx+5,cy+5)],fill=GOLD)
        elif k=="target":
            self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)],fill=GREEN)
            self.draw.line([(cx-8,cy+2),(cx-3,cy+8)],fill=WHITE,width=3)
            self.draw.line([(cx-3,cy+8),(cx+9,cy-6)],fill=WHITE,width=3)
        elif k=="stop":
            self.draw.ellipse([(cx-r,cy-r),(cx+r,cy+r)],fill=RED)
            self.draw.line([(cx-7,cy-7),(cx+7,cy+7)],fill=WHITE,width=3)
            self.draw.line([(cx-7,cy+7),(cx+7,cy-7)],fill=WHITE,width=3)

    def row(self,label,value,bc,y,badge=None,ik="price"):
        rx1,rx2=PAD,W-PAD
        self.draw.rounded_rectangle([(rx1,y),(rx2,y+ROW_H)],radius=10,fill=CARD)
        self.draw.rounded_rectangle([(rx1,y),(rx1+5,y+ROW_H)],radius=3,fill=bc)

        cy  = y + ROW_H//2
        row_w = rx2 - rx1          # عرض الصف الكلي

        # ── تقسيم الصف إلى 3 أعمدة متساوية ──
        col = row_w // 3
        col1_cx = rx1 + col // 2              # مركز العمود الأيسر (شارة)
        col2_cx = rx1 + col + col // 2        # مركز العمود الأوسط (سعر)
        col3_cx = rx1 + col*2 + col // 2      # مركز العمود الأيمن (تسمية + أيقونة)

        # ── شارة النسبة (عمود أيسر) ──
        if badge:
            bcolor = GREEN if badge.startswith("+") else RED
            # نص فقط بدون أي إطار
            bth = self.tw(badge, self.f["bdg"])
            bt  = self.th(badge, self.f["bdg"])
            bx  = col1_cx - bth//2
            by  = cy - bt//2
            self.draw.text((bx, by), badge, font=self.f["bdg"], fill=bcolor)

        # ── السعر (عمود أوسط) ──
        vw = self.tw(value, self.f["val"])
        vh = self.th(value, self.f["val"])
        self.draw.text((col2_cx - vw//2, cy - vh//2), value, font=self.f["val"], fill=bc)

        # ── التسمية + الأيقونة (عمود أيمن) ──
        icx = rx1 + col*3 - IR - 8
        self.icon(icx, cy, ik)
        lbl = ar(label)
        lw  = self.tw(lbl, self.f["lbl"])
        lh  = self.th(lbl, self.f["lbl"])
        lx  = icx - IR - 8 - lw
        lc  = {"price":GRAY,"entry":GOLD_L,"target":GOLD_L,"stop":RED}[ik]
        self.draw.text((lx, cy - lh//2), lbl, font=self.f["lbl"], fill=lc)


    def metrics(self,y):
        d=self.d
        segs=[s for s in [
            f"RSI  {d.get('rsi','')}"                     if d.get('rsi')           else "",
            f"Vol  {d.get('volume_ratio','')}x"            if d.get('volume_ratio')  else "",
            f"Score  {d.get('score','')}"                  if d.get('score')         else "",
        ] if s]
        if not segs: return y
        self.draw.rounded_rectangle(
            [(PAD,y),(W-PAD,y+46)], radius=8,
            fill=CARD, outline=BORDER, width=1
        )
        sw=(W-PAD*2)//len(segs)
        for i,s in enumerate(segs):
            sx=PAD+i*sw
            tw=self.tw(s,self.f["top"])
            self.draw.text((sx+(sw-tw)//2, y+13), s, font=self.f["top"], fill=WHITE)
            if i<len(segs)-1:
                self.draw.line([(sx+sw,y+8),(sx+sw,y+38)],fill=BORDER,width=1)
        return y+56
    def rows(self,y0):
        d=self.d
        price=str(_g(d,"current_price","price",df="0"))
        entry=str(_g(d,"entry_point","entry",df="0"))
        t1=str(_g(d,"target1",df="")); t1p=_g(d,"target1_percent",df="")
        t2=str(_g(d,"target2",df="")); t2p=_g(d,"target2_percent",df="")
        sl=str(_g(d,"stop_loss",df="")); slp=_g(d,"stop_loss_percent",df="")
        def r(v): return f"{v} ريال"
        y=y0
        self.row("السعر الحالي:",r(price),GOLD,  y,ik="price"); y+=ROW_H+GAP
        self.row("نقطة الدخول:",r(entry),GOLD,  y,ik="entry"); y+=ROW_H+GAP
        self.row("الهدف الاول:", r(t1),  GREEN, y,badge=(f"+{t1p}%" if t1p else None),ik="target"); y+=ROW_H+GAP
        self.row("الهدف الثاني:",r(t2),  GREEN, y,badge=(f"+{t2p}%" if t2p else None),ik="target"); y+=ROW_H+GAP
        self.row("وقف الخسارة:",r(sl),  RED,   y,badge=(f"-{slp}%" if slp else None),ik="stop");   y+=ROW_H+GAP
        return y

    def reading(self,y,txt):
        if not txt: return y
        words=str(txt).split(); mw=W-PAD*2-20; lines,ln=[],""
        for w in words:
            t=f"{ln} {w}".strip()
            if self.tw(ar(t),self.f["rd"])<mw: ln=t
            else:
                if ln: lines.append(ln)
                ln=w
        if ln: lines.append(ln)
        lh=24; bh=len(lines)*lh+20
        self.draw.rounded_rectangle([(PAD,y),(W-PAD,y+bh)],radius=8,fill=CARD,outline=GOLD,width=1)
        ty=y+10
        for l in lines:
            dr=ar(l)
            self.draw.text(((W-self.tw(dr,self.f["rd"]))//2,ty),dr,font=self.f["rd"],fill=GRAY)
            ty+=lh
        return y+bh+10

    def footer(self,y):
        disc=ar("محتوى تعليمي وتحليلي فقط - لا يعد توصية استثمارية")
        self.draw.text(((W-self.tw(disc,self.f["ft"]))//2,y),disc,font=self.f["ft"],fill=GRAY)
        by=y+32; btn=BRAND["ch"]
        bw=self.tw(btn,self.f["btn"])+60; bx=(W-bw)//2
        self.draw.rounded_rectangle([(bx,by),(bx+bw,by+42)],radius=21,fill=BTN_BG,outline=GOLD,width=2)
        self.draw.text(((W-self.tw(btn,self.f["btn"]))//2,by+10),btn,font=self.f["btn"],fill=GOLD)

    def generate(self,inp,out):
        print("="*50); print("📊 راصد — مولّد الإشارة اليومية"); print("="*50)
        try: self.d=load(inp)
        except Exception as e: print(f"❌ {e}"); return False
        if not self.d: return False

        self.bg()
        self.topbar()

        # حساب المواضع Y بشكل مركزي
        self.logo(cy=128)
        self.brand(y0=212)    # الراصد + عنوان فرعي (y=240)
        self.div(y=336)       # خط فاصل مع مسافة بعد الراصد
        self.stock(y0=340)    # اسم السهم فوق الخط الثاني
        self.div(y=420)       # خط فاصل تحت اسم السهم → يفصله عن الصفوف
        y = self.rows(y0=438)
        y = self.metrics(y+10)
        rd=_g(self.d,"technical_reading","signal_reason","note")
        y = self.reading(y+8,rd)
        self.div(y+4)
        self.footer(y+18)

        p=Path(out); p.parent.mkdir(parents=True,exist_ok=True)
        self.img.save(p,"PNG",quality=95)
        print(f"✅ {p}"); return True


def main():
    base=Path(__file__).parent.parent
    inp=sys.argv[1] if len(sys.argv)>1 else str(base/"data/daily.json")
    out=sys.argv[2] if len(sys.argv)>2 else str(base/"output.png")
    sys.exit(0 if Post().generate(inp,out) else 1)

if __name__=="__main__": main()
