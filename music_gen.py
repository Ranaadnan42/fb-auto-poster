"""Original background music generator (copyright-free, khud bana).

Har call par naya track: mood ke hisaab se chord progression, piano melody,
soft strings pad aur halka reverb. Kisi label/recording ka use nahi, is liye
Facebook/YouTube Rights Manager claim nahi kar sakta.
"""
import os
import random
import subprocess
import wave

import numpy as np

SR = 44100

# mood -> (bpm range, scale, progressions as scale-degree roots)
MOODS = {
    "calm piano": ((60, 72), "major", [[1, 5, 6, 4], [1, 6, 4, 5], [6, 4, 1, 5]]),
    "dreamy": ((56, 68), "lydian", [[1, 2, 1, 5], [1, 4, 6, 5], [4, 1, 2, 6]]),
    "melancholic": ((54, 66), "minor", [[1, 6, 3, 7], [1, 4, 6, 5], [6, 7, 1, 1]]),
    "uplifting strings": ((70, 84), "major", [[1, 5, 6, 4], [4, 5, 3, 6], [1, 3, 4, 5]]),
    "romantic": ((58, 70), "major", [[1, 3, 4, 4], [6, 4, 1, 5], [1, 6, 2, 5]]),
}
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
}


def _f(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _env(n, a, r):
    e = np.ones(n)
    a, r = min(a, n // 2), min(r, n // 2)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def _piano(freq, secs, vel):
    n = int(secs * SR)
    t = np.arange(n) / SR
    tone = sum(np.sin(2 * np.pi * freq * k * t) * (0.55 ** (k - 1)) * np.exp(-t * (1.6 + k * 0.9))
               for k in range(1, 6))
    return tone * vel * _env(n, int(0.004 * SR), int(0.25 * SR))


def _pad(freqs, secs, vol):
    n = int(secs * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for fr in freqs:
        for det in (-0.12, 0.0, 0.13):
            ph = random.random() * 6.28
            out += np.sin(2 * np.pi * (fr + det) * t + ph) * 0.5 + np.sin(2 * np.pi * 2 * (fr + det) * t + ph) * 0.12
    return out * vol / max(1, len(freqs)) * _env(n, int(1.2 * SR), int(1.2 * SR))


def make_track(path, secs, mood=None, seed=None):
    rnd = random.Random(seed)
    random.seed(rnd.random())
    mood = (mood or "").lower().strip()
    (b0, b1), scale_name, progs = MOODS.get(mood) or rnd.choice(list(MOODS.values()))
    scale = SCALES[scale_name]
    bpm = rnd.uniform(b0, b1)
    beat = 60.0 / bpm
    bar = beat * 4
    key = rnd.randint(55, 62)  # tonic midi note
    prog = rnd.choice(progs)
    total = int((secs + 2) * SR)
    mix = np.zeros(total + SR * 4)

    def degree(d, octave=0):
        i = d - 1
        return key + scale[i % 7] + 12 * (i // 7) + 12 * octave

    pattern = rnd.choice([[0, 1, 2, 1], [0, 2, 1, 2], [0, 1, 2, 3], [0, 2, 3, 2]])
    mel_rate = rnd.choice([1, 2])
    t0, bi, prev = 0.0, 0, rnd.choice([1, 3, 5])
    while t0 < secs + 1:
        root = prog[bi % len(prog)]
        chord = [degree(root, -1), degree(root + 2, -1), degree(root + 4, -1)]
        s = int(t0 * SR)
        pad = _pad([_f(m) for m in chord] + [_f(degree(root, -2))], bar + 1.2, 0.18)
        mix[s:s + len(pad)] += pad[:len(mix) - s]
        # arpeggio (left hand)
        arp = chord + [chord[0] + 12]
        for k in range(8):
            st = int((t0 + k * beat / 2) * SR)
            note = _piano(_f(arp[pattern[k % 4]]), beat * 1.6, 0.16 * rnd.uniform(0.8, 1.0))
            mix[st:st + len(note)] += note[:len(mix) - st]
        # melody (right hand) - chord tones par chalti, kabhi kabhi khamosh
        if bi % 8 >= 1:
            for k in range(2 * mel_rate):
                if rnd.random() < 0.25:
                    continue
                step = rnd.choice([-2, -1, 0, 1, 2]) if rnd.random() < 0.6 else rnd.choice([root, root + 2, root + 4]) - prev
                prev = max(1, min(10, prev + step))
                st = int((t0 + k * bar / (2 * mel_rate)) * SR)
                note = _piano(_f(degree(prev, 1)), bar / mel_rate, 0.22 * rnd.uniform(0.75, 1.0))
                mix[st:st + len(note)] += note[:len(mix) - st]
        t0 += bar
        bi += 1

    mix = mix[:total]
    mix *= _env(len(mix), int(1.5 * SR), int(2.5 * SR))
    mix /= (np.max(np.abs(mix)) or 1) / 0.8
    raw = path + ".raw.wav"
    with wave.open(raw, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                    "aecho=0.8:0.85:60|140|260:0.35|0.25|0.15,highpass=f=50,lowpass=f=9000,"
                    "aformat=channel_layouts=stereo,loudnorm=I=-18:TP=-2",
                    "-ar", "44100", path], check=True)
    os.remove(raw)
    return f"original {mood or 'mix'} {int(bpm)}bpm key{key} #{rnd.randint(1000, 9999)}"


if __name__ == "__main__":
    print(make_track("test_music.m4a", 40, "calm piano"))
