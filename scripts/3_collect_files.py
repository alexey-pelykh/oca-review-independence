#!/usr/bin/env python3
"""Stage-1 of the module-level second study.

Fetch the changed file paths for the 2017+ CAPTURED subset (merges with no
out-of-org approval), so each merge can be reclassified at MODULE granularity
(author IS/IS-NOT a declared maintainer of the touched module) instead of the
repo-level 'shared turf' proxy, which is too coarse to be defensible.

Resumable: caches per PR to files-cache.json, skips done, breaks cleanly on a
run of failures (rate limit) so a re-run continues losslessly.
"""
import json, os, sys, subprocess, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data"); CACHE = os.path.join(HERE, "identity-company.json")
OUT  = os.path.join(HERE, "files-cache.json")

BOTS = {"oca-git-bot","codecov","codecov-io","coveralls","pre-commit-ci","dependabot",
        "mergify","oca-bot","weblate","oca-transbot","github-actions","renovate","oca-ci","sentry-io"}
def isbot(l):
    if not l: return True
    x = l.lower().replace("[bot]","")
    return x in BOTS or x.endswith("-bot") or x.endswith("bot")

VERDICT = {"APPROVED","CHANGES_REQUESTED","DISMISSED"}
def latest_approvers(reviews, author):
    last = {}
    for rv in sorted(reviews or [], key=lambda r: r.get("submittedAt") or ""):
        a = (rv.get("author") or {}).get("login"); st = rv.get("state")
        if not a or st not in VERDICT: continue
        last[a] = st
    return {a for a,s in last.items() if s=="APPROVED" and not isbot(a) and a!=author}

def gh_files(repo, num):
    r = subprocess.run(["gh","pr","view",str(num),"-R",f"OCA/{repo}","--json","files"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, (r.stderr or "")
    try:
        return [f["path"] for f in json.loads(r.stdout).get("files",[])], ""
    except Exception as e:
        return None, str(e)

def main():
    ident = json.load(open(CACHE))
    def org(l): return (ident.get(l) or {}).get("resolved_org")
    captured = []
    for f in os.listdir(DATA):
        if not f.endswith(".json"): continue
        repo = f[:-5]
        for pr in json.load(open(os.path.join(DATA, f))):
            if (pr.get("mergedAt") or "0000")[:4] < "2017": continue
            al = (pr.get("author") or {}).get("login"); ao = org(al)
            if not ao: continue
            appr = latest_approvers(pr.get("reviews"), al)
            res  = [a for a in appr if org(a)]; unres = len(appr)-len(res)
            out  = [a for a in res if org(a)!=ao]
            cap  = (not appr) or (unres==0 and not out)
            if cap: captured.append((repo, pr["number"]))
    print(f"captured subset (2017+): {len(captured)} PRs", flush=True)
    done = json.load(open(OUT)) if os.path.exists(OUT) else {}
    todo = [c for c in captured if f"{c[0]}#{c[1]}" not in done]
    print(f"already cached: {len(done)}  to fetch: {len(todo)}", flush=True)
    fails = 0
    for i,(repo,num) in enumerate(todo, 1):
        files, err = gh_files(repo, num)
        if files is None:
            fails += 1
            if "rate limit" in err.lower() or fails >= 20:
                print(f"stopping at {i}: {err[:120]}", flush=True); break
            time.sleep(1); continue
        fails = 0
        done[f"{repo}#{num}"] = files
        if i % 50 == 0:
            json.dump(done, open(OUT,"w")); print(f"  {i}/{len(todo)} fetched", flush=True)
    json.dump(done, open(OUT,"w"))
    print(f"cached now: {len(done)} / {len(captured)} captured PRs", flush=True)

if __name__ == "__main__":
    main()
