"""
Free AI tasveerein - koi API key ya paisa nahi.
GitHub Actions ke apne CPU par open-source model "stabilityai/sd-turbo" chalta hai.
Model pehli dafa (~5 GB) download hota hai, phir workflow cache se jaldi milta hai.
"""
import os
import time

_pipe = [None]
_failed = [False]
MODEL = os.environ.get("FREE_IMAGE_MODEL", "stabilityai/sd-turbo")


def _load():
    if _pipe[0] is not None or _failed[0]:
        return _pipe[0]
    try:
        import torch
        from diffusers import AutoPipelineForText2Image
        torch.set_num_threads(max(os.cpu_count() or 2, 2))
        t = time.time()
        # sdxl-turbo: fp16 files download karo (aadha size, cache mein fit), CPU par float32 mein chalao
        extra = {"variant": "fp16"} if "sdxl" in MODEL else {}
        pipe = AutoPipelineForText2Image.from_pretrained(MODEL, torch_dtype=torch.float32, **extra)
        pipe.to("cpu")
        pipe.set_progress_bar_config(disable=True)
        _pipe[0] = pipe
        print(f"[free_images] {MODEL} loaded in {time.time() - t:.0f}s", flush=True)
    except Exception as e:
        _failed[0] = True
        print(f"[free_images] model load fail: {str(e)[:300]}", flush=True)
    return _pipe[0]


def generate(prompt, seed, path, width=1024, height=1024, look=""):
    """Tasveer bana kar `path` par JPG save karta hai. Kamyab ho to True."""
    pipe = _load()
    if pipe is None:
        return False
    try:
        import torch
        from PIL import Image
        # sd-turbo 512 ke qareeb sab se acha chalta hai; 8 ke multiple zaroori
        scale = 512 / max(width, height)
        gw = max(int(width * scale) // 8 * 8, 256)
        gh = max(int(height * scale) // 8 * 8, 256)
        text = f"{prompt}, {look}" if look else prompt
        g = torch.Generator("cpu").manual_seed(int(seed) % (2 ** 31))
        steps = 3 if "sdxl" in MODEL else 2            # sdxl-turbo 3 steps par saaf aur prompt ke mutabiq
        img = pipe(prompt=text, num_inference_steps=steps, guidance_scale=0.0,
                   width=gw, height=gh, generator=g).images[0]
        img = img.resize((width, height), Image.LANCZOS)
        img.save(path, "JPEG", quality=92)
        return os.path.getsize(path) > 15000
    except Exception as e:
        print(f"[free_images] generate error: {str(e)[:300]}", flush=True)
        return False
