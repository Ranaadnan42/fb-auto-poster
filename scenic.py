"""
Wander Earth - AGENT (sirf bot nahi). Duniya ke har mulk ki 8-12 second ki khoobsurat cinematic reels.

Ian G Black / Swissaround / Patchara ka formula (audit, Nov 2026): bohat chhoti loop video, ek hi khoobsurat
shot, mood wala music, chhota sha'irana caption + jagah ka naam. Hum woh poori duniya ke liye karte hain.

Har run mein agent khud:
  1) SOCHTA   - pichli reels ke ASLI views (Facebook se) dekh kar agla mulk/shehar/manzar + mood chunta hai:
                jo chala us jaisa zyada, jo nahi chala us se door. Koi jagah 60 din tak dobara nahi.
  2) DHOONDTA - Pixabay, Pexels (key ho), Wikimedia Commons, Internet Archive, Mixkit (sab free, commercial theek).
  3) DEKHTA   - har clip ke 3 frames AI vision ko: sahi mulk/jagah? asli camera footage? watermark/likhai?
                khoobsurati 1-10. Sab se khoobsurat (8+) clip lagti hai; na mile to agent doosri jagah sochta hai.
  4) BANATA   - 9:16, ~10 sec, halka slow-motion, cinematic color grade, pehle 3 sec hook, neeche jagah ka naam,
                public-domain piano/strings (Wikimedia) fade in/out.
  5) LIKHTA   - chhota sha'irana caption + jagah + 3-5 hashtags.
  6) POST     - Reel + Story. Clip/jagah history mein - kabhi repeat nahi.

Env: SCENIC_PAGE_ID, SCENIC_PAGE_TOKEN, GEMINI_API_KEY (SCENIC_GEMINI_API_KEY ho to pehle), GROQ_API_KEY,
     PIXABAY_API_KEY, PEXELS_API_KEY (optional), DRY_RUN=1 (sirf banaye), POST_AT (UTC HH:MM)
"""
import base64
import datetime
import json
import os
import random
import re
import shutil
import subprocess
import time

import requests

import footage

PAGE_NAME = os.environ.get("SCENIC_PAGE_NAME", "Wander Earth")
PAGE_ID = os.environ.get("SCENIC_PAGE_ID")
TOKEN = os.environ.get("SCENIC_PAGE_TOKEN")
KEYS = [k for k in dict.fromkeys([os.environ.get("SCENIC_GEMINI_API_KEY"), os.environ.get("GEMINI_API_KEY")]) if k]
DRY_RUN = os.environ.get("DRY_RUN") == "1"
MODE = (os.environ.get("MODE") or "reel").strip().lower()          # reel | pic | long
GRAPH = "https://graph.facebook.com/v23.0"
W, H, FPS = 1080, 1920, 30
WORK = "work_scenic"
OUT = "final_scenic.mp4"
HIST_FILE = "scenic_history.json"
REPORT_FILE = f"scenic_{MODE}_last_run.json"
FONT = os.path.abspath("fonts/NotoSans-Bold.ttf")
TEXT_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]
VIS_MODELS = ["gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash-lite",
              "gemini-flash-latest", "gemma-4-31b-it", "gemma-4-26b-a4b-it"]
UA = {"User-Agent": "WanderEarthBot/1.0 (https://github.com/Ranaadnan42/fb-auto-poster)"}
REPORT = {"started": datetime.datetime.utcnow().isoformat(timespec="minutes"), "steps": [], "errors": []}
_DEAD = set()


def log(m):
    print(f"[scenic] {m}", flush=True)
    REPORT["steps"].append(str(m)[:300])


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{cmd[0]} fail: {r.stderr[-400:]}")
    return r.stdout


def probe(path):
    try:
        j = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height,r_frame_rate:format=duration", "-of", "json", path]))
        s = j["streams"][0]
        n, d = (s.get("r_frame_rate") or "30/1").split("/")
        return {"w": s["width"], "h": s["height"], "fps": float(n) / max(float(d), 1),
                "dur": float(j["format"]["duration"])}
    except Exception:
        return None


def load_hist():
    try:
        return json.load(open(HIST_FILE))
    except Exception:
        return {"posts": [], "clips": [], "music": []}


def save_hist(h):
    json.dump(h, open(HIST_FILE, "w"), indent=1, ensure_ascii=False)


# ---------------------------------------------------------------- AI (soch)
def _gem(model, key, parts, json_out=True, temp=0.9):
    cfg = {"temperature": temp}
    if json_out and not model.startswith("gemma"):
        cfg["responseMimeType"] = "application/json"
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                      timeout=90, json={"contents": [{"parts": parts}], "generationConfig": cfg})
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text[:150]}")
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _json(t):
    m = re.search(r"\{[\s\S]*\}", t or "")
    return json.loads(m.group(0)) if m else None


def think(prompt, temp=0.9):
    for key in KEYS:
        for m in TEXT_MODELS:
            if (key, m) in _DEAD:
                continue
            try:
                j = _json(_gem(m, key, [{"text": prompt}], temp=temp))
                if j:
                    return j
            except Exception as e:
                if "not valid" in str(e) or str(e)[:3] == "401":
                    _DEAD.update((key, x) for x in TEXT_MODELS + VIS_MODELS)     # key hi ghalat - is key ke sab model band
                elif any(c in str(e)[:4] for c in ("400", "403", "404", "429")):
                    _DEAD.add((key, m))
                log(f"brain {m}: {str(e)[:100]}")
    import groq_backup
    if groq_backup.enabled():
        return groq_backup.ask_json(prompt, temp, log)
    raise RuntimeError("Koi AI brain nahi chala (Gemini + Groq)")


LOOK_Q = """You are the footage-picking agent of "{page}", a Facebook page of 10-second ultra-beautiful cinematic reels
from every country (style of the best travel pages: one stunning, calm, atmospheric shot - rainy old-town streets with
warm shop lights, train-window views of mountains, misty lakes at sunrise, snowy villages, golden-hour skylines).
These {n} frames are from ONE stock clip found for: {want} ({country}).
Judge strictly and answer JSON:
{{"place_ok": true/false,   // really {country} / the kind of place wanted (false if clearly another country/landmark)
  "real": true/false,       // real camera footage (false for CGI, animation, AI art, slideshow, screen recording)
  "clean": true/false,      // false if a watermark, logo, burned-in text/subtitles, black bars or split screen
  "beauty": 1-10,           // how scroll-stopping & cinematic (10 = jaw-dropping; boring/ugly/shaky/dark/plain = 1-4)
  "why": "max 8 words"}}"""


def look(jpgs, want, country):
    """Clip ko AI ki aankh se dekhna. Wapas dict ya None (vision na chal saka)."""
    datas = [open(j, "rb").read() for j in jpgs if os.path.exists(j)]
    if not datas:
        return None
    prompt = LOOK_Q.format(page=PAGE_NAME, n=len(datas), want=want, country=country)
    parts = [{"text": prompt}] + [{"inline_data": {"mime_type": "image/jpeg",
                                                   "data": base64.b64encode(d).decode()}} for d in datas]
    for key in KEYS:
        for m in VIS_MODELS:
            if (key, m) in _DEAD:
                continue
            try:
                j = _json(_gem(m, key, parts, temp=0))
                if j and "beauty" in j:
                    return j
            except Exception as e:
                if "not valid" in str(e) or str(e)[:3] == "401":
                    _DEAD.update((key, x) for x in TEXT_MODELS + VIS_MODELS)     # key hi ghalat - is key ke sab model band
                elif any(c in str(e)[:4] for c in ("400", "403", "404", "429")):
                    _DEAD.add((key, m))
    try:
        import groq_vision
        j = groq_vision.ask_json(datas, prompt)
        if j and "beauty" in j:
            return j
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- 1) seekhna - asli views
def refresh_views(h):
    """Pichli reels ke plays Facebook se - agent inhi se seekhta hai."""
    if not (TOKEN and PAGE_ID):
        return
    now = time.time()
    for p in h["posts"][-60:]:
        if not p.get("vid") or now - p.get("ts", now) < 20 * 3600:
            continue
        if p.get("views_at") and now - p["views_at"] < 3 * 86400 and now - p["ts"] > 10 * 86400:
            continue
        try:
            j = requests.get(f"{GRAPH}/{p['vid']}/video_insights", timeout=30,
                             params={"metric": "blue_reels_play_count", "access_token": TOKEN}).json()
            v = j.get("data", [{}])[0].get("values", [{}])[0].get("value")
            if v is not None:
                p["views"], p["views_at"] = int(v), now
        except Exception:
            pass


def plan_next(h, avoid):
    posts = h["posts"]
    recent = [p for p in posts if time.time() - p.get("ts", 0) < 60 * 86400]
    used = sorted({f"{p['place']}, {p['country']}" for p in recent} | set(avoid))
    perf = [{"place": f"{p['place']}, {p['country']}", "mood": p.get("mood"), "hook": p.get("hook"),
             "views": p.get("views")} for p in posts[-40:] if p.get("views") is not None]
    perf.sort(key=lambda x: -x["views"])
    countries_recent = [p["country"] for p in posts[-12:]]
    return think(f"""You run the Facebook page "{PAGE_NAME}": 8-12 second, ultra-beautiful, calm cinematic reels from
EVERY country of the world. Page theme: Landscape, Nature, Outdoor, Photography - ultra-HD shots so beautiful people
stop scrolling and stare. Mostly NATURE (about 3 of 4 reels): mountains, glaciers, turquoise lakes, waterfalls, fjords,
misty forests, coastlines and cliffs, beaches, deserts at sunset, rice terraces, lavender/tulip fields, volcanoes,
northern lights, starry skies, wildlife-free scenery; the rest are scenic places in nature (alpine/snowy villages,
train-window POV through mountains, rainy old towns with warm lights). Viral reference pages get 10M-67M views.
Short text hook + place name + emotional music + short poetic caption.

Our past reels and their REAL plays (learn: do more of what worked, less of what didn't):
{json.dumps(perf[:25], ensure_ascii=False) if perf else "no data yet - start with the proven winners (Switzerland, Japan, Italy, Norway, Scotland, Austria) mixed with variety"}

Do NOT pick any of these places again: {json.dumps(used[-150:], ensure_ascii=False)}
Avoid the same country as the last few reels: {json.dumps(countries_recent[-4:], ensure_ascii=False)}
Over time cover every country, but favour places that are famously beautiful and that free stock-footage
sites (Pixabay, Pexels, Wikimedia) will really have clean footage of.

Pick the NEXT reel. JSON:
{{"country": "...", "flag": "emoji flag", "place": "city/village/landmark",
 "mood": "e.g. rainy evening / snowy morning / golden hour / misty sunrise / night lights / train window",
 "queries": ["6-8 short English stock-footage search terms, most specific first, e.g. 'hallstatt austria', 'hallstatt lake', 'austria alps village', 'austria'"],
 "hook": "max 6 words, shown on screen first 3 sec, curiosity/emotion, e.g. 'POV: 6AM in Austria' or 'Is this place even real?' (no emoji)",
 "time_label": "local-feeling time like '17:10' or '06:40' that fits the mood",
 "caption": "1-2 short poetic lines (max 25 words) about the feeling of this place, then a blank line, then '📍 Place, Country FLAG'",
 "hashtags": ["#3-5 tags, mix of place + #travel style"],
 "music_mood": "one of: calm piano / dreamy / melancholic / uplifting strings / romantic",
 "why": "why this will do well, max 12 words"}}""")


# ---------------------------------------------------------------- 2-3) footage dhoondna + dekhna
def find_shot(plan, h, job, need=8):
    want = f"{plan['place']} ({plan.get('mood', '')})"
    used = set(h.get("clips", []))
    seen, cands = set(), []
    pwords = set(footage.words(f"{plan['place']} {plan['country']}"))
    for q in (plan.get("queries") or [])[:8] + [plan["place"], plan["country"]]:
        for c in footage.videos(q, vertical=False) + footage.videos(q, vertical=True):
            if c["id"] in used or c["id"] in seen or c.get("dur", 0) < 5:
                continue
            seen.add(c["id"])
            c["score"] = footage.match_score(c.get("text", ""), pwords) + (0.5 if c.get("vertical") else 0)
            cands.append(c)
        if len(cands) >= 40:
            break
    cands.sort(key=lambda c: -c["score"])
    log(f"{len(cands)} clips mili - top {min(10, len(cands))} AI se dekhi jayengi")
    best = None
    for i, c in enumerate(cands[:10 if need >= 8 else 6]):
        raw = os.path.join(job, f"c{i}.mp4")
        try:
            if not footage.download(c["url"], raw, 200000):
                continue
        except Exception:
            continue
        info = probe(raw)
        if not info or info["dur"] < 4 or max(info["w"], info["h"]) < 1900:      # sirf Full-HD/4K
            continue
        jpgs = []
        for k, at in enumerate((0.2, 0.5, 0.8)):
            jp = os.path.join(job, f"c{i}_{k}.jpg")
            if footage.frame(raw, jp, info["dur"] * at):
                jpgs.append(jp)
        v = look(jpgs, want, plan["country"])
        if v is None:
            # aankh band - sirf pakka lafz-match aur saaf stock source chalega
            ok, beauty = c["score"] >= 1 and c.get("src") in ("pixabay", "pexels", "mixkit"), 8
            v = {"why": "vision band - tag match"}
        else:
            ok = v.get("place_ok") and v.get("real") and v.get("clean")
            beauty = int(v.get("beauty") or 0) + (1 if max(info["w"], info["h"]) >= 3800 and int(v.get("beauty") or 0) >= 8 else 0)   # 4K ko tarjeeh
        log(f"clip {c['id']} ({c.get('src')}): ok={bool(ok)} beauty={beauty} - {v.get('why', '')}")
        if ok and (best is None or beauty > best["beauty"]):
            best = {**c, "path": raw, "info": info, "beauty": beauty}
            if beauty >= 9:
                break
    if best and best["beauty"] >= need:
        return best
    return None


# ---------------------------------------------------------------- 4) music (public domain, Wikimedia)
MUSIC = {
    "calm piano": ["Gymnopedie No. 1", "Clair de lune Debussy", "Satie Gnossienne", "Chopin Nocturne E flat"],
    "dreamy": ["Debussy Reverie", "Debussy Arabesque No. 1", "Clair de lune", "Gymnopedie"],
    "melancholic": ["Chopin Prelude E minor", "Albinoni Adagio", "Chopin Nocturne C sharp minor", "Moonlight Sonata"],
    "uplifting strings": ["Air on the G String", "Pachelbel Canon", "Vivaldi Spring", "Grieg Morning Mood"],
    "romantic": ["Liebestraum Liszt", "Meditation Thais", "Saint-Saens The Swan", "Faure Pavane"],
}
_OK_LIC = ("public domain", "pd", "cc0", "cc by", "cc-by", "cc by-sa", "cc-by-sa")


def find_music(mood, h, job):
    pieces = MUSIC.get((mood or "").lower().strip()) or random.choice(list(MUSIC.values()))
    used = set(h.get("music", [])[-25:])
    for q in random.sample(pieces, len(pieces)):
        try:
            r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=40, params={
                "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 15,
                "gsrsearch": f"filetype:audio {q}", "prop": "videoinfo",
                "viprop": "url|size|extmetadata|derivatives"})
            pages = list((r.json().get("query", {}).get("pages", {}) or {}).values())
        except Exception as e:
            log(f"music search error: {str(e)[:80]}")
            continue
        random.shuffle(pages)
        for pg in pages:
            title = pg.get("title", "")
            info = (pg.get("videoinfo") or [{}])[0]
            lic = ((info.get("extmetadata") or {}).get("LicenseShortName", {}).get("value") or "").lower()
            if title in used or not any(lic.startswith(x) for x in _OK_LIC) or "nc" in lic or "nd" in lic:
                continue
            if float(info.get("duration") or 0) < 40:
                continue
            ders = [d.get("src") for d in info.get("derivatives", []) if str(d.get("src", "")).endswith(".mp3")]
            url = ders[0] if ders else info.get("url")
            if not url or float(info.get("size") or 0) > 150e6 and not ders:
                continue
            path = os.path.join(job, "music" + os.path.splitext(url)[1][:5])
            try:
                if footage.download(url, path, 50000):
                    log(f"music: {title} ({lic})")
                    return path, title, float(info.get("duration") or 60)
            except Exception:
                continue
    return None, None, 0


def synth_music(path, secs):
    """Aakhri chara: khud bana halka cinematic pad (copyright free)."""
    root = random.choice([130.8, 146.8, 164.8])
    parts = [f"0.04*sin(2*PI*{root * m:.2f}*t)*(0.6+0.4*sin(2*PI*t/{7 + k}))"
             for k, m in enumerate([1, 1.25, 1.5, 2, 2.5])]
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         f"aevalsrc='{'+'.join(parts)}':s=44100:d={secs + 1:.1f}", "-af", "lowpass=f=2200,aecho=0.8:0.7:400:0.3",
         path])


# ---------------------------------------------------------------- 4) edit
def _plain(s):
    return re.sub(r"[^\x00-ɏ’— ]", "", s or "").strip()


def render(shot, plan, music, mus_dur, job):
    info = shot["info"]
    slow = 1.25 if info["fps"] >= 29 else 1.0                      # halka slow-motion = cinematic
    length = random.uniform(9.0, 11.5)
    src_len = min(length / slow, info["dur"] - 0.2)
    length = src_len * slow
    start = max(0.0, (info["dur"] - src_len) * random.uniform(0.25, 0.6))
    hook = os.path.join(job, "hook.txt")
    place = os.path.join(job, "place.txt")
    open(hook, "w").write(_plain(plan.get("hook")) or _plain(plan["place"]))
    open(place, "w").write(_plain(f"{plan['place']}, {plan['country']}").upper()
                           + (f"   {plan.get('time_label')}" if plan.get("time_label") else ""))
    fade_out = max(length - 0.6, 0)
    vf = (f"setpts={slow}*PTS,scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},fps={FPS},"
          "eq=contrast=1.07:saturation=1.14:brightness=0.005:gamma=0.98,"
          "colorbalance=rs=0.02:bs=-0.02:rh=0.03:bh=-0.03,unsharp=5:5:0.4,vignette=PI/6,"
          f"drawtext=fontfile={FONT}:textfile={hook}:fontcolor=white:fontsize=68:x=(w-text_w)/2:y=h*0.16:"
          "shadowcolor=black@0.7:shadowx=3:shadowy=3:enable='lt(t,3.4)':alpha='if(lt(t,0.3),t/0.3,if(gt(t,3.0),(3.4-t)/0.4,1))',"
          f"drawtext=fontfile={FONT}:textfile={place}:fontcolor=white@0.92:fontsize=38:x=(w-text_w)/2:y=h*0.83:"
          "shadowcolor=black@0.7:shadowx=2:shadowy=2:alpha='if(lt(t,0.8),t/0.8,1)',"
          f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_out:.2f}:d=0.6,format=yuv420p")
    m_off = random.uniform(0, max(0.0, min(25.0, mus_dur - length - 5))) if mus_dur else 0
    af = f"atrim=0:{length:.2f},afade=t=in:st=0:d=0.8,afade=t=out:st={max(length - 1.6, 0):.2f}:d=1.6,loudnorm=I=-15"
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{src_len:.2f}", "-i", shot["path"],
         "-ss", f"{m_off:.2f}", "-i", music, "-filter_complex", f"[0:v]{vf}[v];[1:a]{af}[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{length:.2f}", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-maxrate", "16M", "-bufsize", "24M",
         "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT])
    return length



# ---------------------------------------------------------------- SEO caption
def seo_caption(plan, kind="reel"):
    """Caption = sha'irana lines + jagah + log jo search karte hain woh alfaaz + sawal + hashtags (seo.py)."""
    try:
        import seo
        title = plan.get("title") or f"{plan.get('place')}, {plan.get('country')}"
        text = f"{plan.get('caption', '')}\nMood: {plan.get('mood', '')}. Place: {plan.get('place')}, {plan.get('country')}"
        body = seo.build(lambda pr, temp=0.8: think(pr, temp), "scenic", title, text, lang="en",
                         is_reel=(kind == "reel"), search_terms=plan.get("queries"))
        poem = (plan.get("caption") or "").strip()
        return f"{poem}\n\n{body}".strip() if poem else body
    except Exception as e:
        log(f"seo fallback: {str(e)[:100]}")
        tags = " ".join(t if t.startswith("#") else f"#{t}" for t in (plan.get("hashtags") or [])[:5])
        return f"{(plan.get('caption') or '').strip()}\n\n{tags}".strip()


# ---------------------------------------------------------------- PIC (ultra-HD photo + photo story)
def find_photo(plan, h, job):
    used = set(h.get("clips", []))
    pwords = set(footage.words(f"{plan['place']} {plan['country']}"))
    cands, seen = [], set()
    for q in (plan.get("queries") or [])[:6] + [plan["place"]]:
        for c in footage.photos(q):
            if c["id"] in used or c["id"] in seen:
                continue
            seen.add(c["id"])
            c["score"] = footage.match_score(c.get("text", ""), pwords)
            cands.append(c)
        if len(cands) >= 40:
            break
    cands.sort(key=lambda c: -c["score"])
    best = None
    for i, c in enumerate(cands[:10]):
        jp = os.path.join(job, f"p{i}.jpg")
        try:
            if not footage.download(c["url"], jp, 150000):
                continue
            from PIL import Image
            wd, ht = Image.open(jp).size
        except Exception:
            continue
        if max(wd, ht) < 1900:
            continue
        small = os.path.join(job, f"p{i}_s.jpg")
        Image.open(jp).convert("RGB").resize((640, int(640 * ht / wd))).save(small, quality=85)
        v = look([small], plan["place"], plan["country"]) or {}
        ok = v.get("place_ok") and v.get("real") and v.get("clean")
        beauty = int(v.get("beauty") or 0)
        log(f"photo {c['id']} {wd}x{ht}: ok={bool(ok)} beauty={beauty} - {v.get('why', '')}")
        if ok and (best is None or beauty > best["beauty"]):
            best = {**c, "path": jp, "beauty": beauty}
            if beauty >= 9:
                break
    return best if best and best["beauty"] >= 8 else None


def post_photo(path, caption):
    with open(path, "rb") as f:
        j = fb(requests.post(f"{GRAPH}/{PAGE_ID}/photos", timeout=300, files={"source": f},
                             data={"caption": caption, "access_token": TOKEN}))
    try:                                        # wohi tasveer page story par bhi
        try:
            with open(path, "rb") as f:
                pid = fb(requests.post(f"{GRAPH}/{PAGE_ID}/photos", timeout=300, files={"source": f},
                                       data={"published": "false", "temporary": "true",
                                             "access_token": TOKEN}))["id"]
        except Exception as e:                  # unpublished mana ho to wohi post wali photo
            log(f"unpublished photo nahi bani ({str(e)[:80]}) - post wali photo se story")
            pid = j["id"]
        fb(requests.post(f"{GRAPH}/{PAGE_ID}/photo_stories", timeout=60,
                         data={"photo_id": pid, "access_token": TOKEN}))
        log("photo story lagi")
    except Exception as e:
        log(f"photo story skip: {str(e)[:100]}")
    return j.get("post_id") or j.get("id")


# ---------------------------------------------------------------- LONG (3.5-4 min 4K-feel nature film)
def plan_long(h, avoid):
    done = [p["country"] for p in h["posts"] if p.get("kind") == "long" and time.time() - p.get("ts", 0) < 120 * 86400]
    return think(f"""You run "{PAGE_NAME}" (Landscape, Nature, Outdoor, Photography; ultra-HD). Plan today's LONG video:
a calm ~4 minute cinematic nature film of ONE country ("Norway in 4K - Relaxing Nature Film" style) - 14 different
breathtaking natural places of that country, no narration, only music.
Countries already done (avoid): {json.dumps(done + avoid, ensure_ascii=False)}
Choose a country famous for nature that free stock sites (Pixabay/Pexels/Wikimedia) have lots of clean footage of.
JSON: {{"country": "...", "flag": "emoji",
 "title": "SEO title max 70 chars, e.g. 'Norway 4K - Fjords, Northern Lights & Mountains | Relaxing Nature Film'",
 "shots": [{{"place": "place name", "queries": ["3 short search terms, specific first"]}}  x 14],
 "caption": "2 short poetic lines about this country's nature",
 "music_mood": "calm piano / dreamy / uplifting strings / romantic / melancholic",
 "queries": ["5 phrases people search for this kind of video"]}}""")


def long_film(plan, h, job):
    clips = []
    for k, sh in enumerate(plan.get("shots", [])[:16]):
        sub = {"place": sh.get("place", plan["country"]), "country": plan["country"],
               "queries": sh.get("queries") or [sh.get("place", "")], "mood": ""}
        d = os.path.join(job, f"s{k}")
        os.makedirs(d, exist_ok=True)
        got = find_shot(sub, {"clips": list(h.get("clips", [])) + [c["id"] for c in clips]}, d, need=7)
        if got:
            got["label"] = sub["place"]
            clips.append(got)
        if len(clips) >= 14:
            break
    if len(clips) < 8:
        raise RuntimeError(f"long video ke liye sirf {len(clips)} achi clips mili")
    segs, seg_len = [], 16.0
    for i, c in enumerate(clips):
        out = os.path.join(job, f"seg{i}.mp4")
        info = c["info"]
        slow = 1.25 if info["fps"] >= 29 else 1.0
        src = min(seg_len / slow, info["dur"] - 0.2)
        st = max(0.0, (info["dur"] - src) * 0.3)
        lab = os.path.join(job, f"lab{i}.txt")
        open(lab, "w").write(_plain(c["label"]).upper())
        dur = src * slow
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{st:.2f}", "-t", f"{src:.2f}", "-i", c["path"], "-an", "-vf",
             f"setpts={slow}*PTS,scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,crop=1920:1080,"
             f"fps={FPS},eq=contrast=1.06:saturation=1.12:gamma=0.98,unsharp=5:5:0.35,vignette=PI/7,"
             f"drawtext=fontfile={FONT}:textfile={lab}:fontcolor=white@0.9:fontsize=40:x=80:y=h-130:"
             f"shadowcolor=black@0.7:shadowx=2:shadowy=2:enable='between(t,1,6)':alpha='if(lt(t,1.6),(t-1)/0.6,if(gt(t,5.4),(6-t)/0.6,1))',"
             f"fade=t=in:st=0:d=0.8,fade=t=out:st={dur - 0.8:.2f}:d=0.8,format=yuv420p",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", out])
        segs.append(out)
    # title card pehle 4 sec pehli clip par
    lst = os.path.join(job, "list.txt")
    open(lst, "w").write("".join(f"file '{os.path.abspath(x)}'\n" for x in segs))
    joined = os.path.join(job, "joined.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    total = probe(joined)["dur"]
    title = os.path.join(job, "title.txt")
    open(title, "w").write(_plain(plan["country"]).upper() + "  -  4K")
    music, mtitle, _ = find_music(plan.get("music_mood"), h, job)
    if not music:
        music, mtitle = os.path.join(job, "pad.m4a"), "synth pad"
        synth_music(music, total + 2)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-stream_loop", "-1", "-i", music, "-filter_complex",
         f"[0:v]drawtext=fontfile={FONT}:textfile={title}:fontcolor=white:fontsize=96:x=(w-text_w)/2:y=(h-text_h)/2:"
         f"shadowcolor=black@0.6:shadowx=4:shadowy=4:enable='lt(t,4.5)':alpha='if(lt(t,0.8),t/0.8,if(gt(t,3.7),(4.5-t)/0.8,1))'[v];"
         f"[1:a]atrim=0:{total:.2f},afade=t=in:st=0:d=2,afade=t=out:st={total - 3:.2f}:d=3,loudnorm=I=-16[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "copy" if False else "libx264", "-preset", "medium", "-crf", "19",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.2f}", OUT])
    return clips, mtitle, total


def post_long(title, desc):
    with open(OUT, "rb") as f:
        j = fb(requests.post(f"https://graph-video.facebook.com/v23.0/{PAGE_ID}/videos", timeout=3600,
                             files={"source": f}, data={"title": title[:250], "description": desc,
                                                        "access_token": TOKEN}))
    return j.get("id")


# ---------------------------------------------------------------- 6) post
def fb(r):
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"Facebook: {j['error'].get('message')}")
    return j


def post_reel(desc):
    base = f"{GRAPH}/{PAGE_ID}/video_reels"
    vid = fb(requests.post(base, data={"upload_phase": "start", "access_token": TOKEN}, timeout=60))["video_id"]
    with open(OUT, "rb") as f:
        fb(requests.post(f"https://rupload.facebook.com/video-upload/v23.0/{vid}", data=f, timeout=900,
                         headers={"Authorization": f"OAuth {TOKEN}", "offset": "0",
                                  "file_size": str(os.path.getsize(OUT))}))
    fb(requests.post(base, timeout=60, data={"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                             "description": desc, "access_token": TOKEN}))
    try:
        import stories
        stories.try_story(PAGE_ID, TOKEN, OUT, "v23.0", log, REPORT["errors"])
    except Exception as e:
        log(f"story skip: {str(e)[:100]}")
    return vid


def brand(job):
    """Ek baar: page ki profile picture + cover - sab se khoobsurat ultra-HD tasveer se."""
    from PIL import Image
    h = {"clips": []}
    best = None
    for plan in ({"place": "Moraine Lake", "country": "Canada",
                  "queries": ["moraine lake canada", "moraine lake sunrise", "banff lake mountains"]},
                 {"place": "Lofoten Islands", "country": "Norway",
                  "queries": ["lofoten norway", "reine lofoten", "lofoten mountains"]},
                 {"place": "Dolomites", "country": "Italy",
                  "queries": ["tre cime di lavaredo", "dolomites sunrise", "seceda dolomites"]},
                 {"place": "Lauterbrunnen Valley", "country": "Switzerland",
                  "queries": ["lauterbrunnen valley", "swiss alps valley", "matterhorn"]},
                 {"place": "Torres del Paine", "country": "Chile",
                  "queries": ["torres del paine", "patagonia mountains", "fitz roy patagonia"]}):
        best = find_photo(plan, h, job)
        if best:
            break
    if not best:
        log("brand: koi 8+/10 tasveer nahi mili")
        return
    im = Image.open(best["path"]).convert("RGB")
    w, ht = im.size
    s = min(w, ht)
    prof = os.path.join(job, "profile.jpg")
    im.crop(((w - s) // 2, (ht - s) // 2, (w + s) // 2, (ht + s) // 2)).resize((1080, 1080)).save(prof, quality=95)
    cw, ch = (w, int(w / 1.777)) if w / ht < 1.777 else (int(ht * 1.777), ht)
    cov = os.path.join(job, "cover.jpg")
    im.crop(((w - cw) // 2, (ht - ch) // 2, (w + cw) // 2, (ht + ch) // 2)).resize((1920, 1080)).save(cov, quality=95)
    shutil.copy(prof, "final_scenic.jpg")
    log(f"brand: {best['id']} beauty {best['beauty']}/10")
    if DRY_RUN:
        return

    try:                                        # seedha URL - FB khud square kaat leta hai
        r = requests.post(f"{GRAPH}/{PAGE_ID}/picture", timeout=120,
                          data={"picture": best["url"], "access_token": TOKEN})
        log(f"profile picture: {r.status_code} {r.text[:200]}")
    except Exception as e:
        log(f"profile picture fail: {e}")
    try:                                        # cover ke liye published photo (welcome post) chahiye
        with open(cov, "rb") as f:
            cid = fb(requests.post(f"{GRAPH}/{PAGE_ID}/photos", timeout=300, files={"source": f},
                                   data={"caption": "Welcome to Wander Earth 🌍 Ultra-HD landscapes, nature and "
                                                    "outdoor beauty from every country on Earth. Follow for daily 4K "
                                                    "escapes. 🌄🌿🏞️📸\n\n"
                                                    "#WanderEarth #Nature #Landscape #Travel #4K",
                                         "access_token": TOKEN}))["id"]
        r = requests.post(f"{GRAPH}/{PAGE_ID}", timeout=120,
                          data={"cover": cid, "no_feed_story": "true", "access_token": TOKEN})
        log(f"cover: {r.status_code} {r.text[:200]}")
    except Exception as e:
        log(f"cover fail: {e}")


def fix_token():
    """Agar secret mein user token ho to us se page ka (never-expiring) token nikal lo."""
    global TOKEN
    if not (TOKEN and PAGE_ID):
        return
    try:
        me = requests.get(f"{GRAPH}/me", params={"fields": "id", "access_token": TOKEN}, timeout=30).json()
        if me.get("id") == PAGE_ID:
            log("token: page token theek hai")
            return
        pt = requests.get(f"{GRAPH}/{PAGE_ID}", params={"fields": "access_token", "access_token": TOKEN},
                          timeout=30).json().get("access_token")
        if pt:
            TOKEN = pt
            log("token: user token tha - page token bana kar istemal kiya")
        else:
            log(f"token: page token nahi mila - me={str(me)[:150]}")
    except Exception as e:
        log(f"token check fail: {e}")


def main():
    if not DRY_RUN and not (PAGE_ID and TOKEN):
        log("SCENIC_PAGE_ID / SCENIC_PAGE_TOKEN abhi set nahi - page jurne tak kuch nahi")
        return
    fix_token()
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    h = load_hist()
    refresh_views(h)
    REPORT["mode"] = MODE
    if MODE == "brand":
        return brand(WORK)
    if MODE == "long":
        plan, clips, avoid = None, None, []
        for _ in range(2):
            plan = plan_long(h, avoid)
            log(f"long film: {plan.get('country')} - {plan.get('title')}")
            try:
                clips, mtitle, secs = long_film(plan, h, WORK)
                break
            except RuntimeError as e:
                log(str(e))
                avoid.append(plan.get("country"))
        if not clips:
            raise SystemExit("long video ke liye footage kam")
        plan.setdefault("place", plan["country"])
        desc = seo_caption(plan, "long")
        chapters = "\n".join(f"{int(k * 16 // 60)}:{int(k * 16 % 60):02d} {c['label']}" for k, c in enumerate(clips))
        desc = f"{desc}\n\n{chapters}"
        log(f"long video {secs / 60:.1f} min ({len(clips)} jagahen)")
        REPORT.update(country=plan["country"], title=plan.get("title"), caption=desc)
        if DRY_RUN:
            return
        import slot_wait
        slot_wait.wait(log)
        vid = post_long(plan.get("title") or plan["country"], desc)
        log(f"Long video posted: {vid}")
        h["posts"].append({"ts": time.time(), "vid": vid, "kind": "long", "place": plan["country"],
                           "country": plan["country"], "mood": "long film", "hook": plan.get("title")})
        h["clips"] = (h.get("clips", []) + [c["id"] for c in clips])[-3000:]
        save_hist(h)
        return

    shot, plan, avoid = None, None, []
    for attempt in range(4):
        plan = plan_next(h, avoid)
        log(f"agent ka faisla: {plan.get('place')}, {plan.get('country')} - {plan.get('mood')} ({plan.get('why')})")
        shot = find_photo(plan, h, WORK) if MODE == "pic" else find_shot(plan, h, WORK)
        if shot:
            break
        log("is jagah ki koi 8+/10 khoobsurat saaf footage nahi mili - agent doosri jagah sochta hai")
        avoid.append(f"{plan.get('place')}, {plan.get('country')}")
    if not shot:
        raise SystemExit("4 jagahon par bhi achi footage nahi mili")
    desc = seo_caption(plan, MODE)
    REPORT.update(place=plan.get("place"), country=plan.get("country"), caption=desc, clip=shot["id"],
                  beauty=shot["beauty"])
    mtitle = None
    if MODE == "reel":
        music, mtitle, mdur = find_music(plan.get("music_mood"), h, WORK)
        if not music:
            music, mtitle, mdur = os.path.join(WORK, "pad.m4a"), "synth pad", 0
            synth_music(music, 14)
        secs = render(shot, plan, music, mdur, WORK)
        log(f"video {secs:.1f}s ban gayi (beauty {shot['beauty']}/10, {shot.get('src')})")
    else:
        shutil.copy(shot["path"], "final_scenic.jpg")
    if DRY_RUN:
        log("DRY RUN - post nahi kiya")
        return
    import slot_wait
    slot_wait.wait(log)
    vid = post_photo(shot["path"], desc) if MODE == "pic" else post_reel(desc)
    log(f"{MODE} posted: {vid}")
    REPORT["posted"] = vid
    h["posts"].append({"ts": time.time(), "vid": vid if MODE == "reel" else None, "post": vid, "kind": MODE,
                       "place": plan.get("place"), "country": plan.get("country"), "mood": plan.get("mood"),
                       "hook": plan.get("hook"), "clip": shot["id"], "beauty": shot["beauty"]})
    h["clips"] = (h.get("clips", []) + [shot["id"]])[-3000:]
    if mtitle and mtitle != "synth pad":
        h["music"] = (h.get("music", []) + [mtitle])[-200:]
    save_hist(h)


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        REPORT["errors"].append(f"fatal: {str(e)[:400]}")
        raise
    finally:
        REPORT["finished"] = datetime.datetime.utcnow().isoformat(timespec="minutes")
        json.dump(REPORT, open(REPORT_FILE, "w"), indent=1, ensure_ascii=False)
