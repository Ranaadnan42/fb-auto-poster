"""News Act -> News & media, Sports Hubs -> Sports: FB ki category list se sahi ID dhoond kar lagao."""
import json
import os
import requests

G = "https://graph.facebook.com/v23.0"
WANT = {"NEWS": ["news & media website", "media/news company", "news and media website", "newspaper"],
        "SPORTS": ["sports", "sports & recreation", "sports league", "sports media", "sports team"]}

for env, names in WANT.items():
    pid, tok = os.environ.get(f"{env}_PAGE_ID"), os.environ.get(f"{env}_PAGE_TOKEN")
    if not pid or not tok:
        continue
    cats = []
    for path in ("fb_page_categories", f"{pid}/fb_page_categories"):
        r = requests.get(f"{G}/{path}", params={"access_token": tok, "limit": 2000}, timeout=60).json()
        print(env, path, json.dumps(r)[:300])
        def walk(lst):
            for c in lst or []:
                cats.append((c.get("id"), (c.get("name") or "").lower()))
                walk(c.get("fb_page_categories"))
        walk(r.get("data"))
        if cats:
            break
    pick = [cid for want in names for cid, n in cats if n == want][:1]
    print(env, "matches:", [(i, n) for i, n in cats if any(w.split()[0] in n for w in names)][:15])
    if pick:
        r = requests.post(f"{G}/{pid}", data={"category_list": json.dumps(pick), "access_token": tok}, timeout=60)
        print(env, "set", pick, r.status_code, r.text[:300])
    r = requests.get(f"{G}/{pid}", params={"fields": "category,category_list", "access_token": tok}, timeout=60)
    print(env, "now:", r.text[:300])
