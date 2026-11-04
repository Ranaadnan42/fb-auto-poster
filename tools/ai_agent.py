"""
AI Agent (asal agent) - AI Employee ka dimagh.

ai_employee.py sirf dekhta hai (fail runs, bot reports). Yeh agent us ki report parh kar KHUD sochta hai:
  - fail hue run ka log kholta hai, wajah samajhta hai
  - code parhta/dhoondta hai, chhota fix khud likhta hai (sirf .py), compile check, phir push
  - fail kaam dobara chalata hai, database wala hissa (Supabase) theek karwata hai
  - agar us ka pichhla fix ulta kharab nikla (wohi bot phir fail) -> khud wapas (revert) kar deta hai
Koi email/report nahi. Record: agent_record.json
Dimagh: Groq (gpt-oss-120b / qwen) -> backup Gemini.
"""
import os
import re
import sys
import json
import time
import subprocess
import datetime

import requests

sys.path.insert(0, os.path.dirname(__file__))
import ghapi      # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
REC = "agent_record.json"
MAX_STEPS = 18
MAX_EDITS = 3
NO_EDIT = ("tools/ai_agent.py", "tools/ai_employee.py", "tools/ghapi.py")
SUPA_FIX = "https://fobzocsluzwcqretshnm.supabase.co/functions/v1/ai-employee?run=1"
NOW = ghapi.utcnow()


def log(m):
    print(m, flush=True)


def sh(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return (p.stdout + p.stderr).strip()


# ---------------- dimagh (LLM) ----------------
GROQ_MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
GEM_MODELS = ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"]
_dead = set()


def brain(messages):
    """messages: [{role, content}] -> JSON dict (agent ka agla qadam)."""
    gk, mk = os.environ.get("GROQ_API_KEY"), os.environ.get("GEMINI_API_KEY")
    last = None
    for m in GROQ_MODELS:
        if not gk or m in _dead:
            continue
        body = {"model": m, "temperature": 0.2, "max_tokens": 4000,
                "response_format": {"type": "json_object"}, "messages": messages}
        if m.startswith("openai/"):
            body["reasoning_effort"] = "medium"
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                              headers={"Authorization": f"Bearer {gk}"}, json=body, timeout=90)
            if r.status_code in (404, 400) and "model" in r.text:
                _dead.add(m)
            if r.status_code == 429:
                _dead.add(m)
            r.raise_for_status()
            return json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception as e:
            last = e
            log(f"  brain {m}: {str(e)[:150]}")
    for m in GEM_MODELS:
        if not mk or m in _dead:
            continue
        sys_txt = "\n".join(x["content"] for x in messages if x["role"] == "system")
        contents = [{"role": "model" if x["role"] == "assistant" else "user", "parts": [{"text": x["content"]}]}
                    for x in messages if x["role"] != "system"]
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={mk}",
                              json={"systemInstruction": {"parts": [{"text": sys_txt}]}, "contents": contents,
                                    "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}},
                              timeout=90)
            if r.status_code in (404, 429):
                _dead.add(m)
            r.raise_for_status()
            return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as e:
            last = e
            log(f"  brain {m}: {str(e)[:150]}")
    raise RuntimeError(f"koi AI model na chala: {last}")


# ---------------- agent ke auzaar (tools) ----------------
STATE = {"edits": [], "actions": [], "touched_wf": set(), "reverted": False}


def t_run_log(run_id):
    jobs = ghapi.call("GET", f"/actions/runs/{run_id}/jobs").get("jobs", [])
    out = []
    for j in jobs:
        if j.get("conclusion") not in ("failure", "cancelled", "timed_out"):
            continue
        steps = [s["name"] for s in j.get("steps", []) if s.get("conclusion") == "failure"]
        try:
            r = requests.get(f"https://api.github.com/repos/{ghapi.REPO}/actions/jobs/{j['id']}/logs",
                             headers={"Authorization": f"Bearer {ghapi.TOKEN}"}, timeout=60)
            txt = r.text
        except Exception as e:
            txt = f"log na mila: {e}"
        lines = [re.sub(r"^\S+Z ", "", x) for x in txt.splitlines()]
        keep = [x for x in lines if re.search(r"error|Error|Traceback|Exception|failed|File \"", x)][-40:]
        out.append(f"JOB {j['name']} ({j.get('conclusion')}) failed steps={steps}\n" +
                   "\n".join(keep) + "\n--- aakhri lines ---\n" + "\n".join(lines[-40:]))
    return "\n\n".join(out)[-9000:] or "koi fail job nahi"


def t_read_file(path, start=1, end=200):
    path = os.path.normpath(path)
    if path.startswith("..") or not os.path.isfile(path):
        return "file nahi mili"
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    start, end = max(1, int(start)), min(len(lines), int(end), int(start) + 300)
    return "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))


def t_grep(pattern):
    return sh(f"grep -rnE --include='*.py' --include='*.yml' -e {json.dumps(pattern)} . | grep -v '/\\.git/' | head -40") or "kuch nahi mila"


def t_edit(path, old, new, why=""):
    path = os.path.normpath(path)
    if len(STATE["edits"]) >= MAX_EDITS:
        return "is dafa ki edit limit poori"
    if not path.endswith(".py") or path in NO_EDIT or path.startswith(("..", ".github")):
        return "is file ko edit karne ki ijazat nahi (sirf bots ki .py files)"
    src = open(path, encoding="utf-8").read() if os.path.isfile(path) else None
    if src is None or src.count(old) != 1:
        return "old text file mein theek ek dafa nahi mila - pehle read_file se exact text lo"
    open(path, "w", encoding="utf-8").write(src.replace(old, new))
    chk = sh(f"python3 -m py_compile {path} && echo OK")
    if not chk.endswith("OK"):
        open(path, "w", encoding="utf-8").write(src)
        return f"compile fail, wapas kar diya: {chk[-400:]}"
    STATE["edits"].append({"path": path, "why": why})
    return "edit ho gaya, compile OK"


def t_rerun(run_id):
    r = ghapi.call("GET", f"/actions/runs/{run_id}")
    if r.get("conclusion") not in ("failure", "timed_out", "cancelled"):
        return "yeh run fail nahi - dobara nahi chalaya"
    ghapi.call("POST", f"/actions/runs/{run_id}/rerun-failed-jobs")
    STATE["actions"].append(f"run {run_id} ({r.get('name')}) dobara chalaya")
    return "dobara chala diya"


def t_dispatch(workflow):
    if workflow in STATE["touched_wf"]:
        return "yeh pehle hi chala diya"
    runs = ghapi.call("GET", f"/actions/workflows/{workflow}/runs", params={"per_page": 1}).get("workflow_runs", [])
    if not runs or runs[0].get("conclusion") not in ("failure", "timed_out"):
        return "is workflow ka aakhri run fail nahi - naya run nahi chalaya (double post se bachne ke liye)"
    STATE["touched_wf"].add(workflow)          # fix push hone ke baad chalega
    return "theek - fix push hote hi yeh workflow chal jayega"


def t_supabase():
    try:
        r = requests.get(SUPA_FIX, timeout=170)
        STATE["actions"].append("database wala hissa (leads/demo/cron) theek karwaya")
        return r.text[:1500]
    except Exception as e:
        return f"fail: {e}"


TOOLS = {
    "read_run_log": (t_run_log, "run_id - fail run ka error log"),
    "read_file": (t_read_file, "path, start, end - code parho"),
    "grep": (t_grep, "pattern - repo mein dhoondo (regex)"),
    "edit_file": (t_edit, "path, old, new, why - bot ki .py file mein chhota fix (old exact, ek dafa)"),
    "rerun_failed": (t_rerun, "run_id - fail run dobara (sirf jab wajah aarzi ho: network/timeout/quota)"),
    "run_workflow": (t_dispatch, "workflow (file.yml) - code fix ke baad naya run (sirf agar aakhri run fail tha)"),
    "fix_database": (t_supabase, "Supabase: fail cron, demo tarjuma, leads website check"),
}

SYSTEM = f"""You are the AI agent (employee) that keeps a set of automated bots healthy without any human.
Repo: GitHub Actions bots that post videos/photos to Facebook pages and YouTube channels (Atlas Untold, Frames of Life,
Islamic, Hansi Ka Adda, Legends Untold, Web Builder), a website agent, plus a Supabase sales system.
You get a health report. For every problem: find the real cause, then fix it yourself.
Rules:
- Read the failing run's log (read_run_log) before deciding. Look at code (grep/read_file) before editing.
- Temporary causes (network, timeout, 429 quota, 5xx) -> rerun_failed. Do NOT edit code for them.
- Code bugs (exception in our .py, retired/renamed AI model id, wrong field) -> edit_file with a minimal safe change,
  then run_workflow for that bot. Never remove features, never change captions/branding/schedules, never touch secrets.
- Missing secret / expired token / account banned -> cannot fix; note it in 'needs_owner'.
- Footage not matching narration (Atlas/Frames) is handled by the footage agent in world.py; only fix it if code is broken.
- Database side problems -> fix_database (once).
- Max {MAX_EDITS} edits. Be efficient: at most {MAX_STEPS} steps.
Reply ONLY JSON, one step at a time:
{{"thought": "short reasoning", "tool": "<name>", "args": {{...}}}}
or when finished: {{"thought": "...", "done": true, "summary": "Roman Urdu mein 1-3 lines kya theek kiya", "needs_owner": ["..."]}}
Tools:
""" + "\n".join(f"- {k}: {v[1]}" for k, v in TOOLS.items())


# ---------------- pichhle fix ki jaanch (kharab nikla to wapas) ----------------
def check_old_fixes(rec, notes):
    keep = []
    for fx in rec.get("open_fixes", []):
        try:
            since = datetime.datetime.fromisoformat(fx["time"])
            runs = ghapi.runs_since(fx["workflow"], since) if fx.get("workflow") else []
        except Exception:
            runs = []
        done = [r for r in runs if r.get("status") == "completed"]
        if any(r.get("conclusion") == "success" for r in done):
            notes.append(f"pichhla fix ({fx['commit'][:7]}) kaam kar gaya: {fx['why']}")
        elif len([r for r in done if r.get("conclusion") == "failure"]) >= 2:
            out = sh(f"git revert --no-edit {fx['commit']}")
            notes.append(f"pichhla fix ({fx['commit'][:7]}) se {fx['workflow']} phir fail - wapas kar diya. {out[-120:]}")
            STATE["reverted"] = True
        elif (NOW - since).days < 3:
            keep.append(fx)
    rec["open_fixes"] = keep


def guess_workflow(path):
    name = os.path.splitext(os.path.basename(path))[0]
    hits = sh(f"grep -lE '\\b{name}(\\.py)?\\b' .github/workflows/*.yml | head -1")
    return os.path.basename(hits) if hits else ""


def main():
    rec = json.load(open(REC)) if os.path.exists(REC) else {}
    notes = []
    check_old_fixes(rec, notes)

    health = json.load(open("employee_github.json")) if os.path.exists("employee_github.json") else {}
    # fail runs ki list (id ke saath) taake agent log khol sake
    fails = []
    try:
        for wf in ghapi.call("GET", "/actions/workflows", params={"per_page": 100}).get("workflows", []):
            f = os.path.basename(wf.get("path", ""))
            if wf.get("state") != "active" or f in ("ai_employee.yml",):
                continue
            try:
                runs = ghapi.runs_since(f, NOW - datetime.timedelta(hours=26))
            except Exception:
                continue
            for r in runs:
                if r.get("conclusion") in ("failure", "timed_out"):
                    fails.append({"workflow": f, "name": wf["name"], "run_id": r["id"],
                                  "attempt": r.get("run_attempt"), "at": r["created_at"]})
    except Exception as e:
        notes.append(f"runs list na mili: {e}")

    problems = health.get("problems", [])
    if not fails and not problems:
        rec.update({"time_utc": NOW.strftime("%Y-%m-%d %H:%M"), "summary": "sab theek, kuch karne ki zaroorat nahi",
                    "notes": notes, "actions": [], "needs_owner": []})
        json.dump(rec, open(REC, "w"), ensure_ascii=False, indent=1)
        log("sab theek")
        return

    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "HEALTH REPORT\nproblems:\n" + "\n".join(problems[:30]) +
             "\n\nfailed runs (last 26h):\n" + json.dumps(fails[:25], indent=0) +
             ("\n\nnotes:\n" + "\n".join(notes) if notes else "")}]
    final = {}
    for step in range(MAX_STEPS):
        try:
            act = brain(msgs)
        except Exception as e:
            notes.append(f"dimagh na chala: {e}")
            break
        if isinstance(act, list):      # AI ne [{..}] bheja - pehla hissa lo, crash na ho
            act = next((a for a in act if isinstance(a, dict)), {})
        if not isinstance(act, dict):
            act = {}
        log(f"[{step + 1}] {act.get('thought', '')[:200]}")
        msgs.append({"role": "assistant", "content": json.dumps(act, ensure_ascii=False)})
        if act.get("done"):
            final = act
            break
        name, args = act.get("tool"), act.get("args") or {}
        fn = TOOLS.get(name, (None,))[0]
        try:
            res = fn(**args) if fn else f"'{name}' naam ka tool nahi"
        except Exception as e:
            res = f"tool error: {str(e)[:300]}"
        log(f"    {name}({json.dumps(args, ensure_ascii=False)[:150]}) -> {str(res)[:200]}")
        msgs.append({"role": "user", "content": f"RESULT of {name}:\n{str(res)[:9000]}"})
        if step == MAX_STEPS - 3:
            msgs.append({"role": "user", "content": "Steps khatam hone wale hain - ab kaam samet kar done do."})

    if not final and not STATE["actions"] and not STATE["edits"]:
        # dimagh na chala -> purana tareeqa: pehli dafa fail hue runs dobara
        for f in fails:
            if f.get("attempt") == 1:
                try:
                    t_rerun(f["run_id"])
                except Exception:
                    pass

    # code fix hua -> commit + push, phir us bot ka naya run; yaad rakho taake kharab ho to wapas ho sake
    sh('git config user.name "auto-poster" && git config user.email "auto-poster@users.noreply.github.com"')
    if STATE["edits"]:
        files = " ".join(sorted({e["path"] for e in STATE["edits"]}))
        why = "; ".join(e["why"] for e in STATE["edits"])[:200]
        sh(f"git add {files} && git commit -q -m {json.dumps('AI agent fix: ' + why)}")
    if STATE["edits"] or STATE["reverted"]:
        pushed = False
        for i in range(5):
            sh("git pull -q --rebase origin main")
            if "rejected" not in (o := sh("git push -q origin HEAD:main")) and "error" not in o:
                pushed = True
                break
            time.sleep(5 * (i + 1))
        sha = sh("git rev-parse HEAD")
        if pushed and STATE["edits"]:
            for e in STATE["edits"]:
                wf = guess_workflow(e["path"])
                rec.setdefault("open_fixes", []).append({"commit": sha, "workflow": wf,
                                                         "why": e["why"], "time": NOW.isoformat()})
            STATE["actions"].append(f"code fix push kiya ({sha[:7]})")
        elif not pushed:
            notes.append("fix push na ho saka")
        if pushed:
            for wf in STATE["touched_wf"]:
                try:
                    ghapi.call("POST", f"/actions/workflows/{wf}/dispatches", body={"ref": "main"})
                    STATE["actions"].append(f"{wf} naye code ke saath chalaya")
                except Exception as e:
                    notes.append(f"{wf} na chal saka: {e}")
    rec.update({"time_utc": NOW.strftime("%Y-%m-%d %H:%M"), "summary": final.get("summary", ""),
                "notes": notes, "actions": STATE["actions"], "edits": STATE["edits"],
                "needs_owner": final.get("needs_owner", [])})
    json.dump(rec, open(REC, "w"), ensure_ascii=False, indent=1)
    log(json.dumps(rec, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
