"""
Web Builder page daily promo poster.
Rozana aapke "Web Builder" Facebook page (ID 61594549983462) par 1 promo photo
post karta hai - POS / Website / Mobile App / Online Store - har roz bari bari.
Caption English mein (worldwide clients ke liye), country hashtags ke sath;
POS wali post ke liye khaas #UAE #SaudiArabia #Pakistan. Har post mein aapki
website ka link + WhatsApp number.

Koi naya paid API nahi. Background pics free Pixabay se (na ho to gradient).
photos.py jaisa hi FB posting tareeqa, par alag page token.

Env (GitHub secrets):
  WB_PAGE_TOKEN, WB_PAGE_ID   -> Web Builder page ka apna token + id
  PIXABAY_API_KEY (optional)  -> background pics (na ho to plain gradient)
  FOCUS (optional)            -> pos|website|app|store (hath se test ke liye)
  DRY_RUN=1                   -> sirf pic banaye, post na kare
"""
import os
import sys
import json
import random
import datetime
import subprocess

import requests

# ------------------------------------------------------------- config
GRAPH_VER = "v23.0"
WB_TOKEN = os.environ.get("WB_PAGE_TOKEN")
WB_ID = os.environ.get("WB_PAGE_ID")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
FORCE_FOCUS = (os.environ.get("FOCUS") or "").strip().lower()

SITE = "https://client-hunt-six.vercel.app/"
WA = "+92 307 5267349"
PAGE_NAME = "Web Builder"

HISTORY_FILE = "webbuilder_history.json"
REPORT_FILE = f"webbuilder_{(os.environ.get('LANGUAGE') or 'en').strip().lower()}_last_run.json"
WORK = "work_webbuilder"
FONTS_DIR = os.path.abspath("fonts")
EN_FONT = "Noto Sans"
W, H = 1080, 1350            # 4:5 - Facebook feed mein sab se bari jagah

os.makedirs(WORK, exist_ok=True)

# ------------------------------------------------------------- promos
# Har promo: ek product. head = badi line, sub = neeche choti line,
# scene = background pic search words, tags = hashtags.
COUNTRY_CORE = "#UAE #SaudiArabia #Pakistan #Dubai"
# POS (phase 2): sab se zyada Saudi Arabia + UAE audience
POS_TAGS = ("#RanaPOS #POS #PointOfSale #CashierSystem #RetailSoftware #BillingSoftware "
            "#InventorySoftware #SaudiArabia #KSA #Riyadh #Jeddah #Dammam #Makkah "
            "#UAE #Dubai #AbuDhabi #Sharjah #Ajman")
AR_TAGS = {"pos": "#برنامج_كاشير #نظام_نقاط_البيع #برنامج_محاسبة #نقاط_البيع #السعودية #الرياض #جدة "
                  "#الدمام #مكة #الإمارات #دبي #الشارقة #أبوظبي #عجمان",
           "web": "#تصميم_مواقع #متجر_إلكتروني #تطبيقات_الجوال #تسويق_إلكتروني #السعودية #الرياض "
                  "#جدة #الإمارات #دبي #أبوظبي"}
WEB_TAGS = (f"#WebDesign #WebDevelopment #Website #BusinessWebsite #Ecommerce "
            f"#OnlineStore #SmallBusiness #Startup {COUNTRY_CORE} #London #USA "
            f"#Canada #Australia")
APP_TAGS = (f"#MobileApp #AndroidApp #AppDevelopment #BusinessApp #Startup "
            f"#SmallBusiness {COUNTRY_CORE} #USA #UK #Canada #Australia")

LANG = (os.environ.get("LANGUAGE") or "en").strip().lower()
if LANG not in ("en", "ur", "ar"):
    LANG = "en"
RTL = LANG in ("ur", "ar")      # Urdu aur Arabic dono daayen se baayen
UR_FONT = "Noto Naskh Arabic"

# Har promo = ek offer. Pic "ad" ki shakal mein: upar brand + headline, beech mein
# us cheez ki asal tasveer (POS machine / laptop website / phone app), neeche
# 3 fayde, qeemat ka badge, aur WhatsApp + website ki patti.
# img = sirf us cheez ki tasveer dhoondne wale words (tags mein inmein se koi lafz hona zaroori).
PROMOS = [
    {"focus": "pos", "tags": POS_TAGS,
     "img": ["pos terminal", "cash register", "barcode scanner", "point of sale", "checkout counter"],
     "en": {"label": "POS SOFTWARE", "head": "Run Your Shop the Smart Way",
            "points": ["Fast billing & barcode scanning", "Live stock & inventory control",
                       "Daily sales & profit reports"],
            "badge": "One-time price - No monthly fee",
            "for": "Shops - Supermarkets - Pharmacies - Restaurants",
            "where": "Saudi Arabia  |  UAE"},
     "ur": {"label": "POS سافٹ ویئر", "head": "اپنی دکان کو سمارٹ طریقے سے چلائیں",
            "points": ["تیز بلنگ اور بارکوڈ اسکیننگ", "لائیو اسٹاک اور انوینٹری کنٹرول",
                       "روزانہ سیل اور منافع کی رپورٹ"],
            "badge": "ایک بار قیمت - کوئی ماہانہ فیس نہیں",
            "for": "دکان، سپر مارکیٹ، فارمیسی، ریسٹورنٹ - ہر کاروبار کے لیے",
            "where": "سعودی عرب  |  یو اے ای  |  پاکستان"},
     "ar": {"label": "برنامج كاشير POS", "head": "أدر متجرك بطريقة ذكية",
            "points": ["فواتير سريعة ومسح الباركود", "متابعة المخزون لحظة بلحظة",
                       "تقارير المبيعات والأرباح اليومية"],
            "badge": "دفعة واحدة - بدون اشتراك شهري",
            "for": "للمحلات والسوبرماركت والصيدليات والمطاعم",
            "where": "السعودية  |  الإمارات"},
     "hi": "अपनी दुकान स्मार्ट तरीके से चलाएं - तेज़ बिलिंग, बारकोड, लाइव स्टॉक और रोज़ाना सेल रिपोर्ट। एक बार की कीमत, कोई मासिक फीस नहीं।"},
    {"focus": "website", "tags": WEB_TAGS,
     "img": ["website laptop", "web design", "responsive website", "laptop screen website", "website"],
     "en": {"label": "BUSINESS WEBSITE", "head": "Get Your Business Online",
            "points": ["Professional & mobile friendly", "Fast, clean & Google ready",
                       "Brings you more customers"],
            "badge": "Starting from $150",
            "for": "For every business - anywhere in the world", "where": ""},
     "ur": {"label": "بزنس ویب سائٹ", "head": "اپنے کاروبار کو آن لائن لائیں",
            "points": ["پروفیشنل اور موبائل فرینڈلی ویب سائٹ", "تیز، خوبصورت اور گوگل پر نظر آنے والی",
                       "زیادہ گاہک، زیادہ سیل"],
            "badge": "صرف 150 ڈالر سے شروع",
            "for": "ہر کاروبار کے لیے - دنیا میں کہیں بھی", "where": ""},
     "ar": {"label": "موقع إلكتروني", "head": "انقل نشاطك التجاري إلى الإنترنت",
            "points": ["تصميم احترافي يناسب الجوال", "سريع وجاهز لمحركات البحث",
                       "يجلب لك عملاء أكثر"],
            "badge": "يبدأ من 150 دولار",
            "for": "لكل الأنشطة التجارية - في أي مكان", "where": ""},
     "hi": "अपने बिज़नेस को ऑनलाइन लाएं - प्रोफेशनल, मोबाइल फ्रेंडली वेबसाइट जो ज़्यादा ग्राहक लाए। सिर्फ $150 से शुरू।"},
    {"focus": "app", "tags": APP_TAGS,
     "img": ["smartphone app", "mobile app", "phone screen app", "smartphone hand", "mobile phone"],
     "en": {"label": "MOBILE APP", "head": "Your Business Needs an App",
            "points": ["Online ordering & delivery", "Bookings & customer accounts",
                       "Owner dashboard on your phone"],
            "badge": "Custom Android apps",
            "for": "Restaurants - Shops - Clinics - Schools & more", "where": ""},
     "ur": {"label": "موبائل ایپ", "head": "آپ کے کاروبار کی اپنی موبائل ایپ",
            "points": ["آن لائن آرڈر اور ڈیلیوری", "بکنگ اور کسٹمر اکاؤنٹس",
                       "مالک کے لیے موبائل ڈیش بورڈ"],
            "badge": "ہر کاروبار کے لیے کسٹم ایپ",
            "for": "ریسٹورنٹ، دکان، کلینک، اسکول اور بہت کچھ", "where": ""},
     "ar": {"label": "تطبيق جوال", "head": "نشاطك يحتاج تطبيقا خاصا",
            "points": ["طلبات أونلاين وتوصيل", "حجوزات وحسابات العملاء",
                       "لوحة تحكم للمالك على جوالك"],
            "badge": "تطبيقات أندرويد حسب الطلب",
            "for": "مطاعم، محلات، عيادات، مدارس والمزيد", "where": ""},
     "hi": "आपके बिज़नेस का अपना मोबाइल ऐप - ऑनलाइन ऑर्डर, डिलीवरी, बुकिंग और मालिक के लिए डैशबोर्ड।"},
    {"focus": "store", "tags": WEB_TAGS,
     "img": ["online shopping", "ecommerce", "shopping cart laptop", "online store", "online payment"],
     "en": {"label": "ONLINE STORE", "head": "Start Selling Online",
            "points": ["Customers order 24/7", "Cart, payments & delivery",
                       "Easy product management"],
            "badge": "Starting from $900",
            "for": "Sell to customers anywhere, anytime", "where": ""},
     "ur": {"label": "آن لائن اسٹور", "head": "آن لائن سیل شروع کریں",
            "points": ["گاہک 24 گھنٹے آرڈر کریں", "کارٹ، پیمنٹ اور ڈیلیوری",
                       "پروڈکٹس آسانی سے شامل کریں"],
            "badge": "صرف 900 ڈالر سے شروع",
            "for": "گاہک کہیں سے بھی، کبھی بھی خریدیں", "where": ""},
     "ar": {"label": "متجر إلكتروني", "head": "ابدأ البيع أونلاين",
            "points": ["عملاؤك يطلبون على مدار الساعة", "سلة ودفع وتوصيل",
                       "إدارة سهلة للمنتجات"],
            "badge": "يبدأ من 900 دولار",
            "for": "بع لعملائك في أي مكان وأي وقت", "where": ""},
     "hi": "ऑनलाइन सेल शुरू करें - ग्राहक 24 घंटे ऑर्डर करें, कार्ट, पेमेंट और डिलीवरी सब शामिल। सिर्फ $900 से शुरू।"},
]

IMG_BLOCK = {"woman", "women", "girl", "lady", "female", "model", "sexy", "bikini", "lingerie",
             "kiss", "couple", "romance", "fashion", "beauty", "makeup", "wine", "beer", "alcohol",
             "party", "christmas", "halloween", "church"}


def log(msg):
    print(msg, flush=True)


# ------------------------------------------------------------- history
def load_history():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"posts": [], "used_images": []}


def save_history(h):
    h["posts"] = h.get("posts", [])[-300:]
    h["used_images"] = h.get("used_images", [])[-1500:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


# ------------------------------------------------------------- background
def pixabay_image(queries, path, used):
    """Sirf wo tasveer jiske tags mein query ka koi lafz ho (yani wohi cheez dikhe)."""
    if not PIXABAY_KEY:
        return False
    for q in queries:
        qw = [w for w in q.lower().split() if len(w) > 2]
        try:
            r = requests.get("https://pixabay.com/api/", timeout=40, params={
                "key": PIXABAY_KEY, "q": q, "image_type": "photo", "safesearch": "true",
                "orientation": "horizontal", "per_page": 80, "min_width": 1200, "order": "popular"})
            r.raise_for_status()
            hits = []
            for x in r.json().get("hits", []):
                tags = {t.strip().lower() for t in x.get("tags", "").split(",")}
                words = set(" ".join(tags).split())
                if x["id"] in used or words & IMG_BLOCK:
                    continue
                if qw and not any(w in words for w in qw):
                    continue
                hits.append(x)
        except Exception as e:
            log(f"Pixabay error ({q}): {str(e)[:150]}")
            continue
        random.shuffle(hits)
        for x in hits[:6]:
            url = x.get("largeImageURL") or x.get("webformatURL")
            try:
                data = requests.get(url, timeout=90).content
                if len(data) > 40000:
                    with open(path, "wb") as f:
                        f.write(data)
                    used.append(x["id"])
                    log(f"Product pic: pixabay {x['id']} ({q}) tags={x.get('tags')}")
                    return True
            except Exception as e:
                log(f"Image download fail: {str(e)[:120]}")
    return False


def gradient_bg(path):
    c = random.choice([("0x071b14", "0x0f5a3f"), ("0x0b1a33", "0x15603f"),
                       ("0x06231a", "0x0a7a5a"), ("0x0a1f14", "0x12805a")])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"gradients=s={W}x{H}:c0={c[0]}:c1={c[1]}:d=1", "-frames:v", "1", path],
                   check=True)


# ------------------------------------------------------------- rendering
def esc(s):
    return (s or "").replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def ass_head(styles):
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{styles}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def fit_size(text, base, per_char, lo):
    return max(lo, int(base - max(0, len(text) - 24) * per_char))


# Layout (1080x1350):  brand + label | headline | product pic (badge) | 3 points | for-line | CTA patti
PIC_X, PIC_Y, PIC_W, PIC_H = 70, 335, 940, 520
LABEL_Y = 112
BADGE_R, BADGE_Y = W - PIC_X - PIC_W + 30, PIC_Y + 26


def text_w(text, ur, size):
    """ASS text ki andaazan chaurai (px) - dabba us ke hisaab se."""
    try:
        from PIL import ImageFont
        path = os.path.join(FONTS_DIR, "NotoNaskhArabic-Bold.ttf" if ur else "NotoSans-Bold.ttf")
        f100 = ImageFont.truetype(path, 100)
        a, d = f100.getmetrics()
        f = ImageFont.truetype(path, max(8, int(round(100 * size / (a + d)))))
        w = f.getlength(text)
        if ur:
            w *= 0.9            # jurre hue huroof alag likhe huroof se kuch tang hote hain
        return int(w)
    except Exception:
        return int(len(text) * size * 0.55)


def latin(text, size):
    """Urdu line ke andar English lafz (POS waghera) Noto Sans mein, sahi size par."""
    import re
    return re.sub(r"[A-Za-z][A-Za-z0-9]*", lambda m: "{\\fn" + EN_FONT + "\\fs" + str(size) + "}"
                  + m.group(0) + "{\\r}", text)


def rect(style, x, y, w, h):
    return (f"Dialogue: 0,0:00:00.00,0:00:05.00,{style},,0,0,0,,"
            f"{{\\pos({x},{y})\\p1}}m 0 0 l {w} 0 l {w} {h} l 0 {h}{{\\p0}}")


def render(photo, ass_path, out):
    fonts = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
    ass = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
    fc = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"boxblur=22:2,drawbox=x=0:y=0:w=iw:h=ih:color=0x04140e@0.78:t=fill[bg];"
          f"[0:v]scale={PIC_W}:{PIC_H}:force_original_aspect_ratio=increase,crop={PIC_W}:{PIC_H},"
          f"pad={PIC_W + 12}:{PIC_H + 12}:6:6:color=0x19C37D[pic];"
          f"[bg][pic]overlay={PIC_X - 6}:{PIC_Y - 6},ass='{ass}':fontsdir='{fonts}'[v]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", photo, "-t", "1",
                    "-filter_complex", fc, "-map", "[v]", "-frames:v", "1", "-q:v", "2", out],
                   check=True)
    if os.path.getsize(out) < 30000:
        raise RuntimeError("tasveer theek nahi bani")


def make_card(promo, used_images):
    """Ad jaisi promo pic banata hai (LANG = en/ur) aur uska path deta hai."""
    t = promo[LANG]
    ur = RTL
    F = UR_FONT if ur else EN_FONT
    GREEN = "&H007DC319"      # Web Builder green (BGR)
    YELLOW = "&H0000C8FF"
    WHITE = "&H00FFFFFF"
    DARK = "&H00140E04"
    LIGHT = "&H00E6E6E6"
    k = 1.4 if ur else 1.0      # Naskh font apni line-height ki wajah se chhota dikhta hai
    sz = lambda n: int(n * k)
    head_size = fit_size(t["head"], 84, 1.2, 60) if not ur else 100
    # Urdu: right-aligned (7=left, 9=right top)
    side = 9 if ur else 7
    styles = "\n".join([
        f"Style: Mark,{EN_FONT},46,{GREEN},{GREEN},&H00000000,&H00000000,1,0,0,0,100,100,3,0,1,2,1,8,60,60,42,1",
        # label pill (BorderStyle 3 = rang wala dabba)
        f"Style: Label,{F},{sz(38)},{DARK},{DARK},&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,8,60,60,{LABEL_Y},1",
        f"Style: Head,{F},{head_size},{WHITE},{WHITE},&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,3,8,60,60,190,1",
        # price badge, pic ke upar kone mein
        f"Style: Badge,{F},{sz(40)},{DARK},{DARK},&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,9,{BADGE_R},{BADGE_R},{BADGE_Y},1",
        f"Style: Point,{F},{sz(44)},{WHITE},{WHITE},&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,{side},95,95,0,1",
        f"Style: For,{F},{sz(34)},{LIGHT},{LIGHT},&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,1,8,60,60,1112,1",
        f"Style: Where,{F},{sz(36)},{YELLOW},{YELLOW},&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,1,8,60,60,1158,1",
        f"Style: Bar,{EN_FONT},10,{GREEN},{GREEN},{GREEN},{GREEN},0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        f"Style: BoxY,{EN_FONT},10,{YELLOW},{YELLOW},{YELLOW},{YELLOW},0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        f"Style: Cta,{F},{sz(40)},{DARK},{DARK},&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,2,40,40,72,1",
        f"Style: Site,{EN_FONT},36,{DARK},{DARK},&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,2,40,40,24,1",
    ])
    T = "0:00:00.00,0:00:05.00"
    ev = [
        f"Dialogue: 0,{T},Mark,,0,0,0,,{esc(PAGE_NAME).upper()}",
        f"Dialogue: 1,{T},Label,,0,0,0,,{latin(esc(t['label']), 38) if ur else esc(t['label'])}",
        f"Dialogue: 2,{T},Head,,0,0,0,,{esc(t['head'])}",
        f"Dialogue: 3,{T},Badge,,0,0,0,,{esc(t['badge'])}",
    ]
    # label (green) aur badge (yellow) ke dabbe - text ki chaurai naap kar
    lw = text_w(t["label"], ur, sz(38)) + 44
    ev.append(rect("Bar", (W - lw) // 2, LABEL_Y - 8, lw, sz(38) + 18))
    bw = text_w(t["badge"], ur, sz(40)) + 40
    ev.append(rect("BoxY", W - BADGE_R - bw + 20, BADGE_Y - 10, bw, sz(40) + 22))
    y = PIC_Y + PIC_H + (30 if ur else 40)
    dot = "{\\fn" + EN_FONT + "\\c" + GREEN + "\\fs54}\u2022{\\r}"
    for p in t["points"]:
        line = f"{esc(p)}  {dot}" if ur else f"{dot}  {esc(p)}"
        ev.append(f"Dialogue: 2,{T},Point,,0,0,{y},,{line}")
        y += 68 if ur else 66
    y += 4
    ev.append(f"Dialogue: 2,{T},For,,0,0,{y},,{esc(t['for'])}")
    if t.get("where"):
        ev.append(f"Dialogue: 2,{T},Where,,0,0,{y + (52 if ur else 46)},,{esc(t['where'])}")
    # CTA patti (green dabba neeche)
    bar_y = H - 140
    ev.append(f"Dialogue: 1,{T},Bar,,0,0,0,,{{\\pos(0,{bar_y})\\p1}}m 0 0 l {W} 0 l {W} 140 l 0 140{{\\p0}}")
    if LANG == "ar":
        cta = f"تواصل معنا واتساب  {{\\fn{EN_FONT}\\fs42}}{esc(WA)}"
    elif ur:
        cta = f"ابھی واٹس ایپ کریں  {{\\fn{EN_FONT}\\fs42}}{esc(WA)}"
    else:
        cta = f"WhatsApp now: {esc(WA)}"
    ev.append(f"Dialogue: 3,{T},Cta,,0,0,0,,{cta}")
    ev.append(f"Dialogue: 3,{T},Site,,0,0,0,,{esc(SITE.replace('https://', '').rstrip('/'))}")
    ass = os.path.join(WORK, "wb.ass")
    with open(ass, "w", encoding="utf-8") as f:
        f.write(ass_head(styles) + "\n".join(ev) + "\n")
    photo = os.path.join(WORK, "wb_photo.jpg")
    if not pixabay_image(promo["img"], photo, used_images):
        gradient_bg(photo)
    out = os.path.join(WORK, "wb_post.jpg")
    render(photo, ass, out)
    return out


def build_caption(promo):
    t = promo[LANG]
    pts = "\n".join(f"✅ {p}" for p in t["points"])
    if LANG == "ar":
        ar_tags = AR_TAGS["pos" if promo["focus"] == "pos" else "web"]
        return (
            f"{t['head']} \U0001F680\n{pts}\n\U0001F4B0 {t['badge']}\n{t['for']}\n\n"
            f"✅ عمل احترافي بسعر مناسب وتسليم سريع.\n"
            f"\U0001F4AC شاهد أعمالنا واطلب السعر: {SITE}\n"
            f"\U0001F4F1 واتساب: {WA}\n\n"
            f"{ar_tags} {promo['tags']}"
        )
    if LANG == "ur":
        return (
            f"{t['head']} \U0001F680\n{pts}\n\U0001F4B0 {t['badge']}\n{t['for']}\n\n"
            f"{promo['hi']}\n\n"
            f"\U0001F4AC نمونے دیکھیں اور قیمت پوچھیں: {SITE}\n"
            f"\U0001F4F1 WhatsApp: {WA}\n\n"
            f"{promo['tags']} #Urdu #Hindi #UrduHindi"
        )
    return (
        f"{t['head']} \U0001F680\n{pts}\n\U0001F4B0 {t['badge']}\n{t['for']}\n\n"
        f"✅ Affordable, professional work - delivered fast.\n"
        f"\U0001F4AC See examples & get a price: {SITE}\n"
        f"\U0001F4F1 WhatsApp: {WA}\n\n"
        f"{promo['tags']}"
    )


# ------------------------------------------------------------- Facebook
def post_photo(path, caption):
    if not WB_TOKEN or not WB_ID:
        raise RuntimeError("WB_PAGE_TOKEN ya WB_PAGE_ID secret missing hai")
    with open(path, "rb") as f:
        r = requests.post(f"https://graph.facebook.com/{GRAPH_VER}/{WB_ID}/photos", timeout=180,
                          data={"access_token": WB_TOKEN, "message": caption, "published": "true"},
                          files={"source": ("post.jpg", f, "image/jpeg")})
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"Facebook error: {j['error'].get('message', j)}")
    pid = j.get("post_id") or j.get("id")
    log(f"Web Builder: photo posted {pid}")
    return pid


def pick_promo(hist):
    if FORCE_FOCUS:
        for p in PROMOS:
            if p["focus"] == FORCE_FOCUS:
                return p
    # har zubaan apni baari se chare products ghumaye (aaj Urdu POS, English website ... )
    n = sum(1 for p in hist.get("posts", []) if p.get("lang", "en") == LANG)
    if LANG == "ar":
        # Arabic (Saudi/UAE) - har doosra din POS
        order = ["pos", "website", "pos", "app", "pos", "store"]
        want = order[n % len(order)]
        return next(p for p in PROMOS if p["focus"] == want)
    off = 0 if LANG == "en" else 2
    return PROMOS[(n + off) % len(PROMOS)]


def main():
    hist = load_history()
    promo = pick_promo(hist)
    report = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
              "focus": promo["focus"], "lang": LANG, "dry_run": DRY_RUN, "post_id": None, "error": None}
    try:
        path = make_card(promo, hist.get("used_images", []))
        caption = build_caption(promo)
        log(f"--- Web Builder caption ({promo['focus']} / {LANG}) ---\n{caption}\n")
        if not DRY_RUN:
            report["post_id"] = post_photo(path, caption)
        else:
            report["post_id"] = "dry_run"
        hist.setdefault("posts", []).append(
            {"focus": promo["focus"], "lang": LANG, "date": report["time_utc"], "post_id": report["post_id"]})
    except Exception as e:
        log(f"Web Builder ERROR: {e}")
        report["error"] = str(e)[:300]
    save_history(hist)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    if report["error"]:
        sys.exit(1)
    log("Done!")


if __name__ == "__main__":
    main()
