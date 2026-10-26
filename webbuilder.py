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
REPORT_FILE = "webbuilder_last_run.json"
WORK = "work_webbuilder"
FONTS_DIR = os.path.abspath("fonts")
EN_FONT = "Noto Sans"
W, H = 1080, 1350            # 4:5 - Facebook feed mein sab se bari jagah

os.makedirs(WORK, exist_ok=True)

# ------------------------------------------------------------- promos
# Har promo: ek product. head = badi line, sub = neeche choti line,
# scene = background pic search words, tags = hashtags.
COUNTRY_CORE = "#UAE #SaudiArabia #Pakistan #Dubai"
POS_TAGS = (f"#RanaPOS #POS #PointOfSale #RetailSoftware #BillingSoftware "
            f"#InventorySoftware #SmallBusiness {COUNTRY_CORE} #Riyadh #Jeddah "
            f"#AbuDhabi #Karachi #Lahore")
WEB_TAGS = (f"#WebDesign #WebDevelopment #Website #BusinessWebsite #Ecommerce "
            f"#OnlineStore #SmallBusiness #Startup {COUNTRY_CORE} #London #USA "
            f"#Canada #Australia")
APP_TAGS = (f"#MobileApp #AndroidApp #AppDevelopment #BusinessApp #Startup "
            f"#SmallBusiness {COUNTRY_CORE} #USA #UK #Canada #Australia")

PROMOS = [
    {"focus": "pos", "label": "RANA POS",
     "head": "Run Your Shop the Smart Way",
     "sub": "Fast billing, live stock & inventory, and daily sales reports. Works offline - one-time price, no monthly fee.",
     "scene": ["retail shop counter", "grocery store", "cash register", "supermarket"],
     "tags": POS_TAGS},
    {"focus": "website", "label": "BUSINESS WEBSITE",
     "head": "Get Your Business Online",
     "sub": "A clean, fast, professional website that brings you more customers. Starting from $150.",
     "scene": ["laptop website", "web design office", "computer desk", "startup office"],
     "tags": WEB_TAGS},
    {"focus": "app", "label": "MOBILE APP",
     "head": "Your Business Needs an App",
     "sub": "Custom Android apps - delivery, order booking, owner dashboard. Built for your business.",
     "scene": ["smartphone app", "mobile phone hand", "delivery app", "mobile shopping"],
     "tags": APP_TAGS},
    {"focus": "store", "label": "ONLINE STORE",
     "head": "Start Selling Online",
     "sub": "A complete e-commerce store so customers can order from anywhere, anytime. Starting from $900.",
     "scene": ["online shopping", "ecommerce", "shopping cart laptop", "online payment"],
     "tags": WEB_TAGS},
]


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
    if not PIXABAY_KEY:
        return False
    for q in queries:
        try:
            r = requests.get("https://pixabay.com/api/", timeout=40, params={
                "key": PIXABAY_KEY, "q": q, "image_type": "photo", "safesearch": "true",
                "per_page": 60, "min_width": 1000, "order": "popular"})
            r.raise_for_status()
            hits = [x for x in r.json().get("hits", []) if x["id"] not in used]
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
                    log(f"Background: pixabay {x['id']} ({q})")
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


def render(bg, ass_path, out, dark):
    fonts = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
    ass = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"drawbox=x=0:y=0:w=iw:h=ih:color=black@{dark}:t=fill,"
          f"ass='{ass}':fontsdir='{fonts}'")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", bg, "-t", "1",
                    "-vf", vf, "-frames:v", "1", "-q:v", "2", out], check=True)
    if os.path.getsize(out) < 30000:
        raise RuntimeError("tasveer theek nahi bani")


def make_card(promo, used_images):
    """Promo card banata hai aur uska path deta hai."""
    GREEN = "&H007DC319"      # Web Builder accent green (BGR)
    WHITE = "&H00FFFFFF"
    LIGHT = "&H00EFEFEF"
    head_size = fit_size(promo["head"], 92, 1.1, 62)
    styles = "\n".join([
        # Mark (brand, top)
        f"Style: Mark,{EN_FONT},50,{GREEN},{GREEN},&H00000000,&H00000000,1,0,0,0,100,100,2,0,1,3,2,8,80,80,80,1",
        # Label (product, under mark)
        f"Style: Label,{EN_FONT},46,{WHITE},{WHITE},&H00000000,&H00000000,1,0,0,0,100,100,3,0,1,3,2,8,80,80,165,1",
        # Head (big headline)
        f"Style: Head,{EN_FONT},{head_size},{WHITE},{WHITE},&H00000000,&H90000000,1,0,0,0,100,100,0,0,1,4,3,8,90,90,430,1",
        # Sub (benefit line, wraps)
        f"Style: Sub,{EN_FONT},44,{LIGHT},{LIGHT},&H00000000,&H90000000,1,0,0,0,100,100,0,0,1,3,2,8,100,100,640,1",
        # Site (bottom)
        f"Style: Site,{EN_FONT},44,{GREEN},{GREEN},&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,2,2,80,80,165,1",
        # WhatsApp (bottom)
        f"Style: Wa,{EN_FONT},40,{WHITE},{WHITE},&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,2,2,80,80,90,1",
    ])
    ev = [
        f"Dialogue: 0,0:00:00.00,0:00:05.00,Mark,,0,0,0,,{esc(PAGE_NAME).upper()}",
        f"Dialogue: 1,0:00:00.00,0:00:05.00,Label,,0,0,0,,{esc(promo['label'])}",
        f"Dialogue: 2,0:00:00.00,0:00:05.00,Head,,0,0,0,,{esc(promo['head'])}",
        f"Dialogue: 2,0:00:00.00,0:00:05.00,Sub,,0,0,0,,{esc(promo['sub'])}",
        f"Dialogue: 3,0:00:00.00,0:00:05.00,Site,,0,0,0,,{esc(SITE.replace('https://', '').rstrip('/'))}",
        f"Dialogue: 3,0:00:00.00,0:00:05.00,Wa,,0,0,0,,WhatsApp: {esc(WA)}",
    ]
    ass = os.path.join(WORK, "wb.ass")
    with open(ass, "w", encoding="utf-8") as f:
        f.write(ass_head(styles) + "\n".join(ev) + "\n")
    bg = os.path.join(WORK, "wb_bg.jpg")
    if not pixabay_image(promo["scene"] + ["business"], bg, used_images):
        gradient_bg(bg)
    out = os.path.join(WORK, "wb_post.jpg")
    render(bg, ass, out, 0.6)
    return out


def build_caption(promo):
    return (
        f"{promo['head']} \U0001F680\n"
        f"{promo['sub']}\n\n"
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
    idx = len(hist.get("posts", [])) % len(PROMOS)
    return PROMOS[idx]


def main():
    hist = load_history()
    promo = pick_promo(hist)
    report = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
              "focus": promo["focus"], "dry_run": DRY_RUN, "post_id": None, "error": None}
    try:
        path = make_card(promo, hist.get("used_images", []))
        caption = build_caption(promo)
        log(f"--- Web Builder caption ({promo['focus']}) ---\n{caption}\n")
        if not DRY_RUN:
            report["post_id"] = post_photo(path, caption)
        else:
            report["post_id"] = "dry_run"
        hist.setdefault("posts", []).append(
            {"focus": promo["focus"], "date": report["time_utc"], "post_id": report["post_id"]})
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
