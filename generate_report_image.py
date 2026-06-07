import json, csv, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from datetime import datetime, date, timedelta, timezone

ASSETS = "assets"
W, H   = 1080, 1350

BG     = "#07101B"
CARD   = "#0A1828"
GOLD   = "#F0B429"
GOLD2  = "#C8900A"
GOLD3  = "#9A6E08"
GREEN  = "#22C55E"
RED    = "#EF4444"
BLUE   = "#3B82F6"
WHITE  = "#FFFFFF"
SILVER = "#94A3B8"
MUTED  = "#CBD5E1"
BORDER = "#1A3A55"

def F(s):  return ImageFont.truetype(f"{ASSETS}/Cairo-Bold.ttf",    s)
def FR(s): return ImageFont.truetype(f"{ASSETS}/Tajawal-Regular.ttf",s)
def FB(s): return ImageFont.truetype(f"{ASSETS}/Tajawal-Bold.ttf",   s)

LOG_FILE = "data/signals_log.csv"

def load_stats():
    KSA        = timezone(timedelta(hours=3))
    today      = datetime.now(KSA).date()
    days_since_sunday = (today.weekday() + 1) % 7
    week_start = today - timedelta(days=days_since_sunday)
    week_end   = week_start + timedelta(days=4)

    all_signals  = []
    week_signals = []

    try:
        with open(LOG_FILE, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                all_signals.append(row)
                try:
                    d = datetime.strptime(row["date"], "%Y-%m-%d").date()
                    if week_start <= d <= week_end:
                        week_signals.append(row)
                except:
                    pass
    except:
        pass

    wins   = len([s for s in all_signals if s.get("status") == "win"])
    losses = len([s for s in all_signals if s.get("status") == "loss"])
    open_s = len([s for s in all_signals if s.get("status") == "open"])
    closed = wins + losses
    success= round((wins / closed) * 100, 1) if closed > 0 else 0
    scores = [float(s.get("score",0)) for s in all_signals if s.get("score")]
    avg_sc = round(sum(scores)/len(scores),1) if scores else 0

    return {
        "total":        len(all_signals),
        "wins":         wins,
        "losses":       losses,
        "open":         open_s,
        "success_rate": success,
        "avg_score":    avg_sc,
        "week_signals": week_signals,
        "week_start":   week_start.strftime("%Y/%m/%d"),
        "week_end":     week_end.strftime("%Y/%m/%d"),
        "today":        today.strftime("%Y/%m/%d"),
    }

stats = load_stats()

img  = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

for y in range(H):
    t = y / H
    r = int(7  + (16-7)  * (1-t) * 0.4)
    g = int(16 + (30-16) * (1-t) * 0.4)
    b = int(27 + (52-27) * (1-t) * 0.4)
    draw.line([(0,y),(W,y)], fill=(r,g,b))

glow = Image.new("RGBA",(W,H),(0,0,0,0))
ImageDraw.Draw(glow).ellipse((200,-200,880,320),fill=(240,180,41,25))
glow = glow.filter(ImageFilter.GaussianBlur(80))
img  = Image.alpha_composite(img.convert("RGBA"),glow).convert("RGB")
draw = ImageDraw.Draw(img)

draw.rounded_rectangle((30,30,W-30,H-30),radius=46,fill=CARD,outline=GOLD2,width=3)

def corner(x,y,sx,sy,L=50):
    draw.line([(x,y),(x+sx*L,y)],fill=GOLD,width=4)
    draw.line([(x,y),(x,y+sy*L)],fill=GOLD,width=4)
    draw.ellipse((x-3,y-3,x+3,y+3),fill=GOLD)
M=30
corner(M,M,+1,+1); corner(W-M,M,-1,+1)
corner(M,H-M,+1,-1); corner(W-M,H-M,-1,-1)

LS=96; LX=W//2-LS//2; LY=56
try:
    logo=Image.open(f"{ASSETS}/logo.png").convert("RGBA")
    logo=logo.resize((LS,LS),Image.LANCZOS)
    mask=Image.new("L",(LS,LS),0)
    ImageDraw.Draw(mask).ellipse((0,0,LS,LS),fill=255)
    draw.ellipse((LX-6,LY-6,LX+LS+6,LY+LS+6),fill="#081422",outline=GOLD2,width=2)
    img.paste(logo,(LX,LY),mask)
    draw=ImageDraw.Draw(img)
except:
    pass

draw.text((W//2,192),"تقرير راصد الأسبوعي",
    fill=GOLD,font=F(50),anchor="mm",direction="rtl",language="ar")
draw.text((W//2,244),f"{stats['week_start']}  ←  {stats['week_end']}",
    fill=SILVER,font=FR(26),anchor="mm",direction="ltr")

def divider(y):
    draw.line([(160,y),(W//2-12,y)],fill=GOLD2,width=2)
    draw.line([(W//2+12,y),(W-160,y)],fill=GOLD2,width=2)
    draw.ellipse((W//2-7,y-7,W//2+7,y+7),fill=GOLD)

divider(278)

def stat_card(x, y, w, h, value, label, color):
    draw.rounded_rectangle((x,y,x+w,y+h),radius=22,fill=(10,22,40),outline=color,width=2)
    draw.text((x+w//2, y+h//2-16), str(value),
        fill=color, font=F(44), anchor="mm", direction="ltr")
    draw.text((x+w//2, y+h//2+26), label,
        fill=SILVER, font=FR(22), anchor="mm", direction="rtl", language="ar")

CW=218; CH=108; GAP=16
cx=(W-(4*CW+3*GAP))//2; cy=300
stat_card(cx,            cy, CW, CH, stats["total"],  "إجمالي الإشارات", GOLD)
stat_card(cx+CW+GAP,     cy, CW, CH, stats["wins"],   "رابحة",            GREEN)
stat_card(cx+2*(CW+GAP), cy, CW, CH, stats["losses"], "خاسرة",            RED)
stat_card(cx+3*(CW+GAP), cy, CW, CH, stats["open"],   "مفتوحة",           BLUE)

gy=cy+CH+22; card_h=168

draw.rounded_rectangle((80,gy,W//2-16,gy+card_h),radius=22,fill=(10,22,40),outline=GOLD2,width=1)
s_color=GREEN if stats["success_rate"]>=60 else GOLD if stats["success_rate"]>=40 else RED
cx_g=(80+W//2-16)//2; cy_g=gy+card_h//2; R=58
draw.ellipse((cx_g-R,cy_g-R,cx_g+R,cy_g+R),outline=BORDER,width=8)
if stats["success_rate"]>0:
    draw.arc((cx_g-R,cy_g-R,cx_g+R,cy_g+R),
        start=-90,end=-90+int(360*stats["success_rate"]/100),fill=s_color,width=8)
draw.text((cx_g,cy_g-14),f"{stats['success_rate']}%",
    fill=s_color,font=F(36),anchor="mm",direction="ltr")
draw.text((cx_g,cy_g+24),"نسبة النجاح",
    fill=SILVER,font=FR(22),anchor="mm",direction="rtl",language="ar")

draw.rounded_rectangle((W//2+16,gy,W-80,gy+card_h),radius=22,fill=(10,22,40),outline=GOLD2,width=1)
cx_s=(W//2+16+W-80)//2; cy_s=gy+card_h//2
sc_color=GREEN if stats["avg_score"]>=75 else GOLD if stats["avg_score"]>=55 else SILVER
draw.text((cx_s,cy_s-22),f"{stats['avg_score']}",
    fill=sc_color,font=F(46),anchor="mm",direction="ltr")
draw.text((cx_s,cy_s+18),"متوسط الـ Score",
    fill=SILVER,font=FR(22),anchor="mm",direction="rtl",language="ar")
bx=W//2+40; bw=W-120-bx; by=cy_s+50
draw.rounded_rectangle((bx,by,bx+bw,by+14),radius=7,fill=BORDER)
fw=int(bw*min(stats["avg_score"],100)/100)
if fw>0:
    draw.rounded_rectangle((bx,by,bx+fw,by+14),radius=7,fill=sc_color)
draw.text((cx_s,by+26),"/100",fill=BORDER,font=FR(18),anchor="mm",direction="ltr")

divider(gy+card_h+22)
sy=gy+card_h+44; MX=75

draw.text((W//2,sy),f"إشارات هذا الأسبوع  ({len(stats['week_signals'])})",
    fill=WHITE,font=F(34),anchor="mm",direction="rtl",language="ar")
sy+=42

if not stats["week_signals"]:
    draw.rounded_rectangle((MX,sy,W-MX,sy+70),radius=18,fill=(8,18,32),outline=BORDER,width=1)
    draw.text((W//2,sy+35),"لا توجد إشارات هذا الأسبوع",
        fill=SILVER,font=FR(26),anchor="mm",direction="rtl",language="ar")
    sy+=80
else:
    for sig in stats["week_signals"][:3]:
        status=sig.get("status","open")
        s_color=GREEN if status=="win" else RED if status=="loss" else BLUE
        s_icon ="✅" if status=="win" else "❌" if status=="loss" else "⏳"
        s_label="رابحة" if status=="win" else "خاسرة" if status=="loss" else "مفتوحة"
        draw.rounded_rectangle((MX,sy,W-MX,sy+86),radius=18,fill=(10,20,38),outline=s_color,width=1)
        draw.rounded_rectangle((MX,sy+10,MX+5,sy+76),radius=4,fill=s_color)
        draw.text((W-MX-20,sy+22),f"{sig.get('stock_name','')}  ({sig.get('symbol','')})",
            fill=WHITE,font=FB(26),anchor="rm",direction="rtl",language="ar")
        draw.text((W-MX-20,sy+54),
            f"دخول: {sig.get('entry','')}  |  هدف: {sig.get('target1','')}  |  وقف: {sig.get('stop_loss','')}",
            fill=SILVER,font=FR(21),anchor="rm",direction="rtl",language="ar")
        draw.text((MX+22,sy+30),s_icon,fill=s_color,font=F(24),anchor="lm")
        draw.text((MX+22,sy+58),s_label,fill=s_color,font=FB(20),anchor="lm",direction="rtl",language="ar")
        sy+=96

divider(sy+10); sy+=30
draw.rounded_rectangle((MX,sy,W-MX,sy+94),radius=18,fill=(6,13,24),outline=GOLD3,width=1)
draw.rounded_rectangle((MX,sy+12,MX+5,sy+82),radius=4,fill=GOLD2)
draw.text((W//2,sy+28),"نُصدر 3 إشارات أسبوعياً كحد أقصى",
    fill=WHITE,font=FB(24),anchor="mm",direction="rtl",language="ar")
draw.text((W//2,sy+62),"لا إشارة إلا عند توفر جميع شروط الجودة",
    fill=SILVER,font=FR(22),anchor="mm",direction="rtl",language="ar")

divider(H-78)
draw.text((W//2,H-56),"محتوى تعليمي وتحليلي فقط — لا يُعد توصية استثمارية",
    fill=SILVER,font=FR(22),anchor="mm",direction="rtl",language="ar")
pw=280
draw.rounded_rectangle((W//2-pw//2,H-30,W//2+pw//2,H-8),radius=18,fill=CARD,outline=GOLD2,width=2)
draw.text((W//2,H-19),"t.me/TASI_Smart",fill=GOLD,font=F(23),anchor="mm",direction="ltr")

img.save("data/weekly_report_card.png", quality=97)
print(f"✅ Weekly report image generated — {stats['week_start']} إلى {stats['week_end']}")
