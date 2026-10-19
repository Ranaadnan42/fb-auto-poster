"""
Atlas Untold - duniya ke mulkon/sheharon ki asli documentary (YouTube, English).

- Sirf ASLI camera footage (Pixabay "film" + Pexels agar PEXELS_API_KEY ho). AI/animation nahi.
- Har clip us mulk/shehar ki: tags mein jagah ka naam + Gemini vision se check. Ghalat mulk = reject.
- Pakke numbers: World Bank (abadi) + Wikipedia (taaruf). AI andaza nahi lagata.
- Lambi (~11 min, chapters) ya Short (~55 sec, vertical). MODE=long / short
Secrets: GEMINI_API_KEY, PIXABAY_API_KEY, (PEXELS_API_KEY), YT_WORLD_CLIENT_ID/SECRET/REFRESH_TOKEN
WORLD_LANG=ur -> "Frames of Life": wahi bot Urdu mein, Pakistanion ke liye bahar ki zindagi,
kharcha us mulk ki currency + Pakistani rupay dono mein. Secrets: YT_FRAMES_*
"""
import os
import re
import sys
import json
import math
import time
import random
import asyncio
import datetime
import subprocess

import requests

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
MODE = (os.environ.get("MODE") or "long").strip().lower()
LONG = MODE != "short"
URDU = (os.environ.get("WORLD_LANG") or "en").strip().lower() == "ur"
CHANNEL = (os.environ.get("WORLD_CHANNEL") or ("Frames of Life" if URDU else "Atlas Untold")).strip()
YT_NAME = "frames" if URDU else "world"
SCORE_NAME = "Frames Score" if URDU else "Atlas Score"
W, H = (1920, 1080) if LONG else (1080, 1920)
VOICE, RATE = ("ur-PK-AsadNeural", "-4%") if URDU else ("en-GB-RyanNeural", "-6%")
FONT = "Noto Naskh Arabic" if URDU else "Noto Sans"
FONTS_DIR = os.path.abspath("fonts")
PFX = "frames" if URDU else "world"
WORK = f"work_{PFX}"
HISTORY_FILE = f"{PFX}_{MODE}_history.json"
REPORT_FILE = f"{PFX}_{MODE}_last_run.json"
OUT_FILE = f"final_{PFX}.mp4"
MODELS = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
UA = {"User-Agent": "AtlasUntoldBot/1.0 (youtube documentary; contact ranaadnan320@gmail.com)"}
GEO_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
           "ne_50m_admin_0_countries.geojson")

# roz silsila badalta hai - viewer bor na ho, mauzu kabhi khatam na hon
# paisa: "rehna / shift hona / retire" wale mauzu par ads sab se mehenge - is liye zyada yahi
LONG_SERIES = ["living", "country", "retire", "versus", "moving", "city", "best_list"]
SHORT_SERIES = ["cost_short", "facts", "living_short", "versus_short", "city_facts", "food", "hidden"]
SERIES_HINT = {
    "country": "a complete documentary about ONE country (geography, population, peoples and "
               "communities, religion, languages, history, culture and daily life, food, music and arts, "
               "best cities, living and cost, travel tips)",
    "city": "a complete documentary about ONE famous city (history, neighbourhoods, people, culture, food, "
            "landmarks, living and cost, best time to visit)",
    "living": "'Living in <country>': cost of living, rent, jobs, salaries in general terms, healthcare, "
              "safety, best cities for families / students / workers, pros and cons",
    "history": "the history of ONE country or civilisation from ancient times to today (big eras, empires, "
               "turning points), filmed at real historic places of that country",
    "food_culture": "the food, festivals, traditions, music and daily culture of ONE country",
    "versus": "a comparison of TWO countries or two cities (living, cost, culture, safety, jobs, weather)",
    "retire": "'Retiring in <country>': is it a good place to retire abroad for Americans/Europeans - "
              "affordability, healthcare, safety, climate, visas in general terms, expat communities, best towns",
    "moving": "'Moving to <country>: what nobody tells you' - honest pros and cons of moving there, culture shock, "
              "daily life, jobs, cost, best cities for newcomers",
    "best_list": "a ranked list documentary such as 'The 7 most affordable countries to live well' or "
                 "'Safest countries in <continent>' - each entry a short chapter with real footage",
    "cost_short": "'What life really costs in <city or country>' quick honest overview",
    "facts": "'Amazing facts about <country>' - 6 short surprising true facts",
    "city_facts": "'<city> in 60 seconds' - the most striking things about one city",
    "food": "'Must-try foods of <country>' - 5 famous dishes",
    "hidden": "'Hidden places in <country>' - 5 beautiful lesser known real places",
    "versus_short": "'<A> vs <B>' quick comparison of two countries",
    "living_short": "'Would you live in <city>?' - quick pros/cons and cost",
    # ---- Frames of Life (Urdu) - Pakistani nazar se
    "pk_living": "'<country> mein Pakistani ki zindagi': rent, khana, transport, typical salaries in general "
                 "terms, jobs Pakistanis do there, Pakistani community, mosques and halal food, weather, "
                 "safety, best cities for Pakistanis, honest pros and cons",
    "pk_moving": "'<country> jane se pehle yeh zaroor jaan lein' - what Pakistanis should know before moving "
                 "there for work or study: visa types in general terms (no fake fees), cost, culture, rules, "
                 "common mistakes, how to stay safe from fake agents",
    "pk_versus": "comparison of TWO countries or cities popular with Pakistanis (e.g. Dubai vs Riyadh, "
                 "Canada vs Australia): cost, salaries, saving, life, family life",
    "pk_country": "a complete documentary about ONE country (geography, population, peoples, religion, "
                  "languages, history, culture, food, best cities, living and cost) for Pakistani viewers",
    "pk_city": "a complete documentary about ONE famous city (history, areas, people, culture, food, "
               "landmarks, cost of living, Pakistani community there)",
    "pk_jobs": "'<country> mein kaun se kaam milte hain': common jobs for Pakistanis there, skills needed, "
               "general salary ranges, saving potential, how to find real jobs safely",
    "pk_best_list": "a ranked list like '7 sab se sasti mulk jahan Pakistani ache se reh sakte hain' or "
                    "'Muslim mumalik jahan zindagi aasaan hai' - each entry a short chapter",
    "pk_cost_short": "'<city> mein ek mahine ka kharcha' quick honest overview for a Pakistani",
    "pk_salary_short": "'<country> mein kitna kama kar kitna bacha sakte hain' quick overview",
    "pk_facts": "'<country> ke hairan kun haqaiq' - 6 short surprising true facts",
    "pk_versus_short": "'<A> ya <B>: Pakistani ke liye kaun behtar?' quick comparison",
    "pk_food": "'<country> ke mashhoor khane' - 5 famous dishes, halal tips",
    "pk_city_facts": "'<city> 60 second mein' - the most striking things about one city",
    "pk_hidden": "'<country> ki khoobsurat chhupi jagahein' - 5 beautiful lesser known real places",
}
if URDU:
    LONG_SERIES = ["pk_living", "pk_moving", "pk_versus", "pk_country", "pk_jobs", "pk_city", "pk_best_list"]
    SHORT_SERIES = ["pk_cost_short", "pk_salary_short", "pk_facts", "pk_versus_short", "pk_food",
                    "pk_city_facts", "pk_hidden"]


def fx_rates(codes):
    """Aaj ka rate (free, bina key): 1 <currency> = kitne PKR. Fail ho to {}."""
    try:
        j = requests.get("https://open.er-api.com/v6/latest/USD", timeout=30, headers=UA).json()
        rt = j.get("rates", {})
        pkr = rt.get("PKR")
        out = {}
        for c in codes:
            c = (c or "").upper()
            if pkr and rt.get(c):
                out[c] = f"1 {c} = {pkr / rt[c]:,.2f} PKR (rate {j.get('time_last_update_utc', '')[:16]})"
        if pkr:
            out["USD"] = f"1 USD = {pkr:,.2f} PKR"
        return out
    except Exception as e:
        log(f"fx skip: {str(e)[:120]}")
        return {}

os.makedirs(WORK, exist_ok=True)
REPORT = {"mode": MODE, "clips": 0, "clips_rejected": 0, "vision_checks": 0, "errors": []}
USED = set()
SCORES = []
_client = None


def log(msg):
    print(f"[{datetime.datetime.utcnow():%H:%M:%S}] {msg}", flush=True)


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cmd fail: {' '.join(cmd[:6])} ... {r.stderr[-600:]}")
    return r.stdout


def duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                      path]).strip() or 0)


def load_history():
    try:
        return json.load(open(HISTORY_FILE, encoding="utf-8"))
    except Exception:
        return []


def save_history(h):
    json.dump(h[-500:], open(HISTORY_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def write_report():
    json.dump(REPORT, open(REPORT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- Gemini
def _gem():
    global _client
    from google import genai
    if _client is None:
        _client = genai.Client(api_key=GEMINI_KEY)
    return _client


def ask_json(prompt, temp=0.8):
    from google.genai import types
    last = None
    for model in MODELS:
        for attempt in range(2):
            try:
                res = _gem().models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json",
                                                       temperature=temp))
                return json.loads(res.text)
            except Exception as e:
                last = e
                log(f"{model} try {attempt + 1}: {str(e)[:160]}")
                time.sleep(5)
    raise RuntimeError(f"Gemini fail: {last}")


def vision_ok(jpg, place, what):
    """Gemini se poochho: kya yeh frame waqai is jagah ka hai? Error ho to None (tag par bharosa)."""
    from google.genai import types
    try:
        data = open(jpg, "rb").read()
        for model in MODELS[::-1]:                              # lite pehle - free quota zyada
            try:
                res = _gem().models.generate_content(
                    model=model,
                    contents=[types.Part.from_bytes(data=data, mime_type="image/jpeg"),
                              f"This is a frame from a stock video found for '{what}' in {place}. "
                              f"Could this realistically be real camera footage filmed in {place} "
                              f"(not another country, not animation/CGI/AI art)? "
                              'Answer JSON {"match": true/false}'],
                    config=types.GenerateContentConfig(response_mime_type="application/json",
                                                       temperature=0))
                REPORT["vision_checks"] += 1
                return bool(json.loads(res.text).get("match"))
            except Exception as e:
                last = str(e)
                time.sleep(3)
        log(f"vision skip: {last[:120]}")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- pakke facts
def world_bank(iso3, code):
    try:
        j = requests.get(f"https://api.worldbank.org/v2/country/{iso3}/indicator/{code}",
                         params={"format": "json", "mrnev": 1}, timeout=30, headers=UA).json()
        row = j[1][0]
        return row["value"], row["date"]
    except Exception:
        return None, None


def wiki_summary(title):
    try:
        j = requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/" +
                         requests.utils.quote(title.replace(" ", "_")), timeout=30, headers=UA).json()
        return j.get("extract", "")
    except Exception:
        return ""


def atlas_score(le, hom, plr, gdp):
    """Apna pakka score (sirf World Bank data se): Safety, Health, Affordability, Economy -> /10."""
    parts = {}
    if hom is not None:
        parts["Safety"] = max(0.0, min(10.0, 10 - hom * 0.5))
    if le:
        parts["Health"] = max(0.0, min(10.0, (le - 55) / 3))
    if plr:
        parts["Affordability"] = max(0.0, min(10.0, 10 - (plr - 0.25) * 10))
    if gdp:
        parts["Economy"] = max(0.0, min(10.0, math.log10(max(gdp, 300)) * 4 - 9))
    if len(parts) < 3:
        return None
    parts = {k: round(v, 1) for k, v in parts.items()}
    parts[SCORE_NAME] = round(sum(parts.values()) / len(parts), 1)
    return parts


def gather_facts(plan):
    facts = {}
    for c in plan.get("countries", [])[:2]:
        iso = (c.get("iso3") or "").upper()
        if not re.fullmatch(r"[A-Z]{3}", iso):
            continue
        pop, yr = world_bank(iso, "SP.POP.TOTL")
        urb, _ = world_bank(iso, "SP.URB.TOTL.IN.ZS")
        area, _ = world_bank(iso, "AG.LND.TOTL.K2")
        gdp, gyr = world_bank(iso, "NY.GDP.PCAP.CD")
        le, _ = world_bank(iso, "SP.DYN.LE00.IN")
        hom, _ = world_bank(iso, "VC.IHR.PSRC.P5")
        plr, _ = world_bank(iso, "PA.NUS.PPPC.RF")
        facts[c["name"]] = {
            "life_expectancy_years": f"{le:.1f}" if le else None,
            "homicides_per_100k": f"{hom:.1f}" if hom is not None else None,
            "price_level_vs_usa": f"{plr * 100:.0f}% of US prices" if plr else None,
            "atlas_score": atlas_score(le, hom, plr, gdp),
            "population": f"{pop / 1e6:.1f} million ({yr}, World Bank)" if pop else None,
            "urban_population_percent": f"{urb:.0f}%" if urb else None,
            "land_area_km2": f"{area:,.0f}" if area else None,
            "gdp_per_person_usd": f"${gdp:,.0f} ({gyr})" if gdp else None,
            "wikipedia": wiki_summary(c["name"])[:1500],
        }
    for city in plan.get("cities", [])[:2]:
        facts[city] = {"wikipedia": wiki_summary(city)[:1200]}
    if URDU:
        fx = fx_rates([c.get("currency") for c in plan.get("countries", [])])
        if fx:
            facts["exchange_rates_today"] = fx
    for name, f in facts.items():
        if isinstance(f, dict) and f.get("atlas_score"):
            SCORES.append((name, f["atlas_score"]))
    return facts


# ---------------------------------------------------------------- plan + script
def plan_topic(history):
    n = len(history)
    series = (LONG_SERIES if LONG else SHORT_SERIES)[n % 7]
    used = [h.get("subject", "") for h in history[-300:]]
    aud = ("The audience is Pakistanis (in Pakistan and the Gulf) who dream of living, working or studying "
           "abroad. Prefer countries/cities popular with Pakistanis (Gulf, Europe, UK, Canada, Australia, "
           "Turkey, Malaysia, Japan, China, Central Asia) but rotate widely.\n" if URDU else "")
    plan = ask_json(f"""You plan the next video for the YouTube travel & world documentary channel "{CHANNEL}".
{aud}
Video type: {SERIES_HINT[series]}.
Already covered (do NOT repeat the same subject for this type): {json.dumps(used)}
Pick a subject with strong worldwide search interest and plenty of REAL stock footage online
(well-known places are better). Rotate continents fairly over time.
Return JSON: {{"subject": "short subject e.g. Japan / Kyoto, Japan / Dubai vs Doha",
 "countries": [{{"name": "English country name", "iso3": "ISO 3166 alpha-3", "currency": "ISO 4217 code"}}],
 "cities": ["main city names involved (0-3)"]}}""")
    plan["series"] = series
    return plan


def write_script(plan, facts):
    if URDU:
        return write_script_ur(plan, facts)
    if LONG:
        shape = """"chapters": [{"name": "chapter title (e.g. History)", "scenes": [scene, ...]}, ...]
7-10 chapters, 34-42 scenes in total, about 1500-1700 words in total (about 11 minutes spoken).
The FIRST chapter is a short cold-open hook (2 scenes) and the LAST chapter is a short conclusion that asks
viewers which place they would choose and to subscribe to Atlas Untold."""
    else:
        shape = """"chapters": [{"name": "main", "scenes": [scene, ...]}]
8-10 scenes, 120-140 words in total (about 55 seconds). Scene 1 is a strong hook. Last scene: a question
for the comments and 'Subscribe to Atlas Untold'."""
    return ask_json(f"""You write a premium documentary in the style of National Geographic / BBC travel films for
the YouTube channel "{CHANNEL}". Type: {SERIES_HINT[plan['series']]}. Subject: {plan['subject']}.

VERIFIED FACTS (use these numbers exactly, never invent other statistics; if a number is not here,
describe in words without a number):
{json.dumps(facts, ensure_ascii=False)[:6000]}

Rules:
- Calm, rich, cinematic narrator voice. Spoken plain English sentences only, no emojis/symbols/headings.
- Cover (as fits the type): where it is, population, peoples and communities, religions, languages,
  history, culture and daily life, traditions, food, music and arts, best cities, living and cost, travel tips.
- Religion, ethnicity and politics: respectful, neutral, factual, no opinions, nothing offensive.
- Every scene is about ONE concrete visible thing (a landmark, a street, a dish, a festival, nature).
- "search": 2-3 short stock-video search phrases that MUST include the place name
  (e.g. "Kyoto temple", "Fushimi Inari Kyoto", "Japan street food"). Only things that are filmable.
- "place": the city/region + country of that scene (e.g. "Kyoto, Japan").
- "label": short on-screen place label (max 4 words) or "" if none.
- If VERIFIED FACTS has "atlas_score", one scene near the end presents the Atlas Score (our own rating from
  World Bank data: Safety, Health, Affordability, Economy, each out of 10) and explains what it means.
  Put that scene's "score": true.
- Be honest and useful like a friend who lived there; give practical tips. That makes this channel different.

Return JSON:
{{"title": "documentary title",
 "yt_title": "high-CTR YouTube title, max 70 chars, honest, includes the main place name",
 "thumb_text": "2-4 big words for the thumbnail",
 "description": "3 short SEO paragraphs for YouTube (no timestamps, no hashtags)",
 "hashtags": ["#8 hashtags"],
 "keywords": "6-10 search keywords separated by ' | '",
 "fact_card": ["4 short lines for an on-screen fact card, e.g. 'Capital: Tokyo', using VERIFIED FACTS"],
 {shape}
 }}
scene = {{"text": "narration 1-3 sentences", "place": "...", "search": ["..."], "label": "...", "score": false}}""", temp=0.7)


def write_script_ur(plan, facts):
    if LONG:
        shape = """"chapters": [{"name": "chapter ka naam Urdu mein", "scenes": [scene, ...]}, ...]
7-10 chapters, 34-42 scenes in total, about 1500-1700 Urdu words in total (about 11 minutes spoken).
FIRST chapter = short hook (2 scenes). LAST chapter = short conclusion: ask viewers in which country they
would like to live, and to subscribe to Frames of Life."""
    else:
        shape = """"chapters": [{"name": "main", "scenes": [scene, ...]}]
8-10 scenes, 120-140 Urdu words in total (about 55 seconds). Scene 1 is a strong hook. Last scene: a question
for the comments and 'Frames of Life ko subscribe karein'."""
    return ask_json(f"""You write a premium Urdu documentary (style of BBC Urdu / National Geographic) for the
YouTube channel "{CHANNEL}" for Pakistani viewers. Type: {SERIES_HINT[plan['series']]}. Subject: {plan['subject']}.

VERIFIED FACTS (use these numbers exactly, never invent statistics; if a number is not here, describe
in words or say 'taqreeban' with a clearly rough everyday price):
{json.dumps(facts, ensure_ascii=False)[:6500]}

Rules:
- Narration ("text") in natural spoken Urdu, in URDU SCRIPT (اردو), simple words like a Pakistani friend
  who lives there. No English sentences, no emojis/symbols. Common English words (job, visa, rent) are ok
  written in Urdu script.
- MONEY: whenever you mention a price/salary/rent, say it in the LOCAL currency AND in Pakistani rupees
  using exchange_rates_today, e.g. "تقریباً 3000 درہم، یعنی تقریباً 2 لاکھ 30 ہزار پاکستانی روپے".
  Write numbers as digits. Prices must be realistic, clearly approximate; never fake visa fees.
- Religion, ethnicity, politics: respectful, neutral, factual. Mention mosques/halal food where useful.
- Warn kindly about fake agents and illegal routes where relevant; never encourage illegal migration.
- Every scene is about ONE concrete visible thing (a landmark, street, market, dish, office, nature).
- "search": 2-3 SHORT ENGLISH stock-video search phrases that MUST include the place name
  (e.g. "Dubai Marina", "Dubai metro", "Riyadh skyline"). Only filmable things.
- "place": the city/region + country of that scene IN ENGLISH (e.g. "Dubai, United Arab Emirates").
- "label": short on-screen place label in Urdu script (max 4 words) or "".
- If VERIFIED FACTS has "atlas_score", one scene near the end presents the "{SCORE_NAME}" (our own rating
  from World Bank data: safety, health, affordability, economy, each out of 10). Put that scene's "score": true.

Return JSON:
{{"title": "documentary title in Urdu script",
 "yt_title": "high-CTR YouTube title in Urdu script with the place name, max 70 chars, honest; may end with
   a short English part after | e.g. '... | Life in Dubai'",
 "thumb_text": "2-4 big Urdu words for the thumbnail",
 "description": "3 short SEO paragraphs in Urdu script, then one short English paragraph (no timestamps, no hashtags)",
 "hashtags": ["#8 hashtags, mix Urdu-Roman and English e.g. #DubaiLife #PakistaniAbroad"],
 "keywords": "8-12 search keywords separated by ' | ' (Roman Urdu + English, e.g. dubai mein naukri | life in dubai)",
 "fact_card": ["4 short lines in Urdu script for an on-screen fact card, using VERIFIED FACTS"],
 {shape}
 }}
scene = {{"text": "Urdu narration 1-3 sentences", "place": "...", "search": ["..."], "label": "...", "score": false}}""", temp=0.7)


# ---------------------------------------------------------------- asli footage
def _words(place):
    bad = {"the", "of", "and", "city", "republic", "kingdom", "state", "states", "united", "islands"}
    return [w for w in re.findall(r"[a-z]+", place.lower()) if len(w) > 2 and w not in bad]


def pixabay_search(q):
    if not PIXABAY_KEY:
        return []
    try:
        r = requests.get("https://pixabay.com/api/videos/", timeout=40, params={
            "key": PIXABAY_KEY, "q": q[:90], "safesearch": "true", "per_page": 30, "video_type": "film"})
        out = []
        for h in r.json().get("hits", []):
            v = h.get("videos", {})
            pick = next((v[s] for s in ("large", "medium")
                         if v.get(s, {}).get("url") and v[s].get("width", 0) >= 1280), None)
            if pick and h.get("duration", 0) >= 4:
                out.append({"id": f"px{h['id']}", "url": pick["url"], "text": h.get("tags", "").lower(),
                            "dur": h.get("duration", 10)})
        return out
    except Exception as e:
        log(f"Pixabay error: {str(e)[:120]}")
        return []


def pexels_search(q):
    if not PEXELS_KEY:
        return []
    try:
        r = requests.get("https://api.pexels.com/videos/search", timeout=40, headers={"Authorization": PEXELS_KEY},
                         params={"query": q[:90], "per_page": 30,
                                 "orientation": "landscape" if LONG else "portrait"})
        out = []
        for v in r.json().get("videos", []):
            files = sorted([f for f in v.get("video_files", []) if f.get("width") and f.get("link")
                            and (f["width"] >= 1280 or (not LONG and f["height"] >= 1280))],
                           key=lambda f: f["width"])
            if files and v.get("duration", 0) >= 4:
                slug = (v.get("url") or "").lower().replace("-", " ")
                out.append({"id": f"pe{v['id']}", "url": files[0]["link"], "text": slug, "dur": v["duration"]})
        return out
    except Exception as e:
        log(f"Pexels error: {str(e)[:120]}")
        return []


def get_clips(scene, country_words, job, prefix, need):
    """Is scene ke liye `need` asli clips: jagah ka naam tags mein + vision check. Kabhi doosra mulk nahi."""
    place = scene.get("place") or ""
    pw = _words(place)
    queries = list(scene.get("search") or [])
    city = place.split(",")[0].strip()
    country = place.split(",")[-1].strip()
    queries += [f"{city} aerial", city, f"{country} landscape", f"{country} city", country]
    got = []
    for q in queries:
        if len(got) >= need:
            break
        cands = pexels_search(q) + pixabay_search(q)
        random.shuffle(cands)
        for c in cands:
            if len(got) >= need:
                break
            if c["id"] in USED:
                continue
            # jagah (shehar ya mulk) ka naam tags/naam mein hona zaroori
            if not any(w in c["text"] for w in pw + country_words):
                continue
            path = os.path.join(job, f"{prefix}_{len(got)}.mp4")
            try:
                with requests.get(c["url"], stream=True, timeout=180) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as f:
                        for chunk in resp.iter_content(1 << 20):
                            f.write(chunk)
                if os.path.getsize(path) < 50000:
                    continue
                jpg = path + ".jpg"
                run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(c['dur'] / 2, 3):.1f}", "-i", path,
                     "-frames:v", "1", "-vf", "scale=640:-2", jpg])
                try:
                    from PIL import Image, ImageStat
                    if ImageStat.Stat(Image.open(jpg).convert("L")).mean[0] < 28:   # kaali/andheri clip
                        REPORT["clips_rejected"] += 1
                        USED.add(c["id"])
                        continue
                except Exception:
                    pass
                ok = vision_ok(jpg, place or country, q)
                if ok is False:
                    REPORT["clips_rejected"] += 1
                    USED.add(c["id"])
                    continue
                USED.add(c["id"])
                got.append(path)
                REPORT["clips"] += 1
            except Exception as e:
                log(f"clip fail: {str(e)[:120]}")
    return got


# ---------------------------------------------------------------- awaaz, music, likhai
def tts(text, path):
    import edge_tts

    async def go():
        await edge_tts.Communicate(text, VOICE, rate=RATE).save(path)
    for attempt in range(6):
        try:
            asyncio.run(go())
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            log(f"TTS retry {attempt + 1}: {str(e)[:150]}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("fatal: Awaaz nahi bani")


def make_music(path, secs):
    """Halki documentary music (khud banti hai - copyright free)."""
    root = random.choice([110.0, 123.5, 130.8, 146.8])
    chords = [[1, 1.25, 1.5], [0.89, 1.125, 1.335], [0.75, 0.94, 1.125], [0.84, 1.0, 1.26]]
    parts = []
    for k, ch in enumerate(chords):
        env = f"(0.5+0.5*sin(2*PI*t/32-{k}*PI/2))"
        for m in ch:
            parts.append(f"0.06*sin(2*PI*{root * m:.2f}*t)*{env}")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc='{'+'.join(parts)}':s=44100:d={secs + 2:.1f}",
         "-af", "lowpass=f=1800,aecho=0.8:0.8:900|1500:0.4|0.3,afade=t=in:d=4,"
                f"afade=t=out:st={max(secs - 4, 1):.1f}:d=4,volume=0.9",
         "-ac", "2", "-c:a", "aac", "-b:a", "128k", path])


def ass_time(t):
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass_text(s):
    return (s or "").replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def make_ass(path, text, dur, label=None, chapter=None, card=None, title=None):
    sub = (54 if LONG else 78) if URDU else (46 if LONG else 62)   # Urdu harf chhote lagte hain
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT},{sub},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,{1 if URDU else 0},0,0,0,100,100,0,0,1,3,1,{2 if LONG else 8},120,120,{70 if LONG else 1000},1
Style: Label,{FONT},{40 if LONG else 50},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,{0 if URDU else 1},0,3,10,0,1,70,70,{150 if LONG else 1000},1
Style: Chap,{FONT},{92 if LONG else 96},&H0050D7FF,&H0050D7FF,&H00000000,&H96000000,1,0,0,0,100,100,{0 if URDU else 4},0,1,4,3,5,80,80,0,1
Style: Card,{FONT},{44 if LONG else 52},&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,3,18,0,7,90,90,{120 if LONG else 300},1
Style: Title,{FONT},{100 if LONG else 92},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,{0 if URDU else 3},0,1,5,3,5,80,80,0,1
Style: Mark,{FONT},28,&H60FFFFFF,&H60FFFFFF,&H90000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,9,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = [f"Dialogue: 0,{ass_time(0)},{ass_time(dur + 1)},Mark,,0,0,0,,{CHANNEL}"]
    if title:
        ev.append(f"Dialogue: 3,{ass_time(0.4)},{ass_time(min(dur, 5.5))},Title,,0,0,0,,"
                  f"{{\\fad(700,700)}}{ass_text(title)}")
    if chapter:
        ev.append(f"Dialogue: 3,{ass_time(0.2)},{ass_time(min(dur, 3.2))},Chap,,0,0,0,,"
                  f"{{\\fad(400,500)}}{ass_text(chapter.upper())}")
    if label:
        ev.append(f"Dialogue: 2,{ass_time(0.8)},{ass_time(min(dur, 5.5))},Label,,0,0,0,,"
                  f"{{\\fad(300,300)}}{ass_text(label)}")
    if card:
        body = "\\N".join(ass_text(c) for c in card[:5])
        ev.append(f"Dialogue: 2,{ass_time(0.5)},{ass_time(min(dur, 9))},Card,,0,0,0,,{{\\fad(400,400)}}{body}")
    words = text.split()
    n = 9 if LONG else 4
    chunks = [" ".join(words[i:i + n]) for i in range(0, len(words), n)]
    wts = [len(c) + 3 for c in chunks]
    sc = dur / max(sum(wts), 1)
    t = 0.0
    for c, w in zip(chunks, wts):
        ev.append(f"Dialogue: 1,{ass_time(t)},{ass_time(t + w * sc)},Sub,,0,0,0,,{ass_text(c)}")
        t += w * sc
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(ev) + "\n")


# ---------------------------------------------------------------- naqsha (intro)
def make_map(job, plan, secs):
    """Duniya ka naqsha -> mulk roshan -> zoom. Fail ho to None."""
    try:
        from PIL import Image, ImageDraw
        gj = requests.get(GEO_URL, timeout=60).json()
        isos = {(c.get("iso3") or "").upper() for c in plan.get("countries", [])}
        MW, MH = 3840, 1920
        img = Image.new("RGB", (MW, MH), (8, 22, 38))
        d = ImageDraw.Draw(img)
        boxes = []

        def xy(lon, lat):
            return ((lon + 180) / 360 * MW, (90 - lat) / 180 * MH)
        for ft in gj["features"]:
            p = ft["properties"]
            iso = p.get("ADM0_A3") or p.get("ISO_A3")
            hit = iso in isos or p.get("ISO_A3") in isos
            g = ft["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            for poly in polys:
                pts = [xy(*pt) for pt in poly[0]]
                d.polygon(pts, fill=(235, 180, 60) if hit else (46, 74, 98), outline=(20, 40, 60))
                if hit:
                    xs, ys = [a for a, _ in pts], [b for _, b in pts]
                    boxes.append((min(xs), min(ys), max(xs), max(ys)))
        if not boxes:
            return None
        x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
        x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        span = max((x1 - x0) * 1.8, (y1 - y0) * 1.8 * MW / MH, 300)
        zmax = min(MW / span, 14)
        path_png = os.path.join(job, "map.png")
        img.save(path_png)
        fr = int(secs * 30)
        out = os.path.join(job, "map.mp4")
        # zoompan: poore naqshe se mulk tak
        z = f"1+({zmax:.3f}-1)*min(on/{fr * 0.7:.0f}\\,1)"
        xexp = f"max(0\\,min(iw-iw/zoom\\,{cx:.0f}-iw/zoom/2))"
        yexp = f"max(0\\,min(ih-ih/zoom\\,{cy:.0f}-ih/zoom/2))"
        vf = (f"zoompan=z='{z}':x='{xexp}':y='{yexp}':d={fr}:s={W}x{H if LONG else 1080}:fps=30")
        if not LONG:
            vf += ",pad=1080:1920:0:420:color=0x081626"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", path_png, "-vf", vf + ",format=yuv420p",
             "-frames:v", str(fr), "-c:v", "libx264", "-preset", "veryfast", out])
        return out
    except Exception as e:
        log(f"map skip: {str(e)[:200]}")
        return None


# ---------------------------------------------------------------- video
FPS = 30


def render_scene(job, i, sc, clips, dur, ass_path, bg_override=None):
    fd = f":fontsdir={FONTS_DIR}" if os.path.isdir(FONTS_DIR) else ""
    srcs = [os.path.basename(c) for c in ([bg_override] if bg_override else clips)]   # cwd=job
    k = len(srcs)
    seg = dur / k
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for c in srcs:
        cmd += ["-stream_loop", "-1", "-t", f"{seg + 0.3:.2f}", "-i", c]
    cmd += ["-i", f"a{i}.mp3"]
    ch = []
    for j in range(k):
        start = 0.0
        ch.append(f"[{j}:v]trim=start={start}:duration={seg:.2f},setpts=PTS-STARTPTS,"
                  f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,"
                  f"fade=t=in:st=0:d=0.35,fade=t=out:st={max(seg - 0.35, 0):.2f}:d=0.35[v{j}]")
    ch.append("".join(f"[v{j}]" for j in range(k)) +
              f"concat=n={k}:v=1:a=0,eq=contrast=1.06:saturation=1.12:gamma=0.98,"
              f"subtitles={os.path.basename(ass_path)}{fd},format=yuv420p[v]")
    cmd += ["-filter_complex", ";".join(ch), "-map", "[v]", "-map", f"{k}:a:0", "-af", "apad",
            "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", f"s{i}.mp4"]
    run(cmd, cwd=job)
    return f"s{i}.mp4"


def build(script, plan, out_path):
    job = os.path.join(WORK, "job")
    import shutil
    shutil.rmtree(job, ignore_errors=True)
    os.makedirs(job)
    cwords = []
    for c in plan.get("countries", []):
        cwords += _words(c.get("name", ""))
    scenes = []
    for ci, chap in enumerate(script["chapters"]):
        for si, sc in enumerate(chap.get("scenes", [])):
            if (sc.get("text") or "").strip():
                scenes.append((ci, si, chap.get("name", ""), sc))
    parts, chapters_ts, t = [], [], 0.0
    map_clip = None
    for n, (ci, si, cname, sc) in enumerate(scenes):
        text = sc["text"].strip()
        tts(text, os.path.join(job, f"a{n}.mp3"))
        dur = duration(os.path.join(job, f"a{n}.mp3")) + 0.45
        need = max(1, min(4, math.ceil(dur / 5.5)))
        clips = get_clips(sc, cwords, job, f"c{n}", need)
        if not clips:
            prev = [os.path.join(job, p) for p in os.listdir(job) if p.startswith("c") and p.endswith(".mp4")]
            if prev:
                clips = random.sample(prev, min(len(prev), need))     # usi mulk ki pehle wali clip
            else:
                raise RuntimeError(f"is jagah ki asli videos nahi milin: {sc.get('place')}")
        first_of_chap = si == 0 and LONG and ci > 0
        if first_of_chap:
            chapters_ts.append((t, cname))
        card = script.get("fact_card") if (n == (2 if LONG else 1)) else None
        if sc.get("score") and SCORES:
            name, sco = SCORES[0]
            card = [f"{SCORE_NAME.upper()} - {name}"] + [f"{k}: {v}/10" for k, v in sco.items()]
        title = script.get("title") if n == 0 else None
        make_ass(os.path.join(job, f"s{n}.ass"), text, dur - 0.45, label=sc.get("label") or None,
                 chapter=cname if first_of_chap else None, card=card, title=title)
        bg = None
        if n == 1 and LONG:
            map_clip = map_clip or make_map(job, plan, dur)
            bg = map_clip
        parts.append(render_scene(job, n, sc, clips, dur, os.path.join(job, f"s{n}.ass"), bg))
        t += dur
        log(f"scene {n + 1}/{len(scenes)} ready ({len(clips)} clips)")
    with open(os.path.join(job, "list.txt"), "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
         "-c", "copy", "joined.mp4"], cwd=job)
    make_music(os.path.join(job, "music.m4a"), t)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", "joined.mp4", "-i", "music.m4a", "-filter_complex",
         "[1:a]volume=0.16[m];[0:a][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", os.path.abspath(out_path)], cwd=job)
    REPORT["seconds"] = round(duration(out_path), 1)
    return chapters_ts


def description(script, chapters_ts):
    d = script.get("description", "").strip()
    if chapters_ts:
        lines = ["0:00 " + ("تعارف" if URDU else "Intro")] + [f"{int(s // 60)}:{int(s % 60):02d} {name}" for s, name in chapters_ts]
        d += "\n\nChapters:\n" + "\n".join(lines)
    d += f"\n\n{script.get('keywords', '')}"
    if SCORES:
        d += (f"\n\n{SCORE_NAME}: our own rating out of 10 built only from World Bank data "
              "(safety, health, affordability, economy). It is a guide, not advice.")
    if URDU:
        d += ("\n\nنوٹ: قیمتیں اور تنخواہیں تقریباً ہیں اور وقت کے ساتھ بدلتی ہیں۔ ویزا اور نوکری کے لیے صرف سرکاری "
              "ذرائع اور رجسٹرڈ ایجنٹ پر بھروسہ کریں۔")
    aff = (os.environ.get("AFFILIATE_TEXT") or "").strip()
    if aff:
        d += "\n\n" + aff.replace("\\n", "\n")
    d += ("\n\nFootage: real stock video from Pixabay / Pexels contributors. "
          "Facts: World Bank, Wikipedia" + (", exchange rates: open.er-api.com" if URDU else "") +
          ". Narration voice is synthetic.")
    d += "\n\n" + " ".join(script.get("hashtags", [])[:10])
    return d


def _main():
    if not DRY_RUN:
        import yt
        if not yt.enabled(YT_NAME):
            log(f"YT_{YT_NAME.upper()}_* secrets abhi nahi - channel connect hone tak skip")
            return
    history = load_history()
    plan = None
    for attempt in range(3):
        try:
            plan = plan_topic(history)
            log(f"Topic: {plan['series']} | {plan['subject']}")
            facts = gather_facts(plan)
            script = write_script(plan, facts)
            chapters_ts = build(script, plan, OUT_FILE)
            break
        except Exception as e:
            log(f"try {attempt + 1} fail: {str(e)[:300]}")
            REPORT["errors"].append(str(e)[:300])
            history.append({"subject": (plan or {}).get("subject", ""), "skipped": True})
            if attempt == 2:
                REPORT["errors"].append("fatal: video nahi bani")
                raise
    desc = description(script, chapters_ts)
    entry = {"date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "series": plan["series"],
             "subject": plan["subject"], "title": script.get("yt_title") or script.get("title")}
    REPORT.update({"subject": plan["subject"], "series": plan["series"], "title": entry["title"]})
    if not DRY_RUN:
        import yt
        import slot_wait
        slot_wait.wait(log)
        if yt.enabled(YT_NAME):
            entry["yt_id"] = yt.upload(YT_NAME, OUT_FILE, entry["title"], desc,
                                       short=not LONG, lang="ur" if URDU else "en", category="19",
                                       thumb_title=script.get("thumb_text"))
        else:
            REPORT["errors"].append(f"YT_{YT_NAME.upper()}_* secrets nahi - upload skip")
    history = [h for h in history if not h.get("skipped")] + [entry]
    if not DRY_RUN:
        save_history(history)
    write_report()
    log("Done")


def main():
    try:
        _main()
    except Exception as e:
        REPORT["errors"].append(f"fatal: {str(e)[:300]}")
        write_report()
        raise


if __name__ == "__main__":
    main()
