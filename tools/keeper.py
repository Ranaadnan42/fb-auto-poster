"""
Scheduler bot - GitHub ke late/gire hue cron ka ilaaj.

Yeh ~5.5 ghante chalta hai aur har minute dekhta hai: kisi post ka waqt qareeb hai
(post - lead) aur us ka koi run nahi bana? -> bot ko foran (workflow_dispatch) chala deta hai.
Hath/dispatch se chala run seconds mein shuru hota hai, cron ki tarah ghanton late nahi.
Khatam hone se pehle apna agla Scheduler khud chala deta hai (zanjeer). Har ghante ka cron
backup hai agar zanjeer toot jaye.
"""
import os
import sys
import time
import datetime

sys.path.insert(0, os.path.dirname(__file__))
import slots      # noqa: E402
import ghapi      # noqa: E402

RUN_ID = int(os.environ.get("GITHUB_RUN_ID") or 0)
HANDOFF = os.environ.get("HANDOFF") == "1"
REF = os.environ.get("GITHUB_REF_NAME") or "main"
RUN_MIN = 330                  # itne minute baad agla Scheduler chala kar band
LATE_OK_MIN = 60               # post waqt ke itne minute baad tak bhi chala do
START = time.time()


def log(msg):
    print(f"{ghapi.utcnow():%H:%M} {msg}", flush=True)


def other_keeper():
    """Koi aur Scheduler pehle se chal raha hai? (chhota id = purana)"""
    for st in ("in_progress", "queued"):
        out = ghapi.call("GET", "/actions/workflows/keeper.yml/runs",
                         params={"status": st, "per_page": 20})
        for r in out.get("workflow_runs", []):
            if r["id"] < RUN_ID:
                return r
    return None


def newer_keeper():
    for st in ("in_progress", "queued"):
        out = ghapi.call("GET", "/actions/workflows/keeper.yml/runs",
                         params={"status": st, "per_page": 20})
        for r in out.get("workflow_runs", []):
            if r["id"] > RUN_ID:
                return r
    return None


def dispatch(file, inputs):
    ghapi.call("POST", f"/actions/workflows/{file}/dispatches", {"ref": REF, "inputs": inputs})


if not HANDOFF:
    o = other_keeper()
    if o:
        log(f"Scheduler pehle se chal raha hai ({o['html_url']}) - yeh band")
        sys.exit(0)

done = set()                   # (file, cron, date) jo is run ne chala diye
last_newer_check = 0
log("Scheduler shuru")
while True:
    elapsed = (time.time() - START) / 60
    if elapsed >= RUN_MIN:
        try:
            dispatch("keeper.yml", {"handoff": "1"})
            log("Agla Scheduler chala diya - yeh band")
        except Exception as e:
            log(f"Agla Scheduler nahi chala ({e}) - ghante wala cron sambhalega")
        break

    if time.time() - last_newer_check > 600:
        last_newer_check = time.time()
        try:
            if newer_keeper():
                log("Naya Scheduler aa gaya - yeh band")
                break
        except Exception:
            pass

    now = ghapi.utcnow()
    for s in slots.SLOTS:
        p = ghapi.post_dt(s["post"], now)
        mins_to_post = (p - now).total_seconds() / 60
        if not (-LATE_OK_MIN <= mins_to_post <= s["lead"]):
            continue
        key = (s["file"], s["crons"][0], p.date())
        if key in done:
            continue
        try:
            since = p - datetime.timedelta(hours=slots.WINDOW_H)
            existing = [r for r in ghapi.slot_runs(s, since)
                        if r.get("conclusion") not in ("cancelled", "skipped")]
            if existing:
                done.add(key)
                continue
            dispatch(s["file"], {"sched": s["crons"][0]})
            done.add(key)
            log(f"{s['file']} chala diya - post {p:%H:%M} UTC ({int(mins_to_post)} min baad)")
        except Exception as e:
            log(f"{s['file']} {s['post']}: {e}")
    time.sleep(60)
