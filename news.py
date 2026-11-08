"""
News Act + Sports Hubs - dunya bhar ki khabrein (English + Urdu) khud post karne wala agent.

Har run:
  1. Bohat se mashhoor news/sports RSS feeds (BBC, Al Jazeera, DW, ESPN, Google News waghaira) parhta hai
  2. Taaza (24 ghante) aur pehle na post hui khabar chunta hai - region / sport bari bari badalta hai
  3. AI (Groq, backup Gemini) khabar ko APNE alfaz mein likhta hai (copy nahi) - English ya Urdu
  4. Khabar se milti-julti free (Pixabay) tasveer par headline wala news card banata hai
  5. Page par photo post (source ka naam + link ke sath)

Env:
  PAGES     = "news", "sports" ya "news,sports"
  LANGUAGE  = "en" ya "ur"
  NEWS_PAGE_TOKEN, NEWS_PAGE_ID, SPORTS_PAGE_TOKEN, SPORTS_PAGE_ID
  GROQ_API_KEY, GEMINI_API_KEY, PIXABAY_API_KEY
  DRY_RUN=1 -> sirf card banaye, post na kare
"""
import datetime
import email.utils
import html
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

GRAPH_VER = "v23.0"
HISTORY_FILE = "news_history.json"
REPORT_FILE = "news_last_run.json"
WORK = "work_news"
FONTS_DIR = os.path.abspath("fonts")
W, H = 1080, 1350
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"}

DRY_RUN = os.environ.get("DRY_RUN") == "1"
LANG = (os.environ.get("LANGUAGE") or "en").strip().lower()
BREAKING = os.environ.get("BREAKING") == "1"     # har 2 ghante: sirf bari taaza khabar ho to foran post
BREAKING_PER_DAY = 5
PAGES_TO_RUN = [p.strip() for p in (os.environ.get("PAGES") or "news,sports").split(",") if p.strip()]
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY")
POSTS_LOG = "news_posts_history.json"      # har post ka record - agent (brain.py) is se views seekhta hai
BRAIN_FILE = "news_brain.json"             # agent ka seekha hua plan


def brain():
    try:
        with open(BRAIN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def brain_tips(kind):
    """Agent ne views dekh kar jo seekha - writer ko hidayat."""
    t = (brain().get(kind) or {}).get("tips") or []
    if not t:
        return ""
    return "\nLessons learned from what got the most views on this page (follow them):\n" + \
        "\n".join(f"- {x}" for x in t[:6]) + "\n"


def log_post(page, post_id, fmt, topics, title, sport=None):
    if not post_id:
        return
    try:
        with open(POSTS_LOG, encoding="utf-8") as f:
            log_ = json.load(f)
    except Exception:
        log_ = []
    log_.append({"date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "page": page, "id": str(post_id),
                 "fmt": fmt, "lang": LANG, "topics": topics, "sport": sport, "title": (title or "")[:140]})
    with open(POSTS_LOG, "w", encoding="utf-8") as f:
        json.dump(log_[-1500:], f, ensure_ascii=False, indent=1)

PAGES = {
    "news": {"name": "News Act", "token": os.environ.get("NEWS_PAGE_TOKEN"),
             "id": os.environ.get("NEWS_PAGE_ID"), "color": "&H002020D8", "accent": "0xD82020"},
    "sports": {"name": "Sports Hubs", "token": os.environ.get("SPORTS_PAGE_TOKEN"),
               "id": os.environ.get("SPORTS_PAGE_ID"), "color": "&H0000A5FF", "accent": "0xFFA500"},
}


def gnews(q, lang="en"):
    if lang == "ur":
        return ("https://news.google.com/rss/search?" +
                urllib.parse.urlencode({"q": q + " when:1d", "hl": "ur", "gl": "PK", "ceid": "PK:ur"}))
    return ("https://news.google.com/rss/search?" +
            urllib.parse.urlencode({"q": q + " when:1d", "hl": "en-US", "gl": "US", "ceid": "US:en"}))


# ---------------------------------------------------------------- sources
# News: har "region" ki apni feeds. Bot bari bari region badalta hai taake poori dunya cover ho.
NEWS_REGIONS = {
    "world": ["https://feeds.bbci.co.uk/news/world/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml",
              "https://rss.dw.com/rdf/rss-en-world", "https://www.theguardian.com/world/rss",
              "https://feeds.npr.org/1004/rss.xml", "https://www.france24.com/en/rss",
              gnews("world news")],
    "pakistan": ["https://www.dawn.com/feeds/home", "https://feeds.bbci.co.uk/urdu/rss.xml",
                 "https://rss.dw.com/rdf/rss-ur-all", gnews("Pakistan"), gnews("پاکستان", "ur")],
    "middle_east": ["https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
                    gnews("Saudi Arabia OR UAE OR Gulf"), gnews("Middle East")],
    "asia": ["https://feeds.bbci.co.uk/news/world/asia/rss.xml", gnews("India OR China OR Japan OR Asia")],
    "europe": ["https://feeds.bbci.co.uk/news/world/europe/rss.xml", "https://www.theguardian.com/world/europe-news/rss",
               gnews("Europe")],
    "americas": ["https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
                 "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml", gnews("United States OR Canada OR Brazil")],
    "africa": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", gnews("Africa")],
    "business": ["https://feeds.bbci.co.uk/news/business/rss.xml", gnews("global economy markets")],
    "science_tech": ["https://feeds.bbci.co.uk/news/technology/rss.xml",
                     "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", gnews("technology AI science")],
}
# Urdu posts mein Pakistan / Gulf / South Asia ki khabar zyada (Urdu audience ke liye zyada dilchasp)
NEWS_WEIGHT = {"en": {"world": 4, "middle_east": 2, "asia": 2, "europe": 2, "americas": 2, "africa": 1,
                      "business": 2, "science_tech": 2, "pakistan": 1},
               "ur": {"world": 3, "pakistan": 4, "middle_east": 3, "asia": 2, "europe": 1, "americas": 4,
                      "africa": 1, "business": 1, "science_tech": 1}}

# Sports: dunya ke tamam bare khel - har run mein woh khel jo sab se kam dafa post hua
SPORTS = {
    "cricket": ["https://feeds.bbci.co.uk/sport/cricket/rss.xml",
                "https://www.espncricinfo.com/rss/content/story/feeds/0.xml", gnews("cricket")],
    "football": ["https://feeds.bbci.co.uk/sport/football/rss.xml", "https://www.espn.com/espn/rss/soccer/news",
                 gnews("football soccer")],
    "tennis": ["https://feeds.bbci.co.uk/sport/tennis/rss.xml", gnews("tennis ATP OR WTA")],
    "basketball": ["https://www.espn.com/espn/rss/nba/news", gnews("NBA basketball")],
    "formula1": ["https://feeds.bbci.co.uk/sport/formula1/rss.xml", gnews("Formula 1")],
    "hockey": [gnews("field hockey"), gnews("NHL hockey")],
    "golf": ["https://feeds.bbci.co.uk/sport/golf/rss.xml", gnews("golf PGA")],
    "boxing": ["https://feeds.bbci.co.uk/sport/boxing/rss.xml", gnews("boxing fight")],
    "mma": [gnews("UFC MMA")],
    "athletics": ["https://feeds.bbci.co.uk/sport/athletics/rss.xml", gnews("athletics OR marathon")],
    "badminton": [gnews("badminton")],
    "baseball": ["https://www.espn.com/espn/rss/mlb/news", gnews("MLB baseball")],
    "american_football": ["https://www.espn.com/espn/rss/nfl/news", gnews("NFL")],
    "rugby": ["https://feeds.bbci.co.uk/sport/rugby-union/rss.xml", gnews("rugby")],
    "cycling": ["https://feeds.bbci.co.uk/sport/cycling/rss.xml", gnews("cycling Tour")],
    "snooker": ["https://feeds.bbci.co.uk/sport/snooker/rss.xml", gnews("snooker")],
    "kabaddi": [gnews("kabaddi")],
    "volleyball": [gnews("volleyball")],
    "wrestling": [gnews("wrestling WWE OR freestyle wrestling")],
    "squash": [gnews("squash PSA")],
    "table_tennis": [gnews("table tennis")],
    "motogp": [gnews("MotoGP")],
    # bare tournament: World Cup (FIFA, cricket, hockey, rugby...), Olympics, Asian / Commonwealth Games -
    # jab chal rahe hon to Google News par sab se zyada taaza khabrein inhi ki hoti hain
    "big_events": [gnews("World Cup"), gnews("FIFA World Cup"), gnews("ICC World Cup OR T20 World Cup OR Champions Trophy"),
                   gnews("Olympics OR Olympic Games OR Paralympics"), gnews("Asian Games OR Commonwealth Games"),
                   gnews("Euro OR Copa America OR AFCON OR Asian Cup OR Club World Cup"),
                   gnews("Rugby World Cup OR Hockey World Cup OR Asia Cup")],
    "olympic_sports": [gnews("swimming championship"), gnews("gymnastics championship"), gnews("weightlifting"),
                       gnews("javelin OR Arshad Nadeem"), gnews("archery OR shooting world cup"),
                       gnews("judo OR fencing OR rowing championship"), gnews("handball OR water polo")],
    "winter_sports": [gnews("figure skating OR skiing World Cup OR Winter Olympics")],
    "esports": [gnews("esports tournament")],
    "general": ["https://feeds.bbci.co.uk/sport/rss.xml", "https://www.espn.com/espn/rss/news",
                "https://www.skysports.com/rss/12040", gnews("sports")],
}
# Bare khel (cricket/football) zyada aate hain, chhote khel bhi bari bari aate rehte hain
SPORT_WEIGHT = {"big_events": 5, "olympic_sports": 2, "cricket": 5, "football": 5, "tennis": 2, "basketball": 2, "formula1": 2, "hockey": 2,
                "general": 2}

SPORT_IMG = {"cricket": "cricket stadium", "football": "football stadium", "tennis": "tennis court",
             "basketball": "basketball court", "formula1": "race car track", "hockey": "hockey stick ball",
             "golf": "golf course", "boxing": "boxing ring", "mma": "boxing gloves", "athletics": "running track",
             "badminton": "badminton shuttlecock", "baseball": "baseball stadium",
             "american_football": "american football", "rugby": "rugby ball", "cycling": "road cycling",
             "snooker": "snooker table", "kabaddi": "sports arena", "volleyball": "volleyball",
             "wrestling": "wrestling ring", "squash": "squash court", "table_tennis": "table tennis",
             "motogp": "motorcycle race", "general": "sports stadium", "big_events": "stadium crowd fans flags",
             "olympic_sports": "athletics stadium", "winter_sports": "skiing snow mountain", "esports": "gaming arena"}

REPORT = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "lang": LANG,
          "dry_run": DRY_RUN, "posted": {}, "errors": []}
os.makedirs(WORK, exist_ok=True)


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- AI (Groq pehle, Gemini backup)
CURRENT_PAGE = ""   # "news" / "sports" - har page ki apni Gemini key


def gemini_json(prompt):
    key = (os.environ.get(f"{CURRENT_PAGE.upper()}_GEMINI_API_KEY") if CURRENT_PAGE else None) \
        or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY nahi")
    last = None
    for model in ("gemini-3.5-flash", "gemini-flash-latest", "gemini-3.8-flash", "gemini-3.5-flash-lite",
                  "gemini-2.5-flash", "gemini-2.5-flash-lite"):
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              params={"key": key}, timeout=120,
                              json={"contents": [{"parts": [{"text": prompt}]}],
                                    "generationConfig": {"responseMimeType": "application/json",
                                                         "temperature": 0.6}})
            j = r.json()
            if "error" in j:
                raise RuntimeError(j["error"].get("message", "")[:150])
            return json.loads(j["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as e:
            last = e
            log(f"Gemini {model} fail: {str(e)[:150]}")
    raise RuntimeError(f"Gemini fail: {last}")


def ask_json(prompt):
    import groq_backup
    if CURRENT_PAGE and os.environ.get(f"{CURRENT_PAGE.upper()}_GEMINI_API_KEY"):
        # page ki apni Gemini key pehle, Groq backup
        try:
            return gemini_json(prompt)
        except Exception as e:
            log(f"{CURRENT_PAGE} Gemini fail ({str(e)[:120]}) - Groq try")
        return groq_backup.ask_json(prompt, 0.6, log)
    if groq_backup.enabled():
        try:
            return groq_backup.ask_json(prompt, 0.6, log)
        except Exception as e:
            log(f"Groq fail ({str(e)[:120]}) - Gemini try")
    return gemini_json(prompt)


# ---------------------------------------------------------------- history
def load_history():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            h = json.load(f)
    except Exception:
        h = {}
    for k in ("news", "sports", "used_images"):
        h.setdefault(k, [])
    return h


def save_history(h):
    for k in ("news", "sports"):
        h[k] = h[k][-400:]
    h["used_images"] = h["used_images"][-1500:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


def words(t):
    return set(w for w in re.findall(r"\w+", (t or "").lower()) if len(w) > 3)


def seen(item, past):
    link = item["link"]
    ws = words(item["title"])
    for p in past:
        if p.get("link") == link:
            return True
        pw = set(p.get("words") or [])
        if ws and pw and len(ws & pw) / max(1, min(len(ws), len(pw))) >= 0.6:
            return True
    return False


# ---------------------------------------------------------------- RSS
def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def parse_date(s):
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    return d


def fetch_feed(url):
    try:
        r = requests.get(url, headers=UA, timeout=25)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        log(f"Feed fail {url[:70]}: {str(e)[:80]}")
        return []
    out = []
    host = urllib.parse.urlparse(url).netloc.replace("www.", "").replace("feeds.", "")
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        get = {}
        for c in el:
            ct = c.tag.split("}")[-1]
            if ct == "link" and c.get("href"):
                get.setdefault("link", c.get("href"))
            elif ct == "source":
                get["source"] = (c.text or "").strip()
            else:
                get.setdefault(ct, (c.text or "").strip())
        title = strip_html(get.get("title"))
        link = (get.get("link") or get.get("guid") or "").strip()
        if not title or not link.startswith("http"):
            continue
        source = get.get("source") or ""
        if "news.google.com" in url and " - " in title:          # Google News: "Headline - Source"
            title, _, src2 = title.rpartition(" - ")
            source = source or src2
        if not source:
            source = {"bbc.co.uk": "BBC News", "aljazeera.com": "Al Jazeera", "rss.dw.com": "DW",
                      "theguardian.com": "The Guardian", "npr.org": "NPR", "france24.com": "France 24",
                      "dawn.com": "Dawn", "espn.com": "ESPN", "espncricinfo.com": "ESPNcricinfo",
                      "skysports.com": "Sky Sports"}.get(host, host)
            if "bbc" in host and "/urdu" in url:
                source = "BBC Urdu"
            if "bbc" in host and "/sport" in url:
                source = "BBC Sport"
        desc = strip_html(get.get("description") or get.get("summary") or get.get("content"))
        if desc.lower().startswith(title.lower()[:40]):          # Google News desc = title dobara
            desc = ""
        out.append({"title": title[:300], "link": link, "source": source[:60], "desc": desc[:600],
                    "date": parse_date(get.get("pubDate") or get.get("published") or get.get("updated")
                                       or get.get("date"))})
    return out


def fresh_items(urls, past):
    now = datetime.datetime.now(datetime.timezone.utc)
    items = []
    for u in urls:
        items += fetch_feed(u)
    good = []
    for it in items:
        age = (now - it["date"]).total_seconds() / 3600 if it["date"] else 12
        if age > 30 or age < -2 or seen(it, past):
            continue
        if len(it["title"].split()) < 4:
            continue
        if urls is SPORTS.get("big_events") and not re.search(
                r"world cup|olympi|paralymp|asian games|commonwealth games|\beuro\b|copa am|afcon|asian cup|"
                r"champions trophy|asia cup|club world cup", it["title"], re.I):
            continue
        if re.search(r"\b(live|as it happened|quiz|in pictures|watch:|video:|podcast|newsletter|crossword)\b",
                     it["title"], re.I):
            continue
        it["age"] = age
        good.append(it)
    # nayi khabar pehle, aur jis ki tafseel (desc) ho woh behtar
    good.sort(key=lambda x: (x["age"] - (3 if x["desc"] else 0)))
    uniq, ws_seen = [], []
    for it in good:
        ws = words(it["title"])
        if any(ws and len(ws & o) / max(1, min(len(ws), len(o))) >= 0.6 for o in ws_seen):
            continue
        ws_seen.append(ws)
        uniq.append(it)
    return uniq


def pick_topic(kind, past):
    """Region/khel jo kam dafa (aur der se) post hua - weight ke hisab se."""
    if kind == "news":
        pool, weight = NEWS_REGIONS, NEWS_WEIGHT[LANG]
    else:
        pool, weight = SPORTS, SPORT_WEIGHT
    recent = [p.get("topic") for p in past[-40:]]
    mult = (brain().get(kind) or {}).get("topic_mult") or {}     # agent: jo topic zyada views laya
    scores = {}
    for t in pool:
        w = weight.get(t, 1) * float(mult.get(t, 1))
        cnt = recent.count(t)
        last = len(recent) - 1 - recent[::-1].index(t) if t in recent else -50
        gap = len(recent) - last
        scores[t] = w * (1 + gap / 4) / (1 + cnt)
    order = sorted(pool, key=lambda t: -scores[t] * random.uniform(0.7, 1.3))
    return order


# ---------------------------------------------------------------- AI writing
def write_post(kind, topic, item):
    lang_name = "simple, natural Urdu (Urdu script, like BBC Urdu - not Hindi, not Roman)" if LANG == "ur" \
        else "clear, simple English"
    page = PAGES[kind]["name"]
    prompt = f"""You are the news editor of the Facebook page "{page}" ({'world sports news' if kind == 'sports' else 'world news'}).
Write ONE post about this {('sports (' + topic.replace('_', ' ') + ')') if kind == 'sports' else 'news'} story in {lang_name}.

Headline: {item['title']}
Details from the source: {item['desc'] or '(only the headline is available)'}
Source: {item['source']}

Rules:
- Write everything in your OWN words. Do NOT copy sentences from the source.
- Only use facts that are EXPLICITLY written in the headline/details above. If something is not written there
  (who was appointed, numbers, scores, dates, causes, results, quotes), do NOT state it - not even as a guess.
  With thin details, keep the summary short and say only what is known.
- Neutral, factual tone like a professional news agency. No opinions, no clickbait lies.
- If the story is only rumour/opinion, say "reportedly" / "according to {item['source']}".
{brain_tips(kind)}
Return JSON:
{{"headline": "catchy but true headline, max 12 words",
  "card_title": "very short headline for the image, max 9 words",
  "summary": "2-4 short sentences explaining the story in your own words",
  "label": "1-2 word category in CAPITALS for the image badge, e.g. {'CRICKET' if kind == 'sports' else 'WORLD'} (write in the post language)",
  "subject": "the main REAL person, team or place named in the item, as its English Wikipedia title (e.g. 'Keir Starmer', 'Pakistan national cricket team'), or empty string",
  "image_query": "2-3 plain ENGLISH words for a neutral stock photo matching the topic (a place, object, flag, building or sport scene; never violence, blood, weapons, dead bodies or a specific person's name)",
  "hashtags": ["5 relevant hashtags without #, mix English and the post language"]}}"""
    j = ask_json(prompt)
    for k in ("headline", "card_title", "summary"):
        if not str(j.get(k) or "").strip():
            raise RuntimeError(f"AI ne {k} nahi diya")
    return j


# ---------------------------------------------------------------- image
def pixabay_image(queries, path, used):
    if not PIXABAY_KEY:
        return False
    block = {"blood", "gun", "weapon", "war", "dead", "corpse", "woman", "girl", "bikini", "sexy", "model"}
    for q in queries:
        if not q:
            continue
        try:
            r = requests.get("https://pixabay.com/api/", timeout=40,
                             params={"key": PIXABAY_KEY, "q": q, "image_type": "photo", "safesearch": "true",
                                     "per_page": 50, "min_width": 1000, "order": "popular"})
            r.raise_for_status()
            hits = [x for x in r.json().get("hits", []) if x["id"] not in used
                    and not (block & set((x.get("tags") or "").lower().replace(",", " ").split()))]
        except Exception as e:
            log(f"Pixabay error ({q}): {str(e)[:120]}")
            continue
        random.shuffle(hits)
        for x in hits[:5]:
            try:
                data = requests.get(x.get("largeImageURL") or x["webformatURL"], timeout=90).content
                if len(data) > 40000:
                    with open(path, "wb") as f:
                        f.write(data)
                    used.append(x["id"])
                    log(f"Tasveer: pixabay {x['id']} ({q})")
                    return True
            except Exception as e:
                log(f"Image download fail: {str(e)[:100]}")
    return False


def gradient_bg(path, kind):
    c = ("0x2a0606", "0x0b1a33") if kind == "news" else ("0x0b2a12", "0x0b1a33")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"gradients=s={W}x{H}:c0={c[0]}:c1={c[1]}:d=1", "-frames:v", "1", path], check=True)


def esc(s):
    return (s or "").replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def render_card(kind, bg, label, title, out):
    P = PAGES[kind]
    ur = LANG == "ur"
    font = "Noto Naskh Arabic" if ur else "Noto Sans"
    size = max(60, (104 if ur else 92) - max(0, len(title) - 40))
    date = datetime.datetime.utcnow().strftime("%d %b %Y")
    tag = ("BREAKING NEWS" if kind == "news" else "SPORTS UPDATE") if not ur else \
        ("تازہ ترین خبر" if kind == "news" else "کھیلوں کی خبر")
    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Brand,Noto Sans,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,7,60,60,40,1
Style: Tag,{font},40,&H00FFFFFF,&H00FFFFFF,{P['color']},{P['color']},1,0,0,0,100,100,0,0,3,14,0,7,60,60,40,1
Style: Title,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,4,8,70,70,{int(H * 0.52) + 70},1
Style: Foot,Noto Sans,34,&H00DDDDDD,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,2,60,60,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Brand,,0,0,0,,{{\\pos(60,50)}}{esc(P['name']).upper()}
Dialogue: 0,0:00:00.00,0:00:05.00,Tag,,0,0,0,,{{\\pos(74,128)}}{esc(label or tag)}
Dialogue: 0,0:00:00.00,0:00:05.00,Title,,0,0,0,,{esc(title)}
Dialogue: 0,0:00:00.00,0:00:05.00,Foot,,0,0,0,,{date}  •  Follow {esc(P['name'])}
"""
    ass_path = os.path.join(WORK, f"{kind}.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass)
    fonts = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
    ap = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.25:t=fill,"
          f"drawbox=x=0:y=0:w=iw:h=220:color=black@0.45:t=fill,"
          f"drawbox=x=0:y={int(H * 0.52)}:w=iw:h={int(H * 0.48)}:color=black@0.62:t=fill,"
          f"drawbox=x=0:y={int(H * 0.52)}:w=iw:h=10:color={P['accent']}@1:t=fill,"
          f"ass='{ap}':fontsdir='{fonts}'")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", bg, "-t", "1",
                    "-vf", vf, "-frames:v", "1", "-q:v", "2", out], check=True)
    if os.path.getsize(out) < 30000:
        raise RuntimeError("card theek nahi bana")


# ---------------------------------------------------------------- caption + Facebook
def caption_for(kind, j, item):
    """Baqi pages wala SEO caption (hook, keywords, sawal, follow, 10 hashtags) + khabar ki tafseel aur source."""
    import seo
    src = (f"📰 ذریعہ: {item['source']}" if LANG == "ur" else f"📰 Source: {item['source']}") + f"\n🔗 {item['link']}"
    try:
        cap = seo.build(ask_json, kind, j["headline"].strip(), f"{j['headline']}. {j['summary']}", LANG, is_reel=False)
        parts = cap.split("\n\n")
        parts[0] = "🔴 " + j["headline"].strip() if not parts[0].strip() else parts[0]
        parts[1:1] = [j["summary"].strip(), src]
        extra = " ".join("#" + re.sub(r"[\s#]+", "", t) for t in (j.get("hashtags") or [])[:3] if t)
        if extra and parts[-1].startswith("#"):
            have = set(parts[-1].lower().split())
            parts[-1] = " ".join(parts[-1].split()[:10] + [t for t in extra.split() if t.lower() not in have])[:600]
        return "\n\n".join(parts)
    except Exception as e:
        log(f"SEO caption fail ({str(e)[:100]}) - simple caption")
    P = PAGES[kind]
    tags = " ".join("#" + re.sub(r"[\s#]+", "", t) for t in (j.get("hashtags") or [])[:6] if t)
    return f"🔴 {j['headline'].strip()}\n\n{j['summary'].strip()}\n\n{src}\n\nFollow {P['name']}\n\n{tags}"


def post_photo(kind, path, caption):
    P = PAGES[kind]
    if not P["token"] or not P["id"]:
        raise RuntimeError(f"{kind}: page token/id secret missing")
    with open(path, "rb") as f:
        r = requests.post(f"https://graph.facebook.com/{GRAPH_VER}/{P['id']}/photos", timeout=180,
                          data={"access_token": P["token"], "message": caption, "published": "true"},
                          files={"source": ("post.jpg", f, "image/jpeg")})
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"Facebook error: {j['error'].get('message', j)}")
    pid = j.get("post_id") or j.get("id")
    log(f"{kind}: posted {pid}")
    return pid


# ---------------------------------------------------------------- one post
class NoBreaking(Exception):
    pass


def breaking_pick(kind, past, avoid_links):
    """Woh khabar jo pichle ~3 ghante mein KAI alag sources par aa chuki ho (yani bari breaking) aur hum ne na di ho."""
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    done = sum(1 for p in past if p.get("breaking") and str(p.get("date", "")).startswith(today))
    if done >= BREAKING_PER_DAY:
        raise NoBreaking(f"aaj {done} breaking ho chuki")
    pool = NEWS_REGIONS if kind == "news" else SPORTS
    now = datetime.datetime.now(datetime.timezone.utc)
    allit = []
    for topic, urls in pool.items():
        for u in urls:
            for it in fetch_feed(u):
                age = (now - it["date"]).total_seconds() / 3600 if it["date"] else 99
                if -2 <= age <= 8:
                    it["topic"], it["age"], it["ws"] = topic, age, words(it["title"])
                    allit.append(it)
    best, best_n = None, 0
    for it in allit:
        if it["age"] > 3 or len(it["title"].split()) < 5 or it["link"] in avoid_links or seen(it, past):
            continue
        if re.search(r"\b(live|as it happened|quiz|in pictures|watch:|video:|podcast|newsletter|crossword|opinion)\b",
                     it["title"], re.I):
            continue
        ws = it["ws"]
        if len(ws) < 3:
            continue
        srcs = {o["source"] for o in allit
                if len(ws & o["ws"]) >= 3 and len(ws & o["ws"]) / max(1, min(len(ws), len(o["ws"]))) >= 0.5}
        n = len(srcs) + (0.5 if it["desc"] else 0)
        if n > best_n:
            best, best_n = it, n
    need = 3 if kind == "news" else 2
    if not best or best_n < need:
        raise NoBreaking(f"koi bari breaking nahi (sab se zyada {int(best_n)} sources)")
    log(f"BREAKING ({int(best_n)} sources): {best['title']}")
    return best["topic"], best


def make_post(kind, hist, avoid_links):
    past = hist[kind]
    pool = NEWS_REGIONS if kind == "news" else SPORTS
    if BREAKING:
        bt, bi = breaking_pick(kind, past, avoid_links)
    for topic in ([bt] if BREAKING else pick_topic(kind, past)[:6]):
        items = [bi] if BREAKING else [i for i in fresh_items(pool[topic], past) if i["link"] not in avoid_links]
        log(f"{kind}/{topic}: {len(items)} taaza khabrein")
        if not items:
            continue
        items = [i for i in items if len(i["desc"]) >= 60] or items     # tafseel wali khabar pehle
        item = random.choice(items[:4])
        log(f"Chuni: {item['title']} ({item['source']})")
        j = write_post(kind, topic, item)
        bg = os.path.join(WORK, f"{kind}_bg.jpg")
        q = [j.get("image_query")]
        if kind == "sports":
            q.append(SPORT_IMG.get(topic, "sports stadium"))
        else:
            q += ["world map globe", "city skyline night"]
        import footage
        if footage.real_photo(j.get("subject"), bg, None, min_w=800):      # khabar wale ki ASLI photo pehle
            log(f"asli photo: {j.get('subject')}")
        elif not pixabay_image(q, bg, hist["used_images"]):
            gradient_bg(bg, kind)
        out = os.path.join(WORK, f"{kind}_{LANG}.jpg")
        render_card(kind, bg, j.get("label"), j["card_title"], out)
        return out, caption_for(kind, j, item), item, topic
    raise RuntimeError("koi taaza khabar nahi mili")


def main():
    hist = load_history()
    ok = 0
    used_links = set()
    global CURRENT_PAGE
    for kind in PAGES_TO_RUN:
        CURRENT_PAGE = kind
        for attempt in range(2):
            try:
                path, caption, item, topic = make_post(kind, hist, used_links)
                log(f"--- {kind} caption ---\n{caption}\n")
                meta = {"date": REPORT["time_utc"], "lang": LANG, "topic": topic, "link": item["link"],
                        "title": item["title"][:160], "words": sorted(words(item["title"]))}
                if BREAKING:
                    meta["breaking"] = True
                if not DRY_RUN:
                    meta["post_id"] = post_photo(kind, path, caption)
                    log_post(kind, meta["post_id"], "breaking" if BREAKING else "pic", [topic], item["title"])
                hist[kind].append(meta)
                used_links.add(item["link"])
                REPORT["posted"][kind] = {"post": meta.get("post_id", "dry_run"), "topic": topic,
                                          "title": item["title"][:120]}
                ok += 1
                break
            except NoBreaking as e:
                log(f"{kind}: {e} - is dafa post nahi")
                ok += 1
                break
            except Exception as e:
                log(f"{kind} ERROR (try {attempt + 1}): {e}")
                if attempt == 1:
                    REPORT["errors"].append(f"{kind}: {str(e)[:300]}")
                time.sleep(10)
    save_history(hist)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=1, default=str)
    if ok < len(PAGES_TO_RUN):
        sys.exit(1)
    log("Done!")


if __name__ == "__main__":
    main()
