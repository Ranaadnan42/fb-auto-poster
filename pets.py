"""
Dogs & Cats World - PETS AGENT (Facebook page). Pyare aur mazedaar kuttay aur billiyan - asli video, nasal ka naam,
kahan se hai, aadatein, dekh-bhaal ki basic baatein.

MODE=reel  -> 9:16, ~45-70 sec: EK nasal (dog ya cat, baari baari) - wahi nasal poori video mein
MODE=long  -> 16:9, ~5-7 min: theme film ("Friendliest Dog Breeds", "Fluffiest Cats on Earth"...) - 6-8 nasalein

Agent kaam:
  - Wikipedia se asal facts - AI sirf inhi facts se script likhta hai (koi medical mashwara nahi)
  - Har jumle par wohi nasal: Pixabay, Pexels, Wikimedia Commons, Internet Archive, Mixkit ki ASLI video -
    har clip AI (footage_agent, kind="pets") frames dekh kar pass karta hai: sahi nasal? asli camera? zakhmi/larai nahi
  - Koi nasal dobara nahi (history), aur pichli clip dobara nahi
Env (sirf is page ki apni keys): PETS_PAGE_ID, PETS_PAGE_TOKEN, PETS_GEMINI_API_KEY, PETS_GROQ_API_KEY,
     PETS_PIXABAY_API_KEY, PETS_PEXELS_API_KEY, MODE, POST_AT, DRY_RUN
"""
import datetime
import json
import os
import random
import re
import sys
import time

MODE = (os.environ.get("MODE") or "reel").strip().lower()
os.environ["KIND"] = "reel" if MODE == "reel" else "long"
os.environ["LANGUAGE"] = "en"
os.environ["NO_PHOTOS"] = "1"          # sirf asli video - tasveer nahi
os.environ["NO_REUSE"] = "1"           # jo bola ja raha hai wohi - pichli clip dobara nahi
if MODE == "reel":                       # reel = ek hi janwar: clip kam pare to usi janwar ki pass-clip (naye angle se)
    os.environ["REUSE_SAME"] = "1"
os.environ.setdefault("NEWS_BUDGET_MIN", "55" if MODE == "reel" else "160")

import requests  # noqa: E402

import content_rules  # noqa: E402
import news  # noqa: E402
import news_video as nv  # noqa: E402

PAGE = "pets"
PAGE_NAME = "Dogs & Cats World"
GRAPH = "https://graph.facebook.com/v23.0"
DRY_RUN = os.environ.get("DRY_RUN") == "1"
HIST_FILE = "pets_history.json"
REPORT_FILE = f"pets_{MODE}_last_run.json"
OUT_FILE = "final_pets.mp4"
UA = {"User-Agent": "DogsAndCatsWorldBot/1.0 (https://github.com/Ranaadnan42/fb-auto-poster)"}

news.CURRENT_PAGE = PAGE
news.PAGES[PAGE] = {"name": PAGE_NAME, "token": (os.environ.get("PETS_PAGE_TOKEN") or "").strip(),
                    "id": (os.environ.get("PETS_PAGE_ID") or "").strip(), "color": "&H006A3CF0", "accent": "0xF03C6A"}
log = news.log
REPORT = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "mode": MODE, "dry_run": DRY_RUN,
          "errors": []}

# Reels: baari baari dog / cat - pehle sab se pasand ki jaane wali nasalein (zyada views), phir baqi.
DOGS = ["Golden Retriever", "Siberian Husky", "Pembroke Welsh Corgi", "German Shepherd", "Labrador Retriever",
        "French Bulldog", "Pomeranian", "Samoyed", "Shiba Inu", "Beagle", "Border Collie", "Dachshund",
        "Bernese Mountain Dog", "Cavalier King Charles Spaniel", "Poodle", "Australian Shepherd", "Chow Chow",
        "Alaskan Malamute", "Shih Tzu", "Pug", "Dalmatian", "Akita Inu", "Maltese dog", "Yorkshire Terrier",
        "Great Dane", "Saint Bernard", "Boxer (dog)", "Rottweiler", "Dobermann", "Bichon Frise",
        "Chihuahua (dog)", "Newfoundland dog", "Bulldog", "Basset Hound", "Cocker Spaniel", "Papillon dog",
        "Old English Sheepdog", "Afghan Hound", "Belgian Shepherd", "Whippet"]
CATS = ["Persian cat", "Maine Coon", "Ragdoll", "British Shorthair", "Scottish Fold", "Bengal cat", "Siamese cat",
        "Sphynx cat", "Norwegian Forest Cat", "Russian Blue", "Abyssinian cat", "Birman", "Exotic Shorthair",
        "Siberian cat", "Turkish Angora", "Devon Rex", "Savannah cat", "American Shorthair", "Himalayan cat",
        "Munchkin cat", "Egyptian Mau", "Turkish Van", "Burmese cat", "Oriental Shorthair", "Cornish Rex",
        "Selkirk Rex", "Somali cat", "Toyger", "Chartreux", "Manx cat"]
LONG_THEMES = [
    "The Friendliest Dog Breeds in the World", "The Fluffiest Cats on Earth", "Smartest Dog Breeds",
    "Gentle Giants - Biggest Dog Breeds", "Tiny Dogs With Big Personalities", "Rare Cat Breeds You Have Never Seen",
    "Best Family Dogs for Kids", "Cats That Act Like Dogs", "Snow Dogs - Huskies, Malamutes and Samoyeds",
    "The Most Beautiful Cat Breeds", "Dogs From Japan", "Best Cat Breeds for Apartments", "Herding Dogs and Their Skills",
    "Most Loyal Dog Breeds", "Hairless and Curly Cats", "Puppies Growing Up - Breeds Compared",
]


# ---------------------------------------------------------------- history
def load_hist():
    try:
        with open(HIST_FILE, encoding="utf-8") as f:
            h = json.load(f)
    except Exception:
        h = {}
    h.setdefault("long_i", 0)
    h.setdefault("theme_breeds", {})
    for k in ("reel", "long", "used_clips"):
        h.setdefault(k, [])
    return h


def save_hist(h):
    h["used_clips"] = h["used_clips"][-3000:]
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


def breeds_of(h, theme, n=8):
    """Agent: is theme ki sab se pyari / mash-hoor nasalein (cache)."""
    if h["theme_breeds"].get(theme):
        return h["theme_breeds"][theme]
    j = news.ask_json(f"""For a cute dogs & cats page (real video): list the {n} best dog or cat BREEDS for the film "{theme}",
the most loved / famous ones that are easy to find real video footage of. Return JSON
{{"breeds": ["exact English Wikipedia article title of each breed, e.g. 'Golden Retriever', 'Maine Coon'"]}}""")
    lst = [a.strip() for a in (j.get("breeds") or []) if isinstance(a, str) and a.strip()]
    h["theme_breeds"][theme] = lst
    return lst


def pick_reel(h):
    seen = {x.get("breed") for x in h["reel"]}
    want_cat = sum(1 for x in h["reel"] if x.get("pet") == "dog") > sum(1 for x in h["reel"] if x.get("pet") == "cat")
    order = [("cat", CATS), ("dog", DOGS)] if want_cat else [("dog", DOGS), ("cat", CATS)]
    for pet, lst in order:
        for b in lst:
            if b not in seen:
                return pet, b
    for t in LONG_THEMES:
        for b in breeds_of(h, t):
            if b not in seen:
                return ("cat" if "cat" in b.lower() or "cat" in t.lower() else "dog"), b
    raise RuntimeError("agli nasal nahi mili")


def pick_long(h):
    done = {x.get("theme") for x in h["long"]}
    for _ in range(len(LONG_THEMES)):
        t = LONG_THEMES[h["long_i"] % len(LONG_THEMES)]
        h["long_i"] += 1
        if t not in done or len(done) >= len(LONG_THEMES):
            return t
    return random.choice(LONG_THEMES)


# ---------------------------------------------------------------- facts (Wikipedia)
def _wiki(params):
    params.update({"format": "json", "formatversion": 2})
    for i in range(3):
        try:
            return requests.get("https://en.wikipedia.org/w/api.php", params=params, headers=UA, timeout=40).json()
        except Exception as e:
            log(f"wiki retry {i + 1}: {str(e)[:100]}")
            time.sleep(4)
    return {}


def wiki_text(title, limit):
    j = _wiki({"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": title})
    pages = (j.get("query") or {}).get("pages") or []
    if not pages or pages[0].get("missing"):
        s = _wiki({"action": "query", "list": "search", "srsearch": title, "srlimit": 1})
        hits = (s.get("query") or {}).get("search") or []
        if not hits:
            return title, ""
        title = hits[0]["title"]
        j = _wiki({"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": title})
        pages = (j.get("query") or {}).get("pages") or []
    if not pages:
        return title, ""
    text = pages[0].get("extract") or ""
    text = re.split(r"\n==\s*(See also|References|Notes|Further reading|External links|Citations|Sources)\s*==",
                    text)[0]
    return pages[0].get("title", title), text[:limit]


def reel_facts(pet, breed):
    title, text = wiki_text(breed, 7000)
    if len(text) < 400:
        raise RuntimeError(f"'{breed}' ke facts kam hain")
    return {"title": title, "pet": pet, "text": text}


def long_facts(h, theme):
    breeds = breeds_of(h, theme)[:7]
    parts, names = [], []
    for b in breeds:
        t, tx = wiki_text(b, 1700)
        if len(tx) > 300:
            parts.append(f"### {t}\n{tx}")
            names.append(t)
    if len(parts) < 4:
        raise RuntimeError(f"{theme}: nasalon ke facts kam hain")
    return {"title": theme, "breeds_text": "\n\n".join(parts)[:15000], "breeds": names}


# ---------------------------------------------------------------- script
def write_script(facts):
    trends = ""
    try:
        import trend_scout
        trends = trend_scout.text("pets")
    except Exception:
        pass
    if MODE == "reel":
        b, pet = facts["title"], facts["pet"]
        young = "puppy" if pet == "dog" else "kitten"
        shape = f"""a vertical REEL of 130-180 spoken words (45-70 seconds) in 7-9 scenes about ONE {pet} breed, the {b}:
  1) a cute or funny scroll-stopping hook (most surprising true fact), 2) where the breed comes from (country/history in
  one line), 3) its looks, coat and size, 4) its personality - why people love it, 5) a fun habit or talent,
  6) {young}s of this breed, 7) one simple care fact as written (exercise / grooming - never medical advice),
  8) who it suits (families, apartments...), 9) "Follow Dogs & Cats World for daily cute pets." """
        body = f"BREED: {b} ({pet})\nWIKIPEDIA:\n{facts['text']}"
        vis = (f"EVERY scene shows THIS breed ({b}) doing what the sentence says (e.g. '{b} playing', "
               f"'{b} {young}', '{b} running', '{b} sleeping')")
    else:
        shape = f"""a LONG pets video of 850-1000 spoken words (5-7 minutes) in 28-36 scenes: "{facts['title']}".
  Chapters (put the chapter name in each scene's "label"): "INTRO" (2 scenes), then ONE chapter per breed below
  (label = the breed's name in capitals, 3-4 scenes each: origin, looks, personality, a fun habit), then "OUTRO".
  End: follow Dogs & Cats World, like and share, comment your pet's name and breed."""
        body = f"THEME: {facts['title']}\nBREEDS (cover these, in this order):\n{facts['breeds_text']}"
        vis = "each scene shows THE breed of its chapter doing what the sentence says"
    prompt = f"""You are the narrator and writer of the Facebook page "Dogs & Cats World" (cute, funny and lovable dogs and cats, for
viewers in the USA, UK, Europe, Canada and Australia). Write {shape}
{body}

Rules:
- Warm, playful, happy spoken English like a friendly pet-show host; your OWN words, never copied sentences.
- ONLY facts written above (sizes, numbers, places, status exactly as written). Never invent a number or a place.
- Family friendly; NEVER medical or diet advice beyond what is written (say 'ask your vet'); no sick/hurt animals.
- ORIGINALITY: add 1-2 lines of your own insight (why people love this breed / what it needs from an owner) - clearly as insight.
- VISUALS: {vis}. For EVERY scene give "visuals": 1-3 short ENGLISH search terms for REAL VIDEO, in the order the
  narration mentions them; the FIRST term names the exact breed (+ dog/cat). Never another breed or animal,
  never cartoons, never generic shots without the animal.
{content_rules.MATCH}{content_rules.winners("pets")}- If a sentence talks about something no real video can show (DNA, numbers, history), rewrite it around
  a filmable moment of that breed - picture and voice must always match.
{trends}
Return JSON:
{{"title": "Facebook video title, max 12 words, cute/curious hook + breed name",
  "badge": "short on-screen badge, e.g. 'DOG BREEDS' or 'CAT BREEDS'",
  "card": {{"breed": "...", "origin": "country, max 6 words", "size": "max 6 words", "lifespan": "as written or 'unknown'",
            "personality": "max 8 words", "good_for": "max 8 words"}},
  "scenes": [{{"label": "short on-screen label, max 4 words", "text": "...", "visuals": ["..."], "breed": "breed of this scene"}}],
  "caption": "2-3 sentence post description"}}"""
    j = news.ask_json(prompt)
    sc = [s for s in (j.get("scenes") or []) if str(s.get("text") or "").strip()]
    words = sum(len(s["text"].split()) for s in sc)
    need = 120 if MODE == "reel" else 750
    if len(sc) < 5 or words < need:
        log(f"script chhota ({words} lafz) - dobara likhwa rahe hain")
        j2 = news.ask_json(prompt + f"\nIMPORTANT: your last answer was too short ({words} words). "
                                    f"Write at least {need + 60} spoken words.")
        sc2 = [s for s in (j2.get("scenes") or []) if str(s.get("text") or "").strip()]
        if sum(len(s["text"].split()) for s in sc2) > words:
            j, sc = j2, sc2
    if len(sc) < 4:
        raise RuntimeError("AI ne script nahi di")
    j["scenes"] = sc
    return j


# ---------------------------------------------------------------- video
def build_video(script, facts, h):
    used = h["used_clips"]
    badge = (script.get("badge") or "PETS").strip().upper()[:30]
    main = facts["title"] if MODE == "reel" else ""
    young = "kitten" if facts.get("pet") == "cat" else "puppy"
    nv.STORY_CLIPS.clear()
    scenes = []
    for i, sc in enumerate(script["scenes"]):
        br = str(sc.get("breed") or main or "").strip()
        terms = [t for t in (sc.get("visuals") or []) if isinstance(t, str) and t.strip()] or [br]
        fallback = [br, f"{br} playing", f"{br} {young}"] if br else ["cute puppy", "cute kitten"]
        label = str(sc.get("label") or "").strip().upper()[:40] or None
        try:
            scenes.append(nv.build_scene(i, PAGE, sc["text"], terms, label, badge, used, fallback))
        except Exception as e:
            log(f"scene {i} fail: {str(e)[:200]}")
            REPORT["errors"].append(f"scene {i}: {str(e)[:150]}")
    if len(scenes) < max(3, len(script["scenes"]) // 2):
        raise RuntimeError("bohat se scenes nahi banay")
    lst = os.path.join(nv.WORK, "all.txt")
    with open(lst, "w") as f:
        f.write("".join(f"file '{os.path.abspath(p)}'\n" for p in scenes))
    joined = os.path.join(nv.WORK, "joined.mp4")
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    total = nv.duration(joined)
    music = os.path.join(nv.WORK, "music.wav")
    happy_music(music, total)
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", music, "-filter_complex",
            f"[1:a]volume=0.18,afade=t=in:d=1,afade=t=out:st={max(0, total - 3):.2f}:d=3[m];"
            "[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            OUT_FILE])
    log(f"video ban gayi: {total:.0f}s, {len(scenes)} scenes")
    return OUT_FILE


def happy_music(path, secs):
    """Halki, khush-mizaj plucky dhun (khud bani - koi copyright nahi)."""
    root = random.choice([261.6, 293.7, 329.6])
    notes = [1, 1.25, 1.5, 2, 1.5, 1.25]
    beat, bar = 0.36, 0.36 * 6
    expr = "+".join(f"0.05*sin(2*PI*{root * m:.2f}*t)*exp(-6*mod(t-{k * beat:.2f},{bar:.2f}))"
                    f"*lt(mod(t-{k * beat:.2f},{bar:.2f}),{beat:.2f})" for k, m in enumerate(notes))
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
            f"aevalsrc='{expr}+0.025*sin(2*PI*{root / 2:.2f}*t)':s=44100:d={secs + 1:.1f}",
            "-af", "lowpass=f=3000,volume=1.2", path])


# ---------------------------------------------------------------- Facebook
def page():
    P = dict(news.PAGES[PAGE])
    if P["id"] and P["token"]:
        import fbtoken
        P["token"] = fbtoken.page_token(P["id"], P["token"])      # never-expiring page token
    return P


def description(script, facts):
    import seo
    k = script.get("card") or {}
    em = "🐶" if facts.get("pet") == "dog" else "🐱"
    lines = [f"{em} Breed: {k.get('breed')}", f"🌍 Origin: {k.get('origin')}", f"📏 Size: {k.get('size')}",
             f"⏳ Lifespan: {k.get('lifespan')}", f"💛 Personality: {k.get('personality')}",
             f"🏡 Good for: {k.get('good_for')}"] if MODE == "reel" else []
    card = "\n".join(x for x in lines if x and "None" not in x and not x.endswith(": "))
    said = " ".join(sc.get("text", "") for sc in script["scenes"])
    src = f"📚 Facts: Wikipedia - {facts['title']}"
    try:
        cap = seo.build(news.ask_json, PAGE, script.get("title") or facts["title"], said, "en",
                        is_reel=MODE == "reel")
        parts = cap.split("\n\n")
        parts[1:1] = [card, src]
        out = "\n\n".join(p for p in parts if p)
        return out + (" #reels" if MODE == "reel" and "#reels" not in out.lower() else "")
    except Exception as e:
        log(f"SEO fail ({str(e)[:100]})")
    return (f"🐾 {script.get('title')}\n\n{card}\n\n{script.get('caption', '')}\n\n{src}\n\n"
            f"#DogsAndCatsWorld #dogs #cats #puppy #kitten #pets #cuteanimals")


# ---------------------------------------------------------------- main
def main():
    os.makedirs(nv.WORK, exist_ok=True)
    if not (os.environ.get("PETS_GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY")):
        log("Dogs & Cats World ki apni API key (PETS_GEMINI_API_KEY / PETS_GROQ_API_KEY) abhi nahi - purani key istemal nahi hogi")
        REPORT["waiting"] = "own API key missing"
        return
    P = page()
    if not DRY_RUN and not (P["id"] and P["token"]):
        log("PETS_PAGE_ID / PETS_PAGE_TOKEN abhi set nahi - page jurne tak kuch nahi")
        REPORT["waiting"] = "page secrets missing"
        return
    h = load_hist()
    pet = breed = theme = None
    for attempt in range(6 if MODE == "reel" else 3):
        try:
            if MODE == "reel":
                pet, breed = pick_reel(h)
                if not nv.has_footage(breed, "pets"):
                    raise RuntimeError("is ki asli clips nahi milti")
                log(f"Nasal: {breed} ({pet})")
                facts = reel_facts(pet, breed)
            else:
                theme = pick_long(h)
                log(f"Lambi film: {theme}")
                facts = long_facts(h, theme)
            break
        except Exception as e:
            log(f"facts fail ({e}) - agla")
            if MODE == "reel":
                h["reel"].append({"pet": pet, "breed": breed, "date": REPORT["time_utc"], "skipped": str(e)[:100]})
            else:
                h["long"].append({"theme": theme, "date": REPORT["time_utc"], "skipped": str(e)[:100]})
            save_hist(h)
    else:
        raise RuntimeError("facts nahi mile")
    script = write_script(facts)
    log(f"Title: {script.get('title')} | {len(script['scenes'])} scenes")
    path = build_video(script, facts, h)
    REPORT.update({k: v for k, v in nv.REPORT.items() if k not in ("errors", "posted")})
    cards, good = nv.REPORT.get("headline_cards", 0), len(nv.ALL_CLIPS)
    if cards and cards > 0.2 * (cards + good):         # jo bola ja raha us ki clip nahi - aisi video post nahi
        h["reel" if MODE == "reel" else "long"].append({**{"pet": pet, "breed": breed, "theme": theme}, "date": REPORT["time_utc"],
                                                       "skipped": f"bemel clips {cards}/{cards + good}"})
        save_hist(h)                                    # agli koshish doosre topic par (jis ki asli clips milein)
        raise RuntimeError(f"sirf {good} sahi clips, {cards} text cards - is topic ki video post nahi ki")
    desc = description(script, facts)
    log(f"--- description ---\n{desc}\n")
    meta = {"pet": pet, "breed": breed, "theme": theme, "wiki": facts["title"], "date": REPORT["time_utc"],
            "title": script.get("title", "")[:150], "dur": round(nv.duration(path))}
    if not DRY_RUN:
        import slot_wait
        slot_wait.wait(log)
        meta["post_id"] = nv.post_reel(P, path, desc) if MODE == "reel" else \
            nv.post_long(P, path, script.get("title") or facts["title"], desc)
        log(f"posted {meta['post_id']}")
        news.POSTS_LOG = "pets_posts_history.json"
        news.log_post(PAGE, meta["post_id"], MODE, [breed or theme], meta["title"])
    h[MODE].append(meta)
    save_hist(h)
    REPORT["posted"] = meta


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        REPORT["errors"].append(f"fatal: {str(e)[:300]}")
        raise
    finally:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(REPORT, f, ensure_ascii=False, indent=1, default=str)
    if REPORT["errors"] and not REPORT.get("posted") and not DRY_RUN:
        sys.exit(1)
