"""Comment Helper ka search hissa (GitHub Actions par chalta hai, koi secret nahi chahiye).
Facebook ke public posts/group posts dhoondta hai jahan log POS / website / app / social media / video automation
ka poochh rahe hon, aur comment_hits.json mein likhta hai. Supabase ka `comment-helper` function ye file parh kar
AI se comment likhwata hai aur Rana ko email karta hai. Bot khud Facebook par kuch post NAHI karta."""
import json, re, time, datetime as dt
from ddgs import DDGS

OUT = "comment_hits.json"
QUERIES = [
    'site:facebook.com "POS software" chahiye',
    'site:facebook.com "billing software" chahiye dukan',
    'site:facebook.com "software chahiye" shop',
    'site:facebook.com/groups "POS" recommend shop Pakistan',
    'site:facebook.com "POS system" recommend restaurant',
    'site:facebook.com "looking for POS" shop',
    'site:facebook.com "inventory software" recommend small business',
    'site:facebook.com "need a website" for my business',
    'site:facebook.com "website banwani" hai',
    'site:facebook.com "app banwani" hai',
    'site:facebook.com "looking for web developer" small business',
    'site:facebook.com "need a social media manager"',
    'site:facebook.com "faceless youtube" automation help',
    'site:facebook.com "برنامج كاشير" افضل',
    'site:facebook.com "برنامج محاسبي" محل',
    'site:facebook.com "نظام نقاط البيع" مطعم',
    'site:facebook.com "ابي موقع" لمحلي',
]
POST_URL = re.compile(r"facebook\.com/(groups/|.*/posts/|.*/permalink|permalink\.php|story\.php|.*/videos/|reel/|share/p/|photo|.*/photos/)", re.I)


def clean(url):
    url = url.strip()
    if "story.php" in url or "permalink.php" in url:
        return url
    return url.split("?")[0].rstrip("/")


def main():
    try:
        old = json.load(open(OUT)).get("hits", [])
    except Exception:
        old = []
    seen = {h["url"] for h in old}
    new, stats = [], {}
    with DDGS() as d:
        for q in QUERIES:
            got = []
            for tl in ("m", None):          # pehle pichhla mahina; kuch na mile to bina time limit
                try:
                    got = d.text(q, timelimit=tl, max_results=15) or []
                except Exception as e:
                    stats[q] = f"err {str(e)[:60]}"
                if got:
                    break
            n = 0
            for r in got:
                url = clean(r.get("href") or "")
                if not POST_URL.search(url) or url in seen:
                    continue
                seen.add(url)
                n += 1
                new.append({"url": url, "title": (r.get("title") or "")[:200], "snippet": (r.get("body") or "")[:500],
                            "found": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ")})
            stats.setdefault(q, n)
            time.sleep(2)
    hits = (new + old)[:300]
    json.dump({"updated": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "new": len(new), "stats": stats, "hits": hits},
              open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"new {len(new)} total {len(hits)}")
    for q, s in stats.items():
        print(s, "|", q)


if __name__ == "__main__":
    main()
