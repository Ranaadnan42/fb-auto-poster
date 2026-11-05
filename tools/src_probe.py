"""Naye video platforms check: kaun runner se chalta hai aur unka HTML/JSON kaisa hai."""
import re, json, requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
T = [("mixkit", "https://mixkit.co/free-stock-video/lisbon/"),
     ("mixkit2", "https://mixkit.co/free-stock-video/mosque/"),
     ("europeana", "https://api.europeana.eu/record/v2/search.json?wskey=api2demo&query=lisbon&qf=TYPE:VIDEO&reusability=open&media=true&rows=5&profile=rich"),
     ("videvo", "https://www.videvo.net/search/?q=lisbon"),
     ("coverr", "https://api.coverr.co/videos?query=lisbon"),
     ("loc", "https://www.loc.gov/search/?q=lisbon&fa=original-format:film,+video&fo=json&c=5"),
     ("lifeofvids", "https://www.lifeofvids.com/?s=city"),
     ("mazwai", "https://mazwai.com/stock-video-footage/city"),
     ("dareful", "https://dareful.com/?s=city"),
     ("vidsplay", "https://www.vidsplay.com/?s=city"),
     ("ytdlp", None)]
for name, u in T:
    if not u:
        continue
    try:
        r = requests.get(u, headers=UA, timeout=30)
        body = r.text
        mp4 = list(dict.fromkeys(re.findall(r'https?://[^"\'\s<>]+?\.mp4', body)))[:6]
        print(f"== {name} {r.status_code} len={len(body)}")
        print("  mp4:", mp4)
        if "json" in r.headers.get("content-type", ""):
            print("  json:", body[:1500])
        else:
            i = body.find(".mp4")
            print("  ctx:", re.sub(r"\s+", " ", body[max(0, i - 1200):i + 300]) if i > 0 else body[:400].replace("\n", " "))
    except Exception as e:
        print(f"== {name} ERR {str(e)[:150]}")
