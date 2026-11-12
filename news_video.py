"""
News Act + Sports Hubs - REEL aur LONG VIDEO agent (English + Urdu), asli footage ke sath.

KIND=reel  -> 9:16, ~45-60 sec, ek bari taaza khabar (page reel + story)
KIND=long  -> 16:9, ~3-4 min bulletin: 5 alag khabrein (sports mein 5 alag khel)

Har khabar:
  - news.py wali feeds se taaza, pehle na chali khabar
  - AI apne alfaz mein script likhta hai (copy nahi, sirf asal facts)
  - Har jumle par jo cheez boli ja rahi hai us ki ASLI footage (Pixabay/Wikimedia/NASA/Archive/Mixkit,
    photo mile to Ken Burns harkat) - koi AI chehra nahi
  - Neural awaaz (ur-PK-AsadNeural / en-GB-RyanNeural), subtitles, lower-third headline, halka music

Env: PAGES, LANGUAGE, KIND, NEWS_/SPORTS_PAGE_TOKEN/ID, GROQ_API_KEY, GEMINI_API_KEY, PIXABAY_API_KEY, DRY_RUN
"""
import asyncio
import datetime
import json
import os
import random
import re
import subprocess
import sys
import time

import requests

import footage
import news

KIND = (os.environ.get("KIND") or "reel").strip().lower()
LANG = news.LANG
DRY_RUN = news.DRY_RUN
GRAPH_VER = news.GRAPH_VER
HIST_FILE = "news_video_history.json"
REPORT_FILE = f"news_{KIND}_{LANG}_last_run.json"
WORK = f"work_newsv_{KIND}_{LANG}"
W, H = (1080, 1920) if KIND == "reel" else (1920, 1080)
FPS = 30
VOICE = {"en": ("en-GB-RyanNeural", "+4%"), "ur": ("ur-PK-AsadNeural", "+0%")}[LANG]
FONT = "Noto Naskh Arabic" if LANG == "ur" else "Noto Sans"
STORIES = 1 if KIND == "reel" else 6

REPORT = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "kind": KIND, "lang": LANG,
          "dry_run": DRY_RUN, "posted": {}, "errors": []}
os.makedirs(WORK, exist_ok=True)
log = news.log


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg fail: {r.stderr[-400:]}")


def duration(p):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                              "default=nw=1:nk=1", p], capture_output=True, text=True, timeout=60)
        return float(out.stdout.strip())
    except Exception:
        return 0.0


# ---------------------------------------------------------------- history
def load_hist():
    try:
        with open(HIST_FILE, encoding="utf-8") as f:
            h = json.load(f)
    except Exception:
        h = {}
    for k in ("news", "sports", "used_clips"):
        h.setdefault(k, [])
    return h


def save_hist(h):
    for k in ("news", "sports"):
        h[k] = h[k][-400:]
    h["used_clips"] = h["used_clips"][-2500:]
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- stories
def pick_stories(kind, past):
    pool = news.NEWS_REGIONS if kind == "news" else news.SPORTS
    picked, links, topics = [], set(), set()
    for topic in news.pick_topic(kind, past):
        if len(picked) >= STORIES:
            break
        if topic in topics:
            continue
        items = [i for i in news.fresh_items(pool[topic], past) if i["link"] not in links]
        items = [i for i in items if len(i["desc"]) >= 60] or items    # tafseel wali khabar pehle
        log(f"{kind}/{topic}: {len(items)} taaza")
        if not items:
            continue
        it = random.choice(items[:3])
        it["topic"] = topic
        picked.append(it)
        links.add(it["link"])
        topics.add(topic)
    if not picked:
        raise RuntimeError("koi taaza khabar nahi mili")
    return picked


def write_script(kind, stories):
    P = news.PAGES[kind]
    lang = ("natural spoken Urdu in Urdu script (like a BBC Urdu / Geo news anchor; no Hindi words, no Roman)"
            if LANG == "ur" else "natural spoken English like a BBC news anchor")
    lst = "\n".join(f"{n + 1}. [{s['topic'].replace('_', ' ')}] {s['title']} -- {s['desc'] or '(headline only)'} "
                    f"(source: {s['source']})" for n, s in enumerate(stories))
    per = "4-5 scenes (the whole reel 150-190 spoken words, about 50-60 seconds)" if KIND == "reel" \
        else "4 scenes each (EACH story at least 130-160 spoken words - the whole video must be 3-4 minutes)"
    prompt = f"""You are the anchor and script writer of the Facebook page "{P['name']}"
({'world news' if kind == 'news' else 'world sports news'}). Write a {'short vertical REEL' if KIND == 'reel' else 'news BULLETIN video'}
in {lang} covering these stories in this order:
{lst}

Rules:
- Your OWN words only - never copy the source's sentences.
- Only facts EXPLICITLY written above. Anything not written there (appointments, numbers, scores, quotes, names, dates,
  causes, results) must NOT be stated, not even as a guess. If details are thin, explain general background (what the
  country/league/tournament is) without adding new facts about this story.
- Neutral, professional, easy to understand. Mention the source naturally ("according to BBC").
- ORIGINALITY (Facebook only pays for original content): after the facts of each story add 1-2 sentences of
  your own explanation - why it matters / what it means for viewers in Pakistan, the Gulf and the wider world
  (clearly as analysis, not new facts). The first 3 seconds must be a strong hook about the biggest story.
{news.brain_tips(kind)}- Start with a strong one-sentence hook. End with: ask viewers to follow {P['name']}, like and share.
- Each story gets {per}.
- For every scene give "visuals": 1-3 short ENGLISH search terms IN THE ORDER the narration mentions them.
  The FIRST term must name the SPECIFIC thing of the story (e.g. "Poundland store", "Barcelona general strike",
  "US Capitol building", "Holger Rune tennis") - never generic words like "office building", "shopping street",
  "city skyline" alone (a country's flag/city/landmark, parliament building, stadium, the sport being played,
  oil tanker, stock market screen, rain flood street...). Must be the SPECIFIC thing said. Never a person's
  name, never a logo or channel/page name, never military, violence, blood, weapons, dead bodies or explosions.
  Never generic mood shots (sunset, tunnel, sky, person on phone, smiling people, like/subscribe button, green
  screen, hands typing) - only the concrete place/thing of THIS story. For sports use the exact sport (tennis
  match, cricket match) - never a different sport.

Return JSON:
{{"title": "video title, max 10 words",
  "intro": {{"text": "hook sentence", "visuals": ["..."]}},
  "stories": [{{"headline": "short on-screen headline max 8 words",
    "subjects": ["1-3 REAL names written in that story above: the main company/brand/shop, person, team, player, ship, city/country or building, as their English Wikipedia title (e.g. 'Pete Hegseth', 'Real Madrid CF', 'Gaza City'). [] if none"],
    "scenes": [{{"text": "...", "visuals": ["..."]}}]}}],
  "outro": {{"text": "follow / like / share line", "visuals": ["..."]}},
  "caption": "2-3 sentence post description in the same language",
  "hashtags": ["6 hashtags without #"]}}"""
    j = news.ask_json(prompt)
    if not j.get("stories"):
        raise RuntimeError("AI ne script nahi di")
    return j


# ---------------------------------------------------------------- voice + music
def clean_voice(t):
    t = re.sub(r"[#*_\"“”]", " ", t or "")
    if LANG == "ur":
        t = t.replace("ى", "ی").replace("ي", "ی")
    return re.sub(r"\s{2,}", " ", t).strip()


def tts(text, path):
    import edge_tts

    async def go():
        await edge_tts.Communicate(clean_voice(text), VOICE[0], rate=VOICE[1]).save(path)
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
    root = random.choice([110.0, 123.5, 130.8])
    parts = []
    for k, ch in enumerate([[1, 1.5, 2], [0.89, 1.33, 1.78], [0.84, 1.26, 1.68], [0.94, 1.41, 1.88]]):
        env = f"(0.5+0.5*sin(2*PI*t/12-{k}*PI/2))"
        parts += [f"0.035*sin(2*PI*{root * m:.2f}*t)*{env}" for m in ch]
    parts.append("0.02*sin(2*PI*55*t)*(0.5+0.5*sin(2*PI*t*2))")       # halki news-dhadkan
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         f"aevalsrc='{'+'.join(parts)}':s=44100:d={secs + 1:.1f}", "-af", "lowpass=f=1800,volume=0.8", path])


# ---------------------------------------------------------------- footage (asli)
def color_clip(out, secs):
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         f"gradients=s={W}x{H}:c0=0x0b1a33:c1=0x2a0606:d={secs:.2f}:speed=0.02:r={FPS}",
         "-t", f"{secs:.2f}", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", out])


def _render_clip(raw, secs, out):
    d = duration(raw) or 10
    start = max(0.0, random.uniform(0, max(0.0, d - secs - 0.5))) if d > secs + 1 else 0
    loop = ["-stream_loop", "-1"] if d < secs else []
    run(["ffmpeg", "-y", "-loglevel", "error", *loop, "-ss", f"{start:.2f}", "-i", raw, "-t", f"{secs:.2f}",
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
                f"eq=contrast=1.04:saturation=1.06,format=yuv420p",
         "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", out])


def get_clip(term, secs, out, used, said="", kind="news"):
    """AGENT: har clip ke frames AI dekhta hai - sirf wohi lagti hai jo waqai boli ja rahi cheez dikhaye.
    Pehle video (dunya bhar ki free sites), na mile to asli photo. Be-taalluq clip kabhi nahi."""
    import footage_agent as fa
    want = footage.words(term)
    vertical = H > W
    cands = [c for c in footage.videos(term, vertical) if c["id"] not in used
             and footage.match_score(c.get("text"), want) > 0]          # zero match ab kabhi nahi
    cands.sort(key=lambda c: (-footage.match_score(c.get("text"), want), c.get("vertical") != vertical,
                              random.random()))
    for c in cands[:6]:
        raw = out + ".src"
        try:
            if not footage.download(c["url"], raw, 100000):
                continue
            d = duration(raw) or c.get("dur", 10)
            jpgs = []
            for k, at in enumerate((min(d * 0.25, 2), max(min(d * 0.75, 9), 1))):
                jpg = f"{out}.chk{k}.jpg"
                if footage.frame(raw, jpg, at):
                    jpgs.append(jpg)
            full = footage.match_score(c.get("text"), want) >= len(want)
            v = fa.check(jpgs, term, said, kind) if jpgs else None
            used.append(c["id"])
            if v is not True:          # sirf AI ne dekh kar haan kaha ho - andaze se clip nahi
                REPORT["clips_rejected"] = REPORT.get("clips_rejected", 0) + 1
                log(f"  agent ne clip rad ki '{term}': {c['src']} {c['id']}")
                continue
            _render_clip(raw, secs, out)
            log(f"  clip '{term}': {c['src']} {c['id']} (agent: {v})")
            return True
        except Exception as e:
            log(f"  clip fail {c['id']}: {str(e)[:100]}")
        finally:
            for f in [raw] + [f"{out}.chk{k}.jpg" for k in range(2)]:
                if os.path.exists(f):
                    os.remove(f)
    pics = [p for p in footage.photos(term) if p["id"] not in used and footage.match_score(p.get("text"), want) > 0]
    pics.sort(key=lambda p: -footage.match_score(p.get("text"), want))
    for p in pics[:4]:
        img = out + ".jpg"
        try:
            if footage.download(p["url"], img, 40000):
                used.append(p["id"])
                v = fa.check([img], term, said, kind)
                full = footage.match_score(p.get("text"), want) >= len(want)
                if v is not True:          # sirf AI ne dekh kar haan kaha ho - andaze se clip nahi
                    REPORT["clips_rejected"] = REPORT.get("clips_rejected", 0) + 1
                    continue
                footage.photo_to_clip(img, out, W, H, secs=secs, fps=FPS)
                log(f"  photo-clip '{term}': {p['src']} {p['id']} (agent: {v})")
                return True
        except Exception as e:
            log(f"  photo fail: {str(e)[:100]}")
        finally:
            if os.path.exists(img):
                os.remove(img)
    return False


SUBJECT_HINT = ""      # match recap: "cricketer" / "footballer" - sahi shakhs mile


def subject_clip(name, secs, out, used):
    """Khabar wale asli insaan/team/jagah ki asli photo (Wikipedia Commons) - harkat ke sath."""
    img = out + ".jpg"
    try:
        if footage.real_photo(name, img, used, hint=SUBJECT_HINT):
            footage.photo_to_clip(img, out, W, H, secs=secs, fps=FPS)
            log(f"  asli photo '{name}'")
            return True
    except Exception as e:
        log(f"  asli photo fail '{name}': {str(e)[:100]}")
    finally:
        if os.path.exists(img):
            os.remove(img)
    return False


def _try(t, secs, out, used, said, kind):
    if t.startswith("@"):
        return subject_clip(t[1:], secs, out, used)
    return get_clip(t, secs, out, used, said, kind)


def scene_video(i, terms, secs, used, fallback_terms, said="", kind="news"):
    """Har hissa: boli gayi cheez -> scene ki doosri cheez -> agent ke naye alfaaz -> khabar ke asli
    shakhs/jagah ki photo -> isi khabar ki pehle wali clip. Aam 'news studio' clip ab nahi."""
    import footage_agent as fa
    terms = [t for t in terms if t][:4] or fallback_terms[:1]
    n = max(1, min(len(terms), int(secs // 4.5)))
    seg = secs / n
    parts = []
    alt = None
    for k, t in enumerate(terms[:n]):
        out = os.path.join(WORK, f"s{i}_{k}.mp4")
        ok = _try(t, seg + 0.1, out, used, said, kind)
        if not ok:
            ok = any(_try(x, seg + 0.1, out, used, said, kind) for x in terms if x != t and not x.startswith("@"))
        if not ok:
            if alt is None:
                alt = fa.alt_terms(t.lstrip("@"), said, news.ask_json, kind)
                REPORT["alt_searches"] = REPORT.get("alt_searches", 0) + 1
                log(f"  agent ke naye alfaaz: {alt}")
            ok = any(_try(x, seg + 0.1, out, used, said, kind) for x in alt[:4])
        if not ok:
            ok = any(_try(f, seg + 0.1, out, used, said, kind) for f in fallback_terms)
        if not ok and STORY_CLIPS:
            try:
                _render_clip(random.choice(STORY_CLIPS), seg + 0.1, out)   # isi khabar ki pehle wali (agent-pass) clip
                ok = True
            except Exception:
                ok = False
        if not ok and ALL_CLIPS:
            try:
                _render_clip(random.choice(ALL_CLIPS), seg + 0.1, out)   # kala screen kabhi nahi
                ok = "reuse"
            except Exception:
                ok = False
        if not ok:
            REPORT.setdefault("no_match", []).append(t)
            color_clip(out, seg + 0.1)
        elif ok is True:
            STORY_CLIPS.append(out)
            ALL_CLIPS.append(out)
        parts.append(out)
    if len(parts) == 1:
        return parts[0]
    lst = os.path.join(WORK, f"s{i}.txt")
    with open(lst, "w") as f:
        f.write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    out = os.path.join(WORK, f"s{i}_v.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
    return out


ALL_CLIPS = []        # poori video ki agent-pass clips (kala screen ki jagah)
STORY_CLIPS = []      # mojooda khabar ki agent-pass clips (nayi khabar par khali)


# ---------------------------------------------------------------- text on screen
def ass_t(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def esc(s):
    return (s or "").replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def chunks(text, n_words):
    ws = text.split()
    return [" ".join(ws[k:k + n_words]) for k in range(0, len(ws), n_words)] or [text]


def make_ass(path, kind, text, headline, secs, badge):
    P = news.PAGES[kind]
    reel = KIND == "reel"
    sub = 84 if reel else 64
    head = 72 if reel else 58
    sub_mv = 330 if reel else 70
    head_mv = 640 if reel else 190
    lines = chunks(clean_voice(text), 5 if reel else 8)
    total_w = sum(len(c.split()) for c in lines) or 1
    ev, t = [], 0.0
    for c in lines:
        d = secs * len(c.split()) / total_w
        ev.append(f"Dialogue: 1,{ass_t(t)},{ass_t(t + d)},Sub,,0,0,0,,{esc(c)}")
        t += d
    hl = ""
    if headline:
        hl = f"Dialogue: 2,{ass_t(0)},{ass_t(secs)},Head,,0,0,0,,{esc(headline)}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Brand,Noto Sans,{44 if reel else 40},&H00FFFFFF,&H00FFFFFF,{P['color']},{P['color']},1,0,0,0,100,100,1,0,3,12,0,7,50,50,50,1
Style: Badge,{FONT},{36 if reel else 32},&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,3,10,0,9,50,50,56,1
Style: Head,{FONT},{head},&H0000E5FF,&H00FFFFFF,&H00000000,&HB0000000,1,0,0,0,100,100,0,0,3,16,0,2,60,60,{head_mv},1
Style: Sub,{FONT},{sub},&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,1,4,3,2,70,70,{sub_mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 3,{ass_t(0)},{ass_t(secs)},Brand,,0,0,0,,{esc(P['name']).upper()}
Dialogue: 3,{ass_t(0)},{ass_t(secs)},Badge,,0,0,0,,{esc(badge)}
{hl}
""" + "\n".join(ev) + "\n")


def build_scene(i, kind, text, terms, headline, badge, used, fallback_terms):
    voice = os.path.join(WORK, f"v{i}.mp3")
    tts(text, voice)
    secs = duration(voice) + 0.35
    os.environ["AGENT_PAGE"] = kind
    vid = scene_video(i, terms, secs, used, fallback_terms, text, kind)
    import footage_agent as fa
    REPORT.update(fa.STATS)
    ass = os.path.join(WORK, f"s{i}.ass")
    make_ass(ass, kind, text, headline, secs, badge)
    fonts = news.FONTS_DIR.replace("\\", "/").replace(":", "\\:")
    ap = os.path.abspath(ass).replace("\\", "/").replace(":", "\\:")
    out = os.path.join(WORK, f"scene{i:02d}.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", voice, "-filter_complex",
         f"[0:v]drawbox=x=0:y=ih*0.62:w=iw:h=ih*0.38:color=black@0.35:t=fill,"
         f"ass='{ap}':fontsdir='{fonts}',fps={FPS},format=yuv420p[v];[1:a]apad=pad_dur=0.35,aresample=44100[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{secs:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", out])
    return out


def build_video(kind, script, stories, used):
    fb = (["world map globe", "news studio screen", "city skyline"] if kind == "news"
          else ["sports stadium crowd", "stadium lights"])
    date = datetime.datetime.utcnow().strftime("%d %b %Y")
    badge = date if LANG == "ur" else ("WORLD NEWS" if kind == "news" else "SPORTS") + f" | {date}"
    scenes = []
    i = 0
    intro = script.get("intro") or {}
    if intro.get("text"):
        first = [f"@{x}" for x in ((script["stories"][0].get("subjects") or [])[:1]) if isinstance(x, str) and x.strip()]
        scenes.append(build_scene(i, kind, intro["text"], first + (intro.get("visuals") or []), None, badge, used, fb))
        i += 1
    for n, st in enumerate(script["stories"][:len(stories)]):
        topic = stories[n]["topic"] if n < len(stories) else ""
        sfb = ([news.SPORT_IMG.get(topic, "sports stadium")] if kind == "sports" else []) + fb
        subj = [x.strip() for x in (st.get("subjects") or []) if isinstance(x, str) and x.strip()][:3]
        STORY_CLIPS.clear()                                  # nayi khabar - pichli khabar ki clip na lage
        sfb = [f"@{x}" for x in subj] + sfb                  # aam clip se pehle khabar ke asli shakhs/jagah ki photo
        for k, sc in enumerate((st.get("scenes") or [])[:4]):
            if not str(sc.get("text") or "").strip():
                continue
            real = [f"@{subj[k]}"] if k < len(subj) else []      # har scene ke shuru mein asli shakal/jagah
            scenes.append(build_scene(i, kind, sc["text"], real + (sc.get("visuals") or []), st.get("headline"),
                                      badge, used, sfb))
            i += 1
    outro = script.get("outro") or {}
    if outro.get("text"):
        scenes.append(build_scene(i, kind, outro["text"], fb[:2], None, badge, used, fb))   # outro: page ka apna mahol
    if len(scenes) < 2:
        raise RuntimeError("scenes nahi banay")
    lst = os.path.join(WORK, "all.txt")
    with open(lst, "w") as f:
        f.write("".join(f"file '{os.path.abspath(p)}'\n" for p in scenes))
    joined = os.path.join(WORK, "joined.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    total = duration(joined)
    music = os.path.join(WORK, "music.wav")
    make_music(music, total)
    final = os.path.join(WORK, f"{kind}_final.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", music, "-filter_complex",
         f"[1:a]volume=0.22,afade=t=out:st={max(0, total - 2):.2f}:d=2[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", final])
    log(f"{kind}: video ban gayi {total:.0f}s")
    return final


# ---------------------------------------------------------------- Facebook
def fb_json(r):
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"Facebook jawab samajh nahi aaya (HTTP {r.status_code}): {r.text[:300]}")
    if "error" in j:
        raise RuntimeError(f"Facebook error: {j['error'].get('message', j)}")
    return j


def post_reel(P, path, desc):
    base = f"https://graph.facebook.com/{GRAPH_VER}/{P['id']}/video_reels"
    vid = fb_json(requests.post(base, data={"upload_phase": "start", "access_token": P["token"]},
                                timeout=60))["video_id"]
    with open(path, "rb") as f:
        fb_json(requests.post(f"https://rupload.facebook.com/video-upload/{GRAPH_VER}/{vid}",
                              headers={"Authorization": f"OAuth {P['token']}", "offset": "0",
                                       "file_size": str(os.path.getsize(path))}, data=f, timeout=1800))
    fb_json(requests.post(base, timeout=60, data={"upload_phase": "finish", "video_id": vid,
                                                  "video_state": "PUBLISHED", "description": desc,
                                                  "access_token": P["token"]}))
    try:
        import stories
        stories.try_story(P["id"], P["token"], path, GRAPH_VER, log, REPORT["errors"])
    except Exception as e:
        log(f"story skip: {str(e)[:120]}")
    return vid


def post_long(P, path, title, desc):
    """Resumable (tukron mein) upload - pehle poori file ek dafa jati thi aur FB khaali jawab deta tha."""
    url = f"https://graph-video.facebook.com/{GRAPH_VER}/{P['id']}/videos"
    size = os.path.getsize(path)

    def phase(name, data, timeout):
        # FB kabhi khaali jawab deta hai - status ke saath log aur 3 dafa koshish
        for attempt in range(3):
            r = requests.post(url, timeout=timeout, data=data)
            if r.text.strip():
                return fb_json(r)
            log(f"FB {name}: khaali jawab (HTTP {r.status_code}) - koshish {attempt + 1}")
            time.sleep(10 * (attempt + 1))
        if name == "finish" and r.status_code < 400:
            return {}                     # upload ho chuki, finish ka jawab khaali aaya
        raise RuntimeError(f"Facebook {name}: khaali jawab (HTTP {r.status_code})")

    start = phase("start", {"access_token": P["token"], "upload_phase": "start", "file_size": str(size)}, 120)
    session, vid = start["upload_session_id"], start.get("video_id")
    s_off, e_off = int(start["start_offset"]), int(start["end_offset"])
    with open(path, "rb") as f:
        while s_off < e_off:
            f.seek(s_off)
            chunk = f.read(e_off - s_off)
            for attempt in range(4):
                try:
                    j = fb_json(requests.post(url, timeout=600, data={
                        "access_token": P["token"], "upload_phase": "transfer",
                        "upload_session_id": session, "start_offset": str(s_off)},
                        files={"video_file_chunk": ("chunk", chunk, "application/octet-stream")}))
                    break
                except Exception as e:
                    log(f"Chunk retry {attempt + 1}: {str(e)[:150]}")
                    if attempt == 3:
                        raise
                    time.sleep(5)
            s_off, e_off = int(j["start_offset"]), int(j["end_offset"])
    phase("finish", {"access_token": P["token"], "upload_phase": "finish", "upload_session_id": session,
                     "title": title[:250], "description": desc}, 300)
    return vid


def description(kind, script, stories):
    """Baqi pages wala SEO caption + video ki khabron ke sources."""
    import seo
    src_label = "ذرائع" if LANG == "ur" else "Sources"
    srcs = f"📰 {src_label}:\n" + "\n".join(f"• {s['source']}: {s['link']}" for s in stories)
    title = (script.get("title") or "").strip()
    said = " ".join(sc.get("text", "") for st in script.get("stories", []) for sc in st.get("scenes", []))
    try:
        cap = seo.build(news.ask_json, kind, title, f"{script.get('caption', '')} {said}", LANG, is_reel=KIND == "reel")
        parts = cap.split("\n\n")
        parts[1:1] = [(script.get("caption") or "").strip(), srcs]
        parts = [p for p in parts if p]
        if KIND == "reel" and "#reels" not in parts[-1].lower():
            parts[-1] += " #reels"
        return "\n\n".join(parts)
    except Exception as e:
        log(f"SEO caption fail ({str(e)[:100]}) - simple caption")
    return f"🔴 {title}\n\n{(script.get('caption') or '').strip()}\n\n{srcs}"


# ---------------------------------------------------------------- main
def main():
    hist = load_hist()
    nh = news.load_history()
    ok = 0
    for kind in news.PAGES_TO_RUN:
        news.CURRENT_PAGE = kind
        P = news.PAGES[kind]
        try:
            for f in os.listdir(WORK):
                os.remove(os.path.join(WORK, f))
            past = hist[kind] + nh[kind]            # pic wali khabar video mein dobara na aaye
            stories = pick_stories(kind, past)
            log(f"{kind}: " + " | ".join(s["title"][:60] for s in stories))
            script = write_script(kind, stories)
            path = build_video(kind, script, stories, hist["used_clips"])
            desc = description(kind, script, stories)
            log(f"--- {kind} description ---\n{desc}\n")
            meta = {"date": REPORT["time_utc"], "kind": KIND, "lang": LANG,
                    "title": script.get("title", "")[:120], "dur": round(duration(path))}
            if not DRY_RUN:
                if not P["token"] or not P["id"]:
                    raise RuntimeError(f"{kind}: page token/id secret missing")
                meta["post_id"] = post_reel(P, path, desc) if KIND == "reel" else \
                    post_long(P, path, script.get("title") or P["name"], desc)
                log(f"{kind}: posted {meta['post_id']}")
                news.log_post(kind, meta["post_id"], KIND, [s["topic"] for s in stories], meta["title"])
            for s in stories:
                hist[kind].append({"date": meta["date"], "topic": s["topic"], "link": s["link"],
                                   "title": s["title"][:160], "words": sorted(news.words(s["title"]))})
            REPORT["posted"][kind] = meta
            ok += 1
        except Exception as e:
            log(f"{kind} ERROR: {e}")
            REPORT["errors"].append(f"{kind}: {str(e)[:300]}")
    save_hist(hist)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=1, default=str)
    if ok < len(news.PAGES_TO_RUN):
        sys.exit(1)
    log("Done!")


if __name__ == "__main__":
    main()
