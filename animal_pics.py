"""PIC agent - Birds of the World / Dogs & Cats World / Wild Nations.

Rozana 2 ultra-HD asli tasveerein (har run 1) + wohi tasveer page STORY par.
  - Har tasveer AI agent dekhta hai: sahi nasal/parinda/janwar, asli photo, koi pinjra/cage/kennel/zoo jaali nahi
  - Sirf 1900px+ (ultra HD) tasveer, warna agli
  - Koi tasveer / subject dobara nahi (history)
Env: AGENT=birds|pets|wild (+ us page ke apne secrets), POST_AT, DRY_RUN
"""
import json
import os
import random
import sys

os.environ["MODE"] = "pic"
AGENT = (os.environ.get("AGENT") or "birds").strip().lower()
MOD = {"birds": "birds", "pets": "pets", "wild": "wildlife"}[AGENT]
m = __import__(MOD)
import footage            # noqa: E402
import footage_agent as fa  # noqa: E402
import news               # noqa: E402
import requests           # noqa: E402

GRAPH = "https://graph.facebook.com/v23.0"
DRY_RUN = os.environ.get("DRY_RUN") == "1"
REPORT_FILE = f"{AGENT}_pic_last_run.json"
REPORT = {"mode": "pic", "agent": AGENT, "dry_run": DRY_RUN, "log": [], "errors": []}
OUT = f"final_{AGENT}_pic.jpg"
NOUN = {"birds": "bird", "pets": "", "wild": "animal"}[AGENT]


def log(s):
    print(s, flush=True)
    REPORT["log"].append(str(s)[:300])


def subjects(h):
    if AGENT == "birds":
        base = list(m.STAR_BIRDS) + [x.get("bird") for x in h["reel"]]
    elif AGENT == "pets":
        base = list(m.DOGS) + list(m.CATS) + [x.get("breed") for x in h["reel"]]
    else:
        base = [a for lst in (h.get("animals") or {}).values() for a in (lst or [])] + \
               [x.get("animal") for x in h["reel"]]
        if len(base) < 6:                              # history khali - mojooda mulk ke janwar
            try:
                base += list(m.animals_of(h, m.COUNTRIES[h["country_i"] % len(m.COUNTRIES)]))
            except Exception as e:
                log(f"animals_of fail: {str(e)[:100]}")
    out = []
    for s in base:
        if isinstance(s, str) and s.strip() and s not in out:
            out.append(s.strip())
    return out


def find_photo(subj, used, job):
    said = f"A beautiful ultra HD photo of a {subj} {NOUN}".strip()
    cands, seen = [], set()
    for q in [subj, f"{subj} {NOUN}".strip(), f"{subj} nature", f"{subj} portrait"]:
        for c in footage.photos(q):
            if c["id"] in used or c["id"] in seen or c.get("src") == "pixabay" or c.get("w", 9999) < 1900:   # pixabay sirf 1280px deta
                continue
            seen.add(c["id"])
            c["score"] = footage.match_score(c.get("text", ""), footage.words(subj))
            if c["score"] > 0:
                cands.append(c)
    cands.sort(key=lambda c: -c["score"])
    from PIL import Image
    for i, c in enumerate(cands[:16]):
        jp = os.path.join(job, f"p{i}.jpg")
        try:
            if not footage.download(c["url"], jp, 150000):
                continue
            wd, ht = Image.open(jp).size
            used.append(c["id"])
            if max(wd, ht) < 1900:                   # sirf ultra HD
                log(f"chhoti {c['src']} {c['id']} {wd}x{ht}")
                continue
            small = os.path.join(job, f"p{i}_s.jpg")
            Image.open(jp).convert("RGB").resize((768, int(768 * ht / wd))).save(small, quality=88)
            v = fa.check([small], subj, said + ". It must be free in nature or a home/garden - NO cage, "
                         "bars, wire mesh, kennel, crate, pet-shop or zoo enclosure anywhere.", AGENT)
            log(f"photo {c['src']} {c['id']} {wd}x{ht}: agent={v}")
            if v is True:
                return {**c, "path": jp, "w": wd, "h": ht}
        except Exception as e:
            log(f"photo fail {c.get('id')}: {str(e)[:100]}")
    return None


def caption(subj):
    import seo
    try:
        facts = m.wiki_text(subj, 900)
    except Exception:
        facts = ""
    try:
        return seo.build(news.ask_json, AGENT, subj, facts or subj, "en", is_reel=False)
    except Exception as e:
        log(f"seo fallback: {str(e)[:100]}")
        return f"{subj} 😍\n\nWhich one is your favourite? Comment below 👇\n\n#{subj.replace(' ', '')} #nature #wildlife"


def post_photo(P, path, cap):
    def fb(r):
        j = r.json()
        if "error" in j:
            raise RuntimeError(j["error"].get("message"))
        return j
    with open(path, "rb") as f:
        j = fb(requests.post(f"{GRAPH}/{P['id']}/photos", timeout=300, files={"source": f},
                             data={"caption": __import__("seo").with_usa(cap), "access_token": P["token"]}))
    try:                                        # wohi tasveer page story par bhi
        try:
            with open(path, "rb") as f:
                pid = fb(requests.post(f"{GRAPH}/{P['id']}/photos", timeout=300, files={"source": f},
                                       data={"published": "false", "temporary": "true",
                                             "access_token": P["token"]}))["id"]
        except Exception:
            pid = j["id"]
        fb(requests.post(f"{GRAPH}/{P['id']}/photo_stories", timeout=60,
                         data={"photo_id": pid, "access_token": P["token"]}))
        log("photo story lagi")
    except Exception as e:
        log(f"photo story skip: {str(e)[:100]}")
    return j.get("post_id") or j.get("id")


def main():
    P = m.page()
    if not DRY_RUN and not (P["id"] and P["token"]):
        REPORT["waiting"] = "page secrets missing"
        log("page secrets abhi nahi")
        return
    h = m.load_hist()
    h.setdefault("pic", [])
    h.setdefault("pic_used", [])
    done = {x.get("subject") for x in h["pic"]}
    todo = [s for s in subjects(h) if s not in done] or subjects(h)
    job = f"work_{AGENT}_pic"
    os.makedirs(job, exist_ok=True)
    for subj in todo[:6]:
        log(f"Subject: {subj}")
        got = find_photo(subj, h["pic_used"], job)
        if got:
            break
    else:
        raise RuntimeError("koi saaf ultra-HD tasveer nahi mili")
    from PIL import Image
    Image.open(got["path"]).convert("RGB").save(OUT, quality=95)
    cap = caption(subj)
    log(f"--- caption ---\n{cap}")
    meta = {"subject": subj, "photo": got["id"], "src": got["src"], "size": f"{got['w']}x{got['h']}",
            "date": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d %H:%M")}
    if not DRY_RUN:
        import slot_wait
        slot_wait.wait(log)
        meta["post_id"] = post_photo(P, OUT, cap)
        log(f"posted {meta['post_id']}")
    h["pic"].append(meta)
    h["pic_used"] = h["pic_used"][-2000:]
    m.save_hist(h)
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
