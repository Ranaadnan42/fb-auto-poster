"""Style by Faizi - cover ke liye dress tasveerein (free sdxl-turbo, koi key nahi)."""
import os, sys
os.environ.setdefault("FREE_IMAGE_MODEL", "stabilityai/sdxl-turbo")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import free_images
OUT = "docs/brand/faizi_dresses"; os.makedirs(OUT, exist_ok=True)
LOOK = ("professional fashion catalogue photo, full length dress displayed on a headless dress form mannequin, "
        "no face, no person, studio lighting, soft pastel background, ultra detailed fabric and embroidery, 4k")
P = [
 "red and gold bridal lehenga with heavy zari embroidery and net dupatta",
 "pastel mint green long anarkali frock with silver gota work",
 "royal blue velvet sharara suit with golden tilla embroidery",
 "peach organza angrakha style kurta with pearl work",
 "emerald green and pink party wear gharara with mirror work",
 "white chikankari embroidered long kurti with palazzo, summer lawn",
 "maroon and gold peshwas with intricate dabka embroidery",
 "lilac printed lawn three piece suit with embroidered neckline",
]
for i, p in enumerate(P):
    for s in range(3):
        if free_images.generate(p, 7000 + i * 10 + s, f"{OUT}/d{i}.jpg", 768, 1024, LOOK):
            print("ok", i, flush=True); break
