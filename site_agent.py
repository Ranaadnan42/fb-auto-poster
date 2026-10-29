"""
Website Agent - "BizTools Hub" blog ko rozana khud chalata hai (free, GitHub Actions par).

Har run:
  1. Keyword research: Google autocomplete se asli search phrases (US/UK/global English).
  2. AI (Groq, Gemini backup) se 1 lamba, kaam ka article - Google ki "helpful content" policy ke mutabiq:
     asli sawal ka jawab, FAQ, table, steps; spam/keyword stuffing nahi.
  3. Pexels se free photo (credit ke saath), 1200x630.
  4. Poori site dobara banti hai: home, categories, about/contact/privacy/terms/disclaimer,
     sitemap.xml, robots.txt, feed.xml, schema (Article + FAQ + Breadcrumb), canonical, OG tags,
     internal links (related guides).
  5. Health check (titles, meta, images, links) -> blog_report.json
  6. IndexNow ping (Bing/Yandex) - Google sitemap Search Console se parhta hai.

Backlinks: Google ki policy ke mutabiq khareedi/automatic spam links NAHI banata (site penalty lagti hai).
Sirf jaiz signals: sitemap, IndexNow, internal links, RSS feed.

ENV: GROQ_API_KEY, GEMINI_API_KEY (backup), PEXELS_API_KEY, SITE_URL (canonical domain), MODE=post|rebuild, DRY_RUN
"""
import datetime
import hashlib
import html
import io
import json
import os
import random
import re
import sys
import time
import urllib.parse

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "blog")
DATA = os.path.join(ROOT, "site_posts.json")
REPORT = os.path.join(ROOT, "blog_report.json")
LAST = os.path.join(ROOT, "site_last_run.json")

SITE_NAME = "BizTools Hub"
TAGLINE = "Practical tech guides for small businesses: POS systems, websites, apps & AI tools"
SITE_URL = (os.environ.get("SITE_URL") or "https://ranaadnan42.github.io/fb-auto-poster/blog").rstrip("/")
AUTHOR = "Muhammad Adnan"
AUTHOR_BIO = ("Muhammad Adnan is a software developer who builds point-of-sale (POS) systems, business "
              "websites and mobile apps for retail shops and restaurants. He writes these guides from "
              "hands-on experience setting up software for real small businesses.")
CONTACT_EMAIL = "ranaadnan320@gmail.com"
SERVICE_URL = "https://client-hunt-six.vercel.app/"
WHATSAPP = "+92 307 5267349"
INDEXNOW_KEY = "b7e4c1a9d2f84e6a9c3b5d7e1f2a4c6b"

# Topic clusters (high-value, English, worldwide). Har cluster ki apni category page banti hai.
CATEGORIES = {
    "pos-systems": ("POS Systems", ["best pos system for", "pos system for small", "how to choose a pos",
                                     "restaurant pos", "retail pos", "pos software", "inventory management for"]),
    "websites": ("Business Websites", ["how to make a website for", "small business website", "website cost for",
                                       "ecommerce website for", "seo for small business", "website builder for"]),
    "mobile-apps": ("Mobile Apps", ["how much does it cost to build an app", "app for small business",
                                    "ordering app for restaurant", "loyalty app for", "mobile app ideas for"]),
    "ai-tools": ("AI Tools for Business", ["ai tools for small business", "ai chatbot for", "how to use ai for",
                                           "ai for restaurant", "automate small business", "whatsapp chatbot for"]),
    "business-growth": ("Business Growth", ["how to increase sales in", "how to start a", "social media marketing for",
                                            "customer retention for", "how to manage inventory"]),
}

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
UA = {"User-Agent": "Mozilla/5.0 (compatible; BizToolsHubBot/1.0)"}


LOG_LINES = []


def log(*a):
    msg = " ".join(str(x) for x in a)
    LOG_LINES.append(msg[:300])
    print(msg, flush=True)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def slugify(s):
    s = re.sub(r"[^a-z0-9\s-]", "", (s or "").lower())
    s = re.sub(r"[\s-]+", "-", s).strip("-")
    return s[:70].strip("-") or "post"


def esc(s):
    return html.escape(s or "", quote=True)


# ----------------------------------------------------------------- AI brain
def ask_gemini(prompt, temp=0.7):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY nahi")
    last = None
    for model in ["gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": temp, "responseMimeType": "application/json",
                                           "maxOutputTokens": 16000}}, timeout=180)
            if r.status_code != 200:
                raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
            txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            log(f"Gemini model: {model}")
            return json.loads(txt)
        except Exception as e:
            last = e
            log(f"gemini {model} fail: {str(e)[:200]}")
    raise RuntimeError(f"Gemini fail: {last}")


def ask(prompt, temp=0.7):
    try:
        import groq_backup
        if groq_backup.enabled():
            return groq_backup.ask_json(prompt, temp=temp, log=log)
    except Exception as e:
        log(f"Groq fail, Gemini try: {str(e)[:200]}")
    return ask_gemini(prompt, temp)


# ----------------------------------------------------------- keyword research
def autocomplete(seed, country="US"):
    try:
        r = requests.get(SUGGEST_URL, params={"client": "firefox", "q": seed, "hl": "en", "gl": country},
                         headers=UA, timeout=8)
        return [s.strip() for s in (r.json()[1] if r.status_code == 200 else []) if s and s.strip()]
    except Exception as e:
        log(f"[autocomplete] '{seed}' fail: {str(e)[:100]}")
        return []


def similar(a, b):
    wa, wb = set(re.findall(r"[a-z0-9]+", a.lower())), set(re.findall(r"[a-z0-9]+", b.lower()))
    if not wa or not wb:
        return 0
    return len(wa & wb) / len(wa | wb)


def pick_category(posts):
    counts = {k: 0 for k in CATEGORIES}
    for p in posts:
        if p.get("category") in counts:
            counts[p["category"]] += 1
    # sab se kam posts wali category pehle - site balanced rahe (topical authority)
    low = min(counts.values())
    choices = [k for k, v in counts.items() if v == low]
    return random.choice(choices)


def research(posts, category):
    seeds = list(CATEGORIES[category][1])
    random.shuffle(seeds)
    cands = []
    for seed in seeds[:4]:
        for country in ("US", "GB"):
            cands += autocomplete(seed, country)
        # ek level aur gehra: "seed a/b/c..." long-tail
        for letter in random.sample("abcdefghilmnprstw", 3):
            cands += autocomplete(f"{seed} {letter}")
        time.sleep(0.5)
    used = [p["keyword"] for p in posts] + [p["title"] for p in posts]
    out, seen = [], set()
    for c in cands:
        cl = c.lower()
        if cl in seen or len(cl.split()) < 3:
            continue
        seen.add(cl)
        if any(similar(cl, u) > 0.6 for u in used):
            continue
        out.append(c)
    log(f"Keyword ideas ({category}): {len(out)}")
    return out[:60]


# -------------------------------------------------------------- article
ARTICLE_PROMPT = """You are an expert small-business technology writer for the website "{site}".
Author: {author} - a software developer who builds POS systems, websites and mobile apps for real shops and restaurants.

Category: {cat_name}
Real search phrases people type into Google right now (pick ONE as the main keyword - choose the one with
clear search intent, buying/learning value for US/UK/Canada/Australia readers, and that an honest expert article can fully answer):
{cands}

Already published (do NOT repeat these topics):
{done}

Write ONE genuinely helpful, original article that follows Google's helpful-content and spam policies:
- Answer the searcher's question directly in the first paragraph (no fluff intro).
- 1600-2200 words. Practical, specific, experience-based: real steps, real feature checklists, typical price ranges
  in USD stated as approximate ranges, mistakes to avoid, who should choose what. No fake statistics, no invented
  studies, no fake quotes, no made-up product reviews. If unsure, say "typically" / "around".
- Natural language; use the keyword in the title, first paragraph and one H2 only - never keyword stuffing.
- Structure with <h2> and <h3>; include at least one <ul> or <ol>, and one comparison <table> with <thead>/<tbody>.
- Allowed HTML tags only: h2, h3, p, ul, ol, li, strong, em, table, thead, tbody, tr, th, td, blockquote.
- Do not include <h1>, images, links, scripts or a FAQ section inside "body_html" (FAQ goes separately).
- Do not mention AI or that this was generated.

Return JSON:
{{
 "keyword": "the chosen main search phrase",
 "title": "SEO title, max 60 characters, compelling, includes keyword (year {year} allowed only if truly relevant)",
 "meta_description": "140-155 characters, includes keyword, makes people click",
 "slug": "short-url-slug-with-keyword",
 "excerpt": "1-2 sentence summary for cards",
 "key_takeaways": ["3-5 short bullet takeaways"],
 "body_html": "the full article HTML",
 "faq": [{{"q": "real follow-up question", "a": "2-4 sentence answer"}}, ... 4 to 6 items],
 "image_query": "2-4 word stock-photo search query showing the topic (e.g. 'cashier pos terminal')",
 "image_alt": "descriptive alt text for the cover photo",
 "tags": ["3-6 short tags"]
}}"""


ALLOWED = {"h2", "h3", "p", "ul", "ol", "li", "strong", "em", "table", "thead", "tbody", "tr", "th", "td",
           "blockquote", "br"}


def clean_html(body):
    body = re.sub(r"(?is)<(script|style|iframe).*?</\1>", "", body or "")

    def fix(m):
        closing, tag = m.group(1), m.group(2).lower()
        if tag == "h1":
            tag = "h2"
        if tag not in ALLOWED:
            return ""
        return f"<{closing}{tag}>"
    return re.sub(r"<\s*(/?)\s*([a-zA-Z0-9]+)[^>]*>", fix, body).strip()


def word_count(htmltext):
    return len(re.sub(r"<[^>]+>", " ", htmltext).split())


def add_ids(body):
    """H2 par id lagata hai - table of contents ke liye."""
    toc = []

    def rep(m):
        text = re.sub(r"<[^>]+>", "", m.group(1))
        hid = slugify(text)[:50]
        toc.append((hid, text))
        return f'<h2 id="{hid}">{m.group(1)}</h2>'
    return re.sub(r"(?is)<h2>(.*?)</h2>", rep, body), toc


def write_article(posts, category):
    cands = research(posts, category)
    if len(cands) < 5:
        cands += [s + " guide" for s in CATEGORIES[category][1]]
    done = "\n".join(f"- {p['title']}" for p in posts[-80:]) or "- (none yet)"
    prompt = ARTICLE_PROMPT.format(site=SITE_NAME, author=AUTHOR, cat_name=CATEGORIES[category][0],
                                   cands="\n".join(f"- {c}" for c in cands), done=done,
                                   year=datetime.date.today().year)
    last_err = None
    for attempt in range(3):
        try:
            a = ask(prompt, temp=0.7)
            a["body_html"] = clean_html(a.get("body_html", ""))
            wc = word_count(a["body_html"])
            log(f"Article try {attempt + 1}: '{a.get('title')}' - {wc} words")
            if wc < 1100:
                raise RuntimeError(f"bohat chhota article ({wc} words)")
            if not a.get("title") or not a.get("meta_description"):
                raise RuntimeError("title/meta missing")
            if any(similar(a["title"], p["title"]) > 0.6 for p in posts):
                raise RuntimeError("topic pehle se hai")
            return a
        except Exception as e:
            last_err = e
            log(f"article fail: {str(e)[:200]}")
            time.sleep(5)
    raise RuntimeError(f"Article nahi bana: {last_err}")


# ---------------------------------------------------------------- image
def fetch_image(query, slug):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    try:
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                         params={"query": query, "orientation": "landscape", "per_page": 15}, timeout=20)
        photos = r.json().get("photos", []) if r.status_code == 200 else []
        if not photos:
            r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                             params={"query": "small business technology", "orientation": "landscape",
                                     "per_page": 15}, timeout=20)
            photos = r.json().get("photos", [])
        if not photos:
            return None
        ph = random.choice(photos[:8])
        img = requests.get(ph["src"]["large2x"], timeout=60).content
        from PIL import Image
        im = Image.open(io.BytesIO(img)).convert("RGB")
        w, h = im.size
        tw, th = 1200, 630
        scale = max(tw / w, th / h)
        im = im.resize((int(w * scale) + 1, int(h * scale) + 1))
        w, h = im.size
        im = im.crop(((w - tw) // 2, (h - th) // 2, (w - tw) // 2 + tw, (h - th) // 2 + th))
        os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
        name = f"{slug}.jpg"
        im.save(os.path.join(OUT, "img", name), "JPEG", quality=80, optimize=True, progressive=True)
        return {"file": f"img/{name}", "credit": ph.get("photographer", "Pexels"),
                "credit_url": ph.get("url", "https://www.pexels.com")}
    except Exception as e:
        log(f"image fail: {str(e)[:200]}")
        return None


# ---------------------------------------------------------------- render
CSS = """:root{--bg:#ffffff;--fg:#1d2330;--muted:#5b6475;--line:#e6e9ef;--brand:#0b6e4f;--brand2:#e9f5f0;--card:#f7f9fb}
@media (prefers-color-scheme:dark){:root{--bg:#10141b;--fg:#e8ebf1;--muted:#a3abba;--line:#262d3a;--brand:#4cc79a;--brand2:#14251f;--card:#161b24}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.7 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif}
a{color:var(--brand)}img{max-width:100%;height:auto;display:block;border-radius:12px}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px}.narrow{max-width:760px}
header{border-bottom:1px solid var(--line)}header .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px;padding-top:14px;padding-bottom:14px;flex-wrap:wrap}
.logo{font-weight:800;font-size:20px;color:var(--fg);text-decoration:none}.logo span{color:var(--brand)}
nav a{color:var(--muted);text-decoration:none;margin-left:14px;font-size:15px}nav a:hover{color:var(--brand)}
.hero{padding:40px 0 24px}.hero h1{font-size:34px;line-height:1.2;margin:0 0 8px}.hero p{color:var(--muted);margin:0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:22px;padding:20px 0 40px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;text-decoration:none;color:var(--fg);display:flex;flex-direction:column}
.card img{border-radius:0;aspect-ratio:1200/630;object-fit:cover}.card div{padding:14px 16px 18px}
.card h3{margin:6px 0;font-size:19px;line-height:1.35}.card p{margin:0;color:var(--muted);font-size:15px}
.tag{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--brand);font-weight:700}
article h1{font-size:34px;line-height:1.2;margin:18px 0 10px}.meta{color:var(--muted);font-size:14px;margin-bottom:18px}
.crumbs{font-size:14px;color:var(--muted);margin-top:20px}.crumbs a{color:var(--muted)}
article h2{font-size:26px;margin-top:36px;line-height:1.3}article h3{font-size:20px;margin-top:26px}
table{width:100%;border-collapse:collapse;margin:18px 0;font-size:15px;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:9px 11px;text-align:left;vertical-align:top}th{background:var(--brand2)}
blockquote{border-left:4px solid var(--brand);margin:18px 0;padding:6px 16px;background:var(--card);border-radius:0 10px 10px 0}
.box{background:var(--brand2);border-radius:14px;padding:16px 20px;margin:22px 0}.box h2,.box h3{margin-top:4px}
.toc ol{margin:6px 0 0;padding-left:20px}.credit{font-size:12px;color:var(--muted);margin-top:6px}
.author{display:flex;gap:14px;align-items:flex-start;border-top:1px solid var(--line);margin-top:36px;padding-top:20px;font-size:15px;color:var(--muted)}
.avatar{flex:0 0 52px;height:52px;border-radius:50%;background:var(--brand);color:#fff;display:grid;place-items:center;font-weight:800;font-size:20px}
.cta{border:2px solid var(--brand);border-radius:14px;padding:18px 20px;margin:30px 0}.btn{display:inline-block;background:var(--brand);color:#fff;text-decoration:none;padding:10px 18px;border-radius:10px;font-weight:700}
.related a{display:block;padding:8px 0;border-bottom:1px solid var(--line);text-decoration:none}
footer{border-top:1px solid var(--line);margin-top:30px;padding:24px 0;color:var(--muted);font-size:14px}footer a{color:var(--muted);margin-right:14px}
@media (max-width:600px){.hero h1,article h1{font-size:27px}article h2{font-size:22px}nav a{margin:0 12px 0 0}}"""


def page(title, desc, path, body, rel="", head_extra="", og_image="", og_type="website"):
    """rel = root tak relative raasta ('' ya '../'). path = canonical ke liye site-relative URL."""
    canonical = f"{SITE_URL}/{path}"
    img = f"{SITE_URL}/{og_image}" if og_image else ""
    nav = "".join(f'<a href="{rel}category/{k}/">{esc(v[0])}</a>' for k, v in CATEGORIES.items())
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:site_name" content="{SITE_NAME}"><meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">{f'<meta property="og:image" content="{esc(img)}">' if img else ''}
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="application/rss+xml" title="{SITE_NAME}" href="{rel}feed.xml">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' fill='%230b6e4f'/%3E%3Ctext x='50' y='68' font-size='56' text-anchor='middle' fill='white' font-family='Arial' font-weight='bold'%3EB%3C/text%3E%3C/svg%3E">
<style>{CSS}</style>{head_extra}
</head><body>
<header><div class="wrap"><a class="logo" href="{rel or './'}">BizTools<span>Hub</span></a><nav>{nav}</nav></div></header>
{body}
<footer><div class="wrap"><p>&copy; {datetime.date.today().year} {SITE_NAME} &middot; {esc(TAGLINE)}</p>
<p><a href="{rel}about/">About</a><a href="{rel}contact/">Contact</a><a href="{rel}privacy-policy/">Privacy Policy</a><a href="{rel}terms/">Terms</a><a href="{rel}disclaimer/">Disclaimer</a><a href="{rel}feed.xml">RSS</a></p></div></footer>
</body></html>"""


def write_file(rel_path, content):
    full = os.path.join(OUT, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def card(p, rel):
    img = f'<img src="{rel}{p["image"]["file"]}" alt="{esc(p.get("image_alt"))}" loading="lazy" width="1200" height="630">' if p.get("image") else ""
    return (f'<a class="card" href="{rel}{p["slug"]}/">{img}<div><span class="tag">{esc(CATEGORIES[p["category"]][0])}</span>'
            f'<h3>{esc(p["title"])}</h3><p>{esc(p.get("excerpt"))}</p></div></a>')


def related(p, posts, n=5):
    others = [q for q in posts if q["slug"] != p["slug"]]
    scored = sorted(others, key=lambda q: (q["category"] == p["category"]) * 1 + similar(q["title"], p["title"]) * 2,
                    reverse=True)
    return scored[:n]


def render_post(p, posts):
    rel = "../"
    body, toc = add_ids(p["body_html"])
    date_pub = p["date"]
    date_mod = p.get("updated", p["date"])
    url = f"{SITE_URL}/{p['slug']}/"
    cat_name = CATEGORIES[p["category"]][0]
    ld = [{
        "@context": "https://schema.org", "@type": "Article", "headline": p["title"],
        "description": p["meta_description"], "datePublished": date_pub, "dateModified": date_mod,
        "author": {"@type": "Person", "name": AUTHOR, "url": f"{SITE_URL}/about/"},
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": f"{SITE_URL}/"},
        "mainEntityOfPage": url, "keywords": ", ".join(p.get("tags", [])),
        **({"image": f"{SITE_URL}/{p['image']['file']}"} if p.get("image") else {})},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": cat_name, "item": f"{SITE_URL}/category/{p['category']}/"},
            {"@type": "ListItem", "position": 3, "name": p["title"], "item": url}]}]
    faq = p.get("faq") or []
    if faq:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq]})
    head = "".join(f'\n<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)
    img = ""
    if p.get("image"):
        img = (f'<img src="{rel}{p["image"]["file"]}" alt="{esc(p.get("image_alt"))}" width="1200" height="630" fetchpriority="high">'
               f'<div class="credit">Photo: <a href="{esc(p["image"]["credit_url"])}" rel="nofollow noopener" target="_blank">{esc(p["image"]["credit"])}</a> on Pexels</div>')
    take = "".join(f"<li>{esc(t)}</li>" for t in p.get("key_takeaways", []))
    toc_html = "".join(f'<li><a href="#{h}">{esc(t)}</a></li>' for h, t in toc)
    faq_html = "".join(f"<h3>{esc(f['q'])}</h3><p>{esc(f['a'])}</p>" for f in faq)
    rel_html = "".join(f'<a href="{rel}{q["slug"]}/">{esc(q["title"])}</a>' for q in related(p, posts))
    d = datetime.date.fromisoformat(date_mod[:10]).strftime("%B %-d, %Y")
    html_body = f"""<main class="wrap narrow"><article>
<div class="crumbs"><a href="{rel}">Home</a> &rsaquo; <a href="{rel}category/{p['category']}/">{esc(cat_name)}</a></div>
<h1>{esc(p['title'])}</h1>
<div class="meta">By <a href="{rel}about/">{AUTHOR}</a> &middot; Updated {d} &middot; {max(1, p.get('words', 1500) // 230)} min read</div>
{img}
{f'<div class="box"><h3>Key takeaways</h3><ul>{take}</ul></div>' if take else ''}
{f'<div class="box toc"><strong>In this guide</strong><ol>{toc_html}</ol></div>' if len(toc) > 2 else ''}
{body}
{f'<h2 id="faq">Frequently asked questions</h2>{faq_html}' if faq_html else ''}
<div class="cta"><h3>Need a POS system, website or app for your business?</h3>
<p>I build affordable custom POS software, business websites and mobile apps for shops and restaurants worldwide.</p>
<a class="btn" href="{SERVICE_URL}" rel="noopener" target="_blank">Get a free quote</a></div>
<div class="author"><div class="avatar">MA</div><div><strong>{AUTHOR}</strong><br>{esc(AUTHOR_BIO)}</div></div>
{f'<h2>Related guides</h2><div class="related">{rel_html}</div>' if rel_html else ''}
</article></main>"""
    write_file(f"{p['slug']}/index.html",
               page(p["title"], p["meta_description"], f"{p['slug']}/", html_body, rel=rel, head_extra=head,
                    og_image=(p.get("image") or {}).get("file", ""), og_type="article"))


STATIC = {
    "about": ("About BizTools Hub", "Who writes BizTools Hub and why.",
              f"""<h1>About {SITE_NAME}</h1><p>{SITE_NAME} publishes practical, plain-English guides that help small business owners choose and use technology: point-of-sale (POS) systems, business websites, mobile apps, AI tools and growth tactics.</p>
<h2>Who writes these guides</h2><p>{esc(AUTHOR_BIO)}</p>
<h2>How we write</h2><p>Every guide aims to answer a real question business owners search for, with practical steps, checklists and honest trade-offs. We do not accept payment for rankings. Prices mentioned are typical ranges and can change, so always confirm with the vendor.</p>
<p>Questions or corrections? Email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>"""),
    "contact": ("Contact", "Contact BizTools Hub.",
                f"""<h1>Contact</h1><p>For questions, corrections or business enquiries:</p><ul><li>Email: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></li><li>WhatsApp: {WHATSAPP}</li><li>Software services: <a href="{SERVICE_URL}">{SERVICE_URL}</a></li></ul>"""),
    "privacy-policy": ("Privacy Policy", "Privacy policy for BizTools Hub.",
                       f"""<h1>Privacy Policy</h1><p>Last updated: {{date}}</p>
<p>{SITE_NAME} respects your privacy. This site does not require registration and does not collect personal information unless you contact us by email or WhatsApp.</p>
<h2>Cookies and advertising</h2><p>We may use third-party services such as Google Analytics and Google AdSense. Third-party vendors, including Google, use cookies to serve ads based on a user's prior visits to this website or other websites. Google's use of advertising cookies enables it and its partners to serve ads based on visits to this site and/or other sites on the Internet. You may opt out of personalised advertising by visiting <a href="https://www.google.com/settings/ads" rel="nofollow">Google Ads Settings</a> or <a href="https://www.aboutads.info" rel="nofollow">www.aboutads.info</a>.</p>
<h2>Log data</h2><p>Our hosting provider may log standard data such as IP address, browser type and pages visited for security and performance.</p>
<h2>Contact</h2><p>Questions: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>"""),
    "terms": ("Terms of Use", "Terms of use for BizTools Hub.",
              f"""<h1>Terms of Use</h1><p>Content on {SITE_NAME} is provided for general information only. You may share links to our articles; please do not republish full articles without permission. We are not responsible for decisions made based on this content, and we may update or remove content at any time.</p>"""),
    "disclaimer": ("Disclaimer", "Disclaimer for BizTools Hub.",
                   f"""<h1>Disclaimer</h1><p>The information on {SITE_NAME} is general guidance, not professional financial, legal or tax advice. Prices, features and availability of products change often, so verify details with the provider before buying. Some pages mention our own software services; we will always make that clear.</p>"""),
}


def render_site(posts):
    posts = sorted(posts, key=lambda p: p["date"], reverse=True)
    today = datetime.date.today().isoformat()
    for p in posts:
        render_post(p, posts)
    # home
    cards = "".join(card(p, "") for p in posts[:30])
    home = f"""<main class="wrap"><section class="hero"><h1>Tech guides that help small businesses grow</h1><p>{esc(TAGLINE)}.</p></section>
<div class="grid">{cards or '<p>First guide coming soon.</p>'}</div></main>"""
    ld = {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": f"{SITE_URL}/",
          "description": TAGLINE}
    write_file("index.html", page(f"{SITE_NAME} - Small Business Tech Guides", TAGLINE, "", home, rel="",
                                  head_extra=f'\n<script type="application/ld+json">{json.dumps(ld)}</script>'))
    # categories
    for k, (name, _) in CATEGORIES.items():
        items = [p for p in posts if p["category"] == k]
        body = (f'<main class="wrap"><section class="hero"><h1>{esc(name)}</h1><p>Practical {esc(name.lower())} guides for small business owners.</p></section>'
                f'<div class="grid">{"".join(card(p, "../../") for p in items) or "<p>Guides coming soon.</p>"}</div></main>')
        write_file(f"category/{k}/index.html",
                   page(f"{name} Guides for Small Business | {SITE_NAME}",
                        f"Practical {name.lower()} guides, checklists and comparisons for small business owners.",
                        f"category/{k}/", body, rel="../../"))
    for k, (title, desc, content) in STATIC.items():
        write_file(f"{k}/index.html", page(f"{title} | {SITE_NAME}", desc, f"{k}/",
                                           f'<main class="wrap narrow"><article>{content.replace("{date}", today)}</article></main>',
                                           rel="../"))
    # sitemap
    urls = [(f"{SITE_URL}/", today)] + [(f"{SITE_URL}/{p['slug']}/", p.get("updated", p["date"])[:10]) for p in posts]
    urls += [(f"{SITE_URL}/category/{k}/", today) for k in CATEGORIES] + [(f"{SITE_URL}/{k}/", today) for k in STATIC]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sm += "".join(f"<url><loc>{esc(u)}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls) + "</urlset>\n"
    write_file("sitemap.xml", sm)
    write_file("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n")
    # RSS
    items = "".join(
        f"<item><title>{esc(p['title'])}</title><link>{SITE_URL}/{p['slug']}/</link><guid>{SITE_URL}/{p['slug']}/</guid>"
        f"<pubDate>{datetime.datetime.fromisoformat(p['date'][:10]).strftime('%a, %d %b %Y 08:00:00 +0000')}</pubDate>"
        f"<description>{esc(p.get('excerpt'))}</description></item>" for p in posts[:30])
    write_file("feed.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{SITE_NAME}</title>'
                           f"<link>{SITE_URL}/</link><description>{esc(TAGLINE)}</description>{items}</channel></rss>\n")
    write_file(f"{INDEXNOW_KEY}.txt", INDEXNOW_KEY)
    # vercel: sirf blog folder badle to deploy ho (baqi bots ke commits par nahi)
    save_json(os.path.join(OUT, "vercel.json"),
              {"ignoreCommand": "git diff --quiet HEAD^ HEAD -- .", "cleanUrls": False, "trailingSlash": True})
    write_file("404.html", page(f"Page not found | {SITE_NAME}", "Page not found.", "404.html",
                                f'<main class="wrap narrow"><h1>Page not found</h1><p><a href="{SITE_URL}/">Go to the homepage</a></p></main>',
                                rel=f"{SITE_URL}/"))


# --------------------------------------------------------------- health check
def health(posts):
    issues = []
    slugs = {p["slug"] for p in posts}
    for p in posts:
        if len(p["title"]) > 65:
            issues.append(f"{p['slug']}: title lamba ({len(p['title'])})")
        if not 110 <= len(p["meta_description"]) <= 165:
            issues.append(f"{p['slug']}: meta description length {len(p['meta_description'])}")
        if not p.get("image"):
            issues.append(f"{p['slug']}: image nahi")
        elif not os.path.exists(os.path.join(OUT, p["image"]["file"])):
            issues.append(f"{p['slug']}: image file gum")
        if not os.path.exists(os.path.join(OUT, p["slug"], "index.html")):
            issues.append(f"{p['slug']}: page nahi bana")
    if len(slugs) != len(posts):
        issues.append("duplicate slugs")
    rep = {"checked": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "posts": len(posts),
           "issues": issues}
    save_json(REPORT, rep)
    log(f"Health: {len(posts)} posts, {len(issues)} issues")
    for i in issues:
        log("  -", i)
    return issues


def fix_meta(p):
    """Choti SEO ghaltiyan khud theek: title/meta length."""
    if len(p["title"]) > 65:
        p["title"] = p["title"][:62].rsplit(" ", 1)[0].rstrip(":,-") + ""
    m = p["meta_description"]
    if len(m) > 160:
        p["meta_description"] = m[:155].rsplit(" ", 1)[0].rstrip(",.;") + "."
    return p


def indexnow(urls):
    host = urllib.parse.urlparse(SITE_URL).netloc
    if not urls or host.endswith("github.io"):
        log("IndexNow skip (github.io par key root par nahi rakh sakte) - custom/vercel domain par chalega")
        return
    try:
        r = requests.post("https://api.indexnow.org/indexnow", json={
            "host": host, "key": INDEXNOW_KEY, "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt", "urlList": urls},
            timeout=20)
        log(f"IndexNow: {r.status_code}")
    except Exception as e:
        log(f"IndexNow fail: {str(e)[:150]}")


# --------------------------------------------------------------------- main
def main():
    mode = os.environ.get("MODE", "post")
    dry = os.environ.get("DRY_RUN") == "1"
    posts = load_json(DATA, [])
    today = datetime.date.today().isoformat()
    new_urls = []
    if mode == "post":
        if any(p["date"][:10] == today for p in posts) and not os.environ.get("FORCE"):
            log("Aaj ka article pehle hi publish ho chuka - sirf site rebuild.")
        else:
            cat = pick_category(posts)
            log(f"Category: {cat}")
            a = write_article(posts, cat)
            slug = slugify(a.get("slug") or a["title"])
            if slug in {p["slug"] for p in posts}:
                slug = f"{slug}-{hashlib.md5(a['title'].encode()).hexdigest()[:4]}"
            img = fetch_image(a.get("image_query") or a["keyword"], slug)
            p = {"slug": slug, "category": cat, "date": today, "updated": today, "keyword": a.get("keyword", ""),
                 "title": a["title"], "meta_description": a["meta_description"], "excerpt": a.get("excerpt", ""),
                 "key_takeaways": a.get("key_takeaways", [])[:6], "body_html": a["body_html"],
                 "faq": [f for f in a.get("faq", []) if f.get("q") and f.get("a")][:8],
                 "tags": a.get("tags", [])[:8], "image": img, "image_alt": a.get("image_alt") or a["title"],
                 "words": word_count(a["body_html"])}
            posts.append(fix_meta(p))
            new_urls = [f"{SITE_URL}/{slug}/", f"{SITE_URL}/", f"{SITE_URL}/category/{cat}/"]
            log(f"NEW: {p['title']} -> {SITE_URL}/{slug}/")
    posts = [fix_meta(p) for p in posts]
    render_site(posts)
    health(posts)
    if not dry:
        save_json(DATA, posts)
        indexnow(new_urls)
    save_json(LAST, {"time": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "mode": mode,
                     "posts": len(posts), "new": new_urls[:1], "log": LOG_LINES[-40:]})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        log(f"FAILED: {e}")
        log(traceback.format_exc()[-1500:])
        save_json(LAST, {"time": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                         "failed": str(e)[:500], "log": LOG_LINES[-60:]})
        sys.exit(1)
