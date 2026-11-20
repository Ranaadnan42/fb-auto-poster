"""
Har agent ki SEEKH - apni ghaltiyon se (malik ka hukm: agent khud seekhe, ghalti dobara na kare).

Har page ki apni file learn_<page>.json:
  good     : footage ke woh alfaaz jin se asli, matching clip mili (aainda isi andaaz ke alfaaz)
  bad      : woh alfaaz jin se kabhi kuch na mila (aainda aisi baat/alfaaz nahi)
  mistakes : pichli videos ki ghaltiyan (kam footage, manager ke check mein aawaz-tasveer bemel)
Har script prompt mein text(page) jata hai, aur har run ke baad record() seekh likhta hai.
Manager (tools/match_audit.py -> match_audit.json) ne post ke baad jo bemel pakra, wo bhi yahin se har page
ke prompt mein jata hai.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
# bot ka naam -> page ka naam (match_audit.json / page_manager.json wala)
ALIAS = {"wildlife": "wild", "atlas": "frames", "world": "frames", "main": "islamic", "news_en": "news",
         "news_ur": "newsur", "match": "sports"}


def _page(page):
    return ALIAS.get(page, page)


def _file(page):
    return os.path.join(DIR, f"learn_{_page(page)}.json")


def load(page):
    try:
        with open(_file(page), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def record(page, ok_terms=(), fail_terms=(), mistake=None):
    """Run ke baad: kaun se alfaaz kaam aaye / na aaye, aur koi ghalti."""
    if not page:
        return
    L = load(page)
    g, b = L.setdefault("good", {}), L.setdefault("bad", {})
    for t in ok_terms:
        t = str(t or "").strip()
        if t and not t.startswith("#"):
            g[t] = g.get(t, 0) + 1
            b.pop(t, None)
    for t in fail_terms:
        t = str(t or "").strip()
        if t and not t.startswith("#") and t not in g:
            b[t] = b.get(t, 0) + 1
    for k in (g, b):                      # sirf taaza 300 - file halki
        for t in sorted(k, key=lambda x: k[x])[:max(0, len(k) - 300)]:
            k.pop(t)
    ms = L.setdefault("mistakes", [])
    if mistake and mistake not in ms:
        ms.append(mistake)
    L["mistakes"] = ms[-30:]
    try:
        with open(_file(page), "w", encoding="utf-8") as f:
            json.dump(L, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _audit(page):
    try:
        a = json.load(open(os.path.join(DIR, "match_audit.json"), encoding="utf-8")).get(_page(page)) or {}
        return a.get("lessons") or []
    except Exception:
        return []


def text(page):
    """Script prompt ke liye: pichli videos se seekhe hue sabaq."""
    if not page:
        return ""
    L = load(page)
    good = sorted((L.get("good") or {}).items(), key=lambda x: -x[1])[:25]
    bad = sorted((L.get("bad") or {}).items(), key=lambda x: -x[1])[:25]
    mistakes = (L.get("mistakes") or [])[-6:]
    audit = [m for m in _audit(page)[-6:] if m not in mistakes]
    if not (good or bad or mistakes or audit):
        return ""
    out = "\nLESSONS FROM OUR OWN PAST VIDEOS (the agent learns from its mistakes - never repeat one):"
    if good:
        out += ("\n- Footage search terms that FOUND real matching footage before (write 'visuals' in this style): "
                + "; ".join(t for t, _ in good))
    if bad:
        out += ("\n- Search terms that NEVER found real footage - don't use such terms, and don't write narration "
                "about things that can't be filmed: " + "; ".join(t for t, _ in bad))
    for m in mistakes:
        out += f"\n- Past mistake: {m}"
    for m in audit:
        out += f"\n- Manager's check of a posted video, picture did NOT match the voice: {m}"
    return out + "\n"
