"""
Birds of the World - BIRD DOCUMENTARY AGENT (Facebook page). Duniya bhar ke rang-birangay parinde - asli video,
asli awaz, naam, kahan paye jate hain, hairat-angez facts.

MODE=reel  -> 9:16, ~60-75 sec: EK parinda (wahi parinda poori video mein) + us ki ASLI awaz (call/song)
MODE=long  -> 16:9, ~5-7 min: theme documentary ("The Most Colorful Birds on Earth", "Birds That Dance",
              "Birds of the Amazon"...) - 6-8 parinde, chapter ba chapter, har chapter mein us ki awaz

Agent kaam:
  - Wikipedia se asal facts - AI sirf inhi facts se script likhta hai
  - Har jumle par wohi parinda: Pixabay, Pexels, Wikimedia Commons, Internet Archive, Mixkit, NASA ki ASLI video -
    har clip AI (footage_agent, kind="birds") frames dekh kar pass karta hai: sahi nasal? asli camera?
  - Parinde ki ASLI awaz Wikimedia Commons se (sirf free/commercial license - NC/ND kabhi nahi)
  - Koi parinda dobara nahi (history), aur pichli clip dobara nahi
Env (sirf is page ki apni keys): BIRDS_PAGE_ID, BIRDS_PAGE_TOKEN, BIRDS_GEMINI_API_KEY, BIRDS_GROQ_API_KEY,
     BIRDS_PIXABAY_API_KEY, BIRDS_PEXELS_API_KEY, MODE, POST_AT, DRY_RUN
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

PAGE = "birds"
PAGE_NAME = "Birds of the World"
GRAPH = "https://graph.facebook.com/v23.0"
DRY_RUN = os.environ.get("DRY_RUN") == "1"
HIST_FILE = "birds_history.json"
REPORT_FILE = f"birds_{MODE}_last_run.json"
OUT_FILE = "final_birds.mp4"
UA = {"User-Agent": "BirdsOfTheWorldBot/1.0 (https://github.com/Ranaadnan42/fb-auto-poster)"}

news.CURRENT_PAGE = PAGE
news.PAGES[PAGE] = {"name": PAGE_NAME, "token": (os.environ.get("BIRDS_PAGE_TOKEN") or "").strip(),
                    "id": (os.environ.get("BIRDS_PAGE_ID") or "").strip(), "color": "&H00887A00", "accent": "0x007A88"}
log = news.log
REPORT = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "mode": MODE, "dry_run": DRY_RUN,
          "errors": []}

# Reels: pehle woh parinde jo sab se zyada views laate hain (rang, naach, awaz), phir duniya ke har khitte ke.
STAR_BIRDS = [
    "Indian peafowl", "Scarlet macaw", "Rainbow lorikeet", "Keel-billed toucan", "Greater bird-of-paradise",
    "Western parotia", "Mandarin duck", "Golden pheasant", "Resplendent quetzal", "Lilac-breasted roller",
    "Superb lyrebird", "Ruby-throated hummingbird", "Common kingfisher", "American flamingo", "Atlantic puffin",
    "Hyacinth macaw", "Gouldian finch", "Painted bunting", "Red-crowned crane", "Shoebill", "Harpy eagle",
    "Snowy owl", "Bald eagle", "Andean cock-of-the-rock", "Victoria crowned pigeon", "Superb fairywren",
    "Lady Amherst's pheasant", "Blue-footed booby", "Wilson's bird-of-paradise", "Himalayan monal",
    "Sword-billed hummingbird", "Great hornbill", "Secretarybird", "Emperor penguin", "Kakapo",
    "Grey crowned crane", "Sulphur-crested cockatoo", "Purple gallinule", "Violet-backed starling",
    "Malachite kingfisher", "Rose-ringed parakeet", "Hoopoe", "European bee-eater", "Peregrine falcon",
    "Wood duck", "Northern cardinal", "Blue jay", "Laughing kookaburra", "Southern cassowary", "Kea",
    "Marvelous spatuletail", "Crimson rosella", "Turquoise-browed motmot", "Golden-headed quetzal",
    "Sunbittern", "Club-winged manakin", "Red-capped manakin", "Satin bowerbird", "Great blue turaco",
    "Common ostrich", "Andean condor", "Eurasian eagle-owl", "Barn owl", "Atlantic puffin",
]
LONG_THEMES = [
    "The Most Colorful Birds on Earth", "Birds That Dance - Amazing Courtship Displays", "Birds of the Amazon Rainforest",
    "Birds-of-Paradise of New Guinea", "Parrots and Macaws of the World", "Hummingbirds - Tiny Jewels of the Americas",
    "Birds of Africa", "Birds of India", "Owls of the World", "Eagles and Raptors - Kings of the Sky",
    "Birds of Australia", "Kingfishers of the World", "Birds of the Arctic and Antarctica", "Birds That Sing the Best Songs",
    "Strangest-Looking Birds on Earth", "Birds of Central America", "Birds of Southeast Asia", "Pheasants and Peacocks",
    "Water Birds - Flamingos, Cranes and Herons", "Birds of Europe", "Birds of the Himalayas", "Birds of Madagascar",
    "Birds of Japan", "Birds of North America", "Birds of the Galapagos Islands", "Hornbills and Toucans",
]
# ---------------------------------------------------------------- history
def load_hist():
    try:
        with open(HIST_FILE, encoding="utf-8") as f:
            h = json.load(f)
    except Exception:
        h = {}
    h.setdefault("long_i", 0)
    h.setdefault("theme_birds", {})
    h.setdefault("more_birds", [])
    for k in ("reel", "long", "used_clips", "used_calls"):
        h.setdefault(k, [])
    return h


def save_hist(h):
    h["used_clips"] = h["used_clips"][-3000:]
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


def birds_of(h, theme, n=8):
    """Agent: is theme ke sab se khoobsurat / mash-hoor parinde (cache)."""
    if h["theme_birds"].get(theme):
        return h["theme_birds"][theme]
    j = news.ask_json(f"""For a bird documentary page (colorful birds of the whole world, real video + real calls): list the {n}
best bird species for the film "{theme}" - the most beautiful, colorful, famous or amazing ones, that are easy to find
real video footage of. Return JSON {{"birds": ["exact English Wikipedia article title of each species, e.g. 'Scarlet macaw'"]}}""")
    lst = [a.strip() for a in (j.get("birds") or []) if isinstance(a, str) and a.strip()]
    h["theme_birds"][theme] = lst
    return lst


def pick_reel(h):
    seen = {x.get("bird") for x in h["reel"]}
    for b in STAR_BIRDS:
        if b not in seen:
            return b
    # sab star parinde ho gaye - theme filmon ke parinde, phir agent se naye
    for t in LONG_THEMES:
        for b in birds_of(h, t):
            if b not in seen:
                return b
    j = news.ask_json(f"""List 30 more beautiful, colorful or amazing bird species of the world (exact English Wikipedia
titles), none of these: {', '.join(list(seen)[-200:])}. Return JSON {{"birds": ["..."]}}""")
    for b in j.get("birds") or []:
        if isinstance(b, str) and b.strip() and b not in seen:
            return b.strip()
    raise RuntimeError("agla parinda nahi mila")


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


def sci_name(text):
    m = re.search(r"\(([A-Z][a-z]+ [a-z]+)\)", text[:600])
    return m.group(1) if m else ""


def reel_facts(bird):
    title, text = wiki_text(bird, 7000)
    if len(text) < 400:
        raise RuntimeError(f"'{bird}' ke facts kam hain")
    return {"title": title, "sci": sci_name(text), "text": text}


def proven_birds(h):
    """Jin parindon ki reel asli clips ke sath post ho chuki - un ki footage free sites par waqai milti hai."""
    ok = [x.get("bird") for x in h["reel"] if x.get("bird") and not x.get("skipped")]
    return list(dict.fromkeys(ok + STAR_BIRDS))


def footage_ok(h, bird):
    """Parinde ki asli video waqai milti hai? Jawab yaad rakha jata hai (har dafa dobara check nahi)."""
    okl, nol = h.setdefault("footage_ok", []), h.setdefault("footage_no", [])
    if bird in okl:
        return True
    if bird in nol:
        return False
    ok = nv.has_footage(bird, "birds", need=4)
    (okl if ok else nol).append(bird)
    save_hist(h)
    return ok


def long_birds(h, theme, n=7):
    """Lambi film ke parinde SIRF un mein se jin ki asli video milti hai (nayab parinde = text cards = post fail).
    Har parinde ki footage pehle check hoti hai (4 asli clips) - jis ki na mile woh film mein nahi aata."""
    key = "verified:" + theme
    if h["theme_birds"].get(key):
        return h["theme_birds"][key]
    posted = {x.get("bird") for x in h["reel"] if x.get("post_id")}
    pool = [b for b in proven_birds(h) if b not in h.get("footage_no", [])]
    j = news.ask_json(f"""For the bird documentary film "{theme}", choose {n} species ONLY from this list (copy the names
exactly): {', '.join(pool)}. Pick the ones that fit the theme best; if few fit exactly, pick the closest/most famous ones
and keep the film beautiful. Return JSON {{"birds": ["..."]}}""")
    want = [a.strip() for a in (j.get("birds") or []) if isinstance(a, str) and a.strip() in pool]
    # pehle theme wale, phir jin ki reel ban chuki (pakki footage), phir baqi
    order = want + [b for b in pool if b in posted and b not in want] + \
        [b for b in random.sample(pool, len(pool)) if b not in want and b not in posted]
    lst = []
    for b in order:
        if len(lst) >= n:
            break
        if b in posted or footage_ok(h, b):
            lst.append(b)
    if len(lst) < 5:
        raise RuntimeError(f"{theme}: sirf {len(lst)} parindon ki asli footage mili")
    h["theme_birds"][key] = lst
    return lst


def long_facts(h, theme):
    birds = long_birds(h, theme)[:7]
    parts, names = [], []
    for b in birds:
        t, tx = wiki_text(b, 1700)
        if len(tx) > 300:
            parts.append(f"### {t}\n{tx}")
            names.append(t)
    if len(parts) < 4:
        raise RuntimeError(f"{theme}: parindon ke facts kam hain")
    return {"title": theme, "birds_text": "\n\n".join(parts)[:15000], "birds": names}


# ---------------------------------------------------------------- asli awaz (Wikimedia Commons)
def _commons(params):
    params.update({"format": "json", "formatversion": 2})
    try:
        return requests.get("https://commons.wikimedia.org/w/api.php", params=params, headers=UA, timeout=40).json()
    except Exception:
        return {}


def bird_call(names, out, used):
    """Parinde ki ASLI awaz (song/call) - sirf CC0 / CC-BY / CC-BY-SA / public domain. NC/ND kabhi nahi."""
    for nm in [n for n in names if n]:
        j = _commons({"action": "query", "generator": "search", "gsrnamespace": 6, "gsrlimit": 15,
                      "gsrsearch": f'filetype:audio "{nm}"', "prop": "imageinfo",
                      "iiprop": "url|extmetadata|size|mime"})
        for p in sorted((j.get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 99)):
            ii = (p.get("imageinfo") or [{}])[0]
            lic = ((ii.get("extmetadata") or {}).get("LicenseShortName") or {}).get("value", "").lower()
            url = ii.get("url") or ""
            if not url or p["title"] in used or any(b in lic.replace(" ", "-") for b in ("nc", "nd")):
                continue
            if not (lic.startswith("cc") or "public domain" in lic or lic in ("pd", "cc0")):
                continue
            raw = out + ".src"
            try:
                r = requests.get(url, headers=UA, timeout=60)
                if r.status_code != 200 or len(r.content) < 20000:
                    continue
                with open(raw, "wb") as f:
                    f.write(r.content)
                # 2-12 sec ka saaf hissa, shor kam, awaz barabar
                nv.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.5", "-i", raw, "-t", "12", "-af",
                        "highpass=f=350,afftdn=nf=-25,loudnorm=I=-18:TP=-2,afade=t=in:d=0.4,afade=t=out:st=10.8:d=1.2",
                        "-ar", "44100", "-ac", "2", out])
                if nv.duration(out) >= 2:
                    used.append(p["title"])
                    log(f"asli awaz: {p['title']} ({lic})")
                    REPORT.setdefault("calls", []).append({"file": p["title"], "license": lic})
                    return out
            except Exception as e:
                log(f"awaz fail: {str(e)[:100]}")
            finally:
                if os.path.exists(raw):
                    os.remove(raw)
    return None


# ---------------------------------------------------------------- script
def write_script(facts):
    trends = ""
    try:
        import trend_scout
        trends = trend_scout.text("birds")
    except Exception:
        pass
    if MODE == "reel":
        b = facts["title"]
        shape = f"""a vertical REEL of 160-200 spoken words (60-75 seconds) in 7-9 scenes about ONE bird, the {b}:
  1) a scroll-stopping hook about its colors/sound/dance (most surprising true fact), 2) its name and where in the world
  it lives (countries + habitat), 3) its colors and size, 4) its voice - describe its call or song (the real call plays
  in the video), 5) what it eats, 6-7) its most amazing behaviour (courtship dance, display, flight, nest),
  8) chicks / family life or conservation status (only as written), 9) "Follow Birds of the World for the most
  beautiful birds on Earth." """
        body = f"BIRD: {b} ({facts.get('sci') or ''})\nWIKIPEDIA:\n{facts['text']}"
        vis = (f"EVERY scene shows THIS bird ({b}) alive, doing what the sentence says (e.g. '{b} flying', "
               f"'{b} singing', '{b} display', '{b} nest'); a habitat scene only when the sentence is about the place")
    else:
        shape = f"""a LONG bird documentary of 850-1000 spoken words (5-7 minutes) in 28-36 scenes: "{facts['title']}".
  Chapters (put the chapter name in each scene's "label"): "INTRO" (2 scenes), then ONE chapter per bird below
  (label = the bird's name in capitals, 3-4 scenes each: where in the world it lives, its colors, its voice, its most
  amazing behaviour), then "OUTRO". End: follow Birds of the World, like and share, comment your favourite bird."""
        body = f"THEME: {facts['title']}\nBIRDS (cover these, in this order):\n{facts['birds_text']}"
        vis = ("each scene shows THE bird of its chapter alive doing what the sentence says; keep search terms SIMPLE "
               "and common (first term = just the species name, e.g. 'Scarlet macaw', then '<species> flying' or "
               "'<species> bird') - rare actions like 'eating a lizard' have no free footage")
    prompt = f"""You are the narrator and writer of the Facebook page "Birds of the World" (the most beautiful birds of every
corner of the world, for viewers in the USA, UK, Europe, Canada and Australia). Write {shape}
{body}

Rules:
- Warm, wonder-filled spoken English like a great nature-documentary narrator; your OWN words, never copied sentences.
- ONLY facts written above (sizes, numbers, places, status exactly as written). Never invent a number or a place.
- Family friendly (Facebook monetization): no blood or kills.
- ORIGINALITY: add 1-2 lines of your own insight (why this bird matters / what we can learn) - clearly as insight.
- VISUALS: {vis}. For EVERY scene give "visuals": 1-3 short ENGLISH search terms for REAL VIDEO, in the order the
  narration mentions them; the FIRST term names the exact bird species (or exact place). Never another species,
  never cartoons, never generic mood shots (sunset, sky, forest alone).
{content_rules.MATCH}{content_rules.winners("birds")}- If a sentence talks about something no real video can show (DNA, numbers, history), rewrite it around
  a filmable moment of that bird - picture and voice must always match.
{trends}
Return JSON:
{{"title": "Facebook video title, max 12 words, curiosity hook + bird name",
  "badge": "short on-screen badge, e.g. 'SOUTH AMERICA'",
  "card": {{"bird": "...", "scientific": "...", "found_in": "countries/regions, max 10 words", "habitat": "max 8 words",
            "diet": "max 8 words", "status": "as written, or 'unknown'"}},
  "scenes": [{{"label": "short on-screen label, max 4 words", "text": "...", "visuals": ["..."], "bird": "species of this scene"}}],
  "caption": "2-3 sentence post description"}}"""
    j = news.ask_json(prompt)
    sc = [s for s in (j.get("scenes") or []) if str(s.get("text") or "").strip()]
    words = sum(len(s["text"].split()) for s in sc)
    need = 140 if MODE == "reel" else 750
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
# Ultra HD (4K): reel 2160x3840, long 3840x2160 - aakhri ek hi encode mein lanczos se, FB par 4K quality
UHD_V = ["-vf", f"scale={nv.W * 2}:{nv.H * 2}:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", "-maxrate", "25M", "-bufsize", "50M", "-r", str(nv.FPS)]


def build_video(script, facts, h):
    used = h["used_clips"]
    badge = (script.get("badge") or "BIRDS").strip().upper()[:30]
    main_bird = facts["title"] if MODE == "reel" else ""
    nv.STORY_CLIPS.clear()
    scenes, calls = [], []          # calls: (scene start sec, awaz file)
    t0 = 0.0
    last_bird = None
    for i, sc in enumerate(script["scenes"]):
        bird = str(sc.get("bird") or main_bird or "").strip()
        terms = [t for t in (sc.get("visuals") or []) if isinstance(t, str) and t.strip()] or [bird]
        fallback = [f"{bird} bird", bird, f"{bird} flying"] if bird else ["colorful bird"]
        label = str(sc.get("label") or "").strip().upper()[:40] or None
        try:
            nv.SUBJECT[0] = bird
            p = nv.build_scene(i, PAGE, sc["text"], terms, label, badge, used, fallback)
            scenes.append(p)
            # har naye parinde ke pehle scene par us ki asli awaz (reel: shuru mein)
            if bird and bird != last_bird and (MODE == "long" or not calls):
                sci = facts.get("sci") if MODE == "reel" else ""
                c = bird_call([bird, sci], os.path.join(nv.WORK, f"call{i}.wav"), h["used_calls"])
                if c:
                    calls.append((t0, c))
                last_bird = bird
            t0 += nv.duration(p)
        except Exception as e:
            log(f"scene {i} fail: {str(e)[:200]}")
            REPORT["errors"].append(f"scene {i}: {str(e)[:150]}")
    if len(scenes) < max(3, len(script["scenes"]) // 2):
        raise RuntimeError("bohat se scenes nahi banay")
    nv.fix_cards()                     # likhe hue card ki jagah isi video ki asli clip
    lst = os.path.join(nv.WORK, "all.txt")
    with open(lst, "w") as f:
        f.write("".join(f"file '{os.path.abspath(p)}'\n" for p in scenes))
    joined = os.path.join(nv.WORK, "joined.mp4")
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    total = nv.duration(joined)
    music = os.path.join(nv.WORK, "music.wav")
    nature_music(music, total)
    ins = ["-i", joined, "-i", music]
    fc = [f"[1:a]volume=0.16,afade=t=in:d=2,afade=t=out:st={max(0, total - 3):.2f}:d=3[m]"]
    mix = "[0:a][m]"
    for k, (at, c) in enumerate(calls):
        ins += ["-i", c]
        ms = int(max(0.2, at + 0.2) * 1000)
        fc.append(f"[{k + 2}:a]volume=0.55,adelay={ms}|{ms}[c{k}]")
        mix += f"[c{k}]"
    fc.append(f"{mix}amix=inputs={2 + len(calls)}:duration=first:normalize=0[a]")
    nv.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc),
            "-map", "0:v", "-map", "[a]", *UHD_V, "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            OUT_FILE])
    REPORT["bird_calls"] = len(calls)
    log(f"video ban gayi: {total:.0f}s, {len(scenes)} scenes, {len(calls)} asli awazein")
    return OUT_FILE


def nature_music(path, secs):
    """Naram, khuli fiza wala documentary pad (khud bana - koi copyright nahi)."""
    root = random.choice([130.8, 146.8, 164.8])
    parts = [f"0.04*sin(2*PI*{root * m:.2f}*t)*(0.55+0.45*sin(2*PI*t/{p}))"
             for m, p in ((1, 13), (1.25, 10), (1.5, 16), (2, 12), (3, 19))]
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
            f"aevalsrc='{'+'.join(parts)}':s=44100:d={secs + 1:.1f}", "-af", "lowpass=f=2400,volume=0.9", path])


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
    lines = [f"🦜 Bird: {k.get('bird')}" + (f" ({k.get('scientific')})" if k.get("scientific") else "")
             if MODE == "reel" else "",
             f"🌍 Found in: {k.get('found_in')}" if MODE == "reel" else "",
             f"🌿 Habitat: {k.get('habitat')}" if MODE == "reel" else "",
             f"🍒 Diet: {k.get('diet')}" if MODE == "reel" else "",
             f"🛡️ Status: {k.get('status')}" if MODE == "reel" else ""]
    card = "\n".join(x for x in lines if x and "None" not in x and not x.endswith(": "))
    said = " ".join(sc.get("text", "") for sc in script["scenes"])
    src = f"📚 Facts: Wikipedia - {facts['title']}"
    if REPORT.get("calls"):
        src += "\n🔊 Real bird sounds: Wikimedia Commons (" + ", ".join(
            sorted({c["license"].upper() for c in REPORT["calls"]})) + ")"
    try:
        cap = seo.build(news.ask_json, PAGE, script.get("title") or facts["title"], said, "en",
                        is_reel=MODE == "reel")
        parts = cap.split("\n\n")
        parts[1:1] = [card, src]
        out = "\n\n".join(p for p in parts if p)
        return out + (" #reels" if MODE == "reel" and "#reels" not in out.lower() else "")
    except Exception as e:
        log(f"SEO fail ({str(e)[:100]})")
    return (f"🦜 {script.get('title')}\n\n{card}\n\n{script.get('caption', '')}\n\n{src}\n\n"
            f"#BirdsOfTheWorld #birds #birdwatching #nature #wildlife #colorfulbirds")


# ---------------------------------------------------------------- main
def main():
    os.makedirs(nv.WORK, exist_ok=True)
    if not (os.environ.get("BIRDS_GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY")):
        log("Birds of the World ki apni API key (BIRDS_GEMINI_API_KEY / BIRDS_GROQ_API_KEY) abhi nahi - purani key istemal nahi hogi")
        REPORT["waiting"] = "own API key missing"
        return
    P = page()
    if not DRY_RUN and not (P["id"] and P["token"]):
        log("BIRDS_PAGE_ID / BIRDS_PAGE_TOKEN abhi set nahi - page jurne tak kuch nahi")
        REPORT["waiting"] = "page secrets missing"
        return
    h = load_hist()
    bird = theme = None
    for attempt in range(6 if MODE == "reel" else 3):
        try:
            if MODE == "reel":
                bird = pick_reel(h)
                if not nv.has_footage(bird, "birds"):
                    raise RuntimeError("is ki asli clips nahi milti")
                log(f"Parinda: {bird}")
                facts = reel_facts(bird)
            else:
                theme = pick_long(h)
                log(f"Lambi film: {theme}")
                facts = long_facts(h, theme)
            break
        except Exception as e:
            log(f"facts fail ({e}) - agla")
            if MODE == "reel":
                h["reel"].append({"bird": bird, "date": REPORT["time_utc"], "skipped": str(e)[:100]})
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
        h["reel" if MODE == "reel" else "long"].append({**{"bird": bird, "theme": theme}, "date": REPORT["time_utc"],
                                                       "skipped": f"bemel clips {cards}/{cards + good}"})
        save_hist(h)                                    # agli koshish doosre topic par (jis ki asli clips milein)
        raise RuntimeError(f"sirf {good} sahi clips, {cards} text cards - is topic ki video post nahi ki")
    desc = description(script, facts)
    log(f"--- description ---\n{desc}\n")
    meta = {"bird": bird, "theme": theme, "wiki": facts["title"], "date": REPORT["time_utc"],
            "title": script.get("title", "")[:150], "dur": round(nv.duration(path))}
    if not DRY_RUN:
        import slot_wait
        slot_wait.wait(log)
        meta["post_id"] = nv.post_reel(P, path, desc) if MODE == "reel" else \
            nv.post_long(P, path, script.get("title") or facts["title"], desc)
        log(f"posted {meta['post_id']}")
        news.POSTS_LOG = "birds_posts_history.json"
        news.log_post(PAGE, meta["post_id"], MODE, [bird or theme], meta["title"])
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
