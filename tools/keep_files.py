"""
Save history step ke liye: run ki apni files (/tmp/keep) ko GitHub wali nayi files par lagata hai.

Kai runs ek saath chalte hain (aik post ke waqt ka intezar kar raha hota hai, doosra post kar deta hai).
Pehle seedha copy hoti thi, to baad mein khatam hone wala run doosre run ki entry mita deta tha.
Ab *history*.json (list) MERGE hoti hai: GitHub wali entries + is run ki nayi entries.
Baaqi files (last_run report waghera) pehle ki tarah copy.

python3 tools/keep_files.py /tmp/keep file1.json file2.json ...
"""
import json
import os
import shutil
import sys


def _key(e):
    return json.dumps(e, sort_keys=True, ensure_ascii=False)


def merge(remote, local):
    seen = {_key(e) for e in remote}
    out = list(remote) + [e for e in local if _key(e) not in seen]
    if out and all(isinstance(e, dict) and "date" in e for e in out):
        out.sort(key=lambda e: str(e.get("date", "")))
    return out


def main():
    keep, files = sys.argv[1], sys.argv[2:]
    for f in files:
        src = os.path.join(keep, os.path.basename(f))
        if not os.path.isfile(src):
            continue
        if "history" in os.path.basename(f) and f.endswith(".json") and os.path.isfile(f):
            try:
                with open(src, encoding="utf-8") as a, open(f, encoding="utf-8") as b:
                    local, remote = json.load(a), json.load(b)
                if isinstance(local, list) and isinstance(remote, list):
                    with open(f, "w", encoding="utf-8") as o:
                        json.dump(merge(remote, local), o, ensure_ascii=False, indent=1)
                    print(f"merged {f}: {len(remote)} github + {len(local)} local")
                    continue
            except Exception as e:
                print(f"merge skip {f}: {e}")
        shutil.copy(src, f)


if __name__ == "__main__":
    main()
