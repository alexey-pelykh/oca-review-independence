#!/usr/bin/env python3
"""Stage-2 (fast): resolve declared maintainers for every module touched by a captured PR.

Reads files-cache.json -> unique (repo, module) set -> fetches each module's manifest
at the NEWEST OCA version branch where it exists (current-snapshot). Threaded raw.githubusercontent
HTTP (no GitHub API budget, no git ls-remote — the earlier ls-remote-per-repo hang is gone).
Resumable: caches module_maintainers.json, skips done.
"""
import json, os, re, ast, urllib.request, urllib.error, time
from concurrent.futures import ThreadPoolExecutor, as_completed
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = os.path.join(HERE, "files-cache.json")
OUT   = os.path.join(HERE, "module_maintainers.json")

# OCA version branches, newest first (current-snapshot = newest branch where the module lives)
BRANCHES = ["19.0","18.0","17.0","16.0","15.0","14.0","13.0","12.0","11.0","10.0","9.0","8.0"]
def fname(br):
    try: return "__manifest__.py" if int(br.split(".")[0]) >= 10 else "__openerp__.py"
    except Exception: return "__manifest__.py"

NON_MODULE = {"setup","docs",".github"}
def modules_of(paths):
    mods = set()
    for p in paths or []:
        top = p.split("/",1)[0]
        if not top or top.startswith(".") or top in NON_MODULE or "/" not in p: continue
        mods.add(top)
    return mods

MK = re.compile(r"['\"]maintainers['\"]\s*:\s*\[([^\]]*)\]", re.S)
def parse_maintainers(txt):
    try:
        d = ast.literal_eval(txt)
        if isinstance(d, dict):
            m = d.get("maintainers")
            return ([str(x) for x in m], True) if isinstance(m, list) else ([], True)
    except Exception:
        pass
    mm = MK.search(txt)
    if mm: return re.findall(r"['\"]([^'\"]+)['\"]", mm.group(1)), True
    return [], False

def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as f:
            return f.read().decode("utf-8","replace"), 200
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception:
        return None, 0

def resolve(repo, mod):
    for br in BRANCHES:
        txt, code = fetch(f"https://raw.githubusercontent.com/OCA/{repo}/{br}/{mod}/{fname(br)}")
        if code == 429:
            time.sleep(2); txt, code = fetch(f"https://raw.githubusercontent.com/OCA/{repo}/{br}/{mod}/{fname(br)}")
        if txt is not None:
            maint, parsed = parse_maintainers(txt)
            return {"maintainers": maint, "branch": br, "found": True, "parsed": parsed}
    return {"maintainers": [], "branch": None, "found": False, "parsed": False}

def main():
    files = json.load(open(FILES))
    pairs = set()
    for key, paths in files.items():
        repo = key.split("#",1)[0]
        for m in modules_of(paths): pairs.add((repo, m))
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    todo = [p for p in sorted(pairs) if f"{p[0]}/{p[1]}" not in out]
    print(f"{len(pairs)} unique modules | cached {len(out)} | to fetch {len(todo)}", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(resolve, repo, mod): (repo, mod) for repo, mod in todo}
        for fut in as_completed(futs):
            repo, mod = futs[fut]
            try: out[f"{repo}/{mod}"] = fut.result()
            except Exception: out[f"{repo}/{mod}"] = {"maintainers":[],"branch":None,"found":False,"parsed":False}
            done += 1
            if done % 300 == 0:
                json.dump(out, open(OUT,"w")); print(f"  {done}/{len(todo)}", flush=True)
    json.dump(out, open(OUT,"w"))
    found = sum(1 for v in out.values() if v["found"])
    withm = sum(1 for v in out.values() if v["maintainers"])
    print(f"done: {len(out)} candidates | {found} real modules | {withm} declare maintainers", flush=True)

if __name__ == "__main__":
    main()
