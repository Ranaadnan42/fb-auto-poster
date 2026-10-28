"""
Demo websites ke liye har business qisam ki achhi HD tasveerain (Pixabay, free license) ek dafa download
kar ke repo mein rakhta hai: demo_img/<category>/1..6.jpg  -> jsDelivr CDN se demo site par lagti hain.
Env: PIXABAY_API_KEY
"""
import os
import json
import random
import requests

KEY = os.environ["PIXABAY_API_KEY"]
CATS = {
    "restaurant": ["restaurant interior", "gourmet food plate", "restaurant dining", "chef cooking", "grilled food", "fine dining"],
    "cafe": ["coffee shop", "latte art", "cafe interior", "coffee beans", "pastry coffee", "barista"],
    "bakery": ["bakery bread", "cakes bakery", "croissant", "cupcakes", "bakery shop", "pastries"],
    "grocery": ["supermarket", "fresh vegetables market", "grocery store", "fruits market", "supermarket shelves", "grocery basket"],
    "pharmacy": ["pharmacy", "medicine pharmacy", "pharmacist", "pills medicine", "pharmacy shelves", "health care"],
    "clinic": ["medical clinic", "doctor stethoscope", "dentist clinic", "hospital modern", "medical team", "healthcare"],
    "salon": ["hair salon", "barber shop", "beauty spa", "manicure", "salon interior", "spa massage stones"],
    "gym": ["gym fitness", "dumbbells", "fitness training", "gym equipment", "workout", "treadmill"],
    "fashion": ["clothing store", "fashion boutique", "clothes rack", "shoes store", "fashion shopping", "tailor fabric"],
    "electronics": ["smartphone store", "electronics shop", "mobile phones", "laptop computer", "headphones", "phone repair"],
    "realestate": ["modern house", "luxury villa", "apartment building", "real estate interior", "living room modern", "city skyline"],
    "auto": ["car workshop", "car repair mechanic", "luxury car", "car service", "tyres", "car showroom"],
    "education": ["school classroom", "students learning", "books library", "education", "university campus", "online learning"],
    "hotel": ["hotel room", "hotel lobby", "resort pool", "hotel bedroom luxury", "hotel reception", "resort"],
    "travel": ["travel destination", "airplane travel", "beach resort", "mountains travel", "desert dubai", "luggage travel"],
    "construction": ["construction site", "architecture building", "hardware tools", "interior renovation", "engineer construction", "modern architecture"],
    "jewellery": ["jewelry gold", "diamond ring", "gold necklace", "jewelry store", "luxury watch", "jewellery"],
    "furniture": ["modern furniture", "sofa interior", "furniture store", "bedroom interior", "wooden furniture", "dining table interior"],
    "business": ["modern office", "business meeting", "office workspace", "laptop desk", "teamwork office", "city business"],
}
BLOCK = {"woman", "women", "girl", "lady", "female", "model", "sexy", "bikini", "lingerie", "kiss", "couple",
         "wine", "beer", "alcohol", "cocktail", "bar", "pork", "christmas", "halloween", "church", "cross"}

FIX = {
    "auto": ["car mechanic", "car repair", "car engine", "auto repair", "car wash", "luxury car"],
    "clinic": ["doctor", "dentist", "medical clinic", "hospital", "stethoscope", "medical"],
    "construction": ["construction site", "crane construction", "architecture", "building construction", "excavator", "engineer"],
    "education": ["classroom", "library", "school books", "graduation", "university", "students"],
    "electronics": ["smartphone", "laptop", "electronics", "headphones", "smartwatch", "tablet"],
    "gym": ["gym", "dumbbells", "fitness", "weightlifting", "treadmill", "workout"],
    "jewellery": ["gold jewelry", "diamond ring", "necklace", "jewelry", "gold rings", "bracelet"],
    "pharmacy": ["pharmacy", "medicine", "pills", "pharmacist", "drugstore", "vitamins"],
    "salon": ["hair salon", "barber", "hairdresser", "spa", "nail salon", "makeup brushes"],
}
ONLY = [c for c in (os.environ.get("ONLY") or "").split(",") if c]
if ONLY:
    CATS = {c: FIX.get(c, CATS[c]) for c in ONLY}
try:
    manifest = json.load(open("demo_img/manifest.json"))
except Exception:
    manifest = {}
used = set()
for cat, queries in CATS.items():
    os.makedirs(f"demo_img/{cat}", exist_ok=True)
    n = 0
    for q in queries:
        if n >= 6:
            break
        try:
            r = requests.get("https://pixabay.com/api/", timeout=40, params={
                "key": KEY, "q": q, "image_type": "photo", "orientation": "horizontal", "safesearch": "true",
                "per_page": 40, "min_width": 1600, "order": "popular", "editors_choice": "false"})
            hits = r.json().get("hits", [])
        except Exception as e:
            print("err", q, e); continue
        qw = [w for w in q.lower().split() if len(w) > 2]
        def ok(h):
            words = set(h.get("tags", "").replace(",", " ").lower().split())
            return h["id"] not in used and not (words & BLOCK) and any(w in words or w.rstrip("s") in words for w in qw)
        hits = [h for h in hits if ok(h)]
        for h in hits[:3]:
            url = h.get("largeImageURL")
            try:
                data = requests.get(url, timeout=90).content
            except Exception:
                continue
            if len(data) < 60000:
                continue
            n += 1
            used.add(h["id"])
            with open(f"demo_img/{cat}/{n}.jpg", "wb") as f:
                f.write(data)
            break
    manifest[cat] = n
    print(cat, n)
json.dump(manifest, open("demo_img/manifest.json", "w"), indent=1)
