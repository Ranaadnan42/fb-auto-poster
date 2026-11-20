"""
Style by Faizi - DRESS DESIGN AGENT (Facebook page). Rozana naye trending ladies dress designs.

MODE=pic  -> 4 naye designs ki HD tasveerein ek album post mein + pehli tasveer page STORY par
MODE=reel -> 9:16, ~45-60 sec: 6 designs, har design par awaaz (rang, kapra, kaam, mauqa) + subtitles + music,
             reel page STORY par bhi (post_reel khud lagata hai)
MODE=long -> 16:9, ~2.5-3 min: aaj ka theme (e.g. "Wedding Guest Looks"), 12 designs

Agent kaam:
  - Har roz AI khud trend sochta hai (season, shaadi/Eid/party, rang) - pichle 80 designs dobara nahi (history)
  - Tasveer: asli model ne dress pehni hui (realistic insan, mannequin nahi), ultra detailed kapra/kaam - Pollinations flux (free),
    na mile to is page ki apni Gemini key se image
  - Branding mein Pakistan/India ka naam nahi; USD/EUR + Gulf audience (seo.py "faizi")
Env: FAIZI_PAGE_ID, FAIZI_PAGE_TOKEN, FAIZI_GEMINI_API_KEY (+GEMINI_BACKUP_KEY), MODE, POST_AT, DRY_RUN
"""
try:  # Gemma 4 fallback (free 14,400/din) ke liye Gemini requests theek karta hai - gemfix.py
    import sys as _gf_sys, os as _gf_os
    _gf_dir = _gf_os.path.dirname(_gf_os.path.abspath(__file__))
    _gf_sys.path[:0] = [p for p in (_gf_dir, _gf_os.path.dirname(_gf_dir)) if p not in _gf_sys.path]
    import gemfix  # noqa: F401,E402
except Exception:
    pass
import base64
import datetime
import io
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.parse

MODE = (os.environ.get("MODE") or "reel").strip().lower()
os.environ["KIND"] = "reel" if MODE in ("reel", "pic") else "long"
os.environ["LANGUAGE"] = "en"

import requests  # noqa: E402

import news  # noqa: E402
import news_video as nv  # noqa: E402
import footage  # noqa: E402

PAGE = "faizi"
GRAPH = "https://graph.facebook.com/v23.0"
DRY_RUN = os.environ.get("DRY_RUN") == "1"
HIST_FILE = "faizi_history.json"
REPORT_FILE = f"faizi_{MODE}_last_run.json"
OUT = "final_faizi.mp4"
JOB = f"work_faizi_{MODE}"
VOICE = ("en-US-AvaNeural", "+0%")
log = news.log
REPORT = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "mode": MODE, "dry_run": DRY_RUN,
          "errors": [], "images": {}}
LOOK = ("professional luxury fashion catalogue photo, photorealistic, a real elegant female fashion model wearing "
        "the complete outfit, full-length shot from head to toe, natural realistic beautiful face, natural skin texture, "
        "perfect symmetrical eyes, correct anatomy, correct hands with five fingers, hands relaxed or hidden, graceful modest pose, modest family-friendly styling, the outfit is the main focus, "
        "real photograph shot on DSLR 85mm, boutique studio or elegant location, soft professional lighting, "
        "ultra detailed fabric texture and embroidery, sharp focus, 8k, no mannequin, no dress form, no text, no watermark")
FLAT = ("professional fashion product photo, photorealistic, the complete outfit neatly laid flat and arranged on a "
        "clean soft beige linen or light wooden background, top-down view, matching dupatta/trousers folded beside it, "
        "natural soft daylight, ultra detailed fabric texture, stitching and embroidery, sharp focus, 8k, "
        "no person, no mannequin, no text, no watermark")
DETAIL = ("realistic extreme close-up macro photo of this exact fabric being made: an industrial embroidery machine "
          "stitching the embroidery onto the fabric, or a tailor's hands sewing lace/border on it, real workshop, "
          "natural light, ultra sharp thread and embroidery detail, 8k, no face, no text, no watermark")
TOP_SCORE = 8         # is se kam score wali tasveer dobara banti hai
N_DETAIL = 4          # Tayyaba style: har run mein pehle 4 designs ka "banta hua kaam" close-up
WHO = {"women": "for an adult woman", "men": "for an adult man", "girls": "for a little girl (kids wear)",
       "boys": "for a little boy (kids wear)", "baby": "for a baby / toddler (baby wear)"}
N = {"pic": 4, "reel": 6, "long": 12}[MODE]
W, H = {"pic": (1080, 1350), "reel": (1080, 1920), "long": (1920, 1080)}[MODE]


def _learned():
    """Agent ki apni seekh (agent_learn.py): pichli ghaltiyan dobara nahi."""
    try:
        import agent_learn
        return agent_learn.text("faizi")
    except Exception:
        return ""


def load_hist():
    try:
        return json.load(open(HIST_FILE, encoding="utf-8"))
    except Exception:
        return {"designs": [], "posts": []}


def save_hist(h):
    h["designs"] = h["designs"][-400:]
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- AI: aaj ke designs
def plan(h):
    month = datetime.datetime.utcnow().strftime("%B")
    past = [d["name"] for d in h["designs"][-80:]]
    themes = [p.get("theme") for p in h["posts"][-10:]]
    trends = ""
    try:
        import trend_scout
        trends = trend_scout.text("faizi")
    except Exception as e:
        log(f"trend research fail: {str(e)[:120]}")
    d = news.ask_json(f"""{_learned()}You are the creative director of the fashion page "Style by Faizi". The page bio says:
"Trending dress designs daily - Bridal - Party Wear - Lawn - Eid - Kurti". So EVERY design must be a LADIES (adult
women's) outfit from these bio categories ONLY: Bridal, Party Wear, Lawn, Eid, Kurti. No men's wear, no kids wear,
no baby wear, nothing outside these categories. Viewers are in USA, UK, Canada, Europe, Australia and the Gulf
(UAE, Saudi Arabia, Qatar, Kuwait) and the diaspora. It is {month}. Pick ONE fresh theme from the bio categories
(e.g. a bridal colour trend, party wear for the season, new lawn prints, Eid outfits, kurti styles) that people are
searching for right now - not one of these recent themes:
{json.dumps(themes)}.
{trends}
QUALITY: this page must beat the top dress pages (Tayyaba stitching boutique, Easy Stitching) - every design must
look premium, luxury-catalogue level, something women would save and share; describe rich details (fabric, cut,
embroidery, colour palette of the season).
STRICT: every outfit MUST be a design that is actually trending right now (from the research above: the exact
styles, cuts, colors, fabrics and embroidery going viral this season) - no old-fashioned or random designs.
Then design {N} DIFFERENT outfits for it (different silhouettes and colors), none like these past ones:
{json.dumps(past[-40:])}.
Return JSON:
{{"theme": "short catchy theme title in English",
 "hook": "one spoken opening sentence (max 14 words) that makes women keep watching",
 "designs": [{{"name": "short outfit name, e.g. Emerald Velvet Sharara",
              "who": "women",
              "prompt": "very detailed English image prompt of ONLY the outfit: type, cut, length, exact colors, fabric, embroidery/work, dupatta, sleeves",
              "line": "one spoken sentence (14-22 words) describing it naturally: color, fabric, work and the occasion it suits"}}],
 "outro": "one spoken closing sentence asking viewers to comment their favourite number and follow Style by Faizi"}}
All designs are for adult women only, each from the bio categories (Bridal, Party Wear, Lawn, Eid, Kurti).
Rules: English; never mention Pakistan, India or prices; family friendly; no brand names.""")
    ds = [x for x in d.get("designs", []) if x.get("prompt") and x.get("name")][:N]
    if len(ds) < max(3, N - 2):
        raise RuntimeError("AI ne designs nahi diye")
    d["designs"] = ds
    return d


# ---------------------------------------------------------------- tasveer
def gen_image(prompt, w, h, path, seed, look=LOOK):
    full = f"{prompt}. {look}"
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(full) +
           f"?width={w}&height={h}&seed={seed}&model=flux&nologo=true&enhance=true")
    from PIL import Image
    for attempt in range(6):
        try:
            r = requests.get(url, timeout=240)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image") and len(r.content) > 40000:
                im = Image.open(io.BytesIO(r.content)).convert("RGB")
                im = im.crop((0, 0, im.width, int(im.height * 0.95)))        # neeche ka watermark hata do
                im.resize((w, h), Image.LANCZOS).save(path, quality=96)
                REPORT["images"]["pollinations"] = REPORT["images"].get("pollinations", 0) + 1
                return True
            log(f"pollinations {r.status_code} (try {attempt + 1})")
        except Exception as e:
            log(f"pollinations error: {str(e)[:120]}")
        time.sleep(15 + attempt * 15)
    for key in [os.environ.get("FAIZI_GEMINI_API_KEY"), os.environ.get("GEMINI_BACKUP_KEY")]:
        if not key:
            continue
        for model in gem_models(key, image=True):
            try:
                j = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  params={"key": key}, timeout=180, json={
                                      "contents": [{"parts": [{"text": full + f" Aspect ratio {w}:{h}."}]}],
                                      "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}).json()
                if "error" in j:
                    raise RuntimeError(j["error"].get("message", ""))
                for part in j["candidates"][0]["content"]["parts"]:
                    if part.get("inlineData"):
                        im = Image.open(io.BytesIO(base64.b64decode(part["inlineData"]["data"]))).convert("RGB")
                        # aspect theek karo (crop), phir size
                        tr = w / h
                        if im.width / im.height > tr:
                            nw = int(im.height * tr)
                            im = im.crop(((im.width - nw) // 2, 0, (im.width + nw) // 2, im.height))
                        else:
                            nh = int(im.width / tr)
                            im = im.crop((0, (im.height - nh) // 2, im.width, (im.height + nh) // 2))
                        im.resize((w, h), Image.LANCZOS).save(path, quality=96)
                        REPORT["images"]["gemini"] = REPORT["images"].get("gemini", 0) + 1
                        return True
            except Exception as e:
                log(f"gemini image {model} fail: {str(e)[:120]}")
    return False


_GM = {}


def gem_models(key, image=False):
    """Is key par jo Gemini models abhi zinda hain (purane band ho jate hain) - naye pehle."""
    ck = (key, image)
    if ck not in _GM:
        names = []
        try:
            j = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key,
                             "pageSize": 200}, timeout=30).json()
            for m in j.get("models", []):
                n = m["name"].split("/")[-1]
                if "generateContent" not in m.get("supportedGenerationMethods", []):
                    continue
                bad = ("tts", "live", "audio", "embedding", "robotics", "computer", "gemma", "learnlm")
                if any(b in n for b in bad):
                    continue
                if image and "image" in n:
                    names.append(n)
                elif not image and "flash" in n and "image" not in n:
                    names.append(n)
            names.sort(key=lambda n: ("preview" in n or "exp" in n, "lite" in n,
                                      -float((re.findall(r"(\d+(?:\.\d+)?)", n) or ["0"])[0])))
        except Exception as e:
            log(f"Gemini models list fail: {str(e)[:100]}")
        _GM[ck] = names[:4] or (["gemini-2.5-flash-image"] if image else
                                 ["gemini-3-flash-preview", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemma-4-31b-it", "gemma-4-26b-a4b-it"])
        log(f"Gemini {'image' if image else 'vision'} models: {_GM[ck]}")
    return _GM[ck]


def check_image(path, flat=False):
    """Sakht check: AI tasveer dekh kar batata hai ke model asli insan lagti hai ya nahi (chehra/haath/mannequin)."""
    q = ("You are a strict fashion photo editor. Look at this image. Answer ONLY JSON {\"ok\": true/false, \"why\": \"...\"}. "
         "ok=false if ANY of these: no real-looking human model wearing the dress; a mannequin/dress form/doll; "
         "face distorted, blurry, plastic or uncanny; eyes wrong; extra/missing/fused fingers or deformed hands; "
         "extra limbs or wrong body proportions; text or watermark; revealing or immodest clothing; outfit cut off; "
         "the image is a collage, split, grid or has more than one panel; more than one person; the model is a child "
         "or looks like a doll/cartoon/CGI instead of a real adult woman photographed by a camera.")
    if flat:
        q = ("You are a strict fashion photo editor. Look at this image. Answer ONLY JSON {\"ok\": true/false, \"why\": \"...\"}. "
             "It should be a realistic product photo of a complete outfit laid flat on a background. ok=false if ANY of: "
             "a person, body part, mannequin or doll is visible; the outfit looks melted, broken, garbled or unrealistic; "
             "outfit cut off; text or watermark.")
    q += (" Also add \"score\": 1-10 = how premium, beautiful and ON-TREND this design and photo look for 2026 "
          "fashion buyers in USA/UK/Europe/Gulf, compared with top fashion pages (10 = Vogue/luxury-brand catalogue "
          "quality that people would save and share; 5 = ordinary boutique photo). JSON: {\"ok\":..,\"why\":..,\"score\":..}")
    data = base64.b64encode(open(path, "rb").read()).decode()
    for key in [os.environ.get("FAIZI_GEMINI_API_KEY"), os.environ.get("GEMINI_BACKUP_KEY")]:
        if not key:
            continue
        for model in gem_models(key):
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  params={"key": key}, timeout=90, json={
                                      "contents": [{"parts": [{"text": q},
                                                              {"inlineData": {"mimeType": "image/jpeg", "data": data}}]}],
                                      "generationConfig": {"responseMimeType": "application/json"}})
                if r.status_code != 200:
                    log(f"image check {model} {r.status_code}: {r.text[:120]}")
                    continue
                j = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
                try:
                    sc = float(j.get("score") or 0)
                except Exception:
                    sc = 0
                return bool(j.get("ok")), str(j.get("why", ""))[:150], sc
            except Exception as e:
                log(f"image check {model} fail: {str(e)[:100]}")
    return None, "check nahi ho saka", 0


def split_img(left, right, out):
    from PIL import Image
    c = Image.new("RGB", (W, H), "white")
    half = (W - 8) // 2
    for k, f in enumerate((left, right)):
        im = Image.open(f).convert("RGB")
        r = max(half / im.width, H / im.height)
        im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
        x0, y0 = (im.width - half) // 2, (im.height - H) // 2
        c.paste(im.crop((x0, y0, x0 + half, y0 + H)), (k * (half + 8), 0))
    c.save(out, quality=95)
    return out


def make_images(p):
    os.makedirs(JOB, exist_ok=True)
    out = []
    REPORT["images"]["rejected"] = 0
    for i, d in enumerate(p["designs"]):
        path = os.path.join(JOB, f"d{i}.jpg")
        who = "women"                         # bio: sirf ladies (Bridal/Party/Lawn/Eid/Kurti)
        flat = False                          # har tasveer mein asli insan model - flat-lay nahi
        look = LOOK
        prompt = f"{d['prompt']}, {WHO[who]}"
        good = False
        best = (0, None)
        for attempt in range(4):              # kharab chehra/haath/mannequin ya aam si tasveer -> nayi tasveer
            if not gen_image(prompt, W, H, path, random.randint(1, 10 ** 6), look):
                break
            ok, why, sc = check_image(path, flat)
            if ok is None and attempt >= 1:   # checker hi band ho to aage chalo
                good = True
                break
            if ok and sc >= TOP_SCORE:        # top fashion pages se behtar - tabhi lagao
                good = True
                break
            if ok and sc > best[0]:           # saaf hai magar utni shandar nahi - backup rakho
                bp = path.replace(".jpg", "_best.jpg")
                os.replace(path, bp)
                best = (sc, bp)
            REPORT["images"]["rejected"] += 1
            log(f"design {i + 1} reject (try {attempt + 1}, score {sc}): {why}")
        if not good and best[0] >= 6:
            os.replace(best[1], path)
            good = True
            log(f"design {i + 1}: best backup (score {best[0]})")
        if good and i < N_DETAIL and MODE == "reel":   # close-up sirf reel mein alag clip; pic/long mein jodi tasveer nahi
            dp = os.path.join(JOB, f"d{i}_det.jpg")
            dw, dh = (W, H) if MODE == "reel" else (W // 2, H)
            if gen_image(d["prompt"], dw, dh, dp, random.randint(1, 10 ** 6), DETAIL):
                d = {**d, "detail": dp}
        if good:
            d = {**d, "main": path}           # ek tasveer = ek model, poori (koi split/collage nahi)
            out.append({**d, "path": path})
            log(f"design {i + 1}: {d['name']}")
        else:
            log(f"design fail: {d['name']}")
    if len(out) < max(3, N - 2):
        raise RuntimeError(f"sirf {len(out)} tasveerein bani")
    return out


# ---------------------------------------------------------------- video
def tts(text, path):
    import asyncio
    import edge_tts
    for a in range(5):
        try:
            asyncio.run(edge_tts.Communicate(text, VOICE[0], rate=VOICE[1]).save(path))
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            log(f"TTS retry {a + 1}: {str(e)[:100]}")
        time.sleep(5 * (a + 1))
    raise RuntimeError("awaaz nahi bani")


def esc(s):
    return (s or "").replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def ass_t(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def subs(path, title, text, secs, num):
    reel = H > W
    words = text.split()
    n = 5 if reel else 8
    parts = [" ".join(words[k:k + n]) for k in range(0, len(words), n)] or [text]
    ev, t = [], 0.0
    for c in parts:
        d = secs * len(c.split()) / max(len(words), 1)
        ev.append(f"Dialogue: 1,{ass_t(t)},{ass_t(t + d)},Sub,,0,0,0,,{esc(c)}")
        t += d
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Brand,Noto Serif,{46 if reel else 40},&H00FFFFFF,&H00FFFFFF,&H00602C8C,&H00602C8C,1,1,0,0,100,100,2,0,3,12,0,8,50,50,60,1
Style: Name,Noto Sans,{62 if reel else 52},&H00A6E9FF,&H00FFFFFF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,3,14,0,2,60,60,{560 if reel else 170},1
Style: Sub,Noto Sans,{70 if reel else 54},&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,1,4,3,2,70,70,{330 if reel else 60},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(ev) + "\n")


def scene(i, img, title, text, num):
    a = os.path.join(JOB, f"a{i}.mp3")
    tts(text, a)
    secs = max(nv.duration(a) + 0.6, 4.0)
    raw = os.path.join(JOB, f"r{i}.mp4")
    footage.photo_to_clip(img, raw, W, H, secs=secs)
    s = os.path.join(JOB, f"s{i}.ass")
    subs(s, title, text, secs, num)
    out = os.path.join(JOB, f"c{i}.mp4")
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-i", a, "-vf", f"ass={s}",
            "-af", "apad", "-t", f"{secs:.2f}", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", os.environ.get("VIDEO_CRF", "18"), "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", out])
    return out


def music(path, secs):
    root = random.choice([220.0, 246.9, 261.6])
    notes = [1, 1.26, 1.5, 1.89, 1.5, 1.26, 1.12, 1.5]
    beat, bar = 0.42, 0.42 * 8
    expr = "+".join(f"0.04*sin(2*PI*{root * m:.2f}*t)*exp(-4*mod(t-{k * beat:.2f},{bar:.2f}))"
                    f"*lt(mod(t-{k * beat:.2f},{bar:.2f}),{beat:.2f})" for k, m in enumerate(notes))
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
            f"aevalsrc='{expr}+0.02*sin(2*PI*{root / 2:.2f}*t)':s=44100:d={secs + 1:.1f}",
            "-af", "lowpass=f=3500,aecho=0.6:0.5:120:0.3,volume=1.1", path])


def detail_clip(i, img, secs=2.5):
    """Tayyaba style: model se pehle kapre par kaam banta hua close-up (sirf music, bina awaz)."""
    raw = os.path.join(JOB, f"dr{i}.mp4")
    footage.photo_to_clip(img, raw, W, H, secs=secs)
    out = os.path.join(JOB, f"dc{i}.mp4")
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", f"{secs:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", os.environ.get("VIDEO_CRF", "18"),
            "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", out])
    return out


def build_video(p, imgs):
    clips = [scene(0, imgs[0]["path"], p["theme"], p.get("hook") or p["theme"], 0)]
    for i, d in enumerate(imgs, 1):
        if MODE == "reel" and d.get("detail"):
            try:
                clips.append(detail_clip(i, d["detail"]))
            except Exception as e:
                log(f"detail clip skip: {str(e)[:80]}")
        clips.append(scene(i, d["path"], d["name"], d.get("line") or d["name"], i))
    clips.append(scene(len(imgs) + 1, imgs[-1]["path"], "Which one is your favourite?",
                       p.get("outro") or "Comment your favourite number and follow Style by Faizi.", 0))
    lst = os.path.join(JOB, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(c)}'\n" for c in clips)
    joined = os.path.join(JOB, "joined.mp4")
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    total = nv.duration(joined)
    m = os.path.join(JOB, "music.wav")
    music(m, total)
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", m, "-filter_complex",
            "[1:a]volume=0.35[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", OUT])
    log(f"video ban gayi: {total:.0f}s, {len(clips)} scenes")
    return OUT


# ---------------------------------------------------------------- Facebook
def fb(r):
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"].get("message"))
    return j


def page():
    P = {"id": (os.environ.get("FAIZI_PAGE_ID") or "").strip(), "token": (os.environ.get("FAIZI_PAGE_TOKEN") or "").strip()}
    if P["id"] and P["token"]:
        try:
            import fbtoken
            P["token"] = fbtoken.page_token(P["id"], P["token"])
        except Exception as e:
            log(f"token check skip: {str(e)[:100]}")
    return P


def a_or_b(imgs):
    """Tayyaba-style engagement tasveer: do designs saath saath, 'A or B?' - log comment mein jawab dete hain."""
    from PIL import Image, ImageDraw, ImageFont
    out = os.path.join(JOB, "a_or_b.jpg")
    c = Image.new("RGB", (W, H), (250, 244, 238))
    top = 150
    half = (W - 30) // 2
    for k, d in enumerate(imgs[:2]):
        im = Image.open(d.get("main") or d["path"]).convert("RGB")
        th = H - top - 20
        r = max(half / im.width, th / im.height)
        im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
        x0 = (im.width - half) // 2
        im = im.crop((x0, 0, x0 + half, th))
        c.paste(im, (10 + k * (half + 10), top))
    dr = ImageDraw.Draw(c)
    big = ImageFont.truetype("fonts/NotoSans-Bold.ttf", 92)
    badge = ImageFont.truetype("fonts/NotoSans-Bold.ttf", 70)
    t = "A or B?"
    dr.text(((W - dr.textlength(t, font=big)) / 2, 22), t, font=big, fill=(120, 30, 70))
    for k, L in enumerate("AB"):
        cx = 10 + k * (half + 10) + 70
        dr.ellipse((cx - 55, top + 25, cx + 55, top + 135), fill=(120, 30, 70))
        dr.text((cx - dr.textlength(L, font=badge) / 2, top + 30), L, font=badge, fill="white")
    c.save(out, quality=95)
    return out


def post_album(P, imgs, cap):
    ids = []
    for d in imgs:
        with open(d["path"], "rb") as f:
            ids.append(fb(requests.post(f"{GRAPH}/{P['id']}/photos", timeout=300, files={"source": f},
                                        data={"published": "false", "access_token": P["token"]}))["id"])
    data = {"message": __import__("seo").with_usa(cap), "access_token": P["token"]}
    for k, i in enumerate(ids):
        data[f"attached_media[{k}]"] = json.dumps({"media_fbid": i})
    pid = fb(requests.post(f"{GRAPH}/{P['id']}/feed", timeout=120, data=data))["id"]
    try:                                         # pehla design page story par
        with open(imgs[0]["path"], "rb") as f:
            sid = fb(requests.post(f"{GRAPH}/{P['id']}/photos", timeout=300, files={"source": f},
                                   data={"published": "false", "temporary": "true", "access_token": P["token"]}))["id"]
        fb(requests.post(f"{GRAPH}/{P['id']}/photo_stories", timeout=60, data={"photo_id": sid, "access_token": P["token"]}))
        log("photo story lagi")
    except Exception as e:
        log(f"photo story skip: {str(e)[:100]}")
    return pid


def caption(p, imgs):
    import seo
    said = p["theme"] + ". " + " ".join(f"#{i} {d['name']}: {d.get('line', '')}" for i, d in enumerate(imgs, 1))
    try:
        cap = seo.build(news.ask_json, PAGE, p["theme"], said, "en", is_reel=MODE == "reel")
    except Exception as e:
        log(f"SEO fail {str(e)[:100]}")
        cap = f"{p['theme']} 👗✨\n\nWhich one is your favourite? Comment the number 👇\n\n#StyleByFaizi #dressdesign #fashion"
    names = "\n".join(f"{i}. {d['name']}" for i, d in enumerate(imgs, 1))
    parts = cap.split("\n\n")
    parts[1:1] = [names]
    return "\n\n".join(x for x in parts if x)


def main():
    if not (os.environ.get("FAIZI_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        REPORT["waiting"] = "own API key missing"
        log("FAIZI_GEMINI_API_KEY nahi")
        return
    P = page()
    if not DRY_RUN and not (P["id"] and P["token"]):
        REPORT["waiting"] = "page secrets missing"
        log("FAIZI_PAGE_ID / FAIZI_PAGE_TOKEN nahi")
        return
    h = load_hist()
    p = plan(h)
    log(f"Theme: {p['theme']} | {len(p['designs'])} designs")
    imgs = make_images(p)
    cap = caption(p, imgs)
    log(f"--- caption ---\n{cap}")
    path = None
    if MODE != "pic":
        path = build_video(p, imgs)
    meta = {"mode": MODE, "theme": p["theme"], "designs": [d["name"] for d in imgs], "date": REPORT["time_utc"]}
    if not DRY_RUN:
        import slot_wait
        slot_wait.wait(log)
        if MODE == "pic":                     # sirf alag alag poori tasveerein - "A or B" jodi tasveer nahi
            meta["post_id"] = post_album(P, imgs, cap)
        elif MODE == "reel":
            meta["post_id"] = nv.post_reel(P, path, cap)
        else:
            meta["post_id"] = nv.post_long(P, path, p["theme"], cap)
        log(f"posted {meta['post_id']}")
    elif MODE == "pic":
        from PIL import Image
        Image.open(imgs[0]["path"]).save("final_faizi_pic.jpg", quality=95)
    h["designs"] += [{"name": d["name"], "date": REPORT["time_utc"]} for d in imgs]
    h["posts"].append(meta)
    h["posts"] = h["posts"][-200:]
    save_hist(h)
    REPORT["posted"] = meta


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        REPORT["errors"].append(str(e)[:300])
        raise
    finally:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(REPORT, f, ensure_ascii=False, indent=1, default=str)
