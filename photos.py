"""
Daily photo posts (pics) dono pages ke liye - videos/reels ke ilawa.
  - Islamic Motivational Videos : khoobsurat quote card (Quran/Hadith/naseehat) - scenery background
  - Hansi Ka Adda               : meme photo (mazahiya janwar ki tasveer + Urdu joke)
Har run mein har page par 1 photo. Workflow din mein 2 dafa chalta hai = rozana 2 pics per page.
Free: Gemini (free key) + Pixabay (free key) + ffmpeg. Koi naya secret nahi chahiye.

Env: GEMINI_API_KEY, PIXABAY_API_KEY, FB_PAGE_TOKEN, FB_PAGE_ID, FUNNY_PAGE_TOKEN, FUNNY_PAGE_ID
     SLOT (1 ya 2), PAGES ("islamic,funny"), DRY_RUN
"""
import os
import sys
import json
import time
import random
import datetime
import subprocess

import requests
from google import genai
from google.genai import types

import seo

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
SLOT = (os.environ.get("SLOT") or "1").strip()
PAGES_TO_RUN = [p.strip() for p in (os.environ.get("PAGES") or "islamic,funny").split(",") if p.strip()]
GRAPH_VER = "v23.0"
HISTORY_FILE = "photos_history.json"
REPORT_FILE = "photos_last_run.json"
WORK = "work_photos"
FONTS_DIR = os.path.abspath("fonts")
UR_FONT = "Noto Naskh Arabic"
EN_FONT = "Noto Sans"
W, H = 1080, 1350            # 4:5 - Facebook feed mein sab se bari jagah leta hai
MODEL_CANDIDATES = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"]

PAGES = {
    "islamic": {"name": "Islamic Motivational Videos",
                "token": os.environ.get("FB_PAGE_TOKEN"), "id": os.environ.get("FB_PAGE_ID")},
    "funny": {"name": "Hansi Ka Adda",
              "token": os.environ.get("FUNNY_PAGE_TOKEN"), "id": os.environ.get("FUNNY_PAGE_ID")},
    "frames": {"name": "Frames Of Life",
               "token": os.environ.get("FRAMES_PAGE_TOKEN"), "id": os.environ.get("FRAMES_PAGE_ID")},
}

FRAMES_KINDS = ["did-you-know fact about a country", "cost of living in a city (in local currency + PKR)",
                "visa / work tip (general, official sources only)", "best city to live for Pakistanis",
                "salary and jobs reality in a country", "culture or food fact", "country vs country comparison"]
FRAMES_PLACES = ["Saudi Arabia", "Dubai", "Qatar", "Oman", "Kuwait", "Bahrain", "Turkey", "Malaysia",
                 "United Kingdom", "Canada", "Australia", "Germany", "Italy", "Spain", "Japan",
                 "South Korea", "China", "New Zealand", "Ireland", "Portugal", "France", "Azerbaijan"]

ISLAMIC_KINDS = ["Quran verse", "authentic hadith", "short dua", "life lesson / naseehat",
                 "reminder about salah", "words of hope for a sad heart", "gratitude reminder",
                 "Friday (Jumuah) reminder"]
ISLAMIC_SCENES = ["mosque sunset", "desert dunes", "night sky stars", "mountain lake",
                  "ocean sunrise", "lantern", "green forest", "rain window", "clouds sky",
                  "flowers field", "kaaba", "quran book", "misty mountains", "minaret"]
ANIMALS = ["cat", "kitten", "dog", "puppy", "goat", "monkey", "duck", "parrot", "cow",
           "donkey", "owl", "panda", "squirrel", "camel", "sheep", "chicken", "frog", "hamster"]
FUNNY_TOPICS = ["school and exams", "ammi ki daant", "shaadi wale log", "office ka boss",
                "light ka jana (load shedding)", "biwi aur shohar", "Monday ki subah",
                "diet aur khana", "dost jo udhaar wapas nahi karta", "mehmaan aa gaye",
                "mobile ki battery", "neend aur alarm", "bachpan ki yaadein", "garmi", "cricket match"]

REPORT = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "slot": SLOT,
          "dry_run": DRY_RUN, "posted": {}, "errors": []}
os.makedirs(WORK, exist_ok=True)


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- Gemini
_client = None


def ask_json(prompt):
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_KEY)
    last = None
    for model in MODEL_CANDIDATES:
        for attempt in range(2):
            try:
                res = _client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=0.95))
                return json.loads(res.text)
            except Exception as e:
                last = e
                log(f"{model} try {attempt + 1} failed: {str(e)[:200]}")
                time.sleep(4)
    import groq_backup
    if groq_backup.enabled():
        log(f"Gemini fail ({str(last)[:80]}) - Groq backup try")
        try:
            return groq_backup.ask_json(prompt, 0.95, log)
        except Exception as e:
            last = f"{last} | {e}"
    raise RuntimeError(f"Gemini fail: {last}")


# ---------------------------------------------------------------- history
def load_history():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"islamic": [], "funny": [], "used_images": []}


def save_history(h):
    for k in ("islamic", "funny", "frames"):
        h[k] = h.get(k, [])[-300:]
    h["used_images"] = h.get("used_images", [])[-1500:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- background image
ISLAMIC_BLOCK = {"woman", "women", "girl", "girls", "lady", "female", "model", "yoga", "meditation", "fitness",
                 "workout", "exercise", "beauty", "fashion", "makeup", "bride", "couple", "romance", "kiss",
                 "church", "cathedral", "cross", "jesus", "temple", "hindu", "buddha", "buddhist", "statue",
                 "candle", "christmas", "wine", "bikini", "portrait", "face"}


def pixabay_image(queries, path, used, category=None, block=None):
    if not PIXABAY_KEY:
        return False
    for q in queries:
        try:
            params = {"key": PIXABAY_KEY, "q": q, "image_type": "photo", "safesearch": "true",
                      "per_page": 60, "min_width": 1000, "order": "popular"}
            if category:
                params["category"] = category
            r = requests.get("https://pixabay.com/api/", params=params, timeout=40)
            r.raise_for_status()
            hits = [x for x in r.json().get("hits", []) if x["id"] not in used
                    and not (block and block & set((x.get("tags") or "").lower().replace(",", " ").split()))]
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
    c = random.choice([("0x0b1a33", "0x1f4d7a"), ("0x10261a", "0x2f6b4a"),
                       ("0x2b1a33", "0x5b3d7a"), ("0x2a1c0c", "0x7a5a1f")])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"gradients=s={W}x{H}:c0={c[0]}:c1={c[1]}:d=1", "-frames:v", "1", path],
                   check=True)


# ---------------------------------------------------------------- rendering (ASS + ffmpeg)
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


def render(bg, ass_path, out, dark):
    """Background ko 1080x1350 crop, andhera karo, phir text jalao. 1 frame JPG."""
    fonts = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
    ass = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"drawbox=x=0:y=0:w=iw:h=ih:color=black@{dark}:t=fill,"
          f"ass='{ass}':fontsdir='{fonts}'")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", bg, "-t", "1",
                    "-vf", vf, "-frames:v", "1", "-q:v", "2", out], check=True)
    if os.path.getsize(out) < 30000:
        raise RuntimeError("tasveer theek nahi bani")


def fit_size(text, base, per_char, lo):
    return max(lo, int(base - max(0, len(text) - 60) * per_char))


# ---------------------------------------------------------------- Islamic quote card
def islamic_post(hist):
    lang = "en" if SLOT == "2" else "ur"
    kind = ISLAMIC_KINDS[len(hist["islamic"]) % len(ISLAMIC_KINDS)]
    used = [h["text"][:80] for h in hist["islamic"][-80:]]
    lang_rule = ("simple heart-touching URDU in Urdu script (not Roman), address reader as آپ, "
                 "write صلی اللہ علیہ وسلم after the Prophet's name"
                 if lang == "ur" else "clear, emotional English; write (PBUH) after the Prophet's name")
    d = ask_json(f"""Create one Facebook image post for the page "Islamic Motivational Videos".
Type: {kind}. Language: {lang_rule}.
Do NOT repeat these earlier posts: {json.dumps(used, ensure_ascii=False)}
Accuracy: only well known, authentic Quran verses / Sahih hadith, translated meaning only (no Arabic text).
Give the exact reference (e.g. Surah Al-Baqarah 2:286, Sahih Bukhari). If not 100% sure, write a
naseehat instead and leave reference empty. No politics, no sectarian topics, never invent quotes.
Return JSON:
{{"label": "2-3 word heading in the same language (e.g. قرآن کا پیغام / Hadith of the day)",
 "text": "the main quote, max 28 words",
 "reference": "source or empty",
 "scene": "one of: {', '.join(ISLAMIC_SCENES)}"}}""")
    text, ref, label = d["text"].strip(), (d.get("reference") or "").strip(), (d.get("label") or "").strip()
    font = UR_FONT if lang == "ur" else EN_FONT
    size = fit_size(text, 88 if lang == "ur" else 76, 0.4, 56)
    styles = "\n".join([
        f"Style: Label,{font},46,&H0050D7FF,&H0050D7FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,2,8,80,80,190,1",
        f"Style: Quote,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,3,5,95,95,0,1",
        f"Style: Ref,{font},42,&H0050D7FF,&H0050D7FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,2,2,80,80,250,1",
        "Style: Mark,Noto Sans,34,&H30FFFFFF,&H30FFFFFF,&H90000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,2,40,40,70,1",
    ])
    ev = [f"Dialogue: 0,0:00:00.00,0:00:05.00,Mark,,0,0,0,,{PAGES['islamic']['name']}"]
    if label:
        ev.append(f"Dialogue: 1,0:00:00.00,0:00:05.00,Label,,0,0,0,,{esc(label)}")
        ev.append("Dialogue: 1,0:00:00.00,0:00:05.00,Label,,0,0,0,,{\\pos(540,270)\\fs40}━━━  ✦  ━━━")
    ev.append(f"Dialogue: 2,0:00:00.00,0:00:05.00,Quote,,0,0,0,,{esc(text)}")
    if ref:
        ev.append(f"Dialogue: 1,0:00:00.00,0:00:05.00,Ref,,0,0,0,,— {esc(ref)}")
    ass = os.path.join(WORK, "islamic.ass")
    with open(ass, "w", encoding="utf-8") as f:
        f.write(ass_head(styles) + "\n".join(ev) + "\n")
    bg = os.path.join(WORK, "islamic_bg.jpg")
    scene = d.get("scene") or random.choice(ISLAMIC_SCENES)
    if not pixabay_image([scene, random.choice(ISLAMIC_SCENES), "mosque"], bg, hist["used_images"],
                         block=ISLAMIC_BLOCK):
        gradient_bg(bg)
    out = os.path.join(WORK, "islamic_post.jpg")
    render(bg, ass, out, 0.52)
    caption = seo.build(ask_json, "islamic", label or text[:60], f"{text} {ref}", lang, is_reel=True)
    return out, caption, {"lang": lang, "kind": kind, "text": text, "ref": ref}


# ---------------------------------------------------------------- Funny meme
def funny_post(hist):
    animal = ANIMALS[(len(hist["funny"]) * 5 + int(SLOT)) % len(ANIMALS)]
    topic = FUNNY_TOPICS[(len(hist["funny"]) * 3) % len(FUNNY_TOPICS)]
    bg = os.path.join(WORK, "funny_bg.jpg")
    if not pixabay_image([f"funny {animal}", animal, "funny animal"], bg, hist["used_images"], "animals"):
        gradient_bg(bg)
    used = [h["top"] + " / " + h["bottom"] for h in hist["funny"][-80:]]
    d = ask_json(f"""Write one viral Pakistani Urdu meme for a photo of a {animal} (the animal looks
like it is reacting). Page: "Hansi Ka Adda". Theme: {topic}.
Write in simple everyday Urdu script (not Roman), clean family-friendly desi humor. No religion,
no politics, no insults about any group, no vulgarity. Must be relatable and actually funny.
Do NOT repeat: {json.dumps(used, ensure_ascii=False)}
Return JSON:
{{"top": "setup line, max 12 words (e.g. جب امی کہیں بس پانچ منٹ میں آ رہی ہوں)",
 "bottom": "punchline / animal's reaction, max 10 words"}}""")
    top, bottom = d["top"].strip(), d["bottom"].strip()
    styles = "\n".join([
        f"Style: Top,{UR_FONT},{fit_size(top, 74, 0.6, 54)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,6,2,8,60,60,70,1",
        f"Style: Bottom,{UR_FONT},{fit_size(bottom, 80, 0.6, 58)},&H0000F0FF,&H0000F0FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,6,2,2,60,60,120,1",
        "Style: Mark,Noto Sans,34,&H30FFFFFF,&H30FFFFFF,&H90000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,2,40,40,40,1",
    ])
    ev = [f"Dialogue: 0,0:00:00.00,0:00:05.00,Mark,,0,0,0,,{PAGES['funny']['name']}",
          f"Dialogue: 1,0:00:00.00,0:00:05.00,Top,,0,0,0,,{esc(top)}",
          f"Dialogue: 1,0:00:00.00,0:00:05.00,Bottom,,0,0,0,,{esc(bottom)}"]
    ass = os.path.join(WORK, "funny.ass")
    with open(ass, "w", encoding="utf-8") as f:
        f.write(ass_head(styles) + "\n".join(ev) + "\n")
    out = os.path.join(WORK, "funny_post.jpg")
    render(bg, ass, out, 0.12)
    caption = seo.build(ask_json, "funny", top, f"{top} {bottom}", "ur", is_reel=True)
    return out, caption, {"animal": animal, "top": top, "bottom": bottom}


# ---------------------------------------------------------------- Frames Of Life info card
def frames_post(hist):
    h = hist.setdefault("frames", [])
    kind = FRAMES_KINDS[len(h) % len(FRAMES_KINDS)]
    place = FRAMES_PLACES[(len(h) * 7) % len(FRAMES_PLACES)]
    used = [x["text"][:80] for x in h[-80:]]
    d = ask_json(f"""Create one Facebook image post for the page "Frames Of Life" (life abroad for Pakistanis).
Type: {kind}. Place: {place}. Language: simple Urdu in Urdu script (not Roman), address reader as آپ.
Only true, well-known, general facts. Prices/salaries only as rough approximate ranges and say "تقریباً".
Never promise visas or jobs, no agents, no politics. Do NOT repeat: {json.dumps(used, ensure_ascii=False)}
Return JSON:
{{"label": "2-4 word Urdu heading (e.g. کیا آپ جانتے ہیں؟ / دبئی میں خرچہ)",
 "text": "the main info, max 30 words",
 "scene": "2-3 word English photo search for a famous real view of {place} (e.g. dubai skyline)"}}""")
    text, label = d["text"].strip(), (d.get("label") or "").strip()
    size = fit_size(text, 84, 0.4, 56)
    styles = "\n".join([
        f"Style: Label,{UR_FONT},54,&H0000D7FF,&H0000D7FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,2,8,80,80,170,1",
        f"Style: Quote,{UR_FONT},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,3,5,90,90,0,1",
        f"Style: Place,Noto Sans,48,&H0000D7FF,&H0000D7FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,2,2,80,80,240,1",
        "Style: Mark,Noto Sans,34,&H30FFFFFF,&H30FFFFFF,&H90000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,2,40,40,70,1",
    ])
    ev = [f"Dialogue: 0,0:00:00.00,0:00:05.00,Mark,,0,0,0,,{PAGES['frames']['name']}",
          f"Dialogue: 2,0:00:00.00,0:00:05.00,Quote,,0,0,0,,{esc(text)}",
          f"Dialogue: 1,0:00:00.00,0:00:05.00,Place,,0,0,0,,{esc(place).upper()}"]
    if label:
        ev.append(f"Dialogue: 1,0:00:00.00,0:00:05.00,Label,,0,0,0,,{esc(label)}")
    ass = os.path.join(WORK, "frames.ass")
    with open(ass, "w", encoding="utf-8") as f:
        f.write(ass_head(styles) + "\n".join(ev) + "\n")
    bg = os.path.join(WORK, "frames_bg.jpg")
    if not pixabay_image([d.get("scene") or place, f"{place} city", place], bg, hist["used_images"]):
        gradient_bg(bg)
    out = os.path.join(WORK, "frames_post.jpg")
    render(bg, ass, out, 0.5)
    caption = seo.build(ask_json, "frames", label or text[:60], f"{place}: {text}", "ur", is_reel=False)
    return out, caption, {"kind": kind, "place": place, "text": text}


# ---------------------------------------------------------------- Facebook
def post_photo(page, path, caption):
    P = PAGES[page]
    caption = caption.replace(" #reels", "").replace("#reels ", "")   # pic post hai, reel nahi
    if not P["token"] or not P["id"]:
        raise RuntimeError(f"{page}: page token/id secret missing")
    with open(path, "rb") as f:
        r = requests.post(f"https://graph.facebook.com/{GRAPH_VER}/{P['id']}/photos", timeout=180,
                          data={"access_token": P["token"], "message": caption, "published": "true"},
                          files={"source": ("post.jpg", f, "image/jpeg")})
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"Facebook error: {j['error'].get('message', j)}")
    log(f"{page}: photo posted {j.get('post_id') or j.get('id')}")
    return j.get("post_id") or j.get("id")


def main():
    hist = load_history()
    ok = 0
    for page in PAGES_TO_RUN:
        maker = {"islamic": islamic_post, "funny": funny_post, "frames": frames_post}[page]
        for attempt in range(2):
            try:
                path, caption, meta = maker(hist)
                log(f"--- {page} caption ---\n{caption}\n")
                meta["date"] = REPORT["time_utc"]
                if not DRY_RUN:
                    import slot_wait; slot_wait.wait(log)
                    meta["post_id"] = post_photo(page, path, caption)
                hist.setdefault(page, []).append(meta)
                REPORT["posted"][page] = meta.get("post_id", "dry_run")
                ok += 1
                break
            except Exception as e:
                log(f"{page} ERROR (try {attempt + 1}): {e}")
                if attempt == 1:
                    REPORT["errors"].append(f"{page}: {str(e)[:300]}")
                time.sleep(20)
    save_history(hist)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=1)
    if ok < len(PAGES_TO_RUN):
        sys.exit(1)
    log("Done!")


if __name__ == "__main__":
    main()
