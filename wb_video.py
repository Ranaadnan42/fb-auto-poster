"""
Web Builder page - promo VIDEOS (rozana 2 long + 2 short: English aur Urdu/Hindi).

Har video mein bataya jata hai ke hum kya offer karte hain: Website, Mobile App, POS Software -
har qisam ke business ke liye (restaurant, dukaan, pharmacy, salon, school, clinic ...).
- English video: poori dunya ke clients ke liye.
- Urdu video: aasaan Urdu/Hindi (Hindustani) boli - Pakistan aur India dono samjhein.
  Subtitles Roman mein (Urdu aur Hindi dono parhne wale parh sakein), caption Urdu + Hindi dono mein.
- Hashtags: POS ke liye khaas Saudi Arabia, UAE, Pakistan; Website / App ke liye poori dunya.

Env:
  WB_PAGE_TOKEN, WB_PAGE_ID, PIXABAY_API_KEY, GEMINI_API_KEY (GROQ_API_KEY backup)
  LANGUAGE = en | ur        KIND = reel | long        DRY_RUN=1 -> sirf video banaye
"""
import os
import sys
import json
import time
import random
import asyncio
import datetime
import subprocess

import requests

GRAPH_VER = "v23.0"
WB_TOKEN = os.environ.get("WB_PAGE_TOKEN")
WB_ID = os.environ.get("WB_PAGE_ID")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
LANG = "ur" if (os.environ.get("LANGUAGE") or "en").strip().lower() == "ur" else "en"
LONG = (os.environ.get("KIND") or "reel").strip().lower() == "long"

SITE = "https://client-hunt-six.vercel.app/"
SITE_SHORT = SITE.replace("https://", "").rstrip("/")
WA = "+92 307 5267349"
PAGE_NAME = "Web Builder"
HISTORY_FILE = "webbuilder_video_history.json"
REPORT_FILE = f"webbuilder_video_{LANG}_{'long' if LONG else 'reel'}_last_run.json"
WORK = os.path.abspath(f"work_wbv_{LANG}_{'long' if LONG else 'reel'}")
FONTS_DIR = os.path.abspath("fonts")
FONT = "Noto Sans"
W, H = (1920, 1080) if LONG else (1080, 1920)
MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"]
VOICE = {"en": ("en-US-GuyNeural", "+0%"), "ur": ("ur-PK-AsadNeural", "-2%")}[LANG]

# Har video mein ek business "spotlight" - bari bari, taake har business wale ko lage ye mere liye hai
BUSINESSES = ["restaurant", "grocery store", "pharmacy", "clothing shop", "beauty salon", "school",
              "clinic", "mobile phone shop", "bakery", "hardware store", "cafe", "supermarket",
              "electronics shop", "real estate agency", "gym", "car workshop", "furniture store",
              "wholesale distributor", "jewellery shop", "travel agency"]

# Asal facts - AI inhi se baat kare, apni taraf se qeemat/wade na banaye
FACTS = """- Business website: clean, fast, professional, mobile friendly, brings more customers. Starting from $150.
- Online store (e-commerce): customers order from anywhere, anytime. Starting from $900.
- Mobile app: custom Android apps - online ordering, delivery, booking, owner dashboard.
- POS software (Rana POS): fast billing, barcode, live stock & inventory, daily sales & profit reports,
  works offline, one-time price with no monthly fee. Used by shops in Saudi Arabia, UAE and Pakistan.
- Made for EVERY business: restaurant, grocery, pharmacy, clothing, salon, school, clinic, bakery,
  mobile shop, supermarket, wholesale and more.
- Contact: WhatsApp +92 307 5267349, website client-hunt-six.vercel.app"""

POS_TAGS = "#POS #POSSoftware #BillingSoftware #SaudiArabia #UAE #Pakistan #Dubai #Riyadh #Jeddah #Karachi #Lahore"
WORLD_TAGS = ("#WebDesign #Website #MobileApp #AppDevelopment #SmallBusiness #Ecommerce "
              "#USA #UK #Canada #Australia #Germany #India")

BLOCK = {"bikini", "sexy", "lingerie", "kiss", "kissing", "party", "nightclub", "wine", "beer",
         "alcohol", "church", "temple", "cross", "halloween", "christmas"}

os.makedirs(WORK, exist_ok=True)
REPORT = {"lang": LANG, "kind": "long" if LONG else "reel", "clips": 0, "fallback": 0, "errors": []}
USED = set()


def log(m):
    print(m, flush=True)


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} fail: {r.stderr[-600:]}")
    return r.stdout


def duration(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", p]).strip())


def load_history():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            h = json.load(f)
            return h if isinstance(h, list) else []     # list - taake saath chalne wale runs merge ho sakein
    except Exception:
        return []


# ------------------------------------------------------------- script
def ask_json(prompt):
    last = None
    if GEMINI_KEY:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_KEY)
        for model in MODELS:
            for attempt in range(2):
                try:
                    res = client.models.generate_content(
                        model=model, contents=prompt,
                        config=types.GenerateContentConfig(response_mime_type="application/json",
                                                           temperature=0.9))
                    log(f"Gemini model: {model}")
                    return json.loads(res.text)
                except Exception as e:
                    last = e
                    log(f"{model} try {attempt + 1}: {str(e)[:160]}")
                    time.sleep(4)
    import groq_backup
    if groq_backup.enabled():
        return groq_backup.ask_json(prompt, 0.9, log)
    raise RuntimeError(f"AI fail: {last}")


def write_script(spot, used_titles):
    if LONG:
        shape = ("about 2 minutes 30 seconds spoken (about 330 words), exactly 12 scenes: 1 hook, 1 the problem "
                 "businesses face without these tools, 2 about the WEBSITE / online store, 2 about the MOBILE APP, "
                 "3 about the POS SOFTWARE, 2 showing it works for every business (name many business types, "
                 f"with a short example for a {spot}), 1 final call to action with WhatsApp number and website")
    else:
        shape = ("about 45 seconds spoken (about 105 words), exactly 6 scenes: 1 hook, 1 WEBSITE, 1 MOBILE APP, "
                 f"1 POS SOFTWARE, 1 'for every business' naming many types (spotlight a {spot}), "
                 "1 call to action with WhatsApp number and website")
    if LANG == "en":
        lang_rule = ("Narration in clear, friendly, confident ENGLISH for business owners worldwide. "
                     "Give 'text' only.")
        lang_fields = ('"caption": "3-4 line English Facebook caption that sells, ends with WhatsApp + website"')
    else:
        lang_rule = ("Narration in very simple everyday HINDUSTANI (the shared spoken language of Urdu and Hindi) "
                     "so BOTH Pakistani and Indian viewers fully understand: use common words like dukaan, "
                     "business, customer, order, hisaab, website, app, software, bill; avoid heavy Persian/Arabic "
                     "or Sanskrit words. Address the viewer respectfully as 'aap'. For each scene give "
                     "'text' = the narration in URDU SCRIPT (for the voice) and 'roman' = the SAME words in "
                     "Roman letters (on-screen subtitles that Urdu and Hindi readers can both read). "
                     "Say the WhatsApp number digit by digit.")
        lang_fields = ('"caption_ur": "3 line caption in Urdu script", '
                       '"caption_hi": "the same caption in Hindi (Devanagari script)"')
    data = ask_json(f"""You make a promo video for the Facebook page "{PAGE_NAME}" - a team that builds
websites, mobile apps and POS software for businesses. Length: {shape}.
{lang_rule}
Use ONLY these facts (never invent prices, discounts, guarantees or clients):
{FACTS}
Make it exciting and persuasive like a professional ad: first line is a scroll-stopping hook,
talk about real benefits (more customers, no wrong bills, know daily profit, sell online).
Past video titles (make this one fresh and different): {json.dumps(used_titles[-30:], ensure_ascii=False)}

For each scene also give:
 "label": 1-3 word ENGLISH on-screen heading (e.g. "WEBSITE", "MOBILE APP", "POS SOFTWARE", "EVERY BUSINESS"),
 "visual": 1-3 word ENGLISH stock-video search term showing EXACTLY what this scene talks about
   (e.g. "laptop website", "smartphone app", "cash register", "restaurant kitchen", "grocery store", "pharmacy").

Return JSON: {{"title": "short catchy title (in the video language)",
 "scenes": [{{"text": "...", {'"roman": "...", ' if LANG == 'ur' else ''}"label": "...", "visual": "..."}}],
 {lang_fields}}}""")
    scenes = [s for s in data.get("scenes", []) if (s.get("text") or "").strip()]
    if len(scenes) < (8 if LONG else 4):
        raise RuntimeError("script mein scenes kam hain")
    data["scenes"] = scenes
    return data


FALLBACK = {
    "en": [("Is your business still missing customers online?", "YOUR BUSINESS", "small business owner"),
           ("We build fast, professional websites that bring you new customers, starting from 150 dollars.",
            "WEBSITE", "laptop website"),
           ("Get your own mobile app for orders, delivery and bookings.", "MOBILE APP", "smartphone app"),
           ("Our POS software gives fast billing, live stock and daily profit reports, with no monthly fee.",
            "POS SOFTWARE", "cash register"),
           ("Restaurant, grocery, pharmacy, salon, school or clinic, we build it for every business.",
            "EVERY BUSINESS", "shop owner"),
           (f"Message us on WhatsApp today, plus 92 307 5267349, or visit our website.", "CONTACT US",
            "phone message")],
    "ur": [("کیا آپ کا بزنس ابھی بھی آن لائن کسٹمر کھو رہا ہے؟", "Kya aap ka business abhi bhi online customer kho raha hai?",
            "YOUR BUSINESS", "small business owner"),
           ("ہم آپ کے بزنس کی خوبصورت اور تیز ویب سائٹ بناتے ہیں، جو نئے کسٹمر لاتی ہے۔",
            "Hum aap ke business ki khoobsurat aur tez website banate hain, jo naye customer laati hai.",
            "WEBSITE", "laptop website"),
           ("آرڈر، ڈیلیوری اور بکنگ کے لیے آپ کی اپنی موبائل ایپ۔",
            "Order, delivery aur booking ke liye aap ki apni mobile app.", "MOBILE APP", "smartphone app"),
           ("ہمارا پی او ایس سافٹ ویئر: تیز بل، اسٹاک کا پورا حساب اور روز کا منافع، کوئی ماہانہ فیس نہیں۔",
            "Hamara POS software: tez bill, stock ka poora hisaab aur roz ka munafa, koi mahana fees nahi.",
            "POS SOFTWARE", "cash register"),
           ("ریسٹورنٹ ہو، کریانہ، فارمیسی، سیلون، اسکول یا کلینک، ہر بزنس کے لیے۔",
            "Restaurant ho, kiryana, pharmacy, salon, school ya clinic, har business ke liye.",
            "EVERY BUSINESS", "shop owner"),
           ("ابھی واٹس ایپ کریں: صفر تین صفر سات، پانچ دو چھ سات، تین چار نو۔",
            "Abhi WhatsApp karein: 0307 5267349", "CONTACT US", "phone message")],
}


def fallback_script():
    sc = []
    for row in FALLBACK[LANG]:
        if LANG == "en":
            sc.append({"text": row[0], "label": row[1], "visual": row[2]})
        else:
            sc.append({"text": row[0], "roman": row[1], "label": row[2], "visual": row[3]})
    return {"title": "Website, App & POS for Every Business", "scenes": sc,
            "caption": "Website, mobile app and POS software for every business.",
            "caption_ur": "ہر بزنس کے لیے ویب سائٹ، موبائل ایپ اور پی او ایس سافٹ ویئر",
            "caption_hi": "हर बिज़नेस के लिए वेबसाइट, मोबाइल ऐप और POS सॉफ्टवेयर"}


# ------------------------------------------------------------- voice + music
def tts(text, path):
    import edge_tts

    async def go():
        await edge_tts.Communicate(text, VOICE[0], rate=VOICE[1]).save(path)
    for attempt in range(6):
        try:
            asyncio.run(go())
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            log(f"TTS retry {attempt + 1}: {str(e)[:150]}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("awaaz nahi bani")


def make_music(path, secs):
    root = random.choice([130.8, 146.8, 164.8])
    parts = []
    for k, ch in enumerate([[1, 1.25, 1.5], [0.84, 1.0, 1.26], [0.89, 1.12, 1.33], [0.75, 0.94, 1.12]]):
        env = f"(0.5+0.5*sin(2*PI*t/16-{k}*PI/2))"
        parts += [f"0.05*sin(2*PI*{root * m:.2f}*t)*{env}" for m in ch]
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc='{'+'.join(parts)}':s=44100:d={secs + 1:.1f}",
         "-af", f"lowpass=f=2200,afade=t=in:d=2,afade=t=out:st={max(secs - 3, 1):.1f}:d=3",
         "-ac", "2", "-c:a", "aac", "-b:a", "128k", path])


# ------------------------------------------------------------- clips
def pixabay_clips(query, count, prefix):
    got = []
    if not PIXABAY_KEY:
        return got
    for q in (query, "business office", "laptop", "smartphone"):
        if len(got) >= count:
            break
        try:
            r = requests.get("https://pixabay.com/api/videos/", timeout=40, params={
                "key": PIXABAY_KEY, "q": q, "safesearch": "true", "per_page": 40, "video_type": "film"})
            r.raise_for_status()
            qw = [w for w in q.lower().split() if len(w) > 2]
            hits = []
            for h in r.json().get("hits", []):
                tags = (h.get("tags") or "").lower()
                words = set(tags.replace(",", " ").split())
                if h["id"] in USED or words & BLOCK or (qw and not any(w in tags for w in qw)):
                    continue
                hits.append(h)
        except Exception as e:
            log(f"Pixabay error ({q}): {str(e)[:150]}")
            continue
        random.shuffle(hits)
        if not LONG:   # reel ke liye khari (vertical) clips pehle
            hits.sort(key=lambda h: 0 if h.get("videos", {}).get("medium", {}).get("height", 0)
                      > h.get("videos", {}).get("medium", {}).get("width", 1) else 1)
        for h in hits:
            if len(got) >= count:
                break
            v = h.get("videos", {})
            pick = next((v[s] for s in ("large", "medium")
                         if v.get(s, {}).get("url") and max(v[s].get("width", 0), v[s].get("height", 0)) >= 1280),
                        None)
            if not pick:
                continue
            path = os.path.join(WORK, f"{prefix}_{len(got)}.mp4")
            try:
                with requests.get(pick["url"], stream=True, timeout=180) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as f:
                        for chunk in resp.iter_content(1 << 20):
                            f.write(chunk)
                if os.path.getsize(path) > 50000:
                    USED.add(h["id"])
                    got.append(path)
            except Exception as e:
                log(f"clip download fail: {str(e)[:120]}")
    return got


def fallback_clip(path):
    c = random.choice([("0x071b14", "0x0f5a3f"), ("0x0b1a33", "0x15603f"), ("0x06231a", "0x0a7a5a")])
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"gradients=s={W}x{H}:c0={c[0]}:c1={c[1]}:speed=0.01:d=15",
         "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", path])


# ------------------------------------------------------------- overlay text
def ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def esc(s):
    return (s or "").replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def make_ass(path, sub_text, label, dur):
    v = H > W
    GREEN, WHITE = "&H007DC319", "&H00FFFFFF"
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Brand,{FONT},{58 if v else 50},{GREEN},{GREEN},&H00000000,&H00000000,1,0,0,0,100,100,3,0,1,4,2,8,60,60,{150 if v else 40},1
Style: Label,{FONT},{92 if v else 78},{WHITE},{WHITE},&H00000000,&H64000000,1,0,0,0,100,100,2,0,1,5,3,8,60,60,{250 if v else 110},1
Style: Sub,{FONT},{64 if v else 56},{WHITE},{WHITE},&H70000000,&H70000000,1,0,0,0,100,100,0,0,3,14,0,2,80,80,{560 if v else 170},1
Style: Contact,{FONT},{44 if v else 38},{GREEN},{GREEN},&H00000000,&H90000000,1,0,0,0,100,100,0,0,1,3,2,2,40,40,{330 if v else 50},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = [f"Dialogue: 0,{ass_time(0)},{ass_time(dur + 1)},Brand,,0,0,0,,{PAGE_NAME.upper()}",
          f"Dialogue: 0,{ass_time(0)},{ass_time(dur + 1)},Contact,,0,0,0,,WhatsApp {WA}  |  {SITE_SHORT}"]
    if label:
        ev.append(f"Dialogue: 1,{ass_time(0)},{ass_time(dur)},Label,,0,0,0,,{{\\fad(300,300)}}{esc(label).upper()}")
    words = sub_text.split()
    n = 5 if v else 8
    chunks = [" ".join(words[i:i + n]) for i in range(0, len(words), n)]
    weights = [len(c) + 3 for c in chunks]
    scale = dur / max(sum(weights), 1)
    t = 0.0
    for c, wgt in zip(chunks, weights):
        ev.append(f"Dialogue: 2,{ass_time(t)},{ass_time(t + wgt * scale)},Sub,,0,0,0,,{esc(c)}")
        t += wgt * scale
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(ev) + "\n")


# ------------------------------------------------------------- build
def build_scene(i, sc):
    audio = f"a{i}.mp3"
    tts(sc["text"].strip(), os.path.join(WORK, audio))
    dur = duration(os.path.join(WORK, audio)) + 0.35
    k = max(1, min(3, round(dur / 5)))                 # har ~5 sec naya clip
    clips = pixabay_clips(sc.get("visual") or "business", k, f"c{i}")
    REPORT["clips"] += len(clips)
    if not clips:
        REPORT["fallback"] += 1
        fb = os.path.join(WORK, f"c{i}_fb.mp4")
        fallback_clip(fb)
        clips = [fb]
    k = len(clips)
    seg = dur / k
    sub = (sc.get("roman") or sc["text"]) if LANG == "ur" else sc["text"]
    make_ass(os.path.join(WORK, f"s{i}.ass"), sub, sc.get("label"), dur - 0.35)
    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd += ["-stream_loop", "-1", "-t", f"{seg + 0.2:.2f}", "-i", os.path.basename(c)]
    cmd += ["-i", audio]
    fd = min(0.4, seg / 4)
    chains = [f"[{j}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1,"
              f"trim=duration={seg:.2f},setpts=PTS-STARTPTS,fade=t=in:st=0:d={fd:.2f},"
              f"fade=t=out:st={seg - fd:.2f}:d={fd:.2f}[v{j}]" for j in range(k)]
    fontsdir = f":fontsdir={FONTS_DIR}" if os.path.isdir(FONTS_DIR) else ""
    chains.append("".join(f"[v{j}]" for j in range(k)) +
                  f"concat=n={k}:v=1:a=0,eq=brightness=-0.10:saturation=1.1,"
                  f"subtitles=s{i}.ass{fontsdir},format=yuv420p[v]")
    cmd += ["-filter_complex", ";".join(chains), "-map", "[v]", "-map", f"{k}:a:0", "-af", "apad",
            "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", f"p{i}.mp4"]
    run(cmd, cwd=WORK)
    return f"p{i}.mp4"


def build_video(script):
    parts = []
    for i, sc in enumerate(script["scenes"]):
        parts.append(build_scene(i, sc))
        log(f"scene {i + 1}/{len(script['scenes'])} ready")
    with open(os.path.join(WORK, "list.txt"), "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "joined.mp4"], cwd=WORK)
    total = duration(os.path.join(WORK, "joined.mp4"))
    make_music(os.path.join(WORK, "music.m4a"), total)
    out = os.path.join(WORK, "final.mp4")
    run(["ffmpeg", "-y", "-i", "joined.mp4", "-i", "music.m4a", "-filter_complex",
         "[1:a]volume=0.25[m];[0:a][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", out], cwd=WORK)
    REPORT["seconds"] = round(duration(out), 1)
    log(f"Video ready: {REPORT['seconds']} sec")
    return out


def caption(script):
    contact = f"\U0001F4AC WhatsApp: {WA}\n\U0001F310 {SITE}"
    tags = f"{POS_TAGS} {WORLD_TAGS}"
    if LANG == "en":
        body = script.get("caption") or script.get("title", "")
        return f"{body}\n\n{contact}\n\n{tags}"
    ur = script.get("caption_ur") or ""
    hi = script.get("caption_hi") or ""
    return f"{ur}\n\n{hi}\n\n{contact}\n\n{tags} #UrduHindi #Hindi #Urdu"


# ------------------------------------------------------------- Facebook
def fb_json(r):
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"Facebook jawab samajh nahi aaya: {r.text[:300]}")
    if "error" in j:
        raise RuntimeError(f"Facebook error: {j['error'].get('message', j)}")
    return j


def post_reel(path, desc):
    base = f"https://graph.facebook.com/{GRAPH_VER}/{WB_ID}/video_reels"
    vid = fb_json(requests.post(base, data={"upload_phase": "start", "access_token": WB_TOKEN},
                                timeout=60))["video_id"]
    with open(path, "rb") as f:
        fb_json(requests.post(f"https://rupload.facebook.com/video-upload/{GRAPH_VER}/{vid}",
                              headers={"Authorization": f"OAuth {WB_TOKEN}", "offset": "0",
                                       "file_size": str(os.path.getsize(path))}, data=f, timeout=1800))
    fb_json(requests.post(base, timeout=60, data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": desc, "access_token": WB_TOKEN}))
    return vid


def post_long(path, title, desc):
    with open(path, "rb") as f:
        j = fb_json(requests.post(f"https://graph-video.facebook.com/{GRAPH_VER}/{WB_ID}/videos",
                                  timeout=1800, data={"access_token": WB_TOKEN, "title": title,
                                                      "description": desc, "published": "true"},
                                  files={"source": ("video.mp4", f, "video/mp4")}))
    return j.get("id")


def main():
    vids = load_history()
    spot = BUSINESSES[len(vids) % len(BUSINESSES)]
    report = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "spotlight": spot,
              "post_id": None, "error": None}
    try:
        try:
            script = write_script(spot, [v.get("title", "") for v in vids])
        except Exception as e:
            log(f"AI script fail, fixed script: {e}")
            REPORT["errors"].append(f"script: {str(e)[:200]}")
            script = fallback_script()
        path = build_video(script)
        cap = caption(script)
        log(f"--- caption ---\n{cap}\n")
        if DRY_RUN:
            report["post_id"] = "dry_run"
        else:
            if not WB_TOKEN or not WB_ID:
                raise RuntimeError("WB_PAGE_TOKEN ya WB_PAGE_ID secret missing")
            report["post_id"] = post_long(path, script.get("title", PAGE_NAME), cap) if LONG \
                else post_reel(path, cap)
            log(f"Posted: {report['post_id']}")
        vids.append({"date": report["time_utc"], "lang": LANG, "kind": REPORT["kind"],
                     "title": script.get("title", ""), "spotlight": spot, "post_id": report["post_id"]})
    except Exception as e:
        log(f"ERROR: {e}")
        report["error"] = str(e)[:300]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(vids[-300:], f, ensure_ascii=False, indent=1)
    report.update(REPORT)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    if report["error"]:
        sys.exit(1)
    log("Done!")


if __name__ == "__main__":
    main()
