"""
Scheduler bot - GitHub ke late/gire hue cron ka halka ilaaj.

Yeh har 15 minute chalta hai, ek dafa dekhta hai, aur foran khatam ho jata hai
(koi hamesha-chalta job nahi - GitHub par bojh bilkul kam).

Har post ka waqt qareeb hai (post - lead ke andar) aur us ka koi run nahi bana?
-> us bot ko foran (workflow_dispatch) chala deta hai. Dispatch se chala run
seconds mein shuru hota hai, cron ki tarah ghanton late nahi.
Har bot ka apna cron bhi barqarar hai (doosra backup).
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(__file__))
import slots      # noqa: E402
import ghapi      # noqa: E402

REF = os.environ.get("GITHUB_REF_NAME") or "main"
LATE_OK_MIN = 60               # post waqt ke itne minute baad tak bhi chala do


def log(msg):
    print(f"{ghapi.utcnow():%H:%M} {msg}", flush=True)


def dispatch(file, inputs):
    ghapi.call("POST", f"/actions/workflows/{file}/dispatches", {"ref": REF, "inputs": inputs})


now = ghapi.utcnow()
for s in slots.SLOTS:
    p = ghapi.post_dt(s["post"], now)
    mins_to_post = (p - now).total_seconds() / 60
    # sirf us post ko dekho jo lead khirki ke andar hai (na bohat door, na guzar chuka)
    if not (-LATE_OK_MIN <= mins_to_post <= s["lead"]):
        continue
    try:
        since = p - datetime.timedelta(hours=slots.WINDOW_H)
        existing = [r for r in ghapi.slot_runs(s, since)
                    if r.get("conclusion") not in ("cancelled", "skipped")]
        if existing:
            continue                      # pehle se run hai - kuch na karo
        dispatch(s["file"], {"sched": s["crons"][0]})
        log(f"{s['file']} chala diya - post {p:%H:%M} UTC ({int(mins_to_post)} min baad)")
    except Exception as e:
        log(f"{s['file']} {s['post']}: {e}")
log("Scan mukammal")
