"""
Wild Nations - WILDLIFE AGENT (Facebook page). Har mulk ke asli janwar - asli video, reel aur lambi documentary.

Mulk-ba-mulk: har mulk mein kaun kaun se janwar rehte hain (us mulk ke mash-hoor / sirf wahin milne wale janwar),
un ki asli zindagi - kahan rehte hain, kya khate hain, kaise shikaar / hifazat karte hain, hairat-angez facts.

MODE=reel  -> 9:16, ~60-75 sec: us mulk ka EK janwar (wahi janwar poori video mein, asli wild footage)
MODE=long  -> 16:9, ~5-6 min: "Wildlife of <Country>" - us mulk ke 6-8 janwar, chapter ba chapter

Agent kaam:
  - Wikipedia se asal facts (janwar ka article + "Wildlife of <mulk>") - AI sirf inhi facts se script likhta hai
  - Har jumle par wohi janwar / wohi jagah jo bola ja raha hai: Pixabay, Pexels, Wikimedia Commons, Internet Archive
    ki ASLI video - har clip AI (footage_agent, kind="wild") 3 frames dekh kar pass karta hai: sahi janwar?
    asli camera? cartoon/CGI/khilona/doosra janwar rad. Tasveer kabhi nahi.
  - trend_scout: log aaj kal wildlife mein kya dekh rahe hain - us hisaab se hook
  - Koi janwar / mulk dobara nahi (history), aur pichli clip dobara nahi
Env: WILD_PAGE_ID, WILD_PAGE_TOKEN, WILD_GEMINI_API_KEY (na ho to GEMINI_API_KEY), GROQ_API_KEY, PIXABAY_API_KEY,
     PEXELS_API_KEY (optional), MODE, POST_AT, DRY_RUN
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
os.environ["NO_PHOTOS"] = "1"          # malik: sirf asli video - tasveer nahi
os.environ["NO_REUSE"] = "1"           # jo bola ja raha hai wohi - pichli clip dobara nahi
os.environ.setdefault("NEWS_BUDGET_MIN", "55" if MODE == "reel" else "150")

import requests  # noqa: E402

import content_rules  # noqa: E402
import news  # noqa: E402
import news_video as nv  # noqa: E402

PAGE = "wild"
PAGE_NAME = "Wild Nations"
GRAPH = "https://graph.facebook.com/v23.0"
DRY_RUN = os.environ.get("DRY_RUN") == "1"
HIST_FILE = "wild_history.json"
REPORT_FILE = f"wild_{MODE}_last_run.json"
OUT_FILE = "final_wild.mp4"
UA = {"User-Agent": "WildNationsBot/1.0 (https://github.com/Ranaadnan42/fb-auto-poster)"}

news.CURRENT_PAGE = PAGE
news.PAGES[PAGE] = {"name": PAGE_NAME, "token": (os.environ.get("WILD_PAGE_TOKEN") or "").strip(),
                    "id": (os.environ.get("WILD_PAGE_ID") or "").strip(), "color": "&H00207A3A", "accent": "0x3A7A20"}
log = news.log
REPORT = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "mode": MODE, "dry_run": DRY_RUN,
          "errors": []}

# Pehle woh mulk jin ki wildlife sab se mash-hoor (zyada views), phir baqi duniya. Khatam ho to dobara shuru
# (naye janwar ke sath - pichle janwar history mein hain).
COUNTRIES = [
    "Kenya", "Australia", "India", "Brazil", "South Africa", "Tanzania", "Indonesia", "United States", "Canada",
    "Madagascar", "Botswana", "China", "Russia", "Costa Rica", "Ecuador", "Peru", "Mexico", "Argentina",
    "New Zealand", "Japan", "Thailand", "Malaysia", "Sri Lanka", "Nepal", "Pakistan", "Bangladesh", "Mongolia",
    "Uganda", "Rwanda", "Zambia", "Namibia", "Zimbabwe", "Ethiopia", "Egypt", "Morocco", "Saudi Arabia",
    "United Arab Emirates", "Oman", "Iran", "Turkey", "Norway", "Iceland", "Finland", "Sweden", "United Kingdom",
    "Scotland", "Ireland", "France", "Spain", "Portugal", "Italy", "Germany", "Poland", "Romania", "Greece",
    "Colombia", "Venezuela", "Bolivia", "Chile", "Galapagos Islands", "Philippines", "Papua New Guinea", "Vietnam",
    "Cambodia", "Myanmar", "Laos", "South Korea", "Kazakhstan", "Greenland", "Antarctica", "Cuba", "Belize",
    "Panama", "Guatemala", "Democratic Republic of the Congo", "Gabon", "Cameroon", "Nigeria", "Ghana", "Senegal",
    "Mozambique", "Malawi", "Somalia", "Sudan", "Algeria", "Tunisia", "Jordan", "Israel", "Afghanistan", "Bhutan",
    "Borneo", "Fiji", "Ukraine", "Austria", "Switzerland", "Netherlands", "Denmark", "Croatia", "Bulgaria",
]
PER_COUNTRY = 6        # ek mulk ke zyada se zyada itne janwar (reels), phir agla mulk


# ---------------------------------------------------------------- history
def load_hist():
    try:
        with open(HIST_FILE, encoding="utf-8") as f:
            h = json.load(f)
    except Exception:
        h = {}
    h.setdefault("country_i", 0)
    h.setdefault("long_i", 0)
    h.setdefault("animals", {})
    for k in ("reel", "long", "used_clips"):
        h.setdefault(k, [])
    return h


def save_hist(h):
    h["used_clips"] = h["used_clips"][-3000:]
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


def animals_of(h, country):
    """Agent: is mulk ke mash-hoor / sirf wahin milne wale janwar (cache)."""
    if h["animals"].get(country):
        return h["animals"][country]
    j = news.ask_json(f"""For a wildlife documentary page that shows the real animals of every country: list the {PER_COUNTRY + 2}
most interesting WILD animals that truly live in {country} (native or famous there - endemic ones first, then iconic big
animals, birds or sea life seen there). Only animals that are easy to find real video footage of. No pets/farm animals.
Return JSON {{"animals": ["exact English Wikipedia article title of each species, e.g. 'Snow leopard', 'Koala'"]}}""")
    lst = [a.strip() for a in (j.get("animals") or []) if isinstance(a, str) and a.strip()]
    h["animals"][country] = lst
    return lst


def pick_reel(h):
    """Reel: mojooda mulk ka agla janwar jo abhi tak nahi aaya; mulk ke PER_COUNTRY janwar ke baad agla mulk."""
    done = {(x.get("country"), x.get("animal")) for x in h["reel"]}
    seen_animals = {x.get("animal") for x in h["reel"]}
    for _ in range(len(COUNTRIES) * 2):
        c = COUNTRIES[h["country_i"] % len(COUNTRIES)]
        n_done = sum(1 for (cc, _a) in done if cc == c)
        if n_done < PER_COUNTRY:
            for a in animals_of(h, c):
                if (c, a) not in done and a not in seen_animals:
                    REPORT["country"] = c
                    log(f"Mulk: {c} ({n_done + 1}/{PER_COUNTRY}) - janwar: {a}")
                    return c, a
        h["country_i"] += 1                        # is mulk ke janwar mukammal - agla mulk
    raise RuntimeError("agla janwar nahi mila")


def pick_long(h):
    done = {x.get("country") for x in h["long"]}
    for _ in range(len(COUNTRIES)):
        c = COUNTRIES[h["long_i"] % len(COUNTRIES)]
        h["long_i"] += 1
        if c not in done or len(done) >= len(COUNTRIES):
            return c
    return random.choice(COUNTRIES)


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


def reel_facts(country, animal):
    title, text = wiki_text(animal, 7000)
    if len(text) < 400:
        raise RuntimeError(f"'{animal}' ke facts kam hain")
    _t, ctext = wiki_text(f"Wildlife of {country}", 2500)
    return {"title": title, "country": country, "text": text, "country_text": ctext}


def long_facts(h, country):
    title, ctext = wiki_text(f"Wildlife of {country}", 6000)
    if len(ctext) < 400:
        title, ctext = wiki_text(f"Fauna of {country}", 6000)
    animals = animals_of(h, country)[:7]
    parts = []
    for a in animals:
        t, tx = wiki_text(a, 1600)
        if len(tx) > 300:
            parts.append(f"### {t}\n{tx}")
    if len(parts) < 4:
        raise RuntimeError(f"{country}: janwaron ke facts kam hain")
    return {"title": f"Wildlife of {country}", "country": country, "text": ctext,
            "animals_text": "\n\n".join(parts)[:14000], "animals": animals}


# ---------------------------------------------------------------- script
def write_script(facts):
    trends = ""
    try:
        import trend_scout
        trends = trend_scout.text("wild")
    except Exception:
        pass
    c = facts["country"]
    if MODE == "reel":
        shape = f"""a vertical REEL of 160-200 spoken words (60-75 seconds) in 7-9 scenes about ONE animal of {c}:
  1) a scroll-stopping hook (the most surprising true fact), 2) where in {c} it lives (habitat), 3) what it looks like
  / how big, 4) what it eats and how it hunts or feeds, 5-6) its most amazing behaviour or super-power, 7) family life
  / babies, 8) is it endangered (only as the facts say), 9) "Follow Wild Nations - the real wildlife of every country." """
        body = f"ANIMAL: {facts['title']}\nWIKIPEDIA:\n{facts['text']}\n\nWILDLIFE OF {c.upper()} (context):\n{facts['country_text']}"
        vis = (f"EVERY scene shows THIS animal ({facts['title']}) alive in the wild, doing what the sentence says "
               f"(e.g. '{facts['title']} hunting', '{facts['title']} cub', '{facts['title']} swimming'); a habitat "
               f"scene only when the sentence is about the place (then name the place and '{c}')")
    else:
        shape = f"""a LONG wildlife documentary of 800-950 spoken words (5-6 minutes) in 26-34 scenes: "Wildlife of {c}".
  Chapters (put the chapter name in each scene's "label"): "WELCOME TO {c.upper()}" (its wild landscapes), then ONE chapter
  per animal below (label = the animal's name in capitals, 3-4 scenes each: where it lives in {c}, looks, food,
  amazing behaviour), then "PROTECTING THEM" and "NEXT COUNTRY". End: follow Wild Nations, like and share, comment
  which country's wildlife we should show next."""
        body = (f"COUNTRY: {c}\nWILDLIFE OF {c.upper()}:\n{facts['text']}\n\nANIMALS (cover these, in this order):\n"
                f"{facts['animals_text']}")
        vis = (f"each scene shows THE animal of its chapter alive in the wild doing what the sentence says, or for "
               f"landscape sentences the real wild place of {c} (e.g. 'Serengeti plains Tanzania')")
    prompt = f"""You are the narrator and writer of the Facebook page "Wild Nations" (real wildlife of every country, for viewers
in the USA, UK, Europe, Canada, Australia and the Gulf). Write {shape}
{body}

Rules:
- Warm, wonder-filled spoken English like a great nature-documentary narrator; your OWN words, never copied sentences.
- ONLY facts written above (sizes, speeds, numbers, status exactly as written). Never invent a number.
- Family friendly: hunting can be described, but no blood, gore or graphic kills (Facebook monetization).
- ORIGINALITY: add 1-2 lines of your own insight (why this animal matters / what we can learn) - clearly as insight.
- VISUALS: {vis}. For EVERY scene give "visuals": 1-3 short ENGLISH search terms for REAL VIDEO, in the order the
  narration mentions them; the FIRST term names the exact animal (or exact place). Never another species, never zoo
  cages, never cartoons, never generic mood shots (sunset, sky, forest alone) unless the sentence is about that place.
{content_rules.MATCH}- If a sentence talks about something no real video can show (DNA, numbers, history), rewrite it around
  a filmable moment of that animal - picture and voice must always match.
{trends}
Return JSON:
{{"title": "Facebook video title, max 12 words, curiosity hook + animal/country",
  "badge": "short on-screen badge, e.g. '{c.upper()}'",
  "subjects": ["2-5 exact English Wikipedia titles: the animal(s) and the main wild places in {c}"],
  "card": {{"animal": "...", "country": "{c}", "habitat": "max 8 words", "diet": "max 8 words", "status": "as written, or 'unknown'"}},
  "scenes": [{{"label": "short on-screen label, max 4 words", "text": "...", "visuals": ["..."]}}],
  "caption": "2-3 sentence post description"}}"""
    j = news.ask_json(prompt)
    sc = [s for s in (j.get("scenes") or []) if str(s.get("text") or "").strip()]
    words = sum(len(s["text"].split()) for s in sc)
    need = 140 if MODE == "reel" else 700
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
def build_video(script, facts, used):
    c = facts["country"]
    badge = (script.get("badge") or c).strip().upper()[:30]
    main_animal = facts["title"] if MODE == "reel" else ""
    fallback = ([f"{main_animal} wild", f"{main_animal}", f"{main_animal} {c}"] if main_animal else []) + \
               [f"{c} wildlife", f"{c} national park", f"{c} nature"]
    nv.STORY_CLIPS.clear()
    scenes = []
    for i, sc in enumerate(script["scenes"]):
        terms = [t for t in (sc.get("visuals") or []) if isinstance(t, str) and t.strip()]
        if not terms:
            terms = [main_animal or f"{c} wildlife"]
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
    nature_music(music, total)
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", music, "-filter_complex",
            f"[1:a]volume=0.22,afade=t=in:d=2,afade=t=out:st={max(0, total - 3):.2f}:d=3[m];"
            "[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            OUT_FILE])
    log(f"video ban gayi: {total:.0f}s, {len(scenes)} scenes")
    return OUT_FILE


def nature_music(path, secs):
    """Naram, khuli fiza wala documentary pad (khud bana - koi copyright nahi)."""
    root = random.choice([110.0, 130.8, 146.8])
    parts = [f"0.045*sin(2*PI*{root * m:.2f}*t)*(0.55+0.45*sin(2*PI*t/{p}))"
             for m, p in ((1, 13), (1.25, 10), (1.5, 16), (2, 12), (3, 19))]
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
            f"aevalsrc='{'+'.join(parts)}':s=44100:d={secs + 1:.1f}", "-af", "lowpass=f=2200,volume=0.9", path])


# ---------------------------------------------------------------- Facebook
def page():
    P = dict(news.PAGES[PAGE])
    if P["id"] and P["token"]:
        import fbtoken
        P["token"] = fbtoken.page_token(P["id"], P["token"])      # user token ho to never-expiring page token
    return P


def description(script, facts):
    import seo
    k = script.get("card") or {}
    lines = [f"🐾 Animal: {k.get('animal')}" if MODE == "reel" else "",
             f"🌍 Country: {k.get('country') or facts['country']}",
             f"🌿 Habitat: {k.get('habitat')}" if MODE == "reel" else "",
             f"🍖 Diet: {k.get('diet')}" if MODE == "reel" else "",
             f"🛡️ Status: {k.get('status')}" if MODE == "reel" else ""]
    card = "\n".join(x for x in lines if x and not x.endswith(": None") and not x.endswith(": "))
    said = " ".join(sc.get("text", "") for sc in script["scenes"])
    src = f"📚 Source: Wikipedia - {facts['title']}"
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
            f"#WildNations #wildlife #animals #nature #{re.sub(r'[^A-Za-z]', '', facts['country'])}")


# ---------------------------------------------------------------- main
def main():
    os.makedirs(nv.WORK, exist_ok=True)
    P = page()
    if not DRY_RUN and not (P["id"] and P["token"]):
        log("WILD_PAGE_ID / WILD_PAGE_TOKEN abhi set nahi - page jurne tak kuch nahi")
        REPORT["waiting"] = "page secrets missing"
        return
    h = load_hist()
    for attempt in range(3):
        try:
            if MODE == "reel":
                country, animal = pick_reel(h)
                facts = reel_facts(country, animal)
            else:
                country, animal = pick_long(h), None
                log(f"Lambi film: Wildlife of {country}")
                facts = long_facts(h, country)
            break
        except Exception as e:
            log(f"facts fail ({e}) - agla")
            if MODE == "reel":
                h["reel"].append({"country": country, "animal": animal, "date": REPORT["time_utc"],
                                  "skipped": str(e)[:100]})
            else:
                h["long"].append({"country": country, "date": REPORT["time_utc"], "skipped": str(e)[:100]})
            save_hist(h)
    else:
        raise RuntimeError("facts nahi mile")
    script = write_script(facts)
    log(f"Title: {script.get('title')} | {len(script['scenes'])} scenes")
    path = build_video(script, facts, h["used_clips"])
    REPORT.update({k: v for k, v in nv.REPORT.items() if k not in ("errors", "posted")})
    desc = description(script, facts)
    log(f"--- description ---\n{desc}\n")
    meta = {"country": country, "animal": animal, "wiki": facts["title"], "date": REPORT["time_utc"],
            "title": script.get("title", "")[:150], "dur": round(nv.duration(path))}
    if not DRY_RUN:
        import slot_wait
        slot_wait.wait(log)
        meta["post_id"] = nv.post_reel(P, path, desc) if MODE == "reel" else \
            nv.post_long(P, path, script.get("title") or facts["title"], desc)
        log(f"posted {meta['post_id']}")
        news.POSTS_LOG = "wild_posts_history.json"
        news.log_post(PAGE, meta["post_id"], MODE, [country], meta["title"])
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
