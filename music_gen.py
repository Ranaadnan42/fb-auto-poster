"""Original background music generator (copyright-free, khud bana).

Har video ke liye naya gaana compose hota hai (MIDI), phir FluidR3 GM soundfont
(MIT license) ke asli instruments se render: piano, strings, harp, flute, guitar,
marimba, horns. Mood video/scene ke hisaab se: beach -> tropical, pahar -> epic,
jungle/meadow -> flute, waghera. Structure: soft intro -> build -> peak -> soft
ending, aur melody motif repeat + variation, taake sunne mein bura ya bore na lage.
Kisi label/recording ka use nahi, is liye Rights Manager claim nahi kar sakta.
"""
import os
import random
import shutil
import struct
import subprocess

SF2_PATHS = ["/usr/share/sounds/sf2/FluidR3_GM.sf2", "/usr/share/soundfonts/FluidR3_GM.sf2",
             "/usr/share/sounds/sf2/default-GM.sf2"]

SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10],
          "lydian": [0, 2, 4, 6, 7, 9, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10]}

# GM programs: 0 piano, 8 celesta, 12 marimba, 24 nylon guitar, 32 acoustic bass, 42 cello, 46 harp,
# 47 timpani, 48/49 strings, 52 choir, 60 french horn, 71 clarinet, 73 flute, 75 pan flute, 89 warm pad
MOODS = {
    "calm piano": dict(bpm=(64, 76), scale=["major"], lead=[0, 8, 46], arp=[0, 46], pad=[49, 89, 48], bass=[42, 32],
                       progs=[[1, 5, 6, 4], [1, 6, 4, 5], [6, 4, 1, 5], [1, 3, 4, 5], [1, 4, 2, 5], [4, 1, 5, 6]]),
    "dreamy": dict(bpm=(60, 72), scale=["lydian", "major"], lead=[8, 46, 0], arp=[46, 0], pad=[89, 49], bass=[42],
                   progs=[[1, 2, 1, 5], [1, 4, 6, 5], [4, 1, 2, 6]]),
    "uplifting strings": dict(bpm=(78, 92), scale=["major"], lead=[48, 60, 73], arp=[0, 46, 24], pad=[49, 52], bass=[42, 32],
                              perc="timpani", progs=[[1, 5, 6, 4], [4, 5, 3, 6], [6, 4, 1, 5], [1, 4, 5, 5]]),
    "romantic": dict(bpm=(62, 74), scale=["major"], lead=[0, 42], arp=[0], pad=[49], bass=[42],
                     progs=[[1, 3, 4, 4], [6, 4, 1, 5], [1, 6, 2, 5]]),
    "melancholic": dict(bpm=(60, 70), scale=["minor"], lead=[0, 42], arp=[0, 46], pad=[49, 89], bass=[42],
                        progs=[[1, 6, 3, 7], [1, 4, 6, 5], [6, 7, 1, 1]]),
    "epic cinematic": dict(bpm=(84, 98), scale=["minor", "major"], lead=[60, 48, 61], arp=[48, 45], pad=[52, 49], bass=[42, 43],
                           perc="timpani", ostinato=True, progs=[[1, 6, 3, 7], [6, 4, 1, 5], [1, 7, 6, 7]]),
    "tropical chill": dict(bpm=(88, 100), scale=["major", "mixolydian"], lead=[12, 75, 11, 13], arp=[24, 25, 46], pad=[89, 88], bass=[32, 33],
                           perc="shaker", progs=[[1, 4, 6, 5], [1, 5, 4, 4], [2, 5, 1, 1]]),
    "peaceful flute": dict(bpm=(66, 78), scale=["major", "lydian"], lead=[73, 75, 71, 68], arp=[46, 24, 0], pad=[49, 89, 52],
                           bass=[42], progs=[[1, 4, 1, 5], [1, 6, 4, 5], [4, 5, 1, 1]]),
}
MOOD_NAMES = list(MOODS)
ALIASES = {"calm": "calm piano", "piano": "calm piano", "uplifting": "uplifting strings", "strings": "uplifting strings",
           "epic": "epic cinematic", "cinematic": "epic cinematic", "tropical": "tropical chill", "chill": "tropical chill",
           "flute": "peaceful flute", "peaceful": "peaceful flute", "sad": "melancholic", "emotional": "romantic"}


def pick_mood(mood, text=""):
    m = (mood or "").lower().strip()
    if m in MOODS:
        return m
    for k, v in ALIASES.items():
        if k in m:
            return v
    t = (text or "").lower()      # mood khali/ghalat ho to scene ke words se andaza
    rules = [(("beach", "island", "lagoon", "sea", "ocean", "coast", "tropical", "bay", "reef"), "tropical chill"),
             (("mountain", "peak", "alps", "glacier", "canyon", "fjord", "volcano", "cliff"), "epic cinematic"),
             (("forest", "jungle", "meadow", "valley", "village", "tea", "field", "river", "waterfall"), "peaceful flute"),
             (("lavender", "flower", "tulip", "blossom", "sunset", "lake"), "dreamy")]
    for words, mm in rules:
        if any(w in t for w in words):
            return mm
    return random.choice(["calm piano", "uplifting strings", "dreamy", "peaceful flute"])


# ------------------------------------------------------------------ tiny MIDI writer
def _vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def _write_midi(path, events, bpm, tpq=480):
    """events: (tick, bytes) list - ek hi track."""
    evs = [(0, b"\xff\x51\x03" + struct.pack(">I", int(60e6 / bpm))[1:])] + events
    evs.sort(key=lambda e: (e[0], 0 if e[1][0] & 0xF0 == 0x80 else 1))
    data, last = b"", 0
    for t, msg in evs:
        data += _vlq(t - last) + msg
        last = t
    data += b"\x00\xff\x2f\x00"
    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpq) + b"MTrk" + struct.pack(">I", len(data)) + data)


class Song:
    def __init__(self, tpq=480):
        self.tpq, self.ev = tpq, []

    def prog(self, ch, p):
        self.ev.append((0, bytes([0xC0 | ch, p])))

    def cc(self, t, ch, c, v):
        self.ev.append((int(t * self.tpq), bytes([0xB0 | ch, c, max(0, min(127, int(v)))])))

    def note(self, ch, t, dur, n, v):
        if not 0 <= n <= 127:
            return
        a, b = int(t * self.tpq), int((t + dur) * self.tpq)
        v = max(1, min(127, int(v)))
        self.ev.append((a, bytes([0x90 | ch, n, v])))
        self.ev.append((max(a + 1, b), bytes([0x80 | ch, n, 0])))


def compose(mid_path, secs, mood, rnd, avoid=()):
    cfg = MOODS[mood]
    bpm = rnd.uniform(*cfg["bpm"])
    beats_total = secs * bpm / 60.0
    bars = max(6, int(beats_total // 4) + 1)
    scale = SCALES[rnd.choice(cfg["scale"])]
    key = rnd.randint(57, 64)
    avoid = set(avoid)
    for _ in range(60):                                # pichle gaanon wala combination dobara nahi
        prog = rnd.choice(cfg["progs"])
        lead, arp_i, pad_i = rnd.choice(cfg["lead"]), rnd.choice(cfg["arp"]), rnd.choice(cfg["pad"])
        sig = f"{mood}|{lead}-{arp_i}-{pad_i}|{''.join(map(str, prog))}|{key % 12}"
        if sig not in avoid:
            break
        key = rnd.randint(57, 64)
    prog_b = rnd.choice(cfg["progs"])                 # B-section ke liye doosri progression
    s = Song()
    CH_LEAD, CH_ARP, CH_PAD, CH_BASS, CH_EXTRA = 0, 1, 2, 3, 4
    s.prog(CH_LEAD, lead)
    s.prog(CH_ARP, arp_i)
    s.prog(CH_PAD, pad_i)
    s.prog(CH_BASS, rnd.choice(cfg["bass"]))
    s.prog(CH_EXTRA, 47 if cfg.get("perc") == "timpani" else 49)
    for ch in range(5):
        s.cc(0, ch, 91, 70 if ch != CH_BASS else 40)   # reverb send
        s.cc(0, ch, 93, 25)                            # chorus

    def deg(d, octv=0):
        i = d - 1
        return key + scale[i % 7] + 12 * (i // 7) + 12 * octv

    def chord(root, octv=0):
        return [deg(root, octv), deg(root + 2, octv), deg(root + 4, octv)]

    # melody motif: 2 bar ka chhota tune, baar baar aata hai (variation ke saath) - yahi gaane ko yaad rehne wala banata hai
    rhythm = rnd.choice([[1.5, 0.5, 1, 1, 2, 1, 1], [1, 1, 1, 1, 3, 1], [2, 1, 1, 2, 2], [0.5, 0.5, 1, 2, 1, 1, 2]])
    contour = [rnd.choice([1, 3, 5, 5, 6, 8])]
    for _ in range(len(rhythm) - 1):
        contour.append(max(1, min(10, contour[-1] + rnd.choice([-2, -1, -1, 1, 1, 2, 0]))))
    arp_pat = rnd.choice([[0, 1, 2, 1, 3, 1, 2, 1], [0, 2, 1, 2, 3, 2, 1, 2], [0, 1, 2, 3, 2, 1, 2, 1]])

    # sections: intro -> A -> B (build) -> peak -> soft outro
    def energy(b):
        x = b / bars
        if b < 2:
            return 0
        if b >= bars - 2:
            return 1
        if x < 0.35:
            return 2
        if x < 0.75:
            return 3
        return 2

    for b in range(bars):
        t0 = b * 4.0
        e = energy(b)
        p = prog_b if (0.35 <= b / bars < 0.75 and (b // 4) % 2 == 1) else prog
        root = p[b % 4]
        ch3 = chord(root, -1)
        swell = 50 + 18 * e
        # pad - har waqt, energy ke saath tez
        for n in ch3 + [deg(root, -2) + 12]:
            s.note(CH_PAD, t0, 4.0, n, swell)
        # bass
        if e >= 1:
            s.note(CH_BASS, t0, 2.0 if mood == "tropical chill" else 4.0, deg(root, -2), 62 + 6 * e)
            if mood == "tropical chill":
                s.note(CH_BASS, t0 + 2.5, 1.5, deg(root + 4, -2), 58)
        # arpeggio / ostinato
        if e >= 1 or b == 1:
            notes = ch3 + [ch3[0] + 12]
            step = 0.5 if not cfg.get("ostinato") else 0.25
            for k in range(int(4 / step)):
                if e == 1 and k % 2:
                    continue
                n = notes[arp_pat[k % 8]] + (12 if mood != "epic cinematic" else 0)
                s.note(CH_ARP, t0 + k * step, step * (1.8 if not cfg.get("ostinato") else 0.8), n,
                       (48 + 8 * e) * rnd.uniform(0.85, 1.0) * (1.15 if k % 4 == 0 else 1))
        # melody - motif har 2 bar, chord ke hisaab se shift, peak par octave upar
        if e >= 2 or (e == 1 and b == bars - 2):
            half = b % 2
            tt, acc = 0.0, []
            for r, c in zip(rhythm, contour):
                acc.append((tt, r, c))
                tt += r
            shift = (root - 1) if rnd.random() < 0.5 else 0
            vary = rnd.random() < 0.35
            for st, dur, c in acc:
                if (st >= 4) != bool(half):
                    continue
                cc = c + shift + (rnd.choice([-1, 1]) if vary and rnd.random() < 0.3 else 0)
                n = deg(max(1, cc), 1)
                s.note(CH_LEAD, t0 + (st - 4 * half), dur * 0.95, n, 70 + 8 * (e - 2) + rnd.randint(-6, 6))
                if e == 3 and lead in (48, 60):          # peak par strings/horns double
                    s.note(CH_LEAD, t0 + (st - 4 * half), dur * 0.95, n - 12, 60)
        # percussion
        if cfg.get("perc") == "timpani" and e >= 2 and b % 2 == 0:
            s.note(CH_EXTRA, t0, 1.0, deg(1, -2), 55 + 10 * (e - 2))
            if e == 3:
                s.note(CH_EXTRA, t0 + 3.5, 0.5, deg(5, -3), 50)
        if cfg.get("perc") == "shaker" and e >= 2:
            for k in range(8):
                s.note(9, t0 + k * 0.5, 0.25, 82 if k % 2 else 69, 38 if k % 2 else 30)   # shaker / cabasa
    # ending chord
    tend = bars * 4.0
    for n in chord(1, -1) + [deg(1, -2), deg(1, 1)]:
        s.note(CH_PAD, tend, 4.0, n, 55)
    s.note(CH_ARP, tend, 4.0, deg(1, 1), 50)
    _write_midi(mid_path, s.ev, bpm)
    return bpm, key, sig


def _sf2():
    for p in SF2_PATHS:
        if os.path.exists(p):
            return p
    return None


def used_sigs(titles):
    """History ke titles se purane gaanon ke signature nikalta hai."""
    return {t.split("[", 1)[1].rstrip("]") for t in titles or [] if isinstance(t, str) and "[" in t}


def make_track(path, secs, mood=None, text="", seed=None, used=()):
    """path par original music bana kar title return karta hai. secs = video ki lambai."""
    rnd = random.Random(seed)
    mood = pick_mood(mood, text)
    sf2 = _sf2()
    if not (shutil.which("fluidsynth") and sf2):
        raise RuntimeError("fluidsynth / soundfont nahi mila")
    mid = path + ".mid"
    raw = path + ".raw.wav"
    bpm, key, sig = compose(mid, secs + 4, mood, rnd, used_sigs(used))
    subprocess.run(["fluidsynth", "-ni", "-g", "0.7", "-R", "1", "-C", "1", "-r", "44100", "-F", raw, sf2, mid],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                    "highpass=f=40,afade=t=in:st=0:d=1.5,loudnorm=I=-17:TP=-1.5", "-ar", "44100",
                    "-c:a", "aac", "-b:a", "192k", path], check=True)
    for f in (mid, raw):
        try:
            os.remove(f)
        except OSError:
            pass
    return f"original {mood} {int(bpm)}bpm [{sig}]"


if __name__ == "__main__":
    import sys
    for m in (sys.argv[1:] or ["calm piano", "tropical chill", "epic cinematic", "peaceful flute"]):
        print(make_track(f"sample_{m.replace(' ', '_')}.m4a", 45, m))
