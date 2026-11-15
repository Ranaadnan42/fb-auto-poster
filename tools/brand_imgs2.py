"""Birds aur Pets pages - cover/logo ke liye tasveerein (free sdxl-turbo, koi key nahi)."""
import os, sys
os.environ.setdefault("FREE_IMAGE_MODEL", "stabilityai/sdxl-turbo")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import free_images
SETS = {
 "birds": ("wildlife photography, national geographic style, sharp focus, vivid natural colors, bokeh nature background, 4k", [
   "scarlet macaw parrot perched on a branch in rainforest",
   "male peacock displaying full colorful tail feathers",
   "rainbow lorikeet bird on a flowering branch",
   "hummingbird hovering next to a red tropical flower",
   "keel-billed toucan on a mossy branch in the jungle",
   "kingfisher bird with blue and orange feathers on a twig over water",
   "pink flamingo standing in a shallow lake at golden hour",
   "golden pheasant with bright red and gold plumage",
 ]),
 "pets": ("professional pet photography, cute, sharp focus, soft warm studio light, pastel background, 4k", [
   "golden retriever puppy smiling with tongue out",
   "fluffy white persian kitten with big eyes",
   "corgi dog sitting happily",
   "orange tabby cat lying playfully",
   "husky puppy with blue eyes",
   "british shorthair grey cat portrait",
   "french bulldog puppy wearing a small bow",
   "ragdoll kitten playing with a ball of yarn",
 ]),
}
for name, (look, prompts) in SETS.items():
    out = f"docs/brand/{name}"; os.makedirs(out, exist_ok=True)
    for i, p in enumerate(prompts):
        for s in range(3):
            if free_images.generate(p, 9100 + i * 10 + s, f"{out}/p{i}.jpg", 768, 1024, look):
                print("ok", name, i, flush=True); break
