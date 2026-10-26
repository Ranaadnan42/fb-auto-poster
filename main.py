"""
Islamic Motivational Videos - Auto Poster (GitHub Actions)

Har run (LANGUAGE=ur ya en):
 1. Gemini naya topic chunta hai (pichle titles history.json se repeat nahi hote)
 2. Lambi video (~5 min, 1920x1080) aur reel (~50 sec, 1080x1920) ki script
 3. Edge TTS awaaz (Urdu: ur-PK-AsadNeural, English: en-US-ChristopherNeural)
 4. Har scene mein 2-3 alag Pixabay clips, fade ke saath
 5. Sunehra title, subtitles (box ke saath), page watermark, halka vignette
 6. Dono Facebook page par post

Secrets: GEMINI_API_KEY, PIXABAY_API_KEY, FB_PAGE_ACCESS_TOKEN, FB_PAGE_ID
DRY_RUN=1 -> video banegi, post nahi hogi.
"""
import os
import sys
import json
import time
import random
import asyncio
import shutil
import datetime
import subprocess

import requests
import edge_tts
from google import genai
from google.genai import types

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY")
FB_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
FB_PAGE = os.environ.get("FB_PAGE_ID")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
LANG = (os.environ.get("LANGUAGE") or "ur").strip().lower()
if LANG not in ("ur", "en"):
    LANG = "ur"
# English content sirf YouTube par jata hai - FB page, Instagram aur TikTok par nahi.
# (Ye page/TikTok Urdu audience ke liye hain; English sirf YouTube ke liye.)
YT_ONLY = (LANG == "en")
# is run mein kya post ho: both / long / reel (schedule se workflow batata hai)
POST_TYPE = (os.environ.get("POST_TYPE") or "both").strip().lower()
if POST_TYPE not in ("both", "long", "reel"):
    POST_TYPE = "both"
DO_LONG = POST_TYPE in ("both", "long")
DO_REEL = POST_TYPE in ("both", "reel")

PAGE_NAME = "Islamic Motivational Videos"
GRAPH_VER = "v23.0"
HISTORY_FILE = "history.json"
WORK = "work"
FONTS_DIR = os.path.abspath("fonts")
MODEL_CANDIDATES = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"]

LANGS = {
    "ur": {
        "voice": "ur-PK-AsadNeural", "rate": "-4%", "font": "Noto Naskh Arabic",
        "long_words": 850, "long_min": 700, "long_max": 1000, "reel_words": 130,
        "line_long": 6, "line_reel": 4,
        "write_in": ("simple, heart-touching spoken Pakistani URDU written in Urdu script "
                     "(not Roman Urdu). Use common words people speak daily; Islamic terms "
                     "like Allah, Sabr, Dua, Jannat are fine. Always address the viewer respectfully "
                     "as آپ (never تم or تو). After the Prophet's name write "
                     "صلی اللہ علیہ وسلم"),
        "follow": "آخر میں کہیں: پیج Islamic Motivational Videos کو فالو کریں اور یہ ویڈیو شیئر کریں",
        "reel_end": "آخر میں کہیں: ایسی مزید ویڈیوز کے لیے فالو کریں",
        "caption_lang": "Urdu (Urdu script)",
    },
    "en": {
        "voice": "en-US-ChristopherNeural", "rate": "-5%", "font": "Noto Sans",
        "long_words": 800, "long_min": 680, "long_max": 950, "reel_words": 120,
        "line_long": 7, "line_reel": 4,
        "write_in": ("clear, emotional spoken ENGLISH for a worldwide Muslim audience. "
                     "Say 'peace be upon him' after the Prophet's name"),
        "follow": "End by asking viewers to follow the page 'Islamic Motivational Videos' and share the video.",
        "reel_end": "End with: Follow for more reminders.",
        "caption_lang": "English",
    },
}
L = LANGS[LANG]

THEMES = [
    "patience (sabr) in hardship", "gratitude (shukr)", "trusting Allah (tawakkul)",
    "the mercy and forgiveness of Allah", "the power of dua", "the value of salah",
    "lessons from the life of Prophet Muhammad", "stories of the prophets mentioned in the Quran",
    "stories of the Sahaba", "reflection on a Quran verse", "death, the grave and the hereafter",
    "repentance (tawbah) and second chances", "kindness to parents", "good character and manners",
    "controlling anger", "the value of time", "finding peace in remembering Allah (dhikr)",
    "Islamic history and the golden age", "charity (sadaqah)", "humility and avoiding arrogance",
    "hope after sadness", "the night prayer (tahajjud)", "Jannah and how to reach it",
    "honesty and trust (amanah)", "rizq (provision) comes from Allah",
]

SAFE_VISUALS = ("Visual terms must be Islamic or calm scenery only. Prefer Islamic: mosque, "
                "mosque interior, minaret, mosque dome, mecca, medina, quran, prayer mat, "
                "ramadan lantern, crescent moon, islamic architecture, arabic calligraphy. "
                "Or scenery: sky, clouds, sunrise, sunset, ocean, rain, desert, mountains, "
                "night stars, forest, river. Never people or faces, never church, temple, "
                "cross, candle or statue.")

# Pronunciation: a text-to-speech voice reads the narration, so Arabic/foreign words get mispronounced.
SAY_RULE = ("PRONUNCIATION: a text-to-speech voice reads 'text', so Arabic and other foreign words come out "
            "wrong. For every scene also give a 'say' field: the SAME narration as 'text' but with ONLY the "
            "hard Arabic/foreign words respelled phonetically so the voice says them correctly "
            "(e.g. Bismillah -> 'Biss-mil-lah', Alhamdulillah -> 'Al-ham-du-lil-lah', InshaAllah -> "
            "'In-sha-Allah', SubhanAllah -> 'Sub-haan-Allah', Surah -> 'Soo-rah', Taqwa -> 'Tuq-waa'). "
            "Respell in the SAME language/script as 'text'. Keep every other word identical to 'text'. "
            "If a scene has no hard word, omit 'say'.")

# Har scene mein aadhe clips inn mein se (masjid waghera zyada dikhein)
ISLAMIC_VISUALS = ["mosque", "mosque interior", "minaret", "mosque dome", "mecca", "medina",
                   "quran", "prayer mat", "ramadan lantern", "crescent moon",
                   "islamic architecture", "arabic calligraphy", "mosque sunset"]

# Inn tags wale clips kabhi nahi lagenge (ghair-Islami ibadat gahen / cheezein)
BLOCK_TAGS = {"church", "cathedral", "chapel", "christian", "christianity", "cross", "crucifix",
              "jesus", "christ", "mary", "bible", "priest", "nun", "pope", "vatican", "basilica",
              "monastery", "abbey", "rosary", "christmas", "easter", "temple", "hindu", "buddha",
              "buddhist", "buddhism", "monk", "pagoda", "shrine", "idol", "statue", "sculpture",
              "synagogue", "jewish", "menorah", "shiva", "ganesh", "krishna", "diwali", "halloween",
              "gothic", "angel", "saint", "candle", "candles", "altar", "wine", "beer", "alcohol",
              "bikini", "party", "nightclub", "dance", "dancing", "pig", "pork"}


def clip_blocked(hit):
    tags = [t.strip().lower() for t in (hit.get("tags") or "").split(",")]
    words = {w for t in tags for w in t.split()}
    return bool(words & BLOCK_TAGS)

RULES = """Accuracy rules (very important):
- Only mention Quran verses and hadith that are well known and authentic; name the surah or the
  collection (e.g. Sahih Bukhari) in plain words. If unsure, do not quote - just give the lesson.
- Never invent stories, numbers or quotes. Respectful, hopeful, sincere tone.
- No politics, no sectarian topics, no music talk.
- Spoken plain sentences only: no emojis, no headings, no stage directions, no symbols."""

os.makedirs(WORK, exist_ok=True)
REPORT = {"lang": LANG, "stock_clips": 0, "fallback_clips": 0, "errors": []}
USED_CLIPS = set()


def log(msg):
    print(f"[{datetime.datetime.utcnow():%H:%M:%S}] {msg}", flush=True)


def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError("FFmpeg error: " + p.stderr.decode("utf-8", "ignore")[-1500:])
    return p.stdout.decode("utf-8", "ignore")


def duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", path]).strip())


# ---------------------------------------------------------------- history
def load_history():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(h):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h[-600:], f, ensure_ascii=False, indent=1)


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
                        response_mime_type="application/json", temperature=0.9))
                data = json.loads(res.text)
                log(f"Gemini model: {model}")
                return data
            except Exception as e:
                last = e
                log(f"{model} try {attempt + 1} failed: {str(e)[:200]}")
                time.sleep(4)
    raise RuntimeError(f"Gemini fail: {last}")


# har theme ke search seeds: (English, Urdu script, Roman Urdu) - YouTube suggestions ke liye
THEME_SEEDS = {
    "patience (sabr) in hardship": ("patience in islam", "صبر", "sabr"),
    "gratitude (shukr)": ("gratitude in islam", "شکر", "shukar"),
    "trusting Allah (tawakkul)": ("trust in allah", "اللہ پر بھروسہ", "tawakkul"),
    "the mercy and forgiveness of Allah": ("allah forgives", "اللہ کی رحمت", "allah ki rehmat"),
    "the power of dua": ("power of dua", "دعا", "dua qabool"),
    "the value of salah": ("importance of salah", "نماز", "namaz ki ahmiyat"),
    "lessons from the life of Prophet Muhammad": ("prophet muhammad story", "نبی کریم کا واقعہ", "nabi ka waqia"),
    "stories of the prophets mentioned in the Quran": ("prophet stories", "انبیاء کے واقعات", "hazrat ka waqia"),
    "stories of the Sahaba": ("sahaba stories", "صحابہ کے واقعات", "sahaba ka waqia"),
    "reflection on a Quran verse": ("quran verse", "قرآن کی آیت", "quran ki ayat"),
    "death, the grave and the hereafter": ("life after death islam", "قبر", "qabar ka azab"),
    "repentance (tawbah) and second chances": ("tawbah", "توبہ", "tauba"),
    "kindness to parents": ("parents in islam", "والدین", "maa baap"),
    "good character and manners": ("good character islam", "اخلاق", "achay akhlaq"),
    "controlling anger": ("anger in islam", "غصہ", "gussa"),
    "the value of time": ("value of time islam", "وقت کی قدر", "waqt ki qadar"),
    "finding peace in remembering Allah (dhikr)": ("dhikr for peace", "ذکر", "dil ka sukoon"),
    "Islamic history and the golden age": ("islamic history", "اسلامی تاریخ", "islami tareekh"),
    "charity (sadaqah)": ("sadaqah", "صدقہ", "sadqa"),
    "humility and avoiding arrogance": ("arrogance in islam", "تکبر", "aajzi"),
    "hope after sadness": ("islamic reminder sadness", "اداسی", "mayoosi"),
    "the night prayer (tahajjud)": ("tahajjud", "تہجد", "tahajjud ki fazilat"),
    "Jannah and how to reach it": ("jannah", "جنت", "jannat"),
    "honesty and trust (amanah)": ("honesty in islam", "ایمانداری", "amanat"),
    "rizq (provision) comes from Allah": ("rizq", "رزق", "rizq mein barkat"),
}
PICK_EXTRA = {}   # search phrase / mauqa - history aur description ke liye


def _occasion_today(history):
    """Mauqe ki video har zabaan mein din mein sirf ek - baqi videos evergreen rahein."""
    try:
        import search_demand
        occ = search_demand.islamic_occasion()
    except Exception as e:
        log(f"occasion check fail: {e}")
        return None
    if not occ:
        return None
    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
    for h in history:
        if h.get("lang") == LANG and h.get("occasion") == occ[0] and h.get("pk_day") == today:
            return None
    return occ


def _search_phrases(theme, occ):
    try:
        import search_demand
        if occ:
            en_seeds, ur_seeds = occ[2], occ[3]
        else:
            s = THEME_SEEDS.get(theme, (theme, "", ""))
            en_seeds, ur_seeds = [s[0]], [s[1], s[2]]
        if LANG == "en":
            return search_demand.suggestions(en_seeds, "en", "US")
        return search_demand.suggestions(ur_seeds, "ur", "PK")
    except Exception as e:
        log(f"search suggestions fail: {e}")
        return []


def pick_topic(history):
    used = [h["title"] for h in history[-120:]]
    n_lang = sum(1 for h in history if h.get("lang", "en") == LANG)
    theme = THEMES[(n_lang * 7 + (3 if LANG == "ur" else 0)) % len(THEMES)]
    occ = _occasion_today(history)
    if occ:
        theme = occ[1]
    searches = _search_phrases(theme, occ)
    log(f"Occasion: {occ[0] if occ else '-'} | Search phrases: {searches[:12]}")
    search_part = ""
    if searches:
        search_part = f"""
REAL phrases people are typing into YouTube search about this theme right now:
{json.dumps(searches, ensure_ascii=False)}
Choose the idea so the video truly answers ONE of these real searches (pick one that fits the
theme, is not already covered above, and suits the rules). Put that search's key words
naturally in the title so it shows up in search - but the title must honestly describe
what the video says (no clickbait, no promises the video does not keep).
IGNORE phrases that name a scholar, speaker, channel or person, or ask for a cartoon, movie,
song, status, or another language (Pashto, Hindi...) - never put such names in the title."""
    data = ask_json(f"""You plan videos for the Facebook page "{PAGE_NAME}".
Language of this video: {L['caption_lang']}. Theme for today: {theme}
These titles were ALREADY posted (any language). Do NOT repeat or closely resemble them:
{json.dumps(used, ensure_ascii=False)}
{search_part}
Give ONE fresh, specific, emotionally engaging video idea inside this theme.
Return JSON: {{"topic": "one English sentence describing the idea",
 "title": "catchy title in {L['caption_lang']}, max 70 characters",
 "search_phrase": "the exact real search phrase from the list you answered, or empty"}}""")
    PICK_EXTRA.clear()
    phrase = (data.get("search_phrase") or "").strip()
    if phrase:
        PICK_EXTRA["search"] = phrase
    if occ:
        PICK_EXTRA["occasion"] = occ[0]
    PICK_EXTRA["pk_day"] = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
    REPORT["search_phrases"] = searches[:20]
    REPORT.update({k: v for k, v in PICK_EXTRA.items() if k != "pk_day"})
    return theme, data["topic"], data["title"]


def word_count(script):
    return sum(len((s.get("text") or "").split()) for s in script.get("scenes", []))


def _write_long(topic, title, extra):
    scenes = 12
    per = L["long_words"] // scenes
    return ask_json(f"""Write the voice-over for an Islamic motivational Facebook video.
Title: "{title}". Idea: {topic}
Language: {L['write_in']}.

Structure: a powerful hook in the first 2 sentences that makes people keep watching, then a story
or explanation, practical lessons for daily life, and a heartfelt ending with a short dua.
{L['follow']}
{RULES}

Split into exactly {scenes} scenes, each about {per} words (total about {L['long_words']} words,
between {L['long_min']} and {L['long_max']} - count carefully). {extra}
For each scene give a 1-3 word ENGLISH stock-footage search term. {SAFE_VISUALS}
{SAY_RULE}

Return JSON: {{"scenes": [{{"text": "...", "say": "text with hard words phonetic (omit if none)", "visual": "..."}}],
 "caption": "2-3 line Facebook description in {L['caption_lang']} that invites comments",
 "hashtags": ["#Islam", "..."] (8 hashtags, mix of English and the video language)}}""")


def write_long(topic, title, extra=""):
    best = None
    for _ in range(2):
        data = _write_long(topic, title, extra)
        n = word_count(data)
        log(f"Long script: {n} words")
        target = L["long_words"]
        if len(data.get("scenes", [])) >= 4 and (
                best is None or abs(n - target) < abs(word_count(best) - target)):
            best = data
        if L["long_min"] // 2 <= n <= L["long_max"] * 2:
            break
        if n < L["long_min"]:
            extra = (f"IMPORTANT: your previous draft had only {n} words - too short. Each scene must "
                     f"be about {target // 12 + 8} words, total about {target} words.")
        else:
            extra = (f"IMPORTANT: your previous draft had {n} words - too long. Each scene must be "
                     f"about {target // 12} words, total about {target} words, NOT more.")
    if not best:
        raise RuntimeError("Lambi script nahi bani")
    return best


def voice_minutes(script, job):
    """Har scene ki awaaz bana kar kul minute batata hai (audio job folder mein rehti hai)."""
    shutil.rmtree(job, ignore_errors=True)
    os.makedirs(job)
    total = 0.0
    scenes = [s for s in script["scenes"] if (s.get("text") or "").strip()]
    for i, sc in enumerate(scenes):
        a = os.path.join(job, f"a{i}.mp3")
        tts((sc.get("say") or sc["text"]).strip(), a)   # say = mushkil lafz phonetic (TTS); subtitle `text` hi
        total += duration(a) + 0.5
    script["scenes"] = scenes
    return total / 60


def long_script_with_audio(topic, title):
    """Script likhwa kar awaaz banata hai; 4.3-6 minute na ho to dobara likhwata hai."""
    job = os.path.join(WORK, "long")
    best, best_gap, extra = None, None, ""
    for attempt in range(3):
        data = write_long(topic, title, extra)
        n = word_count(data)
        mins = voice_minutes(data, job)
        log(f"Long script try {attempt + 1}: {n} words, {mins:.2f} min")
        gap = abs(mins - 5.0)
        if best is None or gap < best_gap:
            best, best_gap = data, gap
            keep = os.path.join(WORK, "long_best")
            shutil.rmtree(keep, ignore_errors=True)
            shutil.copytree(job, keep)
        if 4.3 <= mins <= 6.0:
            return data
        want = int(n * 5.0 / max(mins, 0.5))
        extra = (f"IMPORTANT: your previous draft had {n} words and took {mins:.1f} minutes to read "
                 f"aloud. The video must be about 5 minutes, so write about {want} words in total "
                 f"(about {want // 12} words per scene).")
    shutil.rmtree(job, ignore_errors=True)
    shutil.copytree(os.path.join(WORK, "long_best"), job)
    return best


def write_reel(topic, title):
    data = ask_json(f"""Write a {L['reel_words']}-word Facebook Reel voice-over (about 50 seconds).
Title: "{title}" - {topic}
Language: {L['write_in']}.
First sentence must be a strong hook. Deliver one powerful lesson. {L['reel_end']}
{RULES}

Split into exactly 5 scenes. For each scene give a 1-3 word ENGLISH stock-footage search term.
{SAFE_VISUALS}
{SAY_RULE}

Return JSON: {{"scenes": [{{"text": "...", "say": "text with hard words phonetic (omit if none)", "visual": "..."}}],
 "caption": "1-2 lines in {L['caption_lang']}", "hashtags": ["#..."] (6 hashtags)}}""")
    if len(data.get("scenes", [])) < 2:
        raise RuntimeError("Reel script mein scenes kam hain")
    return data


# ---------------------------------------------------------------- audio
def tts(text, path):
    async def go():
        await edge_tts.Communicate(text, L["voice"], rate=L["rate"]).save(path)
    for attempt in range(6):                                   # Microsoft kabhi kabhi rok deta hai
        try:
            asyncio.run(go())
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            log(f"TTS retry {attempt + 1}: {str(e)[:200]}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("Awaaz nahi bani")


# ---------------------------------------------------------------- stock clips
def pixabay_clips(query, count, job, prefix):
    """Ek search se `count` alag clips laata hai. Wapas: file paths ki list."""
    got = []
    if not PIXABAY_KEY:
        return got
    for q in (query, "mosque", "sky clouds", "nature"):
        if len(got) >= count:
            break
        try:
            r = requests.get("https://pixabay.com/api/videos/", timeout=40, params={
                "key": PIXABAY_KEY, "q": q, "safesearch": "true", "per_page": 40,
                "video_type": "film"})
            r.raise_for_status()
            hits = [h for h in r.json().get("hits", [])
                    if h["id"] not in USED_CLIPS and not clip_blocked(h)]
        except Exception as e:
            log(f"Pixabay error ({q}): {str(e)[:150]}")
            continue
        random.shuffle(hits)
        for h in hits:
            if len(got) >= count:
                break
            v = h.get("videos", {})
            pick = next((v[s] for s in ("large", "medium")
                         if v.get(s, {}).get("url") and v[s].get("width", 0) >= 1280), None)
            if not pick:
                continue
            path = os.path.join(job, f"{prefix}_{len(got)}.mp4")
            try:
                with requests.get(pick["url"], stream=True, timeout=180) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as f:
                        for chunk in resp.iter_content(1 << 20):
                            f.write(chunk)
                if os.path.getsize(path) > 50000:
                    USED_CLIPS.add(h["id"])
                    got.append(path)
            except Exception as e:
                log(f"Clip download fail: {str(e)[:150]}")
    return got


def fallback_clip(path, w, h):
    c = random.choice([("0x0b1a33", "0x1f4d7a"), ("0x10261a", "0x2f6b4a"),
                       ("0x2b1a33", "0x5b3d7a"), ("0x2a1c0c", "0x7a5a1f")])
    run(["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"gradients=s={w}x{h}:c0={c[0]}:c1={c[1]}:speed=0.01:d=15",
         "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", path])


# ---------------------------------------------------------------- subtitles (ASS)
def ass_time(t):
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02}:{s:05.2f}"


def ass_text(s):
    return s.replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def make_ass(path, text, total, w, h, title=None):
    vertical = h > w
    font = L["font"]
    sub_size = 76 if vertical else 64
    title_size = 84 if vertical else 76
    sub_margin = 1000 if vertical else 80          # reel: beech mein (neeche YouTube/FB ka text dhak deta tha)
    title_margin = 330 if vertical else 90
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{font},{sub_size},&H00FFFFFF,&H00FFFFFF,&H70000000,&H70000000,1,0,0,0,100,100,0,0,3,14,0,{8 if vertical else 2},80,80,{sub_margin},1
Style: Title,{font},{title_size},&H0050D7FF,&H0050D7FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,3,8,70,70,{title_margin},1
Style: Mark,Noto Sans,{30 if vertical else 28},&H50FFFFFF,&H50FFFFFF,&H90000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,9,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = [f"Dialogue: 0,{ass_time(0)},{ass_time(total + 1)},Mark,,0,0,0,,{PAGE_NAME}"]
    if title:
        ev.append(f"Dialogue: 1,{ass_time(0.3)},{ass_time(min(5.5, total))},Title,,0,0,0,,"
                  f"{{\\fad(500,600)}}{ass_text(title)}")
    words = text.split()
    n = L["line_reel"] if vertical else L["line_long"]
    chunks = [" ".join(words[i:i + n]) for i in range(0, len(words), n)]
    weights = [len(c) + 3 for c in chunks]
    scale = total / max(sum(weights), 1)
    t = 0.0
    for c, wgt in zip(chunks, weights):
        end = t + wgt * scale
        ev.append(f"Dialogue: 2,{ass_time(t)},{ass_time(end)},Sub,,0,0,0,,{ass_text(c)}")
        t = end
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(ev) + "\n")


# ---------------------------------------------------------------- video
def build_scene(job, i, sc, w, h, title):
    text = (sc.get("text") or "").strip()
    audio = f"a{i}.mp3"
    if not os.path.exists(os.path.join(job, audio)):
        tts((sc.get("say") or text).strip(), os.path.join(job, audio))   # say = phonetic (TTS); subtitle `text` hi
    dur = duration(os.path.join(job, audio)) + 0.5
    k = max(1, min(4, round(dur / 8)))                     # har ~8 second baad naya clip
    n_isl = (k + 1) // 2                                   # aadhe (ya zyada) Islamic clips
    clips = pixabay_clips(random.choice(ISLAMIC_VISUALS), n_isl, job, f"c{i}i")
    clips += pixabay_clips(sc.get("visual") or "nature", k - len(clips), job, f"c{i}")
    random.shuffle(clips)
    REPORT["stock_clips"] += len(clips)
    if not clips:
        REPORT["fallback_clips"] += 1
        fb = os.path.join(job, f"c{i}_fb.mp4")
        fallback_clip(fb, w, h)
        clips = [fb]
    k = len(clips)
    seg = dur / k
    make_ass(os.path.join(job, f"s{i}.ass"), text, dur - 0.5, w, h, title)

    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd += ["-stream_loop", "-1", "-t", f"{seg + 0.2:.2f}", "-i", os.path.basename(c)]
    cmd += ["-i", audio]
    fd = min(0.5, seg / 4)
    chains = []
    for j in range(k):
        chains.append(
            f"[{j}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30,"
            f"setsar=1,trim=duration={seg:.2f},setpts=PTS-STARTPTS,"
            f"fade=t=in:st=0:d={fd:.2f},fade=t=out:st={seg - fd:.2f}:d={fd:.2f}[v{j}]")
    fontsdir = f":fontsdir={FONTS_DIR}" if os.path.isdir(FONTS_DIR) else ""
    chains.append("".join(f"[v{j}]" for j in range(k)) +
                  f"concat=n={k}:v=1:a=0,eq=brightness=-0.04:saturation=1.12:contrast=1.04,"
                  f"vignette=PI/5,subtitles=s{i}.ass{fontsdir},format=yuv420p[v]")
    cmd += ["-filter_complex", ";".join(chains), "-map", "[v]", "-map", f"{k}:a:0",
            "-af", "apad", "-t", f"{dur:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-maxrate", "6M", "-bufsize", "12M",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", f"p{i}.mp4"]
    run(cmd, cwd=job)
    return f"p{i}.mp4"


OUTRO = {
    "ur": {"fb": "اگر یہ ویڈیو آپ کو اچھی لگی تو اسے لائک کریں اور آگے شیئر کریں۔ نیکی کی بات آگے پہنچانا بھی نیکی اور ثواب کا کام ہے، "
                 "آپ بھی اس نیکی میں اپنا حصہ ڈالیں۔ اور ہمارے پیج کو فالو کریں تاکہ ہم آپ کے لیے مزید اچھی ویڈیوز بنا سکیں۔",
           "yt": "اگر یہ ویڈیو آپ کو اچھی لگی تو اسے لائک کریں اور آگے شیئر کریں۔ نیکی کی بات آگے پہنچانا بھی نیکی اور ثواب کا کام ہے، "
                 "آپ بھی اس نیکی میں اپنا حصہ ڈالیں۔ اور ہمارے چینل کو سبسکرائب کریں تاکہ ہم آپ کے لیے مزید اچھی ویڈیوز بنا سکیں۔"},
    "en": {"fb": "If this video touched your heart, please like it and share it. Spreading a good word is a good deed and brings reward, "
                 "so be a part of this good deed. And follow our page so we can make more beneficial videos for you.",
           "yt": "If this video touched your heart, please like it and share it. Spreading a good word is a good deed and brings reward, "
                 "so be a part of this good deed. And subscribe to our channel so we can make more beneficial videos for you."},
}


def yt_path(out_path):
    return out_path.replace(".mp4", "_yt.mp4")


def build_video(script, tag, w, h, out_path, title):
    job = os.path.join(WORK, tag)
    os.makedirs(job, exist_ok=True)
    parts = []
    scenes = [s for s in script["scenes"] if (s.get("text") or "").strip()]
    for i, sc in enumerate(scenes):
        parts.append(build_scene(job, i, sc, w, h, title if i == 0 else None))
        log(f"{tag}: scene {i + 1}/{len(scenes)} ready")
    if not parts:
        raise RuntimeError(f"{tag}: koi scene nahi bana")
    # aakhir mein dua/share/follow wali baat: FB ke liye "follow", YouTube ke liye "subscribe"
    outro = {}
    for n, (kind, txt) in enumerate(OUTRO.get(LANG, OUTRO["ur"]).items()):
        try:
            outro[kind] = build_scene(job, 900 + n, {"text": txt, "visual": "mosque sunset sky"}, w, h, None)
        except Exception as e:
            log(f"outro skip ({kind}): {e}")
    for kind, dest in (("fb", out_path), ("yt", yt_path(out_path))):
        lst = parts + ([outro[kind]] if kind in outro else [])
        with open(os.path.join(job, f"list_{kind}.txt"), "w") as f:
            f.writelines(f"file '{p}'\n" for p in lst)
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"list_{kind}.txt", "-c", "copy",
             "-movflags", "+faststart", os.path.abspath(dest)], cwd=job)
    REPORT[f"{tag}_minutes"] = round(duration(out_path) / 60, 2)
    log(f"{tag}: video {REPORT[f'{tag}_minutes']} min")
    return out_path


# ---------------------------------------------------------------- Facebook
def fb_json(r):
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"Facebook ka jawab samajh nahi aaya: {r.text[:300]}")
    if "error" in j:
        raise RuntimeError(f"Facebook error: {j['error'].get('message', j)}")
    return j


def post_long(path, title, desc):
    """Bari file ke liye resumable (tukron mein) upload."""
    url = f"https://graph-video.facebook.com/{GRAPH_VER}/{FB_PAGE}/videos"
    size = os.path.getsize(path)
    start = fb_json(requests.post(url, timeout=120, data={
        "access_token": FB_TOKEN, "upload_phase": "start", "file_size": str(size)}))
    session, vid = start["upload_session_id"], start.get("video_id")
    s_off, e_off = int(start["start_offset"]), int(start["end_offset"])
    with open(path, "rb") as f:
        while s_off < e_off:
            f.seek(s_off)
            chunk = f.read(e_off - s_off)
            for attempt in range(4):
                try:
                    j = fb_json(requests.post(url, timeout=600, data={
                        "access_token": FB_TOKEN, "upload_phase": "transfer",
                        "upload_session_id": session, "start_offset": str(s_off)},
                        files={"video_file_chunk": ("chunk", chunk, "application/octet-stream")}))
                    break
                except Exception as e:
                    log(f"Chunk retry {attempt + 1}: {str(e)[:150]}")
                    if attempt == 3:
                        raise
                    time.sleep(5)
            s_off, e_off = int(j["start_offset"]), int(j["end_offset"])
            log(f"Uploaded {s_off * 100 // size}%")
    fb_json(requests.post(url, timeout=300, data={
        "access_token": FB_TOKEN, "upload_phase": "finish", "upload_session_id": session,
        "title": title, "description": desc}))
    log(f"Long video posted: {vid}")
    return vid


def post_reel(path, desc):
    base = f"https://graph.facebook.com/{GRAPH_VER}/{FB_PAGE}/video_reels"
    vid = fb_json(requests.post(base, data={"upload_phase": "start", "access_token": FB_TOKEN},
                                timeout=60))["video_id"]
    with open(path, "rb") as f:
        fb_json(requests.post(f"https://rupload.facebook.com/video-upload/{GRAPH_VER}/{vid}",
                              headers={"Authorization": f"OAuth {FB_TOKEN}", "offset": "0",
                                       "file_size": str(os.path.getsize(path))},
                              data=f, timeout=1800))
    fb_json(requests.post(base, timeout=60, data={
        "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
        "description": desc, "access_token": FB_TOKEN}))
    log(f"Reel posted: {vid}")
    return vid


def description(title, script, is_reel=True):
    import seo
    text = " ".join((sc.get("text") or "") for sc in script.get("scenes", []))
    return seo.build(ask_json, "islamic", title, text or script.get("caption", ""), LANG, is_reel,
                     search_terms=REPORT.get("search_phrases", [])[:6])


# ---------------------------------------------------------------- main
def write_report():
    with open("last_run.json", "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=1)


def youtube(path, title, desc, short, entry, key):
    """Facebook ke baad wahi video "Islamic Motivational Videos" YouTube channel par. Fail ho to sirf report mein."""
    import yt
    if not yt.enabled("islamic"):
        return
    try:
        entry[key] = yt.upload("islamic", path, title, desc, short=short, lang=LANG, category="22")
    except Exception as e:
        log(f"YOUTUBE ERROR: {e}")
        REPORT["errors"].append(f"youtube: {str(e)[:300]}")


def _main():
    if not DRY_RUN and (not FB_TOKEN or not FB_PAGE):
        raise RuntimeError("FB_PAGE_ACCESS_TOKEN ya FB_PAGE_ID secret missing hai")
    history = load_history()
    theme, topic, title = pick_topic(history)
    log(f"Lang: {LANG} | Theme: {theme} | Title: {title}")

    long_script = long_script_with_audio(topic, title) if DO_LONG else None
    reel_script = write_reel(topic, title) if DO_REEL else None

    entry = {"date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
             "lang": LANG, "theme": theme, "title": title}
    entry.update(PICK_EXTRA)
    ok = 0
    need = int(DO_LONG) + int(DO_REEL)
    try:
        if not DO_LONG:
            raise StopIteration
        build_video(long_script, "long", 1920, 1080, "final_long.mp4", title)
        if not DRY_RUN:
            desc = description(title, long_script, is_reel=False)
            import slot_wait; slot_wait.wait(log)
            if not YT_ONLY:
                entry["long_id"] = post_long("final_long.mp4", title, desc)
            youtube(yt_path("final_long.mp4"), title, desc, False, entry, "long_yt")
            if not YT_ONLY:
                import social
                social.share_long("islamic", "final_long.mp4", desc, entry, REPORT, log)
        ok += 1
    except StopIteration:
        pass
    except Exception as e:
        log(f"LONG VIDEO ERROR: {e}")
        REPORT["errors"].append(f"long: {str(e)[:300]}")

    try:
        if not DO_REEL:
            raise StopIteration
        build_video(reel_script, "reel", 1080, 1920, "final_reel.mp4", title)
        for fpath in ("final_reel.mp4", yt_path("final_reel.mp4")):
            if os.path.exists(fpath) and duration(fpath) > 89:
                run(["ffmpeg", "-y", "-i", fpath, "-t", "89", "-c", "copy", "reel_cut.mp4"])
                shutil.move("reel_cut.mp4", fpath)
        if not DRY_RUN:
            desc = description(title, reel_script)
            import slot_wait; slot_wait.wait(log)
            if not YT_ONLY:
                entry["reel_id"] = post_reel("final_reel.mp4", desc)
            youtube(yt_path("final_reel.mp4"), title, desc, True, entry, "reel_yt")
            if not YT_ONLY:
                import social
                social.share_reel("islamic", FB_PAGE, FB_TOKEN, "final_reel.mp4", desc, entry, REPORT, log)
        ok += 1
    except StopIteration:
        pass
    except Exception as e:
        log(f"REEL ERROR: {e}")
        REPORT["errors"].append(f"reel: {str(e)[:300]}")

    REPORT.update({"time_utc": entry["date"], "title": title, "dry_run": DRY_RUN, "posted_ok": ok})
    write_report()
    if ok and not DRY_RUN:
        history.append(entry)
        save_history(history)
    if ok < need:
        sys.exit(1)
    log("Done successfully!")


def main():
    try:
        _main()
    except SystemExit:
        raise
    except Exception as e:
        REPORT["errors"].append(f"fatal: {str(e)[:300]}")
        write_report()
        raise


if __name__ == "__main__":
    main()
