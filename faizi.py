"""
Style by Faizi - DRESS DESIGN AGENT (Facebook page). Rozana naye trending ladies dress designs.

MODE=pic  -> 4 naye designs ki HD tasveerein ek album post mein + pehli tasveer page STORY par
MODE=reel -> 9:16, ~45-60 sec: 6 designs, har design par awaaz (rang, kapra, kaam, mauqa) + subtitles + music,
             reel page STORY par bhi (post_reel khud lagata hai)
MODE=long -> 16:9, ~2.5-3 min: aaj ka theme (e.g. "Wedding Guest Looks"), 12 designs

Agent kaam:
  - Har roz AI khud trend sochta hai (season, shaadi/Eid/party, rang) - pichle 80 designs dobara nahi (history)
  - Tasveer/video: sirf ASLI insan (malik ka hukam: AI model nahi) - Pexels/Pixabay/Openverse stock, Gemini se check
    (asli adult aurat, poori dress, modest); naam aur awaz usi tasveer ko dekh kar - jo bola jaye wohi dikhe
  - Captions/awaaz mein dress ka style batao: Pakistani/Indian ya Western; USD/EUR + Gulf audience (seo.py "faizi")
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
LOOK = ("real candid fashion photoshoot photo of a real adult woman (not AI, not CGI, not 3D render) wearing "
        "the complete outfit, full-length shot from head to toe, natural face with real skin texture, visible pores, "
        "slight natural asymmetry, natural makeup, real hair with flyaway strands, relaxed natural pose, hands relaxed "
        "or holding the dupatta, modest family-friendly styling, the outfit is the main focus, "
        "shot on Canon EOS R5 50mm, natural daylight, real location (garden, courtyard, haveli, boutique), "
        "realistic fabric folds, weight and embroidery detail, sharp focus, true-to-life colors, "
        "not airbrushed, not porcelain skin, not doll-like, no mannequin, no dress form, no text, no watermark")
# har design ki aur poses - same model, same dress: reel/long mein lage ke model chal kar aa rahi hai aur dress dikha rahi hai
POSES = ["the same woman walking towards the camera in the same outfit, mid-step, dupatta flowing, full-length",
         "the same woman turning to show the side and back of the same outfit, three-quarter back view, full-length"]
N_POSES = {"pic": 0, "reel": 2, "long": 1}
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
N = {"pic": 1, "reel": 6, "long": 12}[MODE]   # malik: pic post mein sirf 1 tasveer (3-4 ikatthi / A-B nahi)
# malik: AI model nahi - asli insan. Tasveer/video sirf asli stock (Pexels/Pixabay/Openverse, commercial free)
GENERIC = ["bride lehenga", "woman saree", "woman salwar kameez", "woman kurta", "bridal dress woman",
           "woman anarkali dress", "woman traditional dress", "woman embroidered dress", "woman eid dress",
           "woman evening gown", "woman maxi dress", "woman party dress", "woman formal gown", "woman elegant dress"]
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
"Trending dress designs daily - Bridal - Party Wear - Lawn - Eid - Kurti". EVERY design must be a LADIES (adult
women's) outfit. MIX in every post: about HALF Pakistani/Indian (desi) styles - bridal lehenga, sharara, gharara,
anarkali, saree, lawn suit, Eid shalwar kameez, kurti, party wear - and about HALF Western styles - evening gowns,
maxi dresses, party/cocktail dresses (modest length), co-ord sets, modest abaya-style dresses. No men's wear, no kids
wear, no baby wear. Viewers are in USA, UK, Canada, Europe, Australia and the Gulf
(UAE, Saudi Arabia, Qatar, Kuwait) and the diaspora. It is {month}. Pick ONE fresh theme that fits both desi and Western looks
(e.g. a wedding-season colour trend, party wear for the season, new prints, festive outfits, everyday chic) that people are
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
              "prompt": "very detailed English description of ONLY the outfit: type, cut, length, exact colors, fabric, embroidery/work, dupatta, sleeves",
              "search": ["3 short (2-4 words) stock photo search phrases that find REAL photos of a real woman wearing this kind of outfit, e.g. 'bride red lehenga', 'woman embroidered kurta', 'woman saree portrait', 'woman salwar kameez', 'woman evening gown', 'woman maxi dress'"],
              "line": "one spoken sentence (14-22 words) describing it naturally: color, fabric, work and the occasion it suits"}}],
 "outro": "one spoken closing sentence asking viewers to comment their favourite number and follow Style by Faizi"}}
All designs are for adult women only; about half desi (Pakistani/Indian) and half Western, alternating; each design
"prompt" must clearly name the style (e.g. "Pakistani bridal lehenga", "Western satin evening gown"). Show every
design so clearly (cut, neckline, sleeves, embroidery, border) that a viewer can show it to her tailor and get it made.
Rules: English; in each "name" and spoken "line" say whether it is a Pakistani, Indian or Western style (e.g. "this Pakistani bridal lehenga", "a Western satin gown"); no prices; family friendly; no brand names.""")
    ds = [x for x in d.get("designs", []) if x.get("prompt") and x.get("name")][:N]
    if len(ds) < max(1, min(3, N - 2)):
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
         "or looks like a doll/cartoon/CGI instead of a real adult woman photographed by a camera; skin is airbrushed, "
         "porcelain-smooth or waxy; the whole image has the typical AI-generated glossy/fake look - it must pass as a "
         "real photo taken by a photographer.")
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


def _vision(q, path):
    """Gemini vision: tasveer + sawal -> JSON (ya None)."""
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
                    log(f"vision {model} {r.status_code}: {r.text[:120]}")
                    continue
                return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            except Exception as e:
                log(f"vision {model} fail: {str(e)[:100]}")
    return None


def check_real(jpg, theme):
    """Asli kamre ki tasveer/video frame: ek asli adult aurat ne poori (eastern/modest) dress pehni ho."""
    j = _vision("You are the strict photo editor of the ladies fashion page 'Style by Faizi' (Bridal, Party Wear, "
                f"Lawn, Eid, Kurti). Today's theme: '{theme}'. Look at this image. ok=true ONLY if: it is a REAL camera "
                "photo (not AI art, CGI, drawing or mannequin) of a real adult woman wearing a ladies outfit of these "
                "kinds (lehenga, saree, shalwar kameez, kurti/kurta, anarkali, sharara, gharara, bridal dress, "
                "embroidered gown, abaya, Western evening gown, maxi dress, modest party/cocktail dress, co-ord set); the outfit is the main subject and mostly visible; modest and family "
                "friendly; no child; at most one main person in focus; no big text, logo or watermark; sharp. "
                "score 1-10 = how beautiful and premium the outfit looks and how well it fits the theme. "
                "Answer ONLY JSON {\"ok\": true/false, \"why\": \"max 10 words\", \"score\": n}", jpg)
    if j is None:
        return None, "check nahi ho saka", 0
    try:
        sc = float(j.get("score") or 0)
    except Exception:
        sc = 0
    return bool(j.get("ok")), str(j.get("why", ""))[:150], sc


def describe(jpg, theme):
    """Jo dress tasveer mein asal mein hai usi ka naam aur awaz - jo bola jaye wohi dikhe."""
    j = _vision("Describe ONLY the outfit this woman is actually wearing in this photo, for the fashion page "
                f"'Style by Faizi' (theme: '{theme}'). Return JSON {{\"name\": \"short catchy outfit name (2-4 words) "
                "true to the real colour and type, e.g. 'Ruby Bridal Lehenga'\", \"line\": \"one spoken English "
                "sentence (14-22 words) describing exactly what is visible: colour, fabric, work and the occasion it "
                "suits, and say if it is a Pakistani, Indian or Western style\"}. Never mention prices or brands. Do not describe anything not visible.", jpg) or {}
    return str(j.get("name") or "").strip(), str(j.get("line") or "").strip()


def find_real(d, i, used, theme):
    """Is design ke liye asli insan wali video (reel/long) ya photo (pic) dhoondo + check karo."""
    terms = [t for t in (d.get("search") or []) if isinstance(t, str) and t.strip()][:3]
    terms += random.sample(GENERIC, 3)
    vert = H > W
    for t in terms:
        cands = []
        if MODE != "pic":
            cands += footage.pexels_videos(t, vert) + footage.pixabay_videos(t, vert)
        cands += footage.pexels_photos(t) + footage.pixabay_photos(t)
        if MODE == "pic":
            cands += footage.openverse(t)
        random.shuffle(cands)
        cands.sort(key=lambda c: c.get("photo", False))           # pehle video (asli harkat), phir photo
        tried = 0
        for c in cands:
            if c["id"] in used or tried >= 4:
                continue
            tried += 1
            used.add(c["id"])
            jpg = os.path.join(JOB, f"d{i}.jpg")
            try:
                if c.get("photo"):
                    if not footage.download(c["url"], jpg):
                        continue
                    src = jpg
                else:
                    src = os.path.join(JOB, f"v{i}.mp4")
                    if not footage.download(c["url"], src, 200000):
                        continue
                    big = os.path.join(JOB, f"d{i}_f.jpg")
                    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(c.get('dur', 6) / 2, 6):.1f}",
                                    "-i", src, "-frames:v", "1", "-q:v", "2", big], capture_output=True)
                    if not os.path.exists(big):
                        continue
                    os.replace(big, jpg)
            except Exception as e:
                log(f"download fail {c['id']}: {str(e)[:80]}")
                continue
            ok, why, sc = check_real(jpg, theme)
            if ok is None or (ok and sc >= 6):
                nv.LEARN["ok"].append(t)
                return {"path": jpg, "video": None if c.get("photo") else src, "id": c["id"], "src": c["src"]}
            REPORT["images"]["rejected"] = REPORT["images"].get("rejected", 0) + 1
            log(f"design {i + 1} reject {c['id']} ({t}): {why} [{sc}]")
        nv.LEARN["fail"].append(t)
    return None


def make_images(p, h=None):
    os.makedirs(JOB, exist_ok=True)
    out = []
    used = set((h or {}).get("used", []))
    REPORT["images"]["rejected"] = 0
    for i, d in enumerate(p["designs"]):
        m = find_real(d, i, used, p["theme"])
        if not m:
            log(f"design fail (asli tasveer na mili): {d['name']}")
            continue
        name, line = describe(m["path"], p["theme"])
        d = {**d, **m, "main": m["path"], "name": name or d["name"], "line": line or d.get("line", "")}
        out.append(d)
        REPORT["images"][m["src"]] = REPORT["images"].get(m["src"], 0) + 1
        log(f"design {i + 1}: {d['name']} ({m['id']}, {'video' if m['video'] else 'photo'})")
    if len(out) < max(1, min(3, N - 2)):
        raise RuntimeError(f"sirf {len(out)} asli tasveerein mili")
    if h is not None:
        h["used"] = (h.get("used", []) + [d["id"] for d in out])[-3000:]
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


def multi_clip(imgs, raw, secs, i):
    """Ek design ki kai poses ko narm crossfade se jodo - model aati, chalti aur ghoom kar dress dikhati lage."""
    if len(imgs) < 2:
        footage.photo_to_clip(imgs[0], raw, W, H, secs=secs)
        return
    fd = 0.6
    part = (secs + fd * (len(imgs) - 1)) / len(imgs)
    parts = []
    for k, im in enumerate(imgs):
        pc = os.path.join(JOB, f"r{i}_{k}.mp4")
        footage.photo_to_clip(im, pc, W, H, secs=part)
        parts.append(pc)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for pc in parts:
        cmd += ["-i", pc]
    fl, prev = [], "[0:v]"
    for k in range(1, len(parts)):
        lab = f"[x{k}]"
        fl.append(f"{prev}[{k}:v]xfade=transition=fade:duration={fd}:offset={part * k - fd * k:.2f}{lab}")
        prev = lab
    cmd += ["-filter_complex", ";".join(fl), "-map", prev, "-t", f"{secs:.2f}", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", raw]
    try:
        nv.run(cmd)
    except Exception as e:
        log(f"poses jodna fail, ek tasveer: {str(e)[:80]}")
        footage.photo_to_clip(imgs[0], raw, W, H, secs=secs)


def scene(i, img, title, text, num, poses=None, video=None):
    a = os.path.join(JOB, f"a{i}.mp3")
    tts(text, a)
    secs = max(nv.duration(a) + 0.6, 4.0)
    raw = os.path.join(JOB, f"r{i}.mp4")
    done = False
    if video and os.path.exists(video):      # asli insan ki asli video
        try:
            nv.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", video, "-t", f"{secs:.2f}",
                    "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,format=yuv420p",
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", raw])
            done = True
        except Exception as e:
            log(f"video clip fail, photo: {str(e)[:80]}")
    if not done:
        multi_clip([img] + [p for p in (poses or []) if os.path.exists(p)], raw, secs, i)
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


# Ultra HD (4K): reel 2160x3840, long 3840x2160 - aakhri ek hi encode mein lanczos + halki sharpness,
# taa ke log kapre ka kaam/kadhai saaf dekh kar tailor se banwa sakein
UHD_V = ["-vf", f"scale={W * 2}:{H * 2}:flags=lanczos,unsharp=5:5:0.6,format=yuv420p", "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "18", "-maxrate", "25M", "-bufsize", "50M", "-r", "30"]


def uhd_pic(src):
    """Pic post ultra HD: 2x lanczos (2160x2700) + halki sharpness - design ki har detail saaf."""
    from PIL import Image, ImageFilter
    out = src.replace(".jpg", "_uhd.jpg")
    try:
        im = Image.open(src).convert("RGB")
        im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
        im.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2)).save(out, quality=95, subsampling=0)
        return out
    except Exception as e:
        log(f"uhd pic fail: {str(e)[:80]}")
        return src


def build_video(p, imgs):
    clips = [scene(0, imgs[0]["path"], p["theme"], p.get("hook") or p["theme"], 0, video=imgs[0].get("video"))]
    for i, d in enumerate(imgs, 1):
        if MODE == "reel" and d.get("detail"):
            try:
                clips.append(detail_clip(i, d["detail"]))
            except Exception as e:
                log(f"detail clip skip: {str(e)[:80]}")
        clips.append(scene(i, d["path"], d["name"], d.get("line") or d["name"], i, d.get("poses"), d.get("video")))
    clips.append(scene(len(imgs) + 1, imgs[-1]["path"], "Which one is your favourite?",
                       p.get("outro") or "Comment your favourite number and follow Style by Faizi.", 0,
                       video=imgs[-1].get("video")))
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
            "-map", "0:v", "-map", "[a]", *UHD_V, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT])
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
        with open(uhd_pic(d["path"]), "rb") as f:
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
    imgs = make_images(p, h)
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
        Image.open(uhd_pic(imgs[0]["path"])).save("final_faizi_pic.jpg", quality=95)
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
