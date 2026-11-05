"""Test: GitHub ke free CPU par kaun sa open-source model behtar aur kitni dair mein tasveer banata hai."""
import gc
import os
import time
import torch

torch.set_num_threads(max(os.cpu_count() or 2, 2))
os.makedirs("probe_out", exist_ok=True)
PROMPTS = [
    "Typhon, a giant monster with many serpent heads and glowing eyes, fighting Zeus who holds a lightning bolt "
    "on a stormy sea cliff, epic dark fantasy painting, cinematic lighting, highly detailed",
    "a young blacksmith hammering a glowing sword in a volcanic forge, sparks flying, a small fire dragon "
    "watching from the anvil, epic fantasy movie still, cinematic lighting, highly detailed",
]


def run(name, loader, kw):
    try:
        t = time.time()
        pipe = loader()
        pipe.set_progress_bar_config(disable=True)
        print(f"LOAD {name} {time.time() - t:.0f}s", flush=True)
        for i, p in enumerate(PROMPTS):
            t = time.time()
            img = pipe(prompt=p, generator=torch.Generator("cpu").manual_seed(7), **kw).images[0]
            img.save(f"probe_out/{name}_{i}.jpg", quality=92)
            print(f"OK {name} img{i} {img.size} {time.time() - t:.1f}s", flush=True)
        del pipe
    except Exception as e:
        print(f"FAIL {name} {str(e)[:300]}", flush=True)
    gc.collect()


from diffusers import AutoPipelineForText2Image

run("sd-turbo", lambda: AutoPipelineForText2Image.from_pretrained("stabilityai/sd-turbo", torch_dtype=torch.float32),
    dict(num_inference_steps=2, guidance_scale=0.0, width=512, height=512))
run("sdxl-turbo", lambda: AutoPipelineForText2Image.from_pretrained(
    "stabilityai/sdxl-turbo", torch_dtype=torch.float32),
    dict(num_inference_steps=3, guidance_scale=0.0, width=512, height=512))
