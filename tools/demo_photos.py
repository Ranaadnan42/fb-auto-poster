"""Har demo website ke liye USI business se milti photos (Pixabay).

make-demo (Supabase) se poochta hai kin demos ko photos chahiye -> har demo ki 3 search lines (jaise
"coffee roasting beans", "barista latte art") Pixabay par dhoondta hai -> achhi horizontal photos ke link
make-demo ko bhejta hai, jo unhein Supabase Storage mein save karke demo mein laga deta hai.
Koi file repo mein commit nahi hoti. Secret: PIXABAY_API_KEY.
"""
import os
import sys

import requests

API = "https://fobzocsluzwcqretshnm.supabase.co/functions/v1/make-demo"
KEY = os.environ.get("PIXABAY_API_KEY", "")


def search(q, seen, want=4):
    try:
        r = requests.get("https://pixabay.com/api/", timeout=30, params={
            "key": KEY, "q": q[:90], "image_type": "photo", "orientation": "horizontal",
            "safesearch": "true", "per_page": 20, "min_width": 1600, "order": "popular"})
        r.raise_for_status()
        hits = r.json().get("hits", [])
    except Exception as e:
        print(f"  pixabay error ({q}): {str(e)[:120]}")
        return []
    out = []
    for h in hits:
        u = h.get("largeImageURL")
        if not u or h["id"] in seen:
            continue
        seen.add(h["id"])
        out.append(u)
        if len(out) >= want:
            break
    return out


def main():
    if not KEY:
        sys.exit("PIXABAY_API_KEY missing")
    for rnd in range(4):          # ek run mein ~24 demos tak
        demos = requests.get(API, params={"pending": "1"}, timeout=60).json().get("demos", [])
        if not demos:
            print("Sab demos ki photos lag chuki hain.")
            return
        for d in demos:
            seen, urls = set(), []
            want = max(3, -(-9 // max(1, len(d["queries"]))))   # kul ~9 photos
            for q in d["queries"]:
                urls += search(q, seen, want)
            if len(urls) < 3:          # bohat khaas lafz par kuch na mile to aam lafz
                for q in d["queries"]:
                    urls += search(" ".join(q.split()[:2]), seen)
            res = requests.post(API, json={"action": "imgs", "id": d["id"], "urls": urls[:9]}, timeout=180).json()
            print(d["id"], d["queries"], "->", res)


if __name__ == "__main__":
    main()
