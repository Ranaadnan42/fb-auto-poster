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
FB_TOKEN = os.environ.get("FUNNY_PAGE_TOKEN")
FB_PAGE = os.environ.get("FUNNY_PAGE_ID")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
MODE = (os.environ.get("MODE") or "reel").strip().lower()

PAGE_NAME = "Funny Videos"
GRAPH_VER = "v23.0"
HISTORY_FILE = "funny_history.json"
REPORT_FILE = "funny_last_run.json"
WORK = "work_funny"
FONTS_DIR = os.path.abspath("fonts")
FONT = "Noto Naskh Arabic"
VOICE = "ur-PK-AsadNeural"
VOICE_RATE = "+0%"
VOICE_PITCH = "+8Hz"            # thori mazahiya awaaz
MODEL_CANDIDATES = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"]

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
    raise RuntimeError(f"Gemini fail: {last}")


def word_count(script):
    return sum(len((s.get("text") or "").split()) for s in script.get("scenes", []))


def write_reel(history):
    used = [h["title"] for h in history[-120:]]
    recent_animals = [h.get("animal") for h in history[-6:]]
    animal = random.choice([a for a in ANIMALS if a not in recent_animals])
    style = random.choice(STYLES)
    situation = SITUATIONS[len(history) % len(SITUATIONS)]
    data = ask_json(f"""You write viral funny Facebook Reels for the Pakistani page "{PAGE_NAME}".
Animal: {animal}. Comedy style: {style}.
Today's topic (relatable everyday Pakistani situation): {situation}.
Invent a FRESH joke idea about this topic - never reuse an idea from these past titles:
{json.dumps(used, ensure_ascii=False)}

Write a 100-word Urdu voice-over (about 40 seconds) for stock clips of a {animal}.
The {animal} is the main character talking in first person like a typical desi person.
Make it GENUINELY funny: one relatable situation, exaggeration, desi references
(ammi, abbu, chai, biryani, load shedding, WhatsApp, rishta, cricket), short punchy lines,
and a surprising twist punchline at the end. Line 1 is a hook that makes people stop scrolling.
Only refer to simple things any clip of a {animal} shows (looking, staring, sitting, eating,
sleeping, walking, running) so the video always matches the words.
After the punchline end with: "ایسی مزید ویڈیوز کے لیے فالو کریں"
{RULES}

Split into exactly 5 scenes. For each scene give a 1-3 word ENGLISH stock-video search term
that will show a {animal} (e.g. "{animal}", "{animal} playing", "funny {animal}").

Return JSON: {{"title": "funny Urdu title, max 60 characters",
 "meme": "very short meme header in Urdu shown on top of the whole reel, max 7 words, like a POV line",
 "scenes": [{{"text": "...", "visual": "..."}}],
 "caption": "1 funny line in Urdu that asks people to tag a friend",
 "hashtags": ["#funny", "..."] (6 hashtags, English and Urdu)}}""")
    if len(data.get("scenes", [])) < 2:
        raise RuntimeError("Reel script mein scenes kam hain")
    data["animal"] = animal
    data["topic"] = situation
    return data


def write_long(history):
    used = [h["title"] for h in history[-120:]]
    animals = random.sample(ANIMALS, 10)
    style = random.choice(STYLES)
    situation = SITUATIONS[(len(history) * 3 + 7) % len(SITUATIONS)]
    extra = ""
    best = None
    for _ in range(3):
        data = ask_json(f"""You write funny Facebook videos for the Pakistani page "{PAGE_NAME}".
Make a 5-minute funny animal compilation with a running joke. Main comedy style: {style}.
Today's topic for the whole video (relatable everyday Pakistani situation): {situation}.
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
Return JSON: {{"title": "funny Urdu title, max 70 characters",
 "scenes": [{{"text": "...", "visual": "...", "meme": "very short funny Urdu header for this segment, max 7 words"}}] (exactly 10),
 "caption": "2 funny lines in Urdu asking people to comment their favourite animal",
 "hashtags": ["#funny", "..."] (8 hashtags)}}""")
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
    best["topic"] = situation
    return best


# ---------------------------------------------------------------- audio
def tts(text, path):
    async def go():
        await edge_tts.Communicate(text, VOICE, rate=VOICE_RATE, pitch=VOICE_PITCH).save(path)
    for attempt in range(3):
        try:
            asyncio.run(go())
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            log(f"TTS retry {attempt + 1}: {e}")
            time.sleep(3)
    raise RuntimeError("Awaaz nahi bani")


# ---------------------------------------------------------------- clips
def pixabay_clips(query, count, job, prefix, backup, want_vertical=False, strict=True):
    got = []
    if not PIXABAY_KEY:
        return got
    queries = []
    for q in (f"funny {backup}", query if backup in query else f"{backup} {query}", backup):
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
                    and (not strict or backup.split()[-1] in h.get("tags", "").lower())
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
Style: Sub,{FONT},{96 if vertical else 74},&H0000F0FF,&H0000F0FF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,7,3,2,60,60,{560 if vertical else 80},1
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
    k = max(1, min(6, round(dur / 4)))                      # har ~4 sec naya clip
    clips = pixabay_clips(sc.get("visual") or backup, k, job, f"c{i}", backup, want_vertical=h > w)
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
    for i, sc in enumerate(scenes):
        backup = sc.get("animal") or script["animal"]
        meme = script.get("meme") if h > w else sc.get("meme")
        parts.append(build_scene(job, i, sc, w, h, script["title"] if i == 0 else None, backup, meme))
        log(f"{tag}: scene {i + 1}/{len(scenes)} ready")
    with open(os.path.join(job, "list.txt"), "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy",
         "-movflags", "+faststart", os.path.abspath(out_path)], cwd=job)
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
    return vid


def description(script):
    tags = " ".join(t if t.startswith("#") else "#" + t for t in script.get("hashtags", []))
    return f"{script['title']}\n\n{script.get('caption', '')}\n\n{tags}".strip()


# ---------------------------------------------------------------- main
def write_report():
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=1)


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
        pk_hour = (now.hour + 5) % 24
        MODE = "long" if (not long_today and pk_hour >= 19) else "reel"
    entry = {"date": now.strftime("%Y-%m-%d %H:%M"), "mode": MODE}
    import chat_comedy
    if MODE == "long":
        fmt = os.environ.get("FORMAT") or "story"       # lambi video: qiston wali kahani
    else:
        # roz sirf 1 chat reel, baaqi janwar wali
        pk_today = (now + datetime.timedelta(hours=5)).strftime("%Y-%m-%d")
        chat_today = sum(1 for h in history if h.get("mode") == "reel" and h.get("format") == "chat"
                         and (datetime.datetime.strptime(h["date"], "%Y-%m-%d %H:%M")
                              + datetime.timedelta(hours=5)).strftime("%Y-%m-%d") == pk_today)
        fmt = os.environ.get("FORMAT") or ("animal" if chat_today >= 1 else "chat")
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
            entry["id"] = post_long("funny_long.mp4", script["title"], description(script))
    else:
        if fmt == "animal":
            script = write_reel(history)
            build_video(script, "reel", 1080, 1920, "funny_reel.mp4")
        else:
            script = chat_comedy.build_reel(history, "funny_reel.mp4")
            REPORT["reel_minutes"] = round(duration("funny_reel.mp4") / 60, 2)
        if duration("funny_reel.mp4") > 89:
            run(["ffmpeg", "-y", "-i", "funny_reel.mp4", "-t", "89", "-c", "copy", "cut.mp4"])
            shutil.move("cut.mp4", "funny_reel.mp4")
        if not DRY_RUN:
            entry["id"] = post_reel("funny_reel.mp4", description(script))
    entry.update({"title": script["title"], "animal": script["animal"], "topic": script.get("topic")})
    for key in ("series", "series_title", "part", "summary", "style"):
        if script.get(key) is not None:
            entry[key] = script[key]
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
        REPORT["errors"].append(str(e)[:400])
        write_report()
        raise


if __name__ == "__main__":
    main()
