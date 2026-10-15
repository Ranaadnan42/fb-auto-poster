"""
Free "chalti hui" effect - tasveer ko 3D jaisa zinda banata hai (sirf CPU, koi paid API nahi).

 - Depth (AI se andaza ke kya qareeb hai, kya door) -> camera hilne par qareeb wali cheez zyada
   hilti hai (2.5D parallax), is se tasveer asli camera shot jaisi lagti hai
 - Mausam ke zarrat: barf, barish, chingariyan, dhool, dhund - har scene ke hisab se
 - Halka camera shake, roshni ki tharthrahat, tez cuts
Depth model na chale to andaze wali depth (neeche qareeb, upar door) se kaam chalta hai.
"""
import math
import random

import numpy as np
import cv2

FPS = 30
_depth_pipe = [None, False]          # [pipeline, try_kiya]


def _load_depth():
    if not _depth_pipe[1]:
        _depth_pipe[1] = True
        try:
            from transformers import pipeline
            _depth_pipe[0] = pipeline("depth-estimation",
                                      model="depth-anything/Depth-Anything-V2-Small-hf", device=-1)
            print("Depth model loaded", flush=True)
        except Exception as e:
            print(f"Depth model nahi chala, andaza wali depth: {str(e)[:150]}", flush=True)
    return _depth_pipe[0]


def depth_map(img_bgr):
    """0..1, 1 = camera ke qareeb."""
    h, w = img_bgr.shape[:2]
    pipe = _load_depth()
    d = None
    if pipe is not None:
        try:
            from PIL import Image
            small = cv2.resize(img_bgr, (518, int(518 * h / w)))
            res = pipe(Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)))
            d = np.array(res["depth"], dtype=np.float32)
            d = cv2.resize(d, (w, h))
        except Exception as e:
            print(f"Depth error: {str(e)[:120]}", flush=True)
            d = None
    if d is None:                                          # andaza: neeche + beech qareeb
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = (yy / h) ** 1.3 * 0.8 + (1 - np.abs(xx / w - 0.5) * 2) * 0.2
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
        d += cv2.GaussianBlur(gray, (0, 0), 25) * 0.15
    d -= d.min()
    d /= max(d.max(), 1e-6)
    k = max(3, (min(h, w) // 25) | 1)
    return cv2.GaussianBlur(d, (k, k), 0)                  # narm, taa ke tasveer na phatay


# ---------------------------------------------------------------- zarrat (particles)
class Particles:
    def __init__(self, kind, w, h, rnd):
        self.kind, self.w, self.h, self.r = kind, w, h, rnd
        n = {"snow": 260, "rain": 320, "embers": 90, "dust": 120, "fog": 0}.get(kind, 0)
        self.p = np.zeros((n, 5), np.float32)              # x, y, vx, vy, size
        for i in range(n):
            self.p[i] = self._new(True)
        self.fog = None
        if kind in ("fog", "snow"):
            noise = rnd.random((h // 16 + 2, w // 16 + 2)).astype(np.float32)
            noise = cv2.resize(noise, (w * 2, h), interpolation=cv2.INTER_CUBIC)
            self.fog = cv2.GaussianBlur(noise, (0, 0), 40)
            self.fog = (self.fog - self.fog.min()) / max(np.ptp(self.fog), 1e-6)

    def _new(self, anywhere=False):
        r, w, h = self.r, self.w, self.h
        x = r.uniform(0, w)
        if self.kind == "snow":
            return [x, r.uniform(0, h) if anywhere else -10, r.uniform(-0.8, 0.8),
                    r.uniform(1.2, 4.0), r.uniform(1.5, 5.5)]
        if self.kind == "rain":
            return [x, r.uniform(0, h) if anywhere else -40, -3, r.uniform(28, 40), r.uniform(1, 2.2)]
        if self.kind == "embers":
            return [x, r.uniform(0, h) if anywhere else h + 10, r.uniform(-0.6, 0.6),
                    -r.uniform(1.0, 3.5), r.uniform(1.5, 4.0)]
        return [x, r.uniform(0, h), r.uniform(-0.4, 0.4), r.uniform(-0.3, 0.3), r.uniform(1, 3)]

    def draw(self, frame, t):
        if self.fog is not None:
            off = int(t * 25) % self.w
            fog = self.fog[:, off:off + self.w]
            a = (0.20 if self.kind == "fog" else 0.08) * fog[..., None]
            frame[:] = (frame * (1 - a) + 235 * a).astype(np.uint8)
        if not len(self.p):
            return
        self.p[:, 0] += self.p[:, 2] + (np.sin(t * 2 + self.p[:, 1] / 60) * 0.6 if self.kind == "snow" else 0)
        self.p[:, 1] += self.p[:, 3]
        layer = np.zeros_like(frame)
        for i, (x, y, vx, vy, s) in enumerate(self.p):
            if y > self.h + 20 or y < -50 or x < -20 or x > self.w + 20:
                self.p[i] = self._new()
                continue
            if self.kind == "snow":
                cv2.circle(layer, (int(x), int(y)), int(s), (255, 255, 255), -1, cv2.LINE_AA)
            elif self.kind == "rain":
                cv2.line(layer, (int(x), int(y)), (int(x + vx * 1.5), int(y + vy * 0.9)),
                         (210, 210, 220), int(s), cv2.LINE_AA)
            elif self.kind == "embers":
                c = (40, 140 + int(60 * math.sin(t * 9 + i)), 255)
                cv2.circle(layer, (int(x), int(y)), int(s), c, -1, cv2.LINE_AA)
            else:
                cv2.circle(layer, (int(x), int(y)), int(s), (200, 220, 235), -1, cv2.LINE_AA)
        blur = 3 if self.kind != "rain" else 1
        layer = cv2.GaussianBlur(layer, (0, 0), blur) if blur > 1 else layer
        strength = {"snow": 0.9, "rain": 0.45, "embers": 1.0, "dust": 0.35}.get(self.kind, 0.5)
        cv2.addWeighted(frame, 1.0, layer, strength, 0, dst=frame)


# ---------------------------------------------------------------- ek shot
def shot_frames(img_bgr, secs, out_w, out_h, style, fx="none", seed=0):
    """Generator: har frame (out_h, out_w, 3) BGR uint8."""
    rnd = np.random.default_rng(seed)
    margin = 1.18
    sw, sh = int(out_w * margin), int(out_h * margin)
    ih, iw = img_bgr.shape[:2]
    sc = max(sw / iw, sh / ih)
    img = cv2.resize(img_bgr, (int(iw * sc + 1), int(ih * sc + 1)), interpolation=cv2.INTER_AREA)
    y0, x0 = (img.shape[0] - sh) // 2, (img.shape[1] - sw) // 2
    img = img[y0:y0 + sh, x0:x0 + sw]
    # 3D jaisa hilna (parallax) band - depth model ki zaroorat nahi

    yy, xx = np.mgrid[0:out_h, 0:out_w].astype(np.float32)
    cx, cy = out_w / 2, out_h / 2
    n = max(2, int(secs * FPS))
    # camera ki chaal: har shot alag
    moves = [(1.0, 0.10, 0, 0), (1.10, -0.08, 0, 0), (1.04, 0.02, 1, 0), (1.04, 0.02, -1, 0),
             (1.02, 0.06, 0, 1), (1.06, 0.04, 0.7, -0.5)]
    z0, dz, px, py = moves[style % len(moves)]
    amp = out_w * 0.035                                    # parallax kitna
    parts = Particles(fx, out_w, out_h, rnd) if fx in ("snow", "rain", "embers", "dust", "fog") else None
    for f in range(n):
        t = f / max(n - 1, 1)
        e = t * t * (3 - 2 * t)                            # narm shuru/khatam
        zoom = z0 + dz * e
        ox = px * amp * (e - 0.5) * 2
        oy = py * amp * (e - 0.5) * 2
        if px == 0 and py == 0:                            # zoom wale shot mein halka sa daayein-baayein
            ox = amp * 0.5 * math.sin(e * math.pi - math.pi / 2)
        # camera shake aur parallax hata diye: poori tasveer ek saath narmi se zoom/pan hoti hai
        mx = (sw / 2) + (xx - cx) / zoom - ox
        my = (sh / 2) + (yy - cy) / zoom - oy
        frame = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if parts:
            parts.draw(frame, f / FPS)
        flick = 1.0 + 0.025 * math.sin(f * 0.5 + seed) * (1 if fx == "embers" else 0.4)
        if flick != 1.0:
            frame = cv2.convertScaleAbs(frame, alpha=flick)
        yield frame
