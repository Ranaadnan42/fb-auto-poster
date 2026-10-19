"""
Cinematic AI Story Shorts - YouTube channel (aur chahein to Facebook page) par roz khud upload.

Har run:
 1. Gemini nayi epic kahani ki qist likhta hai (Urdu narration, 3 qiston ki series, cliffhanger)
 2. Har scene ki AI tasveerein FREE - GitHub ke CPU par open-source sd-turbo model (free_images.py);
    Pollinations sirf tab jab POLLINATIONS_TOKEN ho, Pixabay aakhri backup
 3. Layout aap ki sample video jaisa: upar title, beech mein tasveer (zoom/pan), peeche blur, neeche subtitles
 4. Urdu awaaz (Edge TTS) + halki dramatic background music (khud banti hai, copyright free)
 5. 1080x1920, ~2.5 minute -> YouTube Short + (optional) Facebook page video

Secrets:
  GEMINI_API_KEY                                   (zaroori)
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN  (YouTube upload)
  CINE_FB_PAGE_ID, CINE_FB_TOKEN                   (optional - Facebook page par bhi)
  POLLINATIONS_TOKEN                               (optional - zyada tez tasveerein)
  PIXABAY_API_KEY                                  (optional - tasveer na bane to backup)
  CHANNEL_NAME                                     (optional - video par watermark)
DRY_RUN=1 -> video banegi, upload nahi hogi.
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
import urllib.parse

import requests

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
POLL_TOKEN = os.environ.get("POLLINATIONS_TOKEN")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY")
GENRE = (os.environ.get("GENRE") or "fantasy").strip().lower()  # fantasy = Legends Untold, movie = movie recap channel
if GENRE not in ("fantasy", "movie"):
    GENRE = "fantasy"
MOVIE = GENRE == "movie"
if MOVIE:   # movie channel ki apni YouTube chaabi (aur chahein to apna Google project)
    YT_ID = os.environ.get("YT_MOVIE_CLIENT_ID") or os.environ.get("YT_CLIENT_ID")
    YT_SECRET = os.environ.get("YT_MOVIE_CLIENT_SECRET") or os.environ.get("YT_CLIENT_SECRET")
    YT_REFRESH = os.environ.get("YT_MOVIE_REFRESH_TOKEN")
else:
    YT_ID = os.environ.get("YT_CLIENT_ID")
    YT_SECRET = os.environ.get("YT_CLIENT_SECRET")
    YT_REFRESH = os.environ.get("YT_REFRESH_TOKEN")
FB_PAGE = None if MOVIE else os.environ.get("CINE_FB_PAGE_ID")
FB_TOKEN = None if MOVIE else os.environ.get("CINE_FB_TOKEN")
CHANNEL = (os.environ.get("CHANNEL_NAME") or "").strip()
DRY_RUN = os.environ.get("DRY_RUN") == "1"
LANG = (os.environ.get("LANGUAGE") or "en").strip().lower()      # en = dollar wali audience
MODE = (os.environ.get("MODE") or "short").strip().lower()       # short (~2.5 min) / long (~9 min)
if LANG not in ("en", "ur"):
    LANG = "en"
if MODE not in ("short", "long"):
    MODE = "short"
LONG = MODE == "long"

W, H = (1920, 1080) if LONG else (1080, 1920)
IMG = 1080                      # short: beech wali square tasveer
IMG_Y = 430                     # short: tasveer upar se kitni neeche
SCENES = 34 if LONG else 10                  # Short 3 minute se kam rahe (warna Short nahi ginta)
SHOTS = 2 if LONG else 3                     # Shorts mein tez cuts
if LANG == "en":
    VOICE, RATE, FONT = "en-US-ChristopherNeural", "-4%", "Noto Sans"
    WORDS = "30-36 English words"
    LANGUAGE_TXT = ("simple, gripping spoken ENGLISH like a movie-trailer storyteller for a US/UK "
                    "audience: short punchy sentences, suspense, action, emotion")
    TITLE_LANG, CLIFF = "English", "What happened next? Watch the next part."
    PART_WORD, SUB_TXT = "Part", "Subscribe for the next part 🔔"
else:
    VOICE, RATE, FONT = "ur-PK-AsadNeural", "+0%", "Noto Naskh Arabic"
    WORDS = "24-30 Urdu words"
    LANGUAGE_TXT = ("simple, gripping spoken Pakistani URDU in Urdu script (not Roman Urdu), like a "
                    "dramatic storyteller: short punchy sentences, suspense, action, emotion")
    TITLE_LANG, CLIFF = "Urdu script", "آگے کیا ہوا؟ اگلا حصہ ضرور دیکھیں"
    PART_WORD, SUB_TXT = "حصہ", "مزید کہانیوں کے لیے چینل کو سبسکرائب کریں 🔔"
FONTS_DIR = os.path.abspath("fonts")
_G = "movie_" if MOVIE else ""
HISTORY_FILE = f"cinematic_{_G}{LANG}_{MODE}_history.json"
REPORT_FILE = f"cinematic_{_G}{LANG}_{MODE}_last_run.json"
WORK = "work_cine"
PARTS = 1 if (LONG or MOVIE) else 3
if MOVIE and not LONG:
    SCENES = 10                 # Short 3 minute se kam rahe (YouTube Shorts ki had)
MODELS = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
GRAPH_VER = "v23.0"

WORLDS = [
    "a frozen snow kingdom with ancient stone ruins and mythical beasts",
    "a dark misty jungle with a lost golden temple",
    "a vast desert with sand storms, a hidden oasis city and a desert dragon",
    "towering mountains where a lone warrior protects a village from a giant beast",
    "a stormy sea, a pirate ship and a sea monster",
    "an ancient kingdom under siege by a cursed army",
    "a mysterious forest where animals talk and a half-human creature hunts",
    "a volcanic land with fire creatures and a brave young blacksmith",
    "a hidden valley of giants and a boy who befriends one",
    "a cursed castle on a cliff and a princess who is secretly a warrior",
]

LOOK = ("cinematic still, photorealistic, dramatic lighting, shallow depth of field, ultra detailed, "
        "epic fantasy movie scene, 35mm film, no text, no watermark")

if MOVIE:
    SUB_TXT = "Subscribe for a new movie recap every day 🔔" if LANG == "en" else "روز نئی فلم کی کہانی کے لیے سبسکرائب کریں 🔔"
    LOOK = ("cinematic movie still, photorealistic, dramatic lighting, ultra detailed, 35mm film, "
            "original characters that do not resemble any real actor, no logos, no text, no watermark")

os.makedirs(WORK, exist_ok=True)
REPORT = {"images_ai": 0, "images_backup": 0, "images_failed": 0, "errors": []}


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
        json.dump(h[-400:], f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- Gemini
_client = None


def ask_json(prompt):
    global _client
    from google import genai
    from google.genai import types
    if _client is None:
        _client = genai.Client(api_key=GEMINI_KEY)
    last = None
    for model in MODELS:
        for attempt in range(2):
            try:
                res = _client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=0.95))
                log(f"Gemini model: {model}")
                return json.loads(res.text)
            except Exception as e:
                last = e
                log(f"{model} try {attempt + 1} failed: {str(e)[:200]}")
                time.sleep(4)
    raise RuntimeError(f"Gemini fail: {last}")


def series_state(history):
    if history and history[-1].get("part", PARTS) < PARTS:
        last = history[-1]
        prev = [h for h in history if h.get("series") == last["series"]]
        return {"series": last["series"], "series_title": last.get("series_title", ""),
                "part": last["part"] + 1, "world": last.get("world"),
                "characters": last.get("characters", ""),
                "summaries": [h.get("summary", "") for h in prev]}
    n_series = len({h.get("series") for h in history})
    return {"series": datetime.datetime.utcnow().strftime("%Y%m%d%H%M"), "series_title": "",
            "part": 1, "world": WORLDS[(n_series * 3) % len(WORLDS)], "characters": "",
            "summaries": []}


def write_movie(history):
    """Movie Recap: mashhoor film ki kahani apne alfaaz mein (asal footage/poster nahi - copyright safe)."""
    used = [h.get("series_title", "") for h in history[-300:]]
    length = ("ONE complete recap of about 9 minutes: setup, every major plot point, the twists and the "
              "ending explained clearly" if LONG else
              "a fast ~2.5 minute recap: the hook, the main story beats, the biggest twist and the ending")
    data = ask_json(f"""You run a viral "Movie Recap / Movie Explained" YouTube channel for a US/UK audience.
Pick ONE very famous, well-known movie (Hollywood, or a world-famous Korean/Japanese/Indian/Spanish hit;
thrillers, sci-fi, survival, mystery, horror-lite and twist movies perform best). It must be famous enough
that you know its plot accurately. Do NOT pick any of these already-covered movies: {json.dumps(used, ensure_ascii=False)}

Write {length}, retold in your OWN words (never quote dialogue) in {LANGUAGE_TXT}.
Accuracy: stay true to the real plot - never invent events. Refer to characters by their role or first name.
VIRAL RULES:
- First sentence is a gripping hook about the movie's core situation (no "In this video", no "Hello guys").
- Narrate like a storyteller in present tense; keep suspense, reveal the twist at the right moment.
- Last line asks viewers to subscribe for more movie recaps.
No gore details, no sexual content, no politics.

Exactly {SCENES} scenes, each {WORDS}.
For each scene give {SHOTS} English image prompts ("shots") for an AI image generator: one detailed sentence
of what the camera sees (who, action, place, light, camera angle). Characters must be ORIGINAL looking people,
never a real actor's likeness, no logos or brand names. Use the character sheet so people look the SAME in
every image. For each scene also pick "fx": one of snow, rain, embers, dust, fog, none.

Return JSON:
{{"series_title": "the exact movie name and year, e.g. Inception (2010)",
 "title": "on-screen title, max 45 characters, e.g. INCEPTION EXPLAINED",
 "characters": "ENGLISH character sheet: each main character's role + age + face, hair, clothes (original look)",
 "scenes": [{{"text": "narration", "fx": "none", "shots": ["english prompt 1", "..."]}}],
 "summary": "2 English sentences about the movie",
 "yt_title": "viral YouTube title, max 70 characters, must include the movie name + 'Recap' or 'Explained', e.g. A Man Steals Dreams For A Living | Inception Recap",
 "description": "3-4 line YouTube description: what the movie is about without spoiling the ending, then a question to invite comments, then 'Movie recap and review for commentary and education.'",
 "thumb_text": "2-4 word ALL CAPS curiosity text, e.g. HE NEVER WOKE UP",
 "tags": ["15 English search tags: movie recap, movie explained, the movie name, genre..."]}}""")
    scenes = [s for s in data.get("scenes", []) if (s.get("text") or "").strip()]
    if len(scenes) < (20 if LONG else 6):
        raise RuntimeError("Recap mein scenes kam hain")
    data["scenes"] = scenes
    return data


def write_story(history, st):
    if MOVIE:
        return write_movie(history)
    used = list(dict.fromkeys(h.get("series_title", "") for h in history[-90:]))
    p = st["part"]
    if p == 1:
        series_txt = (f"This is PART 1 of a {PARTS}-part series. Invent 2-3 ORIGINAL memorable characters "
                      "(never famous movie, cartoon or game characters) with simple names. "
                      f"Do not reuse these old series titles: {json.dumps(used, ensure_ascii=False)}")
    else:
        prev = "\n".join(f"Part {i + 1}: {s}" for i, s in enumerate(st["summaries"]))
        series_txt = (f"This is PART {p} of {PARTS} of the series \"{st['series_title']}\".\n"
                      f"Story so far:\n{prev}\nCharacters (keep EXACTLY the same): {st['characters']}")
    if PARTS == 1:
        end = ("This is ONE complete story (about 9 minutes): hook, rising danger, several twists, "
               "an epic climax and a satisfying, surprising ending. Last line asks viewers to subscribe.")
    elif p < PARTS:
        end = f"End on a strong cliffhanger; last line: \"{CLIFF}\""
    else:
        end = "This is the FINAL part: an epic climax and a satisfying, surprising ending."
    data = ask_json(f"""You write viral cinematic story shorts (like AI movie-style YouTube Shorts).
World / setting: {st['world']}
{series_txt}

Write the narration in {LANGUAGE_TXT}.
VIRAL RULES:
- The first sentence (first 2 seconds) is a shocking or mysterious hook that stops scrolling: a bold claim,
  a sudden danger or a forbidden secret. Never start with "Once upon a time" or slow description.
- Open a big mystery early and only answer it at the very end; raise the stakes in every scene.
- Put a surprising twist in the middle; every scene ends with a small question that pulls into the next one.
- Make viewers care: give the hero a personal reason, a fear and a sacrifice. Use vivid, visual words.
{end}
No gore, no blood details, no religion or politics. Family friendly but thrilling.

Exactly {SCENES} scenes, each {WORDS}.
For each scene give {SHOTS} English image prompts ("shots") for an AI image generator, each a single
detailed sentence describing exactly what the camera sees (who, action, place, weather, camera angle:
close-up / wide shot / low angle...). Whenever a character appears, describe their look using the
character sheet so they look the SAME in every image. Mix wide establishing shots, close-ups of faces
and eyes, and dynamic action moments - like a movie trailer.
For each scene also pick "fx" (moving weather layer): one of snow, rain, embers, dust, fog, none.

Return JSON:
{{"series_title": "short catchy series title in {TITLE_LANG}, max 40 characters",
 "title": "on-screen title for this video in {TITLE_LANG}, max 45 characters{" with the part label" if PARTS > 1 else ""}",
 "characters": "ENGLISH character sheet: for each character name + age + face, hair, clothes, body, or creature look",
 "scenes": [{{"text": "narration", "fx": "snow", "shots": ["english prompt 1", "..."]}}],
 "summary": "2 English sentences summarising what happened in this part",
 "yt_title": "viral YouTube title in {TITLE_LANG}, max 70 characters, strong curiosity gap that is honest to the story, include one searchable word like dragon, kingdom, legend, curse or warrior",
 "description": "3-4 line YouTube description in {TITLE_LANG} ending with a question to invite comments",
 "thumb_text": "2-4 word ALL CAPS thumbnail text in English that creates curiosity, e.g. THE DRAGON LIED",
 "tags": ["15 short English YouTube search tags: fantasy story, ai movie, ..."]}}""")
    scenes = [s for s in data.get("scenes", []) if (s.get("text") or "").strip()]
    if len(scenes) < (20 if LONG else 6):
        raise RuntimeError("Kahani mein scenes kam hain")
    data["scenes"] = scenes
    if p > 1:
        data["series_title"] = st["series_title"] or data.get("series_title", "")
        data["characters"] = st["characters"] or data.get("characters", "")
    return data


# ---------------------------------------------------------------- awaaz / music
def tts(text, path):
    import edge_tts

    async def go():
        await edge_tts.Communicate(text, VOICE, rate=RATE).save(path)
    for attempt in range(6):                                   # Microsoft kabhi kabhi rok deta hai
        try:
            asyncio.run(go())
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            log(f"TTS retry {attempt + 1}: {str(e)[:200]}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("Awaaz nahi bani")


def make_music(path, secs):
    """Halki dramatic drone music (khud banti hai, koi copyright nahi)."""
    root = random.choice([49.0, 55.0, 61.7, 65.4])           # G / A / B / C
    notes = [root, root * 1.5, root * 2, root * 2.4, root * 3]
    expr = "+".join(f"{a}*sin(2*PI*{f:.2f}*t)*(0.55+0.45*sin(2*PI*{0.05 + i * 0.03:.2f}*t))"
                    for i, (f, a) in enumerate(zip(notes, [0.30, 0.18, 0.16, 0.10, 0.07])))
    pulse = f"0.35*sin(2*PI*{root / 2:.2f}*t)*exp(-6*mod(t\\,1.6))"
    run(["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"aevalsrc='{expr}+{pulse}':s=44100:d={secs + 2:.1f}",
         "-af", "lowpass=f=900,aecho=0.8:0.7:600|1100:0.35|0.25,"
                "afade=t=in:d=3,afade=t=out:st=" + f"{max(secs - 3, 1):.1f}:d=3,volume=0.5",
         "-ac", "2", "-c:a", "aac", "-b:a", "128k", path])


# ---------------------------------------------------------------- tasveerein
_last_poll = [0.0]


def pollinations(prompt, seed, path):
    gap = 3 if POLL_TOKEN else 16                              # free limit ka khayal
    wait = _last_poll[0] + gap - time.time()
    if wait > 0:
        time.sleep(wait)
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(f"{prompt}, {LOOK}") +
           f"?width={1344 if LONG else 1024}&height={768 if LONG else 1024}&seed={seed}&model=flux&nologo=true&private=true")
    headers = {"Authorization": f"Bearer {POLL_TOKEN}"} if POLL_TOKEN else {}
    for attempt in range(4):
        try:
            _last_poll[0] = time.time()
            r = requests.get(url, headers=headers, timeout=180)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image") \
                    and len(r.content) > 15000:
                with open(path, "wb") as f:
                    f.write(r.content)
                return True
            log(f"Pollinations {r.status_code} (try {attempt + 1})")
        except Exception as e:
            log(f"Pollinations error (try {attempt + 1}): {str(e)[:150]}")
        time.sleep(15 + attempt * 10)
    return False


def pixabay_backup(query, path):
    if not PIXABAY_KEY:
        return False
    try:
        r = requests.get("https://pixabay.com/api/", timeout=40, params={
            "key": PIXABAY_KEY, "q": " ".join(query.split()[:4]), "safesearch": "true",
            "per_page": 30, "image_type": "photo"})
        hits = r.json().get("hits", [])
        if not hits:
            return False
        url = random.choice(hits[:10])["largeImageURL"]
        with open(path, "wb") as f:
            f.write(requests.get(url, timeout=60).content)
        return os.path.getsize(path) > 15000
    except Exception as e:
        log(f"Pixabay backup error: {str(e)[:150]}")
        return False


def get_image(prompt, seed, path):
    if POLL_TOKEN and pollinations(prompt, seed, path):
        REPORT["images_ai"] += 1
        return path
    import free_images                                         # free: GitHub CPU par sd-turbo
    if free_images.generate(f"epic fantasy movie still, cinematic lighting, highly detailed, {prompt}",
                            seed, path, 1344 if LONG else 1024, 768 if LONG else 1024):
        REPORT["images_ai"] += 1
        return path
    if pixabay_backup(prompt, path):
        REPORT["images_backup"] += 1
        return path
    REPORT["images_failed"] += 1
    return None


# ---------------------------------------------------------------- subtitles (ASS)
def ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02}:{t % 60:05.2f}"


def ass_text(s):
    return s.replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def make_ass(path, timed, total, title):
    sub_top = IMG_Y + IMG + 50
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{FONT},{58 if LONG else 74},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,5,3,8,50,50,{50 if LONG else IMG_Y - 190},1
Style: Sub,{FONT},{62 if LONG else 68},&H0040E6FF,&H0040E6FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,2,{2 if LONG else 8},70,70,{70 if LONG else sub_top},1
Style: Mark,Noto Sans,32,&H60FFFFFF,&H60FFFFFF,&H90000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,{9 if LONG else 2},40,40,{40 if LONG else 60},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    shown = min(6.0, total) if LONG else total + 1          # long video mein title sirf shuru mein
    ev = [f"Dialogue: 0,{ass_time(0)},{ass_time(shown)},Title,,0,0,0,,{{\\fad(400,600)}}{ass_text(title)}"]
    if CHANNEL:
        ev.append(f"Dialogue: 0,{ass_time(0)},{ass_time(total + 1)},Mark,,0,0,0,,{ass_text(CHANNEL)}")
    for start, end, text in timed:
        words = text.split()
        n = 6 if LONG else 4
        chunks = [" ".join(words[i:i + n]) for i in range(0, len(words), n)]
        weights = [len(c) + 3 for c in chunks]
        scale = (end - start) / max(sum(weights), 1)
        t = start
        for c, wgt in zip(chunks, weights):
            e = t + wgt * scale
            ev.append(f"Dialogue: 1,{ass_time(t)},{ass_time(e)},Sub,,0,0,0,,"
                      f"{{\\fad(80,80)}}{ass_text(c)}")
            t = e
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(ev) + "\n")


# ---------------------------------------------------------------- video
def shot_clip(job, img, secs, idx, out, fx="none"):
    """Ek tasveer -> 3D jaisi chalti hui shot (motion.py) + Shorts mein blur background."""
    import numpy as np
    import cv2
    import motion
    path = os.path.join(job, img) if img else None
    pic = cv2.imread(path) if path else None
    if pic is None:
        pic = np.zeros((1024, 1024, 3), np.uint8)
        pic[:] = (60, 40, 20)
    fw, fh = (W, H) if LONG else (IMG, IMG)
    if not LONG:
        bg = cv2.resize(pic, (H, H))[:, (H - W) // 2:(H - W) // 2 + W]
        bg = cv2.GaussianBlur(bg, (0, 0), 30)
        bg = cv2.convertScaleAbs(bg, alpha=0.75)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                          "-s", f"{W}x{H}", "-r", "30", "-i", "-", "-vf", "fade=t=in:st=0:d=0.2",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                          os.path.join(job, out)], stdin=subprocess.PIPE)
    try:
        for fr in motion.shot_frames(pic, secs, fw, fh, idx, fx, seed=idx * 7 + 1):
            if LONG:
                p.stdin.write(fr.tobytes())
            else:
                canvas = bg.copy()
                canvas[IMG_Y:IMG_Y + IMG] = fr
                p.stdin.write(canvas.tobytes())
    finally:
        p.stdin.close()
        p.wait()
    if p.returncode != 0:
        raise RuntimeError("Shot video nahi bani")


def ai_clip(job, src, secs, out):
    """Kaggle wala asli chalta AI clip -> shot jaisa format (dheema + aage-peeche loop agar scene lamba ho)."""
    d = max(duration(src), 0.5)
    f = min(max(secs / d, 1.0), 1.8)                     # 1.8x tak dheema - zyada dheema bura lagta hai
    pp = os.path.join(job, f"pp_{out}")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-filter_complex",
         f"[0:v]setpts={f:.3f}*PTS,fps=30,split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1[p]",
         "-map", "[p]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", pp])
    if LONG:
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
    else:
        vf = (f"split[f][g];[g]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"gblur=sigma=30,eq=brightness=-0.1[bg];"
              f"[f]scale={IMG}:{IMG}:force_original_aspect_ratio=increase,crop={IMG}:{IMG}[fg];"
              f"[bg][fg]overlay=0:{IMG_Y},setsar=1")
    run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", pp, "-t", f"{secs:.3f}",
         "-filter_complex", f"[0:v]{vf},fps=30,eq=contrast=1.05:saturation=1.1,fade=t=in:st=0:d=0.2,format=yuv420p[v]",
         "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         os.path.join(job, out)])


def kaggle_clips(script, job, base_seed):
    """Har scene ki pehli shot ka asli chalta clip Kaggle ke free GPU par (sirf Legends Untold)."""
    import kaggle_video
    if MOVIE or not kaggle_video.enabled():
        return {}
    if LONG and datetime.datetime.utcnow().weekday() not in (0, 2, 4, 6):
        log("Aaj lambi video purane tareeqe se (Kaggle quota hafte ke liye bachaya)")
        return {}
    chars = script.get("characters", "")
    jobs = []
    for i, sc in enumerate(script["scenes"]):
        shot = ((sc.get("shots") or [])[:1] or [sc["text"]])[0]
        prompt = (f"Cinematic epic fantasy movie scene, dramatic motion, realistic, highly detailed: {shot}"
                  + (f". Characters: {chars}" if chars else ""))[:700]
        jobs.append({"id": i, "prompt": prompt, "seed": base_seed + i})
    w, h = (832, 480) if LONG else (640, 640)
    REPORT["kaggle_log"] = []

    def klog(m):
        log(m)
        REPORT["kaggle_log"].append(str(m)[:400])
    got = kaggle_video.generate(jobs, w, h, WORK, klog, max_minutes=250 if LONG else 110)
    REPORT["ai_motion_clips"] = len(got)
    return got


def make_sfx(path, total, cuts):
    """Har cut par 'whoosh' aur shuru mein 'boom' - khud banti hai."""
    import numpy as np
    import wave
    sr = 44100
    out = np.zeros(int((total + 1) * sr), np.float32)
    rng = np.random.default_rng(3)
    n = int(0.45 * sr)
    tt = np.linspace(0, 1, n, dtype=np.float32)
    noise = rng.standard_normal(n).astype(np.float32)
    k = np.ones(40, np.float32) / 40
    whoosh = np.convolve(noise, k, mode="same") * np.sin(np.pi * tt) ** 2 * 0.5
    nb = int(1.6 * sr)
    tb = np.arange(nb, dtype=np.float32) / sr
    boom = (np.sin(2 * np.pi * (55 - 20 * tb) * tb) * np.exp(-3 * tb) * 0.9).astype(np.float32)
    out[:nb] += boom
    for c in cuts:
        i = int(max(c - 0.22, 0) * sr)
        seg = out[i:i + n]
        seg += whoosh[:len(seg)] * 0.6
    pcm = (np.clip(out, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def build_video(script, out_path):
    job = os.path.join(WORK, "job")
    shutil.rmtree(job, ignore_errors=True)
    os.makedirs(job)
    base_seed = random.randint(1000, 900000)
    chars = script.get("characters", "")
    # Kaggle par asli chalte clips saath saath bante rahen, yahan tasveeron wali video banti rahe
    import threading
    kres = {}
    kth = threading.Thread(target=lambda: kres.update(kaggle_clips(script, job, base_seed)), daemon=True)
    kth.start()
    first_shot = {}
    timed, clips, voice_parts, cuts, t = [], [], [], [], 0.0
    for i, sc in enumerate(script["scenes"]):
        text = sc["text"].strip()
        a = os.path.join(job, f"a{i}.mp3")
        tts(text, a)
        d = duration(a) + 0.35
        voice_parts.append((f"a{i}.mp3", d))
        timed.append((t, t + d - 0.3, text))
        shots = (sc.get("shots") or [])[:SHOTS] or [text]
        seg = d / len(shots)
        fx = (sc.get("fx") or "none").lower().strip()
        for j, prompt in enumerate(shots):
            full = f"{prompt}. Characters: {chars}" if chars else prompt
            out = f"c{i}_{j}.mp4"
            if j == 0:
                first_shot[i] = (out, seg)
            img = get_image(full[:900], base_seed + i * 10 + j, os.path.join(job, f"i{i}_{j}.jpg"))
            shot_clip(job, os.path.basename(img) if img else None, seg, len(clips), out, fx)
            clips.append(out)
            cuts.append(t + seg * (j + 1))
        t += d
        log(f"scene {i + 1}/{len(script['scenes'])} ready")
    total = t
    kth.join()
    for i, path in kres.items():                       # har scene ki pehli shot -> asli chalta clip
        if i in first_shot:
            out, seg = first_shot[i]
            try:
                ai_clip(job, path, seg, "ai_tmp.mp4")
                os.replace(os.path.join(job, "ai_tmp.mp4"), os.path.join(job, out))
            except Exception as e:
                log(f"AI clip {i} skip: {str(e)[:150]}")

    with open(os.path.join(job, "clips.txt"), "w") as f:
        f.writelines(f"file '{c}'\n" for c in clips)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", "video.mp4"], cwd=job)

    # awaaz: har scene ke baad thori khamoshi
    with open(os.path.join(job, "voice.txt"), "w") as f:
        for name, d in voice_parts:
            f.write(f"file '{name}'\noutpoint {d:.3f}\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "voice.txt",
         "-af", "apad", "-t", f"{total:.3f}", "-ar", "44100", "-ac", "2", "voice.wav"], cwd=job)
    make_music(os.path.join(job, "music.m4a"), total)
    make_sfx(os.path.join(job, "sfx.wav"), total, cuts[:-1])

    make_ass(os.path.join(job, "subs.ass"), timed, total, script.get("title", ""))
    fontsdir = f":fontsdir={FONTS_DIR}" if os.path.isdir(FONTS_DIR) else ""
    run(["ffmpeg", "-y", "-i", "video.mp4", "-i", "voice.wav", "-i", "music.m4a", "-i", "sfx.wav",
         "-filter_complex",
         f"[0:v]subtitles=subs.ass{fontsdir},format=yuv420p[v];"
         f"[1:a]volume=1.0[vo];[2:a]volume=0.22[mu];[3:a]volume=0.35,aformat=channel_layouts=stereo[fx];[vo][mu][fx]amix=inputs=3:duration=first:normalize=0,"
         f"alimiter=limit=0.95[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-maxrate", "8M", "-bufsize", "16M",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", os.path.abspath(out_path)], cwd=job)
    REPORT["seconds"] = round(duration(out_path), 1)
    log(f"Video ready: {REPORT['seconds']} sec")
    return out_path


# ---------------------------------------------------------------- YouTube
def yt_access_token():
    r = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={
        "client_id": YT_ID, "client_secret": YT_SECRET,
        "refresh_token": YT_REFRESH, "grant_type": "refresh_token"})
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError(f"YouTube login fail: {j}")
    return j["access_token"]


def upload_youtube(path, script):
    token = yt_access_token()
    title = (script.get("yt_title") or script.get("title") or "Kahani")[:90]
    if REPORT.get("seconds", 999) <= 180 and "#shorts" not in title.lower():
        title = f"{title} #Shorts"[:100]
    tags = [t.strip("# ") for t in script.get("tags", []) if t.strip("# ")][:20]
    part = f" - {PART_WORD} {script.get('part', 1)}" if PARTS > 1 else ""
    desc = (f"{script.get('description', '')}\n\n"
            f"{script.get('series_title', '')}{part}\n"
            f"{SUB_TXT}\n\n"
            + " ".join("#" + t.replace(" ", "") for t in tags[:8]))
    meta = {"snippet": {"title": title, "description": desc[:4900], "tags": tags,
                        "categoryId": "1", "defaultLanguage": LANG, "defaultAudioLanguage": LANG},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": True}}
    size = os.path.getsize(path)
    r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        data=json.dumps(meta), timeout=60)
    if r.status_code != 200 or "Location" not in r.headers:
        raise RuntimeError(f"YouTube upload start fail: {r.status_code} {r.text[:400]}")
    loc = r.headers["Location"]
    for attempt in range(4):
        try:
            with open(path, "rb") as f:
                r = requests.put(loc, data=f, timeout=1800, headers={
                    "Authorization": f"Bearer {token}", "Content-Type": "video/mp4"})
            if r.status_code in (200, 201):
                vid = r.json()["id"]
                log(f"YouTube uploaded: https://youtu.be/{vid}")
                return vid
            log(f"YouTube upload {r.status_code}: {r.text[:300]}")
        except Exception as e:
            log(f"YouTube upload retry {attempt + 1}: {str(e)[:150]}")
        time.sleep(10)
    raise RuntimeError("YouTube upload fail")


def make_thumbnail(script, out_path):
    """1280x720 thumbnail: sab se acha scene + bari peeli/safed likhai + channel naam."""
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageFont
    job = os.path.join(WORK, "job")
    cands = sorted(f for f in os.listdir(job) if f.startswith("i") and f.endswith(".jpg")) if os.path.isdir(job) else []
    if not cands:
        return None
    pick = cands[min(1, len(cands) - 1)]                       # 1st scene ka close-up aksar behtar
    img = Image.open(os.path.join(job, pick)).convert("RGB")
    tw, th = 1280, 720
    sc = max(tw / img.width, th / img.height)
    img = img.resize((int(img.width * sc + 1), int(img.height * sc + 1)), Image.LANCZOS)
    x0, y0 = (img.width - tw) // 2, (img.height - th) // 3
    img = img.crop((x0, y0, x0 + tw, y0 + th))
    img = ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(1.35)).enhance(1.15)
    shade = Image.new("L", (tw, th), 0)
    d = ImageDraw.Draw(shade)
    for i in range(th // 2):                                   # neeche andhera taa ke likhai saaf parhi jaye
        d.line([(0, th - i), (tw, th - i)], fill=int(200 * (1 - i / (th / 2))))
    img = Image.composite(Image.new("RGB", (tw, th), (0, 0, 0)), img, shade)
    text = (script.get("thumb_text") or script.get("title") or "").upper().strip()[:28]
    font_path = os.path.join(FONTS_DIR, "NotoSans-Bold.ttf")
    draw = ImageDraw.Draw(img)
    words, lines = text.split(), []
    for w in words:
        if lines and len(lines[-1] + " " + w) <= 14:
            lines[-1] += " " + w
        else:
            lines.append(w)
    lines = lines[:2]
    size = 120 if max((len(l) for l in lines), default=0) <= 10 else 96
    try:
        font = ImageFont.truetype(font_path, size)
        small = ImageFont.truetype(font_path, 34)
    except Exception:
        font = small = ImageFont.load_default()
    y = th - 60 - len(lines) * (size + 10)
    for k, line in enumerate(lines):
        color = (255, 214, 64) if k == 0 else (255, 255, 255)
        w = draw.textlength(line, font=font)
        draw.text(((tw - w) / 2, y), line, font=font, fill=color, stroke_width=8, stroke_fill=(0, 0, 0))
        y += size + 10
    if CHANNEL:
        draw.text((30, 24), CHANNEL.upper(), font=small, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
    img.save(out_path, "JPEG", quality=90)
    return out_path


def set_thumbnail(video_id, path):
    token = yt_access_token()
    with open(path, "rb") as f:
        r = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}",
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
                          data=f.read(), timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"thumbnail {r.status_code}: {r.text[:300]}")
    log("YouTube thumbnail set")


# ---------------------------------------------------------------- Facebook (optional)
def fb_json(r):
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"Facebook ka jawab samajh nahi aaya: {r.text[:300]}")
    if "error" in j:
        raise RuntimeError(f"Facebook error: {j['error'].get('message', j)}")
    return j


def upload_facebook(path, script):
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
            j = fb_json(requests.post(url, timeout=600, data={
                "access_token": FB_TOKEN, "upload_phase": "transfer",
                "upload_session_id": session, "start_offset": str(s_off)},
                files={"video_file_chunk": ("chunk", chunk, "application/octet-stream")}))
            s_off, e_off = int(j["start_offset"]), int(j["end_offset"])
    tags = " ".join("#" + t.strip("# ").replace(" ", "") for t in script.get("tags", [])[:8])
    fb_json(requests.post(url, timeout=300, data={
        "access_token": FB_TOKEN, "upload_phase": "finish", "upload_session_id": session,
        "title": script.get("title", ""),
        "description": f"{script.get('title', '')}\n\n{script.get('description', '')}\n\n{tags}"}))
    log(f"Facebook posted: {vid}")
    return vid


# ---------------------------------------------------------------- main
def write_report():
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=1)


def _main():
    yt_ok = bool(YT_ID and YT_SECRET and YT_REFRESH)
    fb_ok = bool(FB_PAGE and FB_TOKEN)
    if not DRY_RUN and not (yt_ok or fb_ok):
        raise RuntimeError("YouTube (YT_CLIENT_ID/YT_CLIENT_SECRET/YT_REFRESH_TOKEN) ya Facebook "
                           "(CINE_FB_PAGE_ID/CINE_FB_TOKEN) secrets missing hain")
    history = load_history()
    st = series_state(history)
    script = write_story(history, st)
    script["part"] = st["part"]
    log(f"Series: {script.get('series_title')} | Part {st['part']} | {script.get('title')}")

    # schedule run jaldi chalta hai (Kaggle ke liye waqt) - Kaggle na ho to pehle thora intezar
    import slot_wait
    tgt = slot_wait.target_time()
    if tgt is not None:
        import kaggle_video
        uses_k = kaggle_video.enabled() and not MOVIE and (
            not LONG or datetime.datetime.utcnow().weekday() in (0, 2, 4, 6))
        need = (330 if LONG else 120) if uses_k else (110 if LONG else 45)
        secs = (tgt - datetime.timedelta(minutes=need) - datetime.datetime.utcnow()).total_seconds()
        if secs > 0:
            log(f"Pehle {int(secs // 60)} minute intezar, phir video banegi")
            time.sleep(secs)

    build_video(script, "final_cinematic.mp4")
    if not DRY_RUN:
        slot_wait.wait(log)
    thumb = None
    try:
        thumb = make_thumbnail(script, "thumbnail.jpg")
    except Exception as e:
        log(f"Thumbnail nahi bani: {str(e)[:200]}")
    entry = {"date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
             "series": st["series"], "series_title": script.get("series_title", ""),
             "part": st["part"], "world": st["world"], "characters": script.get("characters", ""),
             "title": script.get("title", ""), "summary": script.get("summary", "")}
    posted = 0
    if not DRY_RUN and yt_ok:
        try:
            entry["yt_id"] = upload_youtube("final_cinematic.mp4", script)
            posted += 1
            if thumb:
                try:
                    set_thumbnail(entry["yt_id"], thumb)
                except Exception as e:
                    log(f"THUMBNAIL ERROR: {e}")
                    REPORT["errors"].append(f"thumbnail: {str(e)[:200]}")
        except Exception as e:
            log(f"YOUTUBE ERROR: {e}")
            REPORT["errors"].append(f"youtube: {str(e)[:300]}")
    if not DRY_RUN and fb_ok:
        try:
            entry["fb_id"] = upload_facebook("final_cinematic.mp4", script)
            posted += 1
        except Exception as e:
            log(f"FACEBOOK ERROR: {e}")
            REPORT["errors"].append(f"facebook: {str(e)[:300]}")

    REPORT.update({"time_utc": entry["date"], "title": entry["title"], "part": st["part"],
                   "dry_run": DRY_RUN, "posted": posted})
    write_report()
    if posted and not DRY_RUN:
        history.append(entry)
        save_history(history)
    if not DRY_RUN and posted == 0:
        sys.exit(1)
    log("Done!")


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
