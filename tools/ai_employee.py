"""
AI Employee - GitHub wala hissa (din mein 2 dafa).

Saare bots ka kaam check karta hai aur jo theek ho sakta hai khud theek karta hai:
  1. Pichhle ~26 ghante ke har workflow run dekho. Fail hua (aur pehli dafa) -> khud dobara chalao.
  2. Har bot ki last_run report parho: error, purani (bot chala hi nahi), video mein footage bina check
     ke lagi (Atlas Untold / Frames of Life), AI model band (404) waghera.
  3. Sab kuch employee_github.json mein likho. Supabase wala AI employee (ai-employee function) ise parh
     kar database wala kaam khud theek karta hai (koi email nahi).
"""
import os
import sys
import json
import glob
import datetime

sys.path.insert(0, os.path.dirname(__file__))
import ghapi      # noqa: E402

NOW = ghapi.utcnow()
SINCE = NOW - datetime.timedelta(hours=26)
OUT = "employee_github.json"
SKIP_WF = {"ai_employee.yml", "keeper.yml", "tts_probe.yml", "tiktok_connect.yml"}

# report file -> (bot ka naam, kitne ghante tak purani chalegi)
BOTS = {
    "last_run.json": ("Islamic Motivational Videos (FB)", 30),
    "funny_last_run.json": ("Hansi Ka Adda (FB)", 30),
    "world_long_last_run.json": ("Atlas Untold - lambi video", 30),
    "world_short_last_run.json": ("Atlas Untold - short", 30),
    "frames_long_last_run.json": ("Frames of Life - lambi video", 30),
    "frames_short_last_run.json": ("Frames of Life - short", 30),
    "cinematic_en_long_last_run.json": ("Legends Untold - lambi", 30),
    "cinematic_en_short_last_run.json": ("Legends Untold - short", 30),
    "photos_last_run.json": ("Photo posts", 30),
    "webbuilder_en_last_run.json": ("Web Builder photo (English)", 30),
    "webbuilder_ur_last_run.json": ("Web Builder photo (Urdu)", 30),
    "webbuilder_ar_last_run.json": ("Web Builder photo (Arabic)", 30),
    "webbuilder_video_en_reel_last_run.json": ("Web Builder reel (English)", 30),
    "webbuilder_video_ur_reel_last_run.json": ("Web Builder reel (Urdu)", 30),
    "webbuilder_video_ar_reel_last_run.json": ("Web Builder reel (Arabic)", 30),
    "site_last_run.json": ("Website/blog agent", 30),
    "growth_last_run.json": ("Growth (comments)", 30),
}


def log(m):
    print(m, flush=True)


def when(d, path):
    for k in ("time_utc", "time", "at", "started"):
        v = d.get(k)
        if isinstance(v, str) and v[:4].isdigit():
            try:
                return datetime.datetime.fromisoformat(v.replace("Z", "").replace("T", " ")[:19])
            except Exception:
                pass
    try:   # file mein waqt nahi -> git se aakhri commit ka waqt
        import subprocess
        t = subprocess.run(["git", "log", "-1", "--format=%cI", "--", path], capture_output=True, text=True).stdout.strip()
        if t:
            return datetime.datetime.fromisoformat(t).astimezone(datetime.timezone.utc).replace(tzinfo=None)
    except Exception:
        pass
    return None


def check_workflows(fixed, problems, ok):
    wfs = ghapi.call("GET", "/actions/workflows", params={"per_page": 100}).get("workflows", [])
    for wf in wfs:
        file = os.path.basename(wf.get("path", ""))
        if wf.get("state") != "active" or file in SKIP_WF:
            continue
        try:
            runs = ghapi.runs_since(file, SINCE)
        except Exception:
            continue          # dynamic/purana workflow - runs API 404
        done = [r for r in runs if r.get("status") == "completed"]
        bad = [r for r in done if r.get("conclusion") == "failure"]
        good = [r for r in done if r.get("conclusion") == "success"]
        if good:
            ok.append(f"{wf['name']}: {len(good)} kamyab run")
        for r in bad:
            if r.get("run_attempt", 1) == 1:
                try:
                    ghapi.call("POST", f"/actions/runs/{r['id']}/rerun-failed-jobs")
                    fixed.append(f"{wf['name']}: fail hua tha ({r['created_at'][:16]} UTC) - dobara chala diya")
                except Exception as e:
                    problems.append(f"{wf['name']}: fail hua, dobara chalana bhi na ho saka ({str(e)[:80]})")
            else:
                problems.append(f"{wf['name']}: dobara chalane par bhi fail ({r['created_at'][:16]} UTC) - {r['html_url']}")


def check_reports(problems, ok):
    for path, (name, max_h) in BOTS.items():
        if not os.path.exists(path):
            continue
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            problems.append(f"{name}: report file kharab hai")
            continue
        t = when(d, path)
        if t and (NOW - t).total_seconds() / 3600 > max_h:
            problems.append(f"{name}: {int((NOW - t).total_seconds() // 3600)} ghante se nahi chala")
        errs = [e for e in (d.get("errors") or []) if e] + ([d["error"]] if d.get("error") else [])
        for e in errs[:2]:
            problems.append(f"{name}: error - {str(e)[:160]}")
        # Atlas / Frames: footage agent ne har clip check ki?
        if path.startswith(("world_", "frames_")):
            clips = d.get("clips") or 0
            skipped = d.get("vision_skipped") or 0
            checks = d.get("vision_checks") or 0
            if clips and skipped > max(3, 0.25 * (checks + skipped)):
                problems.append(f"{name}: {skipped} clips bina agent check ke (AI quota khatam) - footage ghalat ho sakti hai")
            elif clips:
                ok.append(f"{name}: {clips} clips, agent ne {checks} check kin, {d.get('clips_rejected', 0)} ghalat clips hata din")
            if d.get("no_match"):
                problems.append(f"{name}: in cheezon ki sahi footage nahi mili: {', '.join(map(str, d['no_match'][:4]))}")
        for line in (d.get("log") or []):
            if "does not exist" in str(line) or "model_not_found" in str(line):
                problems.append(f"{name}: ek AI model band ho chuka hai (backup chal raha hai) - {str(line)[:90]}")
                break


def main():
    fixed, problems, ok = [], [], []
    try:
        check_workflows(fixed, problems, ok)
    except Exception as e:
        problems.append(f"GitHub runs check na ho saka: {str(e)[:120]}")
    check_reports(problems, ok)
    out = {"time_utc": NOW.strftime("%Y-%m-%d %H:%M"), "fixed": fixed,
           "problems": list(dict.fromkeys(problems)), "ok": ok[:40]}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
