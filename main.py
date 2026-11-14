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
import re
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
MODEL_CANDIDATES = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]

LANGS = {
    "ur": {
        "voice": "ur-PK-AsadNeural", "rate": "-4%", "font": "Noto Naskh Arabic",
        "long_words": 850, "long_min": 700, "long_max": 1000, "reel_words": 130,
        "line_long": 6, "line_reel": 4,
        "write_in": ("simple, heart-touching spoken Pakistani URDU written in Urdu script "
                     "(not Roman Urdu). Use common words people speak daily; Islamic terms "
                     "like Allah, Sabr, Dua, Jannat are fine. Always address the viewer respectfully "
                     "as آپ (never تم or تو). After the Prophet's name ALWAYS write the full words "
                     "صلی اللہ علیہ وسلم (never the ﷺ symbol, never abbreviations). Never add "
                     "zabar/zer/pesh/tashdeed (harakat) to any word"),
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
    # Zyada waqiat/qissay (log zyada aate hain)
    "a true miracle in the life of Prophet Muhammad", "a powerful story of a Sahabi's sacrifice",
    "a story of a sinner who truly repented", "a dua that Allah answered (true incident)",
    "a lesson-filled event from early Islamic history", "a story of a prophet's trial and patience",
    "an authentic hadith of Prophet Muhammad and its meaning", "a sunnah of the Prophet for daily life",
]

from footage import VISUALS_RULE

SAFE_VISUALS = ("The visual term is what the viewer SEES while this scene is spoken, so it MUST match the "
                "narration. If the scene mentions a concrete thing, the term is THAT thing: food or drink "
                "(dates fruit, honey, milk, bread, water, olives, figs, pomegranate, grapes), an animal "
                "(camel, horse, sheep, spider web, birds, ant, whale), nature (cave, desert, mountain, rain, "
                "sea, river, fire, moon, stars, sun, garden, trees, water well), or an object (old book, "
                "sword, lamp, coins, ship, tent, door). If nothing concrete is mentioned, use an Islamic "
                "visual (mosque, mosque interior, minaret, kaaba, mecca, medina, open quran, prayer mat, "
                "ramadan lantern, crescent moon, arabic calligraphy) or calm scenery (sky, clouds, sunrise, "
                "sunset, night stars). Never people, faces, women or girls, never church, temple, cross, "
                "candle or statue. Any building must be a MOSQUE - never a temple, church, mandir or plain "
                "'architecture/building' that could be another religion's place.")

# Pronunciation: a text-to-speech voice reads the narration, so Arabic/foreign words get mispronounced.
SAY_RULE = ("PRONUNCIATION: a text-to-speech voice reads 'text', so Arabic and other foreign words come out "
            "wrong. For every scene also give a 'say' field: the SAME narration as 'text' but with ONLY the "
            "hard Arabic/foreign words respelled phonetically so the voice says them correctly "
            "(e.g. Bismillah -> 'Biss-mil-lah', Alhamdulillah -> 'Al-ham-du-lil-lah', InshaAllah -> "
            "'In-sha-Allah', SubhanAllah -> 'Sub-haan-Allah', Surah -> 'Soo-rah', Taqwa -> 'Tuq-waa'). "
            "Respell in the SAME language/script as 'text'. Keep every other word identical to 'text'. "
            "URDU: NEVER add zabar/zer/pesh/tashdeed (harakat) - they make the voice mispronounce; split hard "
            "Arabic words with hyphens instead (e.g. بس-م-اللہ، ال-حم-دو-لل-لاہ، ان-شا-اللہ، سب-حان-اللہ). "
            "Never respell or hyphenate the Prophet's name محمد or صلی اللہ علیہ وسلم - keep them exactly so. "
            "If a scene has no hard word, omit 'say'.")

# Har scene mein aadhe clips inn mein se (masjid waghera zyada dikhein)
ISLAMIC_VISUALS = ["mosque", "mosque interior", "minaret", "mosque dome", "mecca", "medina",
                   "kaaba", "masjid nabawi", "mosque at night", "mosque courtyard", "mosque arches",
                   "blue mosque", "grand mosque interior", "mosque chandelier", "mosque calligraphy",
                   "mosque silhouette sunset", "ramadan mosque", "istanbul mosque", "madinah mosque",
                   "quran", "prayer mat", "ramadan lantern", "crescent moon",
                   "islamic architecture", "arabic calligraphy", "mosque sunset"]

# Inn tags wale clips kabhi nahi lagenge (ghair-Islami ibadat gahen / cheezein)
BLOCK_TAGS = {"church", "cathedral", "chapel", "christian", "christianity", "cross", "crucifix",
              "jesus", "christ", "mary", "bible", "priest", "nun", "pope", "vatican", "basilica",
              "monastery", "abbey", "rosary", "christmas", "easter", "temple", "hindu", "buddha",
              "buddhist", "buddhism", "monk", "pagoda", "shrine", "idol", "statue", "sculpture",
              "synagogue", "jewish", "menorah", "shiva", "ganesh", "krishna", "diwali", "halloween",
              "gothic", "angel", "saint", "candle", "candles", "altar", "wine", "beer", "alcohol",
              "bikini", "party", "nightclub", "dance", "dancing", "pig", "pork",
              # aurat/larki, yoga, fitness waghera - Islamic page par kabhi nahi
              "woman", "women", "girl", "girls", "lady", "ladies", "female", "model", "models",
              "yoga", "meditation", "meditate", "pilates", "fitness", "workout", "exercise", "gym",
              "stretching", "aerobics", "sport", "sports", "beauty", "fashion", "makeup", "bride",
              "couple", "romance", "romantic", "kiss", "kissing", "hug", "sexy", "swimsuit",
              "swimming", "lingerie", "dress", "portrait", "face", "selfie", "teen", "teenager"}


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
try:
    import page_brain as _pb
    RULES = RULES + _pb.load("islamic")[1]      # AGENT ke seekhe sabaq har script mein
except Exception:
    pass

os.makedirs(WORK, exist_ok=True)
REPORT = {"lang": LANG, "stock_clips": 0, "fallback_clips": 0, "errors": []}
USED_CLIPS = set()
OLD_CLIPS = set()     # pichle dinon mein lag chuki clips - pehle nayi clips, purani sirf majboori mein
GOOD_CLIPS = []       # is run mein waqai video mein lagi clips (history mein save - agle din repeat na hon)


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
    import groq_backup
    if groq_backup.enabled():
        log(f"Gemini fail ({str(last)[:80]}) - Groq backup try")
        try:
            return groq_backup.ask_json(prompt, 0.9, log)
        except Exception as e:
            last = f"{last} | {e}"
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
    "a true miracle in the life of Prophet Muhammad": ("prophet muhammad miracle", "نبی کریم کا معجزہ", "nabi ka mojza"),
    "a powerful story of a Sahabi's sacrifice": ("sahaba sacrifice story", "صحابی کی قربانی", "sahabi ka waqia"),
    "a story of a sinner who truly repented": ("true repentance story islam", "گناہگار کی توبہ", "tauba ka waqia"),
    "a dua that Allah answered (true incident)": ("dua answered true story", "قبول دعا کا واقعہ", "dua qabool waqia"),
    "a lesson-filled event from early Islamic history": ("islamic history story", "اسلامی تاریخ کا واقعہ", "islami tareekh waqia"),
    "a story of a prophet's trial and patience": ("prophet story patience", "نبی کا صبر", "nabi ka sabr waqia"),
    "an authentic hadith of Prophet Muhammad and its meaning": ("hadith explained", "حدیث", "hadees ki tashreeh"),
    "a sunnah of the Prophet for daily life": ("sunnah of prophet", "نبی کی سنت", "nabi ki sunnat"),
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


CLAIMS_FILE = "islamic_claims.json"   # jo topic kisi chalte run ne chun liya (abhi post nahi hua) - doosra run wohi na chune


def _git(*a):
    return subprocess.run(["git", *a], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)


def _remote_json(name):
    """GitHub par abhi wali file (doosre runs ki nayi entries samet). Na mile to []."""
    try:
        _git("fetch", "-q", "origin", "main")
        p = _git("show", f"origin/main:{name}")
        if p.returncode == 0:
            d = json.loads(p.stdout.decode("utf-8"))
            return d if isinstance(d, list) else []
    except Exception:
        pass
    return []


def _norm_words(t):
    t = re.sub(r"[^\w\s]", " ", (t or "").lower())
    stop = {"the", "a", "an", "of", "and", "in", "to", "for", "how", "his", "her", "when", "who", "with", "on",
            "is", "was", "story", "islam", "islamic", "prophet", "allah", "lesson", "true", "power", "about",
            "واقعہ", "واقعات", "ایمان", "افروز", "فضیلت", "سبق", "اسلام", "نبی", "کریم", "حضرت", "عظیم",
            "خوبصورت", "سچا", "سچی", "نبوی", "اللہ", "کیسے", "والا", "والی"}
    return {w for w in t.split() if len(w) > 2 and w not in stop}


def _same_story(a, b):
    """Do waqiat ek hi hain? (alfaaz badal kar wohi qissa dobara na aaye)"""
    wa, wb = _norm_words(a), _norm_words(b)
    if not wa or not wb:
        return False
    inter = len(wa & wb)
    return inter >= 3 and inter / min(len(wa), len(wb)) >= 0.6


def _claim(story, title):
    """Chuna hua topic foran GitHub par 'claim' - saath chalne wala doosra run yahi waqia na uthaye.
    Working folder ko haath nahi lagata (alag index se seedha commit)."""
    if DRY_RUN:
        return
    env = dict(os.environ, GIT_INDEX_FILE="/tmp/claim_index", GIT_AUTHOR_NAME="auto-poster",
               GIT_AUTHOR_EMAIL="auto-poster@users.noreply.github.com", GIT_COMMITTER_NAME="auto-poster",
               GIT_COMMITTER_EMAIL="auto-poster@users.noreply.github.com")

    def g(*a, inp=None):
        return subprocess.run(["git", *a], input=inp, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=60, env=env)
    for i in range(4):
        try:
            claims = _remote_json(CLAIMS_FILE)
            cut = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
            claims = [c for c in claims if str(c.get("date", "")) >= cut]
            claims.append({"date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "lang": LANG,
                           "story": story, "title": title})
            data = json.dumps(claims, ensure_ascii=False, indent=1).encode("utf-8")
            blob = g("hash-object", "-w", "--stdin", inp=data).stdout.decode().strip()
            g("read-tree", "origin/main")
            g("update-index", "--add", "--cacheinfo", f"100644,{blob},{CLAIMS_FILE}")
            tree = g("write-tree").stdout.decode().strip()
            com = g("commit-tree", tree, "-p", "origin/main", "-m", "Claim Islamic topic").stdout.decode().strip()
            if com and g("push", "-q", "origin", f"{com}:refs/heads/main").returncode == 0:
                log(f"Topic claim saved: {story}")
                return
        except Exception as e:
            log(f"claim fail: {str(e)[:100]}")
        time.sleep(5 * (i + 1))


def pick_topic(history):
    # GitHub wali taaza history + abhi chal rahe runs ke chune topics (warna ek hi din do run wohi waqia utha lete the)
    seen = {(h.get("date"), h.get("title")) for h in history}
    history = history + [h for h in _remote_json(HISTORY_FILE) if (h.get("date"), h.get("title")) not in seen]
    claims = _remote_json(CLAIMS_FILE)
    for h in history[-60:]:
        OLD_CLIPS.update(h.get("clips") or [])
    past = [h.get("story") or h["title"] for h in history[-400:]] + [c.get("story") or c.get("title", "") for c in claims]
    used = [h["title"] for h in history[-150:]] + [c.get("title", "") for c in claims]
    stories = [h["story"] for h in history[-400:] if h.get("story")] + [c["story"] for c in claims if c.get("story")]
    n_lang = sum(1 for h in history if h.get("lang", "en") == LANG)
    # AGENT: jo theme zyada views laya wo zyada baar (page_brain.py), pichle 4 themes dobara nahi
    import page_brain
    a_mult, a_tips = page_brain.load("islamic")
    recent_t = [h.get("theme") for h in history if h.get("lang", "en") == LANG][-4:]
    opts = [t for t in THEMES if t not in recent_t] or THEMES
    theme = random.choices(opts, weights=[max(float(a_mult.get(t, 1.0)), 0.2) for t in opts])[0]
    log(f"Agent theme: {theme}")
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
    import content_rules
    prompt = f"""You plan videos for the Facebook page "{PAGE_NAME}".{content_rules.text("islamic")}
Language of this video: {L['caption_lang']}. Theme for today: {theme}
These titles were ALREADY posted (any language). Do NOT repeat or closely resemble them:
{json.dumps(used, ensure_ascii=False)}
These STORIES / incidents were ALREADY told (any language, any wording). Do NOT tell the same incident,
the same person's same event, or the same hadith again - even with a new title or a new angle:
{json.dumps(stories[-250:], ensure_ascii=False)}{{AVOID}}
{search_part}
{a_tips}Give ONE fresh, specific, emotionally engaging video idea inside this theme.
IMPORTANT: prefer a REAL ISLAMIC STORY / incident (واقعہ / قصہ) that teaches this theme - an authentic
event from the life of Prophet Muhammad (peace be upon him), the Sahaba, the prophets in the Quran,
Islamic history, or an authentic hadith / sunnah - with real people and a clear turning point. Story
videos get many more viewers than plain lectures. Use only well-known authentic narrations (Quran and
sahih hadith); never invent fake events or weak/fabricated tales.
Return JSON: {{"topic": "one English sentence describing the idea",
 "story": "the core incident/hadith in 4-8 plain English words, e.g. 'Prophet visits sick Jewish boy'",
 "title": "catchy title in {L['caption_lang']}, max 70 characters",
 "search_phrase": "the exact real search phrase from the list you answered, or empty"}}"""
    avoid = []
    for attempt in range(4):
        extra = ("\nREJECTED just now because already told - pick a DIFFERENT incident: " +
                 json.dumps(avoid, ensure_ascii=False)) if avoid else ""
        data = ask_json(prompt.replace("{AVOID}", extra))
        story = (data.get("story") or data.get("topic") or "").strip()
        dup = next((p for p in past if _same_story(story, p) or _same_story(data.get("title", ""), p)), None)
        if not dup:
            break
        log(f"Topic repeat tha ({story} ~ {dup}) - naya chun raha hoon")
        avoid.append(story)
    data["story"] = story
    PICK_EXTRA.clear()
    PICK_EXTRA["story"] = data["story"]
    _claim(data["story"], data["title"])
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

Structure: a powerful hook in the first 2 sentences that makes people keep watching, then TELL THE STORY
(the واقعہ / incident) like a gripping narration - set the scene, the people, what happened, the turning
point - and only after the story draw out the practical lessons for daily life, then a heartfelt ending
with a short dua. Make it feel like a story being told, not a lecture. Stay faithful to authentic
narrations; never invent events, names or details.
{L['follow']}
{RULES}

Split into exactly {scenes} scenes, each about {per} words (total about {L['long_words']} words,
between {L['long_min']} and {L['long_max']} - count carefully). {extra}
For each scene give a 1-3 word ENGLISH stock-footage search term. {SAFE_VISUALS}
{VISUALS_RULE} The same Islamic-safety rules apply to every term in 'visuals'.
{SAY_RULE}

Return JSON: {{"scenes": [{{"text": "...", "say": "text with hard words phonetic (omit if none)", "visual": "...", "visuals": ["...", "..."]}}],
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
        tts(spoken_text(sc, sc["text"]), a)   # say = mushkil lafz phonetic (TTS); subtitle `text` hi
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
First sentence must be a strong hook. Tell ONE short, gripping Islamic story/incident (واقعہ) with a
clear turning point, then its one powerful lesson. Keep it a story, not a lecture; use only authentic
narrations, never invented events. {L['reel_end']}
{RULES}

Split into exactly 5 scenes. For each scene give a 1-3 word ENGLISH stock-footage search term.
{SAFE_VISUALS}
{VISUALS_RULE} The same Islamic-safety rules apply to every term in 'visuals'.
{SAY_RULE}

Return JSON: {{"scenes": [{{"text": "...", "say": "text with hard words phonetic (omit if none)", "visual": "...", "visuals": ["...", "..."]}}],
 "caption": "1-2 lines in {L['caption_lang']}", "hashtags": ["#..."] (6 hashtags)}}""")
    if len(data.get("scenes", [])) < 2:
        raise RuntimeError("Reel script mein scenes kam hain")
    return data


# ---------------------------------------------------------------- audio
DUROOD_UR = " صلی اللہ علیہ وسلم "
_HARAKAT = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")


def clean_for_voice(text):
    """Awaaz se pehle text saaf: Nabi pak ka naam aur durood hamesha theek bole.
    Test (Whisper) se pata chala: ﷺ nishan awaaz bilkul skip kar deti hai, aur zabar/zer/pesh/tashdeed
    lagane se lafz bigar jaate hain (محمد -> 'معیمیت'). Saada likha 'صلی اللہ علیہ وسلم' sab se saaf bolta hai."""
    t = text
    if LANG == "ur":
        t = re.sub(r"\(?\s*(ﷺ|\u0610|صلعم|\(ص\))\s*\)?", DUROOD_UR, t)
        t = _HARAKAT.sub("", t)                                        # zabar/zer/pesh/shadd hatao
        t = re.sub(r"صل[یىي]?\s*-?\s*ا?لل[هہ]\s*-?\s*عل[یىي][هہ]\s*-?\s*(و\s*آل[هہ]\s*)?و?\s*-?\s*سلم",
                   lambda m: "صلی اللہ علیہ وآلہ وسلم" if m.group(1) else DUROOD_UR.strip(), t)  # ek saaf shakal
        t = re.sub(r"صل-?لل-?لاہو\s*علیہ-?\s*وسلم", DUROOD_UR.strip(), t)
        t = t.replace("ى", "ی").replace("ي", "ی")
    else:
        t = re.sub(r"\(?\s*(ﷺ|\u0610|PBUH|P\.B\.U\.H\.?|SAWS|SAW|S\.A\.W\.?)\s*\)?", " peace be upon him ", t)
    return re.sub(r"\s{2,}", " ", t).strip()



def spoken_text(sc, text):
    """`say` sirf tab jab poora jumla ho - AI kabhi sirf mushkil lafz likh deta hai, phir awaaz adhoori bolti hai."""
    say = (sc.get("say") or "").strip()
    return say if len(say.split()) >= 0.7 * len(text.split()) else text.strip()

def tts(text, path):
    text = clean_for_voice(text)

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
PEXELS_KEY = os.environ.get("PEXELS_API_KEY")
WM_UA = {"User-Agent": "IslamicVideosBot/1.0 (https://github.com/Ranaadnan42/fb-auto-poster)"}
VISION_MODELS = ["gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3-flash-preview", "gemma-4-31b-it", "gemma-4-26b-a4b-it"]
_VDEAD = set()
_VSLOW = {}


def _blocked_text(text):
    return bool(set(re.findall(r"[a-z]+", (text or "").lower())) & BLOCK_TAGS)


def _cands(q):
    """Teen jagah se clips: Pixabay, Pexels, Wikimedia Commons (asli Makkah/Madinah/masjid footage)."""
    out = []
    if PIXABAY_KEY:
        try:
            r = requests.get("https://pixabay.com/api/videos/", timeout=40, params={
                "key": PIXABAY_KEY, "q": q, "safesearch": "true", "per_page": 40, "video_type": "film"})
            for h in r.json().get("hits", []):
                v = h.get("videos", {})
                pick = next((v[x] for x in ("large", "medium")
                             if v.get(x, {}).get("url") and v[x].get("width", 0) >= 1280), None)
                if pick:
                    out.append({"id": f"px{h['id']}", "url": pick["url"], "text": (h.get("tags") or "").lower(),
                                "dur": h.get("duration", 10)})
        except Exception as e:
            log(f"Pixabay error ({q}): {str(e)[:120]}")
    if PEXELS_KEY:
        try:
            r = requests.get("https://api.pexels.com/videos/search", timeout=40, headers={"Authorization": PEXELS_KEY},
                             params={"query": q, "per_page": 30})
            for v in r.json().get("videos", []):
                fs = sorted([f for f in v.get("video_files", []) if (f.get("width") or 0) >= 1280 and f.get("link")],
                            key=lambda f: f["width"])
                if fs:
                    out.append({"id": f"pe{v['id']}", "url": fs[0]["link"],
                                "text": (v.get("url") or "").lower().replace("-", " "), "dur": v.get("duration", 10)})
        except Exception as e:
            log(f"Pexels error ({q}): {str(e)[:120]}")
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", headers=WM_UA, timeout=40, params={
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 25,
            "gsrsearch": "filetype:video " + q, "prop": "videoinfo", "viprop": "url|size|derivatives"})
        for pg in (r.json().get("query", {}).get("pages", {}) or {}).values():
            info = (pg.get("videoinfo") or [{}])[0]
            ders = sorted([d for d in info.get("derivatives", []) if d.get("src") and (d.get("height") or 0) >= 480],
                          key=lambda d: abs((d.get("height") or 0) - 1080))
            if (info.get("width") or 0) >= 640 and float(info.get("duration") or 0) >= 4:
                out.append({"id": f"wm{pg.get('pageid')}", "url": ders[0]["src"] if ders else info.get("url"),
                            "text": (pg.get("title") or "").lower().replace("_", " "),
                            "dur": float(info.get("duration") or 10)})
    except Exception as e:
        log(f"Commons error ({q}): {str(e)[:120]}")
    return out


def _vision_ok(jpg, want):
    """Agent frame dekh kar batata hai: kya yeh WOHI cheez hai aur Islamic page ke laiq hai? None = check na ho saka."""
    import base64
    if not GEMINI_KEY:
        return None
    img = base64.b64encode(open(jpg, "rb").read()).decode()
    prompt = (f"This frame is for a respectful Islamic video. The narration needs: '{want}'. "
              "Answer JSON {\"match\": true/false, \"safe\": true/false}. match = the frame clearly shows that "
              "thing (a mosque must be a real mosque, not a church/temple/other building). safe = no women or girls, "
              "no close-up faces, no musical instruments, no alcohol, no church/temple/cross/statue, nothing "
              "immodest or silly.")
    for m in VISION_MODELS:
        if m in _VDEAD:
            continue
        try:
            t0 = time.time()
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_KEY}",
                              timeout=25, json={"contents": [{"parts": [{"text": prompt},
                                                                         {"inline_data": {"mime_type": "image/jpeg", "data": img}}]}],
                                                "generationConfig": {"responseMimeType": "application/json", "temperature": 0}})
            if r.status_code in (401, 403, 404, 429):
                _VDEAD.add(m)
            if time.time() - t0 > 20:
                _VSLOW[m] = _VSLOW.get(m, 0) + 1
                if _VSLOW[m] >= 2:
                    _VDEAD.add(m)
            r.raise_for_status()
            d = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            REPORT["vision_checks"] = REPORT.get("vision_checks", 0) + 1
            return bool(d.get("match")) and bool(d.get("safe"))
        except Exception as e:
            log(f"vision {m}: {str(e)[:100]}")
    # Gemini busy/khatam -> Groq vision backup (live model list, limit par ruk kar / agla model)
    import groq_vision
    d = groq_vision.ask_json([img], prompt)
    if d is not None:
        REPORT["vision_checks"] = REPORT.get("vision_checks", 0) + 1
        return bool(d.get("match")) and bool(d.get("safe"))
    return None


def pixabay_clips(query, count, job, prefix):
    """`count` clips jo WOHI cheez dikhayen jo boli ja rahi hai. Har clip agent dekh kar pass karta hai."""
    got = []
    for q in (query, random.choice(ISLAMIC_VISUALS), "mosque", "sky clouds"):
        if len(got) >= count or not q:
            continue
        qw = [w for w in q.lower().split() if len(w) > 2]
        cands = [c for c in _cands(q) if c["id"] not in USED_CLIPS and not _blocked_text(c["text"])]
        full = [c for c in cands if all(w in c["text"] for w in qw)]       # sab lafz match - pehle
        part = [c for c in cands if c not in full and any(w in c["text"] for w in qw)]
        random.shuffle(full)
        random.shuffle(part)
        full.sort(key=lambda c: c["id"] in OLD_CLIPS)     # purani (pichle dinon wali) clips aakhir mein
        part.sort(key=lambda c: c["id"] in OLD_CLIPS)
        tries = 0
        for c in full + part:
            if len(got) >= count or tries >= 8:
                break
            tries += 1
            path = os.path.join(job, f"{prefix}_{len(got)}.mp4")
            try:
                with requests.get(c["url"], stream=True, timeout=180, headers=WM_UA) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as f:
                        for chunk in resp.iter_content(1 << 20):
                            f.write(chunk)
                if os.path.getsize(path) < 50000:
                    continue
                ok = True
                for k, at in enumerate((min(c["dur"] * 0.25, 2), max(min(c["dur"] * 0.75, 9), 1))):
                    jpg = f"{path}.chk{k}.jpg"
                    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at:.1f}", "-i", path,
                                    "-frames:v", "1", "-vf", "scale=640:-2", jpg], capture_output=True)
                    if not os.path.exists(jpg):
                        continue
                    v = _vision_ok(jpg, q)
                    if v is False or (v is None and c not in full):
                        ok = False
                        break
                USED_CLIPS.add(c["id"])
                if not ok:
                    REPORT["clips_rejected"] = REPORT.get("clips_rejected", 0) + 1
                    continue
                GOOD_CLIPS.append(c["id"])
                got.append(path)
            except Exception as e:
                log(f"Clip download fail: {str(e)[:150]}")
    return got


def scene_clips(terms, count, job, prefix, w, h):
    """Har clip slot ko WOHI cheez jo us waqt boli ja rahi hai (terms isi tarteeb mein).
    Pehle har platform ki videos (Pixabay, Commons, NASA, Pexels-agar-key), na milen to usi cheez ki asli
    photo (zoom ke saath). Be-taalluq 'random Islamic' clip sirf tab jab kuch bhi na mile."""
    import footage
    slots = [terms[min(j * len(terms) // count, len(terms) - 1)] if terms else "" for j in range(count)]
    res = [None] * count
    # 1) har jagah pehle VIDEO  2) na mile to is scene ki doosri boli gayi cheez ki video  3) tab jaa kar photo
    for j, term in enumerate(slots):
        if term:
            res[j] = _one_clip(term, job, f"{prefix}_{j}", w, h, ("video",))
    for j, term in enumerate(slots):
        if not res[j] and term:
            for t2 in [t for t in terms if t != term][:2]:
                res[j] = _one_clip(t2, job, f"{prefix}_{j}", w, h, ("video",))
                if res[j]:
                    break
    for j, term in enumerate(slots):
        if not res[j] and term:
            res[j] = _one_clip(term, job, f"{prefix}_{j}", w, h, ("photo",))
            if not res[j]:
                REPORT.setdefault("no_match", []).append(term)
    got = [c for c in res if c]
    if not got:   # is scene ki koi cheez kahin na mili - tab hi purana tareeqa (mosque/aasman)
        got = pixabay_clips(random.choice(ISLAMIC_VISUALS), min(count, 2), job, prefix)
    return got


def _one_clip(term, job, name, w, h, kinds=("video", "photo")):
    import footage
    qw = footage.words(term)
    for kind in kinds:
        cands = footage.videos(term, h > w) if kind == "video" else footage.photos(term)
        cands = [c for c in cands if c["id"] not in USED_CLIPS and not _blocked_text(c["text"])
                 and footage.match_score(c["text"], qw) > 0]
        random.shuffle(cands)
        cands.sort(key=lambda c: (c["id"] in OLD_CLIPS, -footage.match_score(c["text"], qw), c.get("vertical") != (h > w)))
        for c in cands[:12 if kind == "video" else 6]:     # pehle video ki poori koshish
            USED_CLIPS.add(c["id"])
            path = os.path.join(job, f"{name}.mp4")
            src = path + (".jpg" if kind == "photo" else "")
            try:
                if not footage.download(c["url"], src):
                    continue
                full = footage.match_score(c["text"], qw) == len(qw)
                points = [None] if kind == "photo" else [min(c["dur"] * 0.25, 2), max(min(c["dur"] * 0.75, 9), 1)]
                ok = True
                for k, at in enumerate(points):
                    jpg = f"{path}.chk{k}.jpg"
                    if kind == "photo":
                        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", "scale=640:-2", jpg],
                                       capture_output=True)
                    elif not footage.frame(src, jpg, at):
                        continue
                    v = _vision_ok(jpg, term)
                    # photo sirf agent ki haan par; video agent na dekh sake to sirf poore lafz match par
                    if v is False or (v is None and (kind == "photo" or not full)):
                        ok = False
                        break
                if not ok:
                    REPORT["clips_rejected"] = REPORT.get("clips_rejected", 0) + 1
                    continue
                if kind == "photo":
                    footage.photo_to_clip(src, path, w, h)
                    REPORT["photo_clips"] = REPORT.get("photo_clips", 0) + 1
                REPORT.setdefault("sources", {})
                REPORT["sources"][c["src"]] = REPORT["sources"].get(c["src"], 0) + 1
                GOOD_CLIPS.append(c["id"])
                return path
            except Exception as e:
                log(f"clip fail ({term}): {str(e)[:120]}")
    return None


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
        tts(spoken_text(sc, text), os.path.join(job, audio))   # say = phonetic (TTS); subtitle `text` hi
    dur = duration(os.path.join(job, audio)) + 0.5
    k = max(1, min(4, round(dur / 8)))                     # har ~8 second baad naya clip
    # pehle WOHI cheez jiska is scene mein zikr ho raha hai (khaana, janwar, jagah...);
    # Islamic clips sirf tab jab us cheez ki poori clips na milen
    import footage
    terms = footage.scene_terms(sc)
    clips = scene_clips(terms, max(k, min(4, len(terms))), job, f"c{i}", w, h)
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
    import stories
    stories.try_story(FB_PAGE, FB_TOKEN, path, GRAPH_VER, log, REPORT["errors"])
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
        entry["clips"] = list(dict.fromkeys(GOOD_CLIPS))[:80]   # agle dinon mein yeh clips dobara na lagen
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
