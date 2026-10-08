"""
Islamic Motivational Videos - Auto Poster (GitHub Actions)

Har run par:
 1. Gemini naya topic chunta hai (pichle topics history.json se repeat nahi hote)
 2. Lambi video (~5 min, 16:9) aur reel (~50 sec, 9:16) ki script likhta hai
 3. Edge TTS se har scene ki awaaz banti hai
 4. Har scene ke liye Pixabay se alag stock clip aati hai (na mile to simple background)
 5. Screen par subtitles jalaye jate hain
 6. Dono Facebook page par post hoti hain

Secrets: GEMINI_API_KEY, PIXABAY_API_KEY, FB_PAGE_ACCESS_TOKEN, FB_PAGE_ID
DRY_RUN=1 ho to video banegi lekin post nahi hogi.
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

GRAPH_VER = "v23.0"
VOICE = "en-US-ChristopherNeural"
VOICE_RATE = "-5%"                 # thori dheemi, sukoon wali awaaz
LONG_WORDS = 700                   # ~4.5-5 minute
LONG_SCENES = 12
REEL_WORDS = 120                   # ~45-55 second
REEL_SCENES = 5
HISTORY_FILE = "history.json"
WORK = "work"

MODEL_CANDIDATES = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"]

THEMES = [
    "patience (sabr) in hardship", "gratitude (shukr)", "trusting Allah (tawakkul)",
    "the mercy and forgiveness of Allah", "the power of dua", "the value of salah",
    "lessons from the life of Prophet Muhammad (peace be upon him)",
    "stories of the prophets mentioned in the Quran", "stories of the Sahaba",
    "reflection on a Quran verse", "death, the grave and the hereafter",
    "repentance (tawbah) and second chances", "kindness to parents",
    "good character and manners", "the virtues of Ramadan and fasting",
    "controlling anger", "the value of time", "finding peace in remembering Allah (dhikr)",
    "Islamic history and the golden age", "charity (sadaqah)", "humility and avoiding arrogance",
    "hope after sadness and depression", "the importance of the night prayer (tahajjud)",
    "Jannah and how to reach it", "honesty and trust (amanah)",
]

SAFE_VISUALS = ("Use only calm cinematic scenery: nature, sky, clouds, sunrise, sunset, ocean, "
                "rain, desert, mountains, mosques, lanterns, candles, prayer beads, an open book, "
                "night stars, city lights. Never people's faces, never religious figures.")

os.makedirs(WORK, exist_ok=True)


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
        json.dump(h[-500:], f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- Gemini
client = genai.Client(api_key=GEMINI_KEY)


def ask_json(prompt):
    last = None
    for model in MODEL_CANDIDATES:
        for attempt in range(2):
            try:
                res = client.models.generate_content(
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


def pick_topic(history):
    used = [h["title"] for h in history[-80:]]
    theme = THEMES[len(history) % len(THEMES)]        # har din alag theme, ghoom kar
    data = ask_json(f"""You plan videos for the Facebook page "Islamic Motivational Videos"
(audience: Muslims worldwide, English).
Theme for today: {theme}
These titles were ALREADY posted, do NOT repeat or closely resemble them:
{json.dumps(used, ensure_ascii=False)}

Give ONE fresh, specific, emotionally engaging video idea inside this theme.
Return JSON: {{"topic": "one sentence describing the idea", "title": "catchy title, max 70 characters"}}""")
    return theme, data["topic"], data["title"]


RULES = """Accuracy rules (very important):
- Only mention Quran verses and hadith that are well known and authentic; give the surah name
  or the collection (e.g. Sahih Bukhari) in plain words. If unsure, do not quote, just give the lesson.
- Never invent stories, numbers or quotes. Say "peace be upon him" after prophets' names.
- Respectful, hopeful, sincere tone. No politics, no sectarian topics.
- Spoken plain sentences only: no emojis, no headings, no stage directions."""


def write_long(topic, title):
    data = ask_json(f"""Write the voice-over for a {LONG_WORDS}-word YouTube-style Islamic motivational
video for Facebook. Title: "{title}". Idea: {topic}

Structure: a powerful hook in the first 2 sentences that makes people keep watching,
then a story or explanation, practical lessons for daily life, and a heartfelt ending with a short dua.
Last scene: ask viewers to follow the page "Islamic Motivational Videos" and share the video.
{RULES}

Split into exactly {LONG_SCENES} scenes of similar length (total about {LONG_WORDS} words).
For each scene give a 1-3 word English stock-footage search term. {SAFE_VISUALS}

Return JSON: {{"scenes": [{{"text": "...", "visual": "..."}}],
 "caption": "2-3 line Facebook description that invites comments",
 "hashtags": ["#Islam", "..."] (8 hashtags)}}""")
    if len(data.get("scenes", [])) < 4:
        raise RuntimeError("Lambi script mein scenes kam hain")
    return data


def write_reel(topic, title):
    data = ask_json(f"""Write a {REEL_WORDS}-word Facebook Reel voice-over (about 50 seconds) on:
"{title}" - {topic}
First sentence must be a strong hook. Deliver one powerful lesson. End with:
"Follow for more reminders."
{RULES}

Split into exactly {REEL_SCENES} scenes. For each scene give a 1-3 word English stock-footage
search term. {SAFE_VISUALS}

Return JSON: {{"scenes": [{{"text": "...", "visual": "..."}}], "caption": "1-2 lines", "hashtags": ["#..."] (6 hashtags)}}""")
    if len(data.get("scenes", [])) < 2:
        raise RuntimeError("Reel script mein scenes kam hain")
    return data


# ---------------------------------------------------------------- audio
def tts(text, path):
    async def go():
        await edge_tts.Communicate(text, VOICE, rate=VOICE_RATE).save(path)
    for attempt in range(3):
        try:
            asyncio.run(go())
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            log(f"TTS retry {attempt + 1}: {e}")
            time.sleep(3)
    raise RuntimeError("Awaaz nahi bani")


# ---------------------------------------------------------------- stock clips
USED_CLIPS = set()


def pixabay_clip(query, path):
    if not PIXABAY_KEY:
        return False
    for q in (query, "islamic mosque", "nature sky", "clouds"):
        try:
            r = requests.get("https://pixabay.com/api/videos/", timeout=40, params={
                "key": PIXABAY_KEY, "q": q, "safesearch": "true", "per_page": 30,
                "video_type": "film"})
            r.raise_for_status()
            hits = [h for h in r.json().get("hits", []) if h["id"] not in USED_CLIPS]
        except Exception as e:
            log(f"Pixabay error ({q}): {str(e)[:150]}")
            continue
        random.shuffle(hits)
        for h in hits[:4]:
            v = h.get("videos", {})
            pick = next((v[s] for s in ("medium", "large", "small")
                         if v.get(s, {}).get("url") and v[s].get("width", 0) >= 960), None)
            if not pick:
                continue
            try:
                with requests.get(pick["url"], stream=True, timeout=120) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as f:
                        for chunk in resp.iter_content(1 << 20):
                            f.write(chunk)
                if os.path.getsize(path) > 50000:
                    USED_CLIPS.add(h["id"])
                    return True
            except Exception as e:
                log(f"Clip download fail: {str(e)[:150]}")
    return False


def fallback_clip(path, w, h):
    colors = random.choice([("0x0b1a33", "0x1f4d7a"), ("0x1b2a1f", "0x3d6b4f"),
                            ("0x2b1a33", "0x6b3d7a"), ("0x332411", "0x7a5a1f")])
    run(["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"gradients=s={w}x{h}:c0={colors[0]}:c1={colors[1]}:speed=0.01:d=15",
         "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", path])


# ---------------------------------------------------------------- subtitles
def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_srt(text, total, path, words_per_line):
    words = text.split()
    chunks = [" ".join(words[i:i + words_per_line]) for i in range(0, len(words), words_per_line)]
    weights = [len(c) + 3 for c in chunks]
    scale = total / max(sum(weights), 1)
    t, out = 0.0, []
    for i, (c, w) in enumerate(zip(chunks, weights), 1):
        end = t + w * scale
        out.append(f"{i}\n{srt_time(t)} --> {srt_time(end)}\n{c}\n")
        t = end
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


# ---------------------------------------------------------------- video
def build_video(script, tag, w, h, out_path):
    vertical = h > w
    job = os.path.join(WORK, tag)
    shutil.rmtree(job, ignore_errors=True)
    os.makedirs(job)
    style = ("FontName=DejaVu Sans,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
             "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,"
             + ("Fontsize=13,MarginV=70" if vertical else "Fontsize=17,MarginV=22"))
    parts = []
    for i, sc in enumerate(script["scenes"]):
        text = (sc.get("text") or "").strip()
        if not text:
            continue
        audio, clip, srt, part = f"a{i}.mp3", f"c{i}.mp4", f"s{i}.srt", f"p{i}.mp4"
        tts(text, os.path.join(job, audio))
        dur = duration(os.path.join(job, audio)) + 0.4
        if not pixabay_clip(sc.get("visual") or "nature", os.path.join(job, clip)):
            fallback_clip(os.path.join(job, clip), w, h)
        make_srt(text, dur - 0.4, os.path.join(job, srt), 4 if vertical else 6)
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30,"
              f"eq=brightness=-0.06,subtitles={srt}:force_style='{style}',format=yuv420p")
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", clip, "-i", audio, "-t", f"{dur:.2f}",
             "-vf", vf, "-af", "apad", "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
             "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k", part], cwd=job)
        parts.append(part)
        log(f"{tag}: scene {i + 1}/{len(script['scenes'])} ready")
    if not parts:
        raise RuntimeError(f"{tag}: koi scene nahi bana")
    with open(os.path.join(job, "list.txt"), "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy",
         "-movflags", "+faststart", os.path.abspath(out_path)], cwd=job)
    log(f"{tag}: video {duration(out_path) / 60:.2f} min")
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


def post_long(path, title, description):
    with open(path, "rb") as f:
        j = fb_json(requests.post(
            f"https://graph-video.facebook.com/{GRAPH_VER}/{FB_PAGE}/videos",
            data={"access_token": FB_TOKEN, "title": title, "description": description},
            files={"source": f}, timeout=3600))
    log(f"Long video posted: {j.get('id')}")
    return j.get("id")


def post_reel(path, description):
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
        "description": description, "access_token": FB_TOKEN}))
    log(f"Reel posted: {vid}")
    return vid


def description(title, script):
    tags = " ".join(t if t.startswith("#") else "#" + t for t in script.get("hashtags", []))
    return f"{title}\n\n{script.get('caption', '')}\n\n{tags}".strip()


# ---------------------------------------------------------------- main
def main():
    if not DRY_RUN and (not FB_TOKEN or not FB_PAGE):
        raise RuntimeError("FB_PAGE_ACCESS_TOKEN ya FB_PAGE_ID secret missing hai")
    history = load_history()
    theme, topic, title = pick_topic(history)
    log(f"Theme: {theme}\nTitle: {title}\nIdea: {topic}")

    long_script = write_long(topic, title)
    reel_script = write_reel(topic, title)

    entry = {"date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
             "theme": theme, "title": title}
    ok = 0

    try:
        build_video(long_script, "long", 1280, 720, "final_long.mp4")
        if not DRY_RUN:
            entry["long_id"] = post_long("final_long.mp4", title, description(title, long_script))
        ok += 1
    except Exception as e:
        log(f"LONG VIDEO ERROR: {e}")

    try:
        build_video(reel_script, "reel", 1080, 1920, "final_reel.mp4")
        if duration("final_reel.mp4") > 89:
            run(["ffmpeg", "-y", "-i", "final_reel.mp4", "-t", "89", "-c", "copy", "reel_cut.mp4"])
            shutil.move("reel_cut.mp4", "final_reel.mp4")
        if not DRY_RUN:
            entry["reel_id"] = post_reel("final_reel.mp4", description(title, reel_script))
        ok += 1
    except Exception as e:
        log(f"REEL ERROR: {e}")

    if ok and not DRY_RUN:
        history.append(entry)
        save_history(history)
    if ok < 2:
        sys.exit(1)
    log("Done successfully!")


if __name__ == "__main__":
    main()
