"""
Kaggle ke FREE GPU (T4 x2) par Wan 2.1 se asli chalte hue AI clips.

GitHub bot -> Kaggle par ek private kernel push -> dono GPU saath saath clips banate hain
-> bot clips download kar ke video mein jor deta hai.
Secret: KAGGLE_API_TOKEN (Kaggle Settings > API Tokens).
Kuch bhi fail ho (quota khatam, Kaggle band, time zyada) -> {} wapas, video purane tareeqe se banti hai.
"""
import json
import os
import shutil
import subprocess
import time

USER = os.environ.get("KAGGLE_USERNAME") or "ranaadnanking"
SLUG = "legends-motion-clips"
KERNEL = f"{USER}/{SLUG}"

WORKER = r'''
import json, os, sys, time, gc
JOBS = json.loads(%(jobs)r)
W, H, FRAMES, STEPS = %(w)d, %(h)d, %(frames)d, %(steps)d
NEG = ("close-up face, deformed face, distorted face, melting face, bad eyes, bad hands, extra fingers, "
       "extra limbs, bad anatomy, body horror, blurry, low quality, worst quality, jpeg artifacts, "
       "watermark, text, logo, static, cartoon, flicker")
OUT = "/kaggle/working"
gpu, NG, delay = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
time.sleep(delay)                                       # RAM bachane ke liye doosra GPU thora baad
import torch
from diffusers import WanPipeline, AutoencoderKLWan
from diffusers.utils import export_to_video
mid = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
mine = [j for k, j in enumerate(JOBS) if k %% NG == gpu]
vae = AutoencoderKLWan.from_pretrained(mid, subfolder="vae", torch_dtype=torch.float32)
from transformers import UMT5EncoderModel
# UMT5 text encoder fp16 mein overflow -> kaali video. bf16 mein chalao
te = UMT5EncoderModel.from_pretrained(mid, subfolder="text_encoder", torch_dtype=torch.bfloat16)
pipe = WanPipeline.from_pretrained(mid, vae=vae, text_encoder=te, torch_dtype=torch.float16)
# pehle saare prompts ka text encode, phir bara text encoder nikal do
pipe.text_encoder.to("cuda")
embs = []
with torch.no_grad():
    for j in mine:
        pe, ne = pipe.encode_prompt(j["prompt"], NEG, do_classifier_free_guidance=True, device="cuda")
        embs.append((pe.to(torch.float16).cpu(), ne.to(torch.float16).cpu()))
        print(f"GPU{gpu} emb {j['id']} nan={bool(torch.isnan(pe).any())} std={float(pe.float().std()):.3f}", flush=True)
pipe.text_encoder = None
gc.collect(); torch.cuda.empty_cache()
pipe.transformer.to("cuda"); pipe.vae.to("cuda")
for j, (pe, ne) in zip(mine, embs):
    t0 = time.time()
    try:
        fr = pipe(prompt_embeds=pe.to("cuda"), negative_prompt_embeds=ne.to("cuda"),
                  width=W, height=H, num_frames=FRAMES, num_inference_steps=STEPS,
                  guidance_scale=5.0, generator=torch.Generator("cuda").manual_seed(j["seed"])).frames[0]
        import numpy as np
        arr = np.asarray(fr[len(fr) // 2], dtype=np.float32)
        print(f"GPU{gpu} clip {j['id']} mean={float(np.nanmean(arr)):.3f} nan={bool(np.isnan(arr).any())}", flush=True)
        export_to_video(fr, f"{OUT}/clip_{j['id']}.mp4", fps=16)
        print(f"GPU{gpu} clip {j['id']} {time.time() - t0:.0f}s", flush=True)
    except Exception as e:
        print(f"GPU{gpu} clip {j['id']} FAIL {e}", flush=True)
'''

MAIN = r'''
import json, os, subprocess, sys, time
t0 = time.time()
open("/tmp/w.py", "w").write(%(worker)r)
subprocess.run("pip install -q -U diffusers transformers accelerate ftfy imageio imageio-ffmpeg && "
               "pip uninstall -y -q torchao", shell=True)
ng = max(1, int(subprocess.run("nvidia-smi -L | wc -l", shell=True, capture_output=True,
                               text=True).stdout.strip() or 1))
ng = min(ng, 2, %(njobs)d)
ps = [subprocess.Popen([sys.executable, "/tmp/w.py", str(g), str(ng), str(g * 150)],
                       env={**os.environ, "CUDA_VISIBLE_DEVICES": str(g)}) for g in range(ng)]
for p in ps:
    p.wait()
OUT = "/kaggle/working"
done = sorted(f for f in os.listdir(OUT) if f.startswith("clip_"))
json.dump({"gpus": ng, "clips": len(done), "minutes": round((time.time() - t0) / 60, 1)},
          open(f"{OUT}/done.json", "w"))
print("DONE", ng, "GPU", len(done), "clips", round((time.time() - t0) / 60, 1), "min")
'''


def enabled():
    return bool(os.environ.get("KAGGLE_API_TOKEN"))


def _kg(*args, timeout=600):
    r = subprocess.run(["kaggle", *args], capture_output=True, text=True, timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def generate(jobs, w, h, work, log=print, max_minutes=240, frames=49, steps=30):
    """jobs: [{"id": 3, "prompt": "...", "seed": 11}, ...] -> {id: local_mp4_path}"""
    if not enabled() or not jobs:
        return {}
    try:
        kdir = os.path.join(work, "kernel")
        out = os.path.join(work, "kclips")
        shutil.rmtree(kdir, ignore_errors=True)
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(kdir)
        os.makedirs(out)
        with open(os.path.join(kdir, "run.py"), "w") as f:
            wsrc = WORKER % {"jobs": json.dumps(jobs), "w": w, "h": h, "frames": frames, "steps": steps}
            f.write(MAIN % {"worker": wsrc, "njobs": len(jobs)})
        with open(os.path.join(kdir, "kernel-metadata.json"), "w") as f:
            json.dump({"id": KERNEL, "title": SLUG, "code_file": "run.py", "language": "python",
                       "kernel_type": "script", "is_private": True, "enable_gpu": True,
                       "enable_internet": True, "dataset_sources": [], "competition_sources": [],
                       "kernel_sources": []}, f)
        try:
            log("Kaggle quota: " + _kg("quota")[:300].replace("\n", " | "))
        except Exception:
            pass
        res = _kg("kernels", "push", "-p", kdir, "--accelerator", "NvidiaTeslaT4")
        log(f"Kaggle push: {res.strip()[:300]}")
        if "error" in res.lower() and "successfully" not in res.lower():
            res = _kg("kernels", "push", "-p", kdir)
            log(f"Kaggle push (default GPU): {res.strip()[:300]}")
            if "error" in res.lower() and "successfully" not in res.lower():
                return {}
        t0 = time.time()
        time.sleep(60)
        status = ""
        while time.time() - t0 < max_minutes * 60:
            status = _kg("kernels", "status", KERNEL, timeout=120).lower()
            if "complete" in status or "error" in status or "cancel" in status:
                break
            time.sleep(60)
        log(f"Kaggle status: {status.strip()[:200]} ({(time.time() - t0) / 60:.0f} min)")
        if "complete" not in status and "error" not in status:
            return {}                                        # time khatam - purana tareeqa
        log(_kg("kernels", "output", KERNEL, "-p", out, "--force", timeout=900)[-300:])
        try:
            log(f"Kaggle result: {open(os.path.join(out, 'done.json')).read()}")
        except Exception:
            pass
        got = {}
        for j in jobs:
            p = os.path.join(out, f"clip_{j['id']}.mp4")
            if os.path.exists(p) and os.path.getsize(p) > 10000:
                got[j["id"]] = p
        log(f"Kaggle clips mile: {len(got)}/{len(jobs)}")
        return got
    except Exception as e:
        log(f"Kaggle skip: {str(e)[:300]}")
        return {}
