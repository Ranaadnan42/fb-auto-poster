"""
Funny Videos page - Auto Poster (GitHub Actions)

MODE=reel : ek janwar par mazahiya Urdu voiceover reel (~40 sec, 1080x1920)
MODE=long : 10 alag janwaron ki funny compilation (~5 min, 1920x1080) - ads ke liye

Har clip Pixabay se (free, copyright-safe), awaaz Edge TTS (ur-PK-AsadNeural),
script Gemini (free). Pichle titles funny_history.json se repeat nahi hote.

Secrets: GEMINI_API_KEY, PIXABAY_API_KEY, FUNNY_PAGE_TOKEN, FUNNY_PAGE_ID
DRY_RUN=1 -> video banegi, post nahi hogi.
"""
import os
import sys
import json
import time
import re
import random
import asyncio
import shutil
import datetime
import subprocess

import requests

from footage import VISUALS_RULE
import edge_tts

import sfx
from google import genai
from google.genai import types

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY")
HUMAN = {"man", "woman", "men", "women", "people", "person", "boy", "girl", "family", "friends", "kid", "kids",
         "child", "children", "guy", "student", "students", "couple", "father", "mother", "grandmother",
         "grandfather", "worker", "businessman", "teenager", "baby", "crowd", "lady", "chef", "teacher"}
FB_TOKEN = os.environ.get("FUNNY_PAGE_TOKEN")
FB_PAGE = os.environ.get("FUNNY_PAGE_ID")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
MODE = (os.environ.get("MODE") or "reel").strip().lower()

PAGE_NAME = "Hansi Ka Adda"
GRAPH_VER = "v23.0"
HISTORY_FILE = "funny_history.json"
REPORT_FILE = "funny_last_run.json"
WORK = "work_funny"
FONTS_DIR = os.path.abspath("fonts")
FONT = "Noto Naskh Arabic"
VOICE = "ur-PK-AsadNeural"
VOICE_RATE = "+0%"
VOICE_PITCH = "+8Hz"            # thori mazahiya awaaz
MODEL_CANDIDATES = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-3.5-flash-lite"]

ANIMALS = ["cat", "kitten", "dog", "puppy", "goat", "monkey", "duck", "parrot", "cow",
           "chicken", "rooster", "panda", "horse", "donkey", "sheep", "rabbit", "squirrel",
           "penguin", "camel", "elephant", "bear", "fox", "hamster", "owl", "turtle", "pig",
           "llama", "seal", "raccoon", "meerkat"]

SITUATIONS = [
    "school / tuition", "exams and results", "shaadi (wedding) season", "cricket match",
    "Eid shopping", "office / job interview", "mobile phone addiction", "diet and gym",
    "ammi ki daant (mother's scolding)", "guests arriving at home", "monday morning",
    "online shopping", "load of homework", "cooking disaster", "road trip", "bijli ka bill",
    "rishta aunty", "sleeping late and waking late", "salary day", "friends' group chat",
    "teacher vs students", "summer heat", "winter mornings", "street food", "barish (rain)",
    "petrol price and bike", "wedding food (shaadi ka khaana) rush", "cousin ki shaadi dance practice",
    "gas load shedding and cold water", "rickshaw / Careem bargaining", "bargaining in bazaar",
    "neighbour aunty's gossip", "family WhatsApp group forwards", "dentist visit", "barber shop",
    "first day at gym", "buying a new phone", "phone battery 1%", "wifi password at relatives' house",
    "Sunday breakfast halwa puri", "chai addiction", "fridge raid at midnight", "fake diet plans",
    "selfie / TikTok craze", "village cousins visiting city", "traffic jam", "motorway road trip",
    "PSL / cricket fans", "relatives asking 'kitne number aaye' and 'shaadi kab'", "power nap at office",
    "bank queue", "government office file", "ATM out of cash", "parking fight", "ice cream truck",
    "Ramzan sehri wake up", "Eid ul Adha bakra mandi", "Eidi collection", "mehndi function",
    "moving to a new house", "plumber who never comes on time", "mechanic's 'sirf 5 minute'",
    "online class mute button", "group project where one does all work", "freelancing client",
    "gaming addiction (PUBG / Ludo)", "Ludo fights at home", "remote control fight", "AC vs electricity bill",
    "mosquito season", "pigeon / kabootar baazi", "pet cat ruling the house", "grandma's home remedies",
    "laundry day", "lost TV remote", "aunties at a wedding judging food", "train journey",
]

STYLES = [
    "the animal's inner thoughts, like a Pakistani person complaining about daily life",
    "a cricket-commentary style narration of what the animal is doing",
    "the animal acting like a desi aunty / uncle giving advice",
    "the animal as a lazy employee on Monday morning",
    "the animal as a student before exams",
    "a dramatic TV-serial style narration (saas-bahu drama) of the animal's life",
    "the animal giving a news report like a breaking-news anchor",
    "the animal planning a wedding / shaadi",
    "a nature-documentary narrator who takes the animal far too seriously",
    "the animal as a food vlogger reviewing everything",
    "the animal as a motivational speaker giving terrible advice",
    "the animal as a strict PT teacher",
    "the animal as a property dealer selling its home",
    "the animal giving a cooking show like a famous chef",
    "the animal as a cricket player at a press conference",
    "the animal as a government officer who says 'kal aana'",
    "the animal as a shopkeeper bargaining",
    "the animal as a tour guide",
]

# Reel ke alag andaaz - har dafa pichhle se mukhtalif (ek hi pattern bar bar na ho)
REEL_FORMATS = {
    "voiceover": "One {animal} talks in first person about the topic (classic funny voice-over).",
    "latifay": "3 short, clean, NEW Urdu jokes (latifay) about the topic, one after another, each with its own "
               "punchline. Never use old famous jokes. The {animal} clips just play along.",
    "paheli": "A funny riddle (paheli) about the topic: ask it in scene 1, give silly wrong guesses in the "
              "middle scenes, reveal the surprising funny answer in the last scene. Ask viewers to comment "
              "their guess before the answer.",
    "kya_hota_agar": "'Kya hota agar...' - a funny 'what if' story: what if the {animal} had to deal with "
                     "this topic for a day. Escalating chaos, twist ending.",
    "types": "'Types of people' video about the topic: each scene is ONE type of person, played by a DIFFERENT "
             "animal (give a different 'animal' in each scene), e.g. 'type 1: the one who...'.",
    "expectation": "'Expectation vs Reality' about the topic: first scenes show the dream, then the funny reality.",
    "news": "A fake funny 'breaking news' bulletin about the topic, read by the {animal} as a news anchor, "
            "with an on-the-spot reporter and a silly twist.",
}

PEOPLE_FORMATS = {
    "pov": "'POV / Jab...' reel: the viewer IS the person in the situation, each scene a funnier escalation.",
    "latifay": "3 short, clean, NEW Urdu jokes (latifay) about the topic with desi characters, each with its own punchline. Never old famous jokes.",
    "types": "'Types of people' about the topic: each scene is ONE type of person ('type 1: woh jo...').",
    "expectation": "'Expectation vs Reality' about the topic: first scenes the dream, then the painfully funny reality.",
    "har_ghar": "'Har ghar mein...' - the funny things that happen in EVERY Pakistani home in this situation.",
    "kya_hota_agar": "'Kya hota agar...' - a funny what-if: escalating chaos, twist ending.",
    "news": "A fake funny 'breaking news' bulletin about the topic with an on-the-spot reporter and a silly twist.",
    "dialogue": "A short funny conversation between two desi characters (e.g. ammi and beta, dukandaar and customer); the narrator voices both, naming who speaks.",
}

PEOPLE_STYLES = [
    "observational desi comedy - 'har kisi ke saath hota hai'", "dramatic TV-serial narration of a tiny problem",
    "cricket-commentary style narration of an everyday moment", "sarcastic narrator roasting the situation (gently)",
    "over-the-top breaking-news style", "a desi aunty's commentary", "a lazy student's confessions",
    "a middle-class abbu's logic", "a motivational speaker giving terrible advice",
    "nature-documentary narrator describing desi people", "a strict ammi's rules explained",
]

RULES = """Humor rules (very important):
- Clean family-friendly comedy only: no abuse, no vulgar words, no double meaning.
- Never make fun of any religion, sect, ethnicity, region, language, gender or disability.
- No politics, no real people's names.
- Write in simple spoken Pakistani URDU in Urdu script (not Roman Urdu). Short punchy lines.
- Spoken sentences only: no emojis, no stage directions, no symbols."""

os.makedirs(WORK, exist_ok=True)
REPORT = {"mode": MODE, "stock_clips": 0, "fallback_clips": 0, "errors": []}
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
                        response_mime_type="application/json", temperature=1.0))
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
            return groq_backup.ask_json(prompt, 1.0, log)
        except Exception as e:
            last = f"{last} | {e}"
    raise RuntimeError(f"Gemini fail: {last}")


def fbrain():
    try:
        with open("funny_brain.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def wpick(options, mult_key):
    """Agent ke seekhe weights se chunao (jo zyada hansaya wo zyada, baqi bhi kabhi kabhi)."""
    m = fbrain().get(mult_key) or {}
    options = list(options)
    return random.choices(options, weights=[float(m.get(o, 1)) for o in options])[0]


def punch_up(data, who):
    """Writers' room: head writer draft ko sakhti se parakhta hai aur zyada mazahiya bana kar wapas deta hai."""
    scenes = data.get("scenes") or []
    draft = {"title": data.get("title"), "meme": data.get("meme"), "caption": data.get("caption"),
             "scenes": [{"text": sc.get("text"), "shows": sc.get("visual")} for sc in scenes]}
    try:
        j = ask_json(f"""You are the HEAD WRITER of Pakistan's funniest Facebook comedy page "{PAGE_NAME}".
A junior writer wrote this Urdu reel script ({who}). Most AI comedy is NOT funny: generic, explains the joke,
predictable, no real punchline. Be brutally honest and fix that.

DRAFT (JSON): {json.dumps(draft, ensure_ascii=False)}

1. Rate how hard a normal Pakistani viewer would actually laugh (1-10).
2. REWRITE it much funnier:
   - Line 1 = scroll-stopping hook from a moment EVERY desi has lived.
   - Specific desi details instead of generic words (exact things ammi says, the 'sirf 5 minute' mechanic, the
     cousin who..., prices, excuses), big exaggeration, comic timing: setup -> misdirection -> punchline.
   - Every scene must have a laugh or set up the next one; cut explanations and filler; never explain a joke.
   - The LAST punchline must be an unexpected twist people want to tag a friend for.
   - Keep the closing line "ایسی مزید ویڈیوز کے لیے فالو کریں" at the very end.
   - Keep EXACTLY {len(scenes)} scenes in the same order; each scene's text must still match what "shows" shows.
   - About the same length (90-115 words total).
{RULES}
Return JSON: {{"score_before": 1-10, "score_after": 1-10, "title": "funnier Urdu title, max 60 chars",
 "meme": "short Urdu meme header, max 7 words", "caption": "1 funny Urdu line asking to tag a friend",
 "scenes": [{{"text": "...", "laugh": true/false}}]}}""")
        new = j.get("scenes") or []
        if len(new) != len(scenes) or sum(len((x.get("text") or "").split()) for x in new) < 60:
            raise RuntimeError("editor ne scenes badal diye")
        for sc, n in zip(scenes, new):
            if (n.get("text") or "").strip():
                sc["text"] = n["text"].strip()
                sc["laugh"] = bool(n.get("laugh", sc.get("laugh")))
        for k in ("title", "meme", "caption"):
            if (j.get(k) or "").strip():
                data[k] = j[k].strip()
        REPORT["funny_score"] = f"{j.get('score_before')} -> {j.get('score_after')}"
        log(f"Writers' room: hansi score {REPORT['funny_score']}")
    except Exception as e:
        log(f"punch-up skip: {str(e)[:150]}")
    return data


def word_count(script):
    return sum(len((s.get("text") or "").split()) for s in script.get("scenes", []))


def _search_part(situation):
    """Is topic par asal YouTube searches (gl=PK). Fail ho to khali - purana tareeqa chale."""
    key = situation.split("(")[0].split("/")[0].strip()
    try:
        import search_demand
        searches = search_demand.suggestions([f"{key} funny", f"{key} comedy"], "ur", "PK")
    except Exception as e:
        log(f"search suggestions fail: {e}")
        searches = []
    log(f"Search phrases: {searches[:12]}")
    REPORT["search_phrases"] = searches[:20]
    if not searches:
        return "", ""
    return searches, f"""
REAL phrases Pakistanis are typing into YouTube search about this topic right now:
{json.dumps(searches, ensure_ascii=False)}
If one fits this topic and the rules, build the joke around it so the video truly matches that search,
and put its key words naturally in the title - the title must honestly describe the video (no clickbait).
IGNORE phrases that name a real person, celebrity, YouTuber, channel, drama, brand, or are about news,
politics or real tragedies."""


def _take_phrase(data, searches):
    phrase = (data.get("search_phrase") or "").strip() if searches else ""
    data["search_phrase"] = phrase
    if phrase:
        REPORT["search"] = phrase


SEARCH_FIELD = ',\n "search_phrase": "the exact real search phrase from the list you used, or empty"'


def write_reel(history, people=False):
    used = [h["title"] for h in history[-120:]]
    recent_animals = [h.get("animal") for h in history[-8:]]
    animal = "people" if people else random.choice([a for a in ANIMALS if a not in recent_animals])
    recent_styles = [h.get("style") for h in history[-6:]]
    style = random.choice([x for x in STYLES if x not in recent_styles] or STYLES)
    recent_topics = {h.get("topic") for h in history[-40:]}
    situation = wpick([x for x in SITUATIONS if x not in recent_topics] or SITUATIONS, "topic_mult")
    recent_fmts = [h.get("reel_format") for h in history[-4:]]
    fmts = PEOPLE_FORMATS if people else REEL_FORMATS
    rfmt = os.environ.get("REEL_FORMAT") or wpick([k for k in fmts if k not in recent_fmts] or list(fmts),
                                                  "reel_format_mult")
    searches, search_txt = _search_part(situation)
    import content_rules
    if people:
        recent_styles = [h.get("style") for h in history[-6:]]
        style = wpick([x for x in PEOPLE_STYLES if x not in recent_styles] or PEOPLE_STYLES, "style_mult")
        data = ask_json(f"""You write VIRAL funny Facebook Reels for the Pakistani comedy page "{PAGE_NAME}".{content_rules.text("funny")}
The page is pure COMEDY about everyday desi life - people must laugh out loud (lot pot), share it and tag friends.
Comedy style: {style}.
REEL FORMAT (follow this, it decides the whole structure): {PEOPLE_FORMATS[rfmt]}
Today's topic (relatable everyday Pakistani situation): {situation}.{search_txt}
Invent a FRESH, ORIGINAL joke idea about this topic - never reuse an idea from these past titles:
{json.dumps(used, ensure_ascii=False)}

Write a 100-word Urdu voice-over (about 40 seconds) shown over real stock clips of PEOPLE.
Make it GENUINELY hilarious: one super-relatable moment everybody has lived, big exaggeration, desi
characters (ammi, abbu, chachu, phupho, bhabhi, dost, teacher, dukandaar), desi references (chai, biryani,
load shedding, WhatsApp, rishta, cricket), short punchy lines, a twist punchline at the end.
Line 1 is a hook that makes people stop scrolling (e.g. "Har ghar mein ek aisa banda hota hai...").
After the punchline end with: "ایسی مزید ویڈیوز کے لیے فالو کریں"
{RULES}

Split into exactly 5 scenes. For each scene give a 2-5 word ENGLISH stock-video search term showing PEOPLE
doing what that line says, with a clear expression (e.g. "man laughing phone", "woman angry kitchen",
"student sleeping desk", "family dinner table", "man shocked bill", "friends laughing cafe").

{VISUALS_RULE}
Return JSON: {{"title": "funny Urdu title, max 60 characters",
 "meme": "very short meme header in Urdu shown on top of the whole reel, max 7 words, like a POV line",
 "scenes": [{{"text": "...", "visual": "...", "visuals": ["...", "..."], "laugh": true/false}}] ("laugh": true if this scene ends with a punchline (about half the scenes), else false),
 "caption": "1 funny line in Urdu that asks people to tag a friend",
 "hashtags": ["#funny", "..."] (6 hashtags, English and Urdu){SEARCH_FIELD if searches else ""}}}""")
    else:
        data = ask_json(f"""You write viral funny Facebook Reels for the Pakistani page "{PAGE_NAME}".{content_rules.text("funny")}
    Animal: {animal}. Comedy style: {style}.
    REEL FORMAT (follow this, it decides the whole structure): {REEL_FORMATS[rfmt].format(animal=animal)}
    Today's topic (relatable everyday Pakistani situation): {situation}.{search_txt}
    Invent a FRESH joke idea about this topic - never reuse an idea from these past titles:
    {json.dumps(used, ensure_ascii=False)}

    Write a 100-word Urdu voice-over (about 40 seconds) for stock clips of a {animal}.
    Follow the REEL FORMAT above for structure (the {animal} is the main character unless the format says otherwise).
    Make it GENUINELY funny: one relatable situation, exaggeration, desi references
    (ammi, abbu, chai, biryani, load shedding, WhatsApp, rishta, cricket), short punchy lines,
    and a surprising twist punchline at the end. Line 1 is a hook that makes people stop scrolling.
    Only refer to simple things any clip of a {animal} shows (looking, staring, sitting, eating,
    sleeping, walking, running) so the video always matches the words.
    After the punchline end with: "ایسی مزید ویڈیوز کے لیے فالو کریں"
    {RULES}

    Split into exactly 5 scenes. For each scene give a 1-3 word ENGLISH stock-video search term
    that will show a {animal} (e.g. "{animal}", "{animal} playing", "funny {animal}").

    {VISUALS_RULE}
    Return JSON: {{"title": "funny Urdu title, max 60 characters",
     "meme": "very short meme header in Urdu shown on top of the whole reel, max 7 words, like a POV line",
     "scenes": [{{"text": "...", "visual": "...", "visuals": ["...", "..."], "animal": "only for the types format: that scene's animal (one English word)", "laugh": true/false}}] ("laugh": true if this scene ends with a punchline or someone laughs (about half the scenes), else false),
     "caption": "1 funny line in Urdu that asks people to tag a friend",
     "hashtags": ["#funny", "..."] (6 hashtags, English and Urdu){SEARCH_FIELD if searches else ""}}}""")
    if len(data.get("scenes", [])) < 2:
        raise RuntimeError("Reel script mein scenes kam hain")
    data = punch_up(data, "desi people comedy" if people else f"funny {animal} voice-over")
    _take_phrase(data, searches)
    data["animal"] = animal
    data["topic"] = situation
    data["style"] = style
    data["reel_format"] = rfmt
    if rfmt != "types":
        for sc in data.get("scenes", []):
            sc.pop("animal", None)
    REPORT["reel_format"] = rfmt
    return data


def write_long(history):
    used = [h["title"] for h in history[-120:]]
    animals = random.sample(ANIMALS, 10)
    style = random.choice(STYLES)
    situation = SITUATIONS[(len(history) * 3 + 7) % len(SITUATIONS)]
    searches, search_txt = _search_part(situation)
    extra = ""
    best = None
    for _ in range(3):
        import content_rules
        data = ask_json(f"""You write funny Facebook videos for the Pakistani page "{PAGE_NAME}".{content_rules.text("funny")}
Make a 5-minute funny animal compilation with a running joke. Main comedy style: {style}.
Today's topic for the whole video (relatable everyday Pakistani situation): {situation}.{search_txt}
Every animal reacts to this topic in its own funny way.
Use these 10 animals, one segment each, in this order: {', '.join(animals)}.
These titles were already used: {json.dumps(used, ensure_ascii=False)}

Write the Urdu voice-over: each segment about 95 words (total about 950 words) - count carefully.
Segment 1 starts with a hook that makes people keep watching. Each animal talks in first person
like a typical desi person, with exaggeration, desi references (ammi, chai, biryani, WhatsApp, cricket)
and a surprising punchline. Only refer to simple actions any clip of that animal shows
(looking, sitting, eating, sleeping, walking, running).
Last segment ends with: "ویڈیو اچھی لگی ہو تو پیج فالو کریں اور دوستوں کو شیئر کریں"
{RULES}
{extra}

For each segment give a 1-3 word ENGLISH stock-video search term showing that animal.
{VISUALS_RULE}
Return JSON: {{"title": "funny Urdu title, max 70 characters",
 "scenes": [{{"text": "...", "visual": "...", "visuals": ["...", "..."], "meme": "very short funny Urdu header for this segment, max 7 words", "laugh": true/false}}] (exactly 10; "laugh": true if this scene ends with a punchline or someone laughs (about half the scenes), else false),
 "caption": "2 funny lines in Urdu asking people to comment their favourite animal",
 "hashtags": ["#funny", "..."] (8 hashtags){SEARCH_FIELD if searches else ""}}}""")
        n = word_count(data)
        log(f"Long script: {n} words")
        if len(data.get("scenes", [])) >= 5 and (best is None or n > word_count(best)):
            best = data
        if n >= 820:
            break
        extra = f"IMPORTANT: your last draft had only {n} words. Each segment must be about 100 words."
    if not best:
        raise RuntimeError("Lambi script nahi bani")
    for sc, a in zip(best["scenes"], animals):
        sc["animal"] = a
    best["animal"] = "compilation"
    _take_phrase(best, searches)
    best["topic"] = situation
    return best


# ---------------------------------------------------------------- audio
def tts(text, path):
    async def go():
        await edge_tts.Communicate(text, VOICE, rate=VOICE_RATE, pitch=VOICE_PITCH).save(path)
    for attempt in range(6):                                   # Microsoft kabhi kabhi rok deta hai
        try:
            asyncio.run(go())
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            log(f"TTS retry {attempt + 1}: {str(e)[:200]}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("Awaaz nahi bani")


# ---------------------------------------------------------------- clips
def pixabay_clips(query, count, job, prefix, backup, want_vertical=False, strict=True):
    got = []
    if backup == "people" and PEXELS_KEY:      # insaanon ki footage Pexels par behtar
        got += _pexels_people(query, count, job, prefix)
    if not PIXABAY_KEY:
        return got
    queries = []
    seeds = (query, f"{query} funny", "funny people laughing") if backup == "people" else \
        (f"funny {backup}", query if backup in query else f"{backup} {query}", backup)
    for q in seeds:
        if q not in queries:
            queries.append(q)
    for q in queries:
        if len(got) >= count:
            break
        try:
            r = requests.get("https://pixabay.com/api/videos/", timeout=40, params={
                "key": PIXABAY_KEY, "q": q, "safesearch": "true", "per_page": 40})
            r.raise_for_status()
            bad = ("animation", "3d", "cartoon", "render", "illustration", "christmas", "abstract")
            hits = [h for h in r.json().get("hits", []) if h["id"] not in USED_CLIPS
                    and (not strict or (bool(HUMAN & set(re.findall(r"[a-z]+", h.get("tags", "").lower())))
                                        if backup == "people" else backup.split()[-1] in h.get("tags", "").lower()))
                    and not any(b in h.get("tags", "").lower() for b in bad)]
        except Exception as e:
            log(f"Pixabay error ({q}): {str(e)[:150]}")
            continue
        random.shuffle(hits)
        if want_vertical:
            hits.sort(key=lambda h: 0 if (h.get("videos", {}).get("medium", {}).get("height", 0)
                                         > h.get("videos", {}).get("medium", {}).get("width", 1)) else 1)
        for h in hits:
            if len(got) >= count:
                break
            v = h.get("videos", {})
            pick = next((v[s] for s in ("large", "medium")
                         if v.get(s, {}).get("url") and v[s].get("width", 0) >= 1280), None)
            if not pick:
                continue
            path = os.path.join(job, f"{prefix}_{len(got)}.mp4")
            if os.path.exists(path):
                path = os.path.join(job, f"{prefix}_x{len(got)}.mp4")
            try:
                with requests.get(pick["url"], stream=True, timeout=180) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as f:
                        for chunk in resp.iter_content(1 << 20):
                            f.write(chunk)
                if os.path.getsize(path) > 50000:
                    USED_CLIPS.add(h["id"])
                    if _clip_ok(path, backup, query, h.get("duration", 10)) is False:
                        REPORT["clips_rejected"] = REPORT.get("clips_rejected", 0) + 1
                        continue
                    got.append(path)
            except Exception as e:
                log(f"Clip download fail: {str(e)[:150]}")
    return got


def _pexels_people(query, count, job, prefix):
    got = []
    for q in (query, " ".join(query.split()[:2])):
        if len(got) >= count:
            break
        try:
            r = requests.get("https://api.pexels.com/videos/search", timeout=40, headers={"Authorization": PEXELS_KEY},
                             params={"query": q, "per_page": 30})
            vids = r.json().get("videos", [])
        except Exception as e:
            log(f"Pexels error ({q}): {str(e)[:120]}")
            continue
        random.shuffle(vids)
        for v in vids:
            if len(got) >= count:
                break
            if f"pe{v['id']}" in USED_CLIPS:
                continue
            slug = set(re.findall(r"[a-z]+", (v.get("url") or "").lower()))
            if not HUMAN & slug:
                continue
            fs = sorted([f for f in v.get("video_files", []) if (f.get("width") or 0) >= 1080 and f.get("link")],
                        key=lambda f: f["width"])
            if not fs:
                continue
            path = os.path.join(job, f"{prefix}_pe{len(got)}.mp4")
            try:
                with requests.get(fs[0]["link"], stream=True, timeout=180) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as f:
                        for chunk in resp.iter_content(1 << 20):
                            f.write(chunk)
                USED_CLIPS.add(f"pe{v['id']}")
                if os.path.getsize(path) < 50000 or _clip_ok(path, "people", query, v.get("duration", 10)) is False:
                    REPORT["clips_rejected"] = REPORT.get("clips_rejected", 0) + 1
                    continue
                got.append(path)
            except Exception as e:
                log(f"Clip download fail: {str(e)[:150]}")
    return got


_VDEAD = set()


def _clip_ok(path, animal, query, dur):
    """Agent clip ka frame dekhta hai: asli {animal} hai, scene ki baat se milta hai, family-friendly hai?
    None = check na ho saka (tab tag wala match hi kaafi)."""
    import base64
    jpg = path + ".chk.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(float(dur) * 0.4, 4):.1f}", "-i", path,
                    "-frames:v", "1", "-vf", "scale=640:-2", jpg], capture_output=True)
    if not os.path.exists(jpg):
        return None
    img = base64.b64encode(open(jpg, "rb").read()).decode()
    if animal == "people":
        prompt = (f"Frame from a stock clip for a funny family-friendly Pakistani comedy reel. The scene needs: '{query}'. "
                  "Reply JSON {\"ok\": true/false}. ok = real people clearly doing roughly that (matching action/mood), "
                  "modestly dressed (no swimwear, no revealing clothes), no alcohol, no romance/kissing, "
                  "nothing sad, violent or adult.")
    else:
        prompt = (f"Frame from a stock clip for a funny family-friendly reel. The scene needs: '{query}' "
                  f"(main animal: {animal}). Reply JSON {{\"ok\": true/false}}. ok = it is a REAL {animal} (not cartoon/3D/toy), "
                  "clearly visible, and nothing sad, injured, dead, violent, or adult.")
    gk = os.environ.get("GROQ_API_KEY")
    for m in ("gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemma-4-31b-it", "gemma-4-26b-a4b-it"):
        if not GEMINI_KEY or m in _VDEAD:
            continue
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_KEY}",
                              timeout=25, json={"contents": [{"parts": [{"text": prompt},
                                                                         {"inline_data": {"mime_type": "image/jpeg", "data": img}}]}],
                                                "generationConfig": {"responseMimeType": "application/json", "temperature": 0}})
            if r.status_code in (401, 403, 404, 429):
                _VDEAD.add(m)
            r.raise_for_status()
            REPORT["vision_checks"] = REPORT.get("vision_checks", 0) + 1
            return bool(json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"]).get("ok"))
        except Exception as e:
            log(f"vision {m}: {str(e)[:90]}")
    import groq_vision
    d = groq_vision.ask_json([img], prompt)
    if d is not None:
        REPORT["vision_checks"] = REPORT.get("vision_checks", 0) + 1
        return bool(d.get("ok"))
    return None


def term_clips(terms, count, job, prefix, backup, w, h):
    """Har slot par WOHI cheez jo us waqt boli ja rahi hai (khaana, jagah, cheez, kaam) - sab platforms se.
    Video na mile to usi cheez ki asli photo (zoom ke saath)."""
    import footage
    got = []
    for j in range(count):
        term = terms[min(j * len(terms) // count, len(terms) - 1)] if terms else ""
        if not term:
            continue
        qw = footage.words(term)
        human = bool(HUMAN & set(qw))
        subject = "people" if human else (backup if backup != "people" and backup in term else term)
        done = False
        # pehle is cheez ki video, phir scene ki doosri boli gayi cheez ki video, photo sab se aakhir mein
        tries_k = [("video", term)] + [("video", t) for t in terms if t != term][:2] + [("photo", term)]
        for kind, term in tries_k:
            if done or (kind == "photo" and human):      # insaan ke kaam ki photo bejaan lagti hai
                continue
            qw = footage.words(term)
            cands = footage.videos(term, h > w) if kind == "video" else footage.photos(term)
            bad = ("animation", "3d", "cartoon", "render", "illustration", "abstract")
            cands = [c for c in cands if c["id"] not in USED_CLIPS and footage.match_score(c["text"], qw) > 0
                     and not any(b in c["text"] for b in bad)]
            random.shuffle(cands)
            cands.sort(key=lambda c: (-footage.match_score(c["text"], qw), c.get("vertical") != (h > w)))
            for c in cands[:5]:
                USED_CLIPS.add(c["id"])
                path = os.path.join(job, f"{prefix}_t{j}.mp4")
                src = path + (".jpg" if kind == "photo" else "")
                try:
                    if not footage.download(c["url"], src):
                        continue
                    if kind == "photo":
                        footage.photo_to_clip(src, path, w, h, secs=5)
                    ok = _clip_ok(path, subject, term, c.get("dur", 5) if kind == "video" else 2)
                    full = footage.match_score(c["text"], qw) == len(qw)
                    if ok is False or (ok is None and (kind == "photo" or not full)):
                        REPORT["clips_rejected"] = REPORT.get("clips_rejected", 0) + 1
                        continue
                    REPORT.setdefault("sources", {})
                    REPORT["sources"][c["src"]] = REPORT["sources"].get(c["src"], 0) + 1
                    got.append(path)
                    done = True
                    break
                except Exception as e:
                    log(f"clip fail ({term}): {str(e)[:120]}")
        if not done:
            REPORT.setdefault("no_match", []).append(terms[min(j * len(terms) // count, len(terms) - 1)])
    return got


def fallback_clip(path, w, h):
    c = random.choice([("0xff9a00", "0xff3d77"), ("0x00c6ff", "0x7a00ff"), ("0x11d483", "0xffd200")])
    run(["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"gradients=s={w}x{h}:c0={c[0]}:c1={c[1]}:speed=0.02:d=15",
         "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", path])


# ---------------------------------------------------------------- subtitles
def ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02}:{t % 60:05.2f}"


def ass_text(s):
    return s.replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def make_ass(path, text, total, w, h, title=None, meme=None):
    vertical = h > w
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT},{96 if vertical else 74},&H0000F0FF,&H0000F0FF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,7,3,{8 if vertical else 2},60,60,{1000 if vertical else 80},1
Style: Meme,{FONT},{70 if vertical else 60},&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,1,0,0,0,100,100,0,0,3,22,0,8,50,50,{170 if vertical else 50},1
Style: Title,{FONT},{80 if vertical else 72},&H00FFFFFF,&H00FFFFFF,&H002A2AE0,&H002A2AE0,1,0,0,0,100,100,0,0,3,18,0,8,60,60,{300 if vertical else 80},1
Style: Mark,Noto Sans,{32 if vertical else 28},&H40FFFFFF,&H40FFFFFF,&H80000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,9,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = [f"Dialogue: 0,{ass_time(0)},{ass_time(total + 1)},Mark,,0,0,0,,{PAGE_NAME}"]
    if meme:
        ev.append(f"Dialogue: 1,{ass_time(0)},{ass_time(total + 1)},Meme,,0,0,0,,{ass_text(meme)}")
    elif title:
        ev.append(f"Dialogue: 1,{ass_time(0.2)},{ass_time(min(4.5, total))},Title,,0,0,0,,"
                  f"{{\\fad(300,400)}}{ass_text(title)}")
    words = text.split()
    n = 4 if vertical else 6
    chunks = [" ".join(words[i:i + n]) for i in range(0, len(words), n)]
    weights = [len(c) + 3 for c in chunks]
    scale = total / max(sum(weights), 1)
    t = 0.0
    for c, wgt in zip(chunks, weights):
        end = t + wgt * scale
        # halka "pop" effect: shuru mein thora bara, phir normal
        ev.append(f"Dialogue: 2,{ass_time(t)},{ass_time(end)},Sub,,0,0,0,,"
                  f"{{\\fscx115\\fscy115\\t(0,120,\\fscx100\\fscy100)}}{ass_text(c)}")
        t = end
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(ev) + "\n")


# ---------------------------------------------------------------- video
def build_scene(job, i, sc, w, h, title, backup, meme=None):
    text = (sc.get("text") or "").strip()
    audio = f"a{i}.mp3"
    tts(text, os.path.join(job, audio))
    dur = duration(os.path.join(job, audio)) + 0.4
    if sc.get("laugh"):
        dur += 1.8                                          # hansi ke liye jagah
    k = max(1, min(6, round(dur / 4)))                      # har ~4 sec naya clip
    import footage
    terms = footage.scene_terms(sc)
    clips = term_clips(terms, max(k, min(6, len(terms))), job, f"c{i}", backup, w, h) if terms else []
    if len(clips) < k:   # baqi jagah purane tareeqe se (us scene ke kaam/janwar ki clips)
        clips += pixabay_clips(sc.get("visual") or backup, k - len(clips), job, f"c{i}", backup, want_vertical=h > w)
    if not clips:   # sakht filter se kuch na mile to naram filter
        clips = pixabay_clips(sc.get("visual") or backup, k, job, f"c{i}", backup,
                              want_vertical=h > w, strict=False)
    REPORT["stock_clips"] += len(clips)
    if not clips:
        REPORT["fallback_clips"] += 1
        fb = os.path.join(job, f"c{i}_fb.mp4")
        fallback_clip(fb, w, h)
        clips = [fb]
    k = len(clips)
    seg = dur / k
    make_ass(os.path.join(job, f"s{i}.ass"), text, dur - 0.4, w, h, title, meme)
    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd += ["-stream_loop", "-1", "-t", f"{seg + 0.2:.2f}", "-i", os.path.basename(c)]
    cmd += ["-i", audio]
    chains = []
    for j in range(k):
        chains.append(
            f"[{j}:v]fps=30,trim=duration={seg:.2f},setpts=PTS-STARTPTS,split[a{j}][b{j}];"
            f"[a{j}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"boxblur=25:2,eq=brightness=-0.15[bg{j}];"
            f"[b{j}]scale={w}:{h}:force_original_aspect_ratio=decrease[fg{j}];"
            f"[bg{j}][fg{j}]overlay=(W-w)/2:(H-h)/2,setsar=1[v{j}]")
    fontsdir = f":fontsdir={FONTS_DIR}" if os.path.isdir(FONTS_DIR) else ""
    chains.append("".join(f"[v{j}]" for j in range(k)) +
                  f"concat=n={k}:v=1:a=0,eq=saturation=1.25:contrast=1.05,"
                  f"subtitles=s{i}.ass{fontsdir},format=yuv420p[v]")
    cmd += ["-filter_complex", ";".join(chains), "-map", "[v]", "-map", f"{k}:a:0",
            "-af", "apad", "-t", f"{dur:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", f"p{i}.mp4"]
    run(cmd, cwd=job)
    return f"p{i}.mp4"


def build_video(script, tag, w, h, out_path):
    job = os.path.join(WORK, tag)
    shutil.rmtree(job, ignore_errors=True)
    os.makedirs(job)
    scenes = [s for s in script["scenes"] if (s.get("text") or "").strip()]
    parts = []
    if scenes:
        scenes[-1]["laugh"] = True
    for i, sc in enumerate(scenes):
        if sfx.is_funny_text(sc.get("text")):
            sc["laugh"] = True
        backup = sc.get("animal") or script["animal"]
        meme = script.get("meme") if h > w else sc.get("meme")
        parts.append(build_scene(job, i, sc, w, h, script["title"] if i == 0 else None, backup, meme))
        log(f"{tag}: scene {i + 1}/{len(scenes)} ready")
    with open(os.path.join(job, "list.txt"), "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy",
         "-movflags", "+faststart", os.path.abspath(out_path)], cwd=job)
    laugh_at, t = [], 0.0
    for p, sc in zip(parts, scenes):
        t += duration(os.path.join(job, p))
        if sc.get("laugh"):
            laugh_at.append(t - 2.1)
    REPORT["laughs"] = REPORT.get("laughs", 0) + sfx.add_laughs(os.path.abspath(out_path), laugh_at)
    REPORT[f"{tag}_minutes"] = round(duration(out_path) / 60, 2)
    log(f"{tag}: video {REPORT[f'{tag}_minutes']} min")


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


def description(script, is_reel=True):
    import seo
    text = " ".join((sc.get("text") or "") for sc in script.get("scenes", []))
    if not text and script.get("chats"):
        text = " ".join(m.get("text", "") for c in script["chats"] for m in c.get("messages", []))
    return seo.build(ask_json, "funny", script["title"], text or script.get("caption", ""), "ur", is_reel)


# ---------------------------------------------------------------- main
def write_report():
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=1)


def youtube(path, title, desc, short, entry):
    """Facebook ke baad wahi video "Hansi Ka Adda" YouTube channel par. Fail ho to sirf report mein."""
    import yt
    if not yt.enabled("funny"):
        return
    if short:                              # YouTube par roz sirf 1 reel (Pakistan din ke hisaab se)
        pk_today = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
        for h in load_history():
            d = (datetime.datetime.strptime(h["date"], "%Y-%m-%d %H:%M")
                 + datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
            if h.get("mode") == "reel" and h.get("yt_id") and d == pk_today:
                log("YouTube: aaj ki reel pehle hi lag chuki - sirf Facebook")
                return
    try:
        entry["yt_id"] = yt.upload("funny", path, title, desc, short=short, lang="ur", category="23")
    except Exception as e:
        log(f"YOUTUBE ERROR: {e}")
        REPORT["errors"].append(f"youtube: {str(e)[:300]}")


def _main():
    if not DRY_RUN and (not FB_TOKEN or not FB_PAGE):
        raise RuntimeError("FUNNY_PAGE_TOKEN ya FUNNY_PAGE_ID secret missing hai")
    global MODE
    history = load_history()
    now = datetime.datetime.utcnow()
    if MODE == "auto":
        # GitHub ke scheduled runs kabhi late/skip ho jate hain, is liye history se faisla:
        # aaj (Pakistan waqt) lambi video nahi gayi aur shaam ho chuki hai -> lambi video
        pk_today = (now + datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
        long_today = any(h.get("mode") == "long" and
                         (datetime.datetime.strptime(h["date"], "%Y-%m-%d %H:%M")
                          + datetime.timedelta(hours=5)).strftime("%Y-%m-%d") == pk_today
                         for h in history)
        import slot_wait
        pk_hour = ((slot_wait.target_time() or now).hour + 5) % 24
        MODE = "long" if (not long_today and pk_hour >= 19) else "reel"
    entry = {"date": now.strftime("%Y-%m-%d %H:%M"), "mode": MODE}
    import chat_comedy
    if MODE == "long":
        # lambi video: har din alag qism - pichhli 2 se mukhtalif
        recent_long = [h.get("format") for h in history if h.get("mode") == "long"][-2:]
        fmt = os.environ.get("FORMAT") or random.choice(
            [f for f in ("story", "cartoon", "chat") if f not in recent_long] or ["story"])
    else:
        # roz sirf 1 chat reel, baaqi janwar wali
        pk_today = (now + datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
        chat_today = sum(1 for h in history if h.get("mode") == "reel" and h.get("format") == "chat"
                         and (datetime.datetime.strptime(h["date"], "%Y-%m-%d %H:%M")
                              + datetime.timedelta(hours=5)).strftime("%Y-%m-%d") == pk_today)
        # FB originality: har reel pichhli se alag format; cartoon kabhi kabhi (2 din mein zyada se zyada 1), roz pakka kuch nahi
        reels = [h for h in history if h.get("mode") == "reel"]
        last_fmt = reels[-1].get("format") if reels else None
        cut = (now - datetime.timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        cartoon_recent = any(h.get("format") == "cartoon" and h["date"] >= cut for h in reels)
        # janwar nahi - asli desi insaanon wali comedy zyada, chat kabhi, cartoon kabhi kabhi
        pool = {"people": 5, "chat": 2, "cartoon": 0 if cartoon_recent else 1}
        if last_fmt != "people":      # people reels ke andar format khud badalta hai
            pool.pop(last_fmt, None)
        if chat_today >= 1:
            pool.pop("chat", None)
        fmult = fbrain().get("format_mult") or {}
        pool = {k: v * float(fmult.get(k, 1)) for k, v in pool.items() if v} or {"people": 1}
        fmt = os.environ.get("FORMAT") or random.choices(list(pool), weights=list(pool.values()))[0]
    entry["format"] = fmt
    REPORT["format"] = fmt
    if MODE == "long":
        if fmt == "animal":
            script = write_long(history)
            build_video(script, "long", 1920, 1080, "funny_long.mp4")
        elif fmt in ("story", "ai", "cartoon"):
            import story
            script = story.build_long(history, "funny_long.mp4",
                                      force_style=fmt if fmt in ("ai", "cartoon") else None)
            REPORT["long_minutes"] = round(duration("funny_long.mp4") / 60, 2)
            REPORT["series"] = f"{script['series_title']} part {script['part']} ({script['style']})"
            import funny as _f   # story module apni REPORT copy mein ginti rakhta hai
            REPORT["stock_clips"] = _f.REPORT.get("stock_clips", 0)
            REPORT["fallback_clips"] = _f.REPORT.get("fallback_clips", 0)
        else:
            script = chat_comedy.build_long(history, "funny_long.mp4")
        REPORT["long_minutes"] = round(duration("funny_long.mp4") / 60, 2)
        if not DRY_RUN:
            desc = description(script, is_reel=False)
            import slot_wait; slot_wait.wait(log)
            entry["id"] = post_long("funny_long.mp4", script["title"], desc)
            youtube("funny_long.mp4", script["title"], desc, False, entry)
            import social
            social.share_long("funny", "funny_long.mp4", desc, entry, REPORT, log)
    else:
        if fmt in ("people", "animal"):
            script = write_reel(history, people=(fmt == "people"))
            build_video(script, "reel", 1080, 1920, "funny_reel.mp4")
        elif fmt == "cartoon":
            import story
            script = story.build_reel(history, "funny_reel.mp4")
            REPORT["reel_minutes"] = round(duration("funny_reel.mp4") / 60, 2)
        else:
            script = chat_comedy.build_reel(history, "funny_reel.mp4")
            REPORT["reel_minutes"] = round(duration("funny_reel.mp4") / 60, 2)
        if duration("funny_reel.mp4") > 89:
            run(["ffmpeg", "-y", "-i", "funny_reel.mp4", "-t", "89", "-c", "copy", "cut.mp4"])
            shutil.move("cut.mp4", "funny_reel.mp4")
        if not DRY_RUN:
            desc = description(script)
            import slot_wait; slot_wait.wait(log)
            entry["id"] = post_reel("funny_reel.mp4", desc)
            youtube("funny_reel.mp4", script["title"], desc, True, entry)
            import social
            social.share_reel("funny", FB_PAGE, FB_TOKEN, "funny_reel.mp4", desc, entry, REPORT, log)
    entry.update({"title": script["title"], "animal": script["animal"], "topic": script.get("topic")})
    if script.get("search_phrase"):
        entry["search"] = script["search_phrase"]
    for key in ("series", "series_title", "part", "summary", "style", "reel_format"):
        if script.get(key) is not None:
            entry[key] = script[key]
    import funny as _f          # doosre modules ki ginti isi report mein
    REPORT["laughs"] = REPORT.get("laughs", 0) + (_f.REPORT.get("laughs", 0) if _f.REPORT is not REPORT else 0)
    REPORT.update({"time_utc": entry["date"], "title": script["title"], "dry_run": DRY_RUN})
    write_report()
    if not DRY_RUN:
        history.append(entry)
        save_history(history)
    log("Done successfully!")


def main():
    try:
        _main()
    except Exception as e:
        REPORT["errors"].append(f"fatal: {str(e)[:400]}")
        write_report()
        raise


if __name__ == "__main__":
    main()
