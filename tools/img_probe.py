"""Test: kaun sa free AI image model is key se tasveer bana sakta hai (Legends ke liye behtar tasveerein)."""
import os
import time
from google import genai
from google.genai import types

key = os.environ.get("GEMINI_KEY_LEGENDS") or os.environ.get("GEMINI_API_KEY")
c = genai.Client(api_key=key)
names = []
for m in c.models.list():
    n = m.name.split("/")[-1]
    acts = getattr(m, "supported_actions", None) or []
    if "image" in n.lower() or "imagen" in n.lower():
        names.append(n)
        print("MODEL", n, acts)
os.makedirs("probe_out", exist_ok=True)
PROMPT = ("Vertical 9:16 epic dark fantasy painting: Typhon, a giant monster with many serpent heads and glowing "
          "eyes, fighting Zeus with a lightning bolt on a stormy sea cliff, cinematic lighting, highly detailed")
for n in names:
    t0 = time.time()
    try:
        if "imagen" in n:
            r = c.models.generate_images(model=n, prompt=PROMPT,
                                         config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="9:16"))
            data = r.generated_images[0].image.image_bytes
        else:
            r = c.models.generate_content(model=n, contents=PROMPT,
                                          config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]))
            data = None
            for p in r.candidates[0].content.parts:
                if getattr(p, "inline_data", None) and p.inline_data.data:
                    data = p.inline_data.data
        if data:
            open(f"probe_out/{n}.png", "wb").write(data)
            print("OK", n, len(data), f"{time.time() - t0:.1f}s")
        else:
            print("NOIMG", n)
    except Exception as e:
        print("FAIL", n, str(e)[:250])
