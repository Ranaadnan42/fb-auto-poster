import sys, requests
sys.path.insert(0, ".")
import footage, world
r = requests.get("https://mixkit.co/free-stock-video/lisbon-tram/", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}, timeout=30)
print("status lisbon-tram", r.status_code, r.url)
for q in ["lisbon", "lisbon tram", "mosque", "pasteis de nata", "desert camel", "kaaba"]:
    a = footage.mixkit(q); b = world.mixkit_search(q)
    print(q, len(a), len(b), [c["text"][:40] for c in a[:4]], a[0]["url"] if a else "", a[0]["dur"] if a else "")
