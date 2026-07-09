#!/usr/bin/env python3
"""Merge-time verification of the org-level (a)/(b) classification.

Current-snapshot uses NEWEST-branch maintainers, which could mask historical capture:
an org that merged another org's module in year Y, then became its maintainer by now,
reads as (a)-EXCUSED today but was (b)-CAPTURE at merge time. This samples (a) and (b)
PRs, refetches each touched module's manifest AT THE MERGE COMMIT, reclassifies with
merge-time maintainer orgs, and reports the transition matrix. The load-bearing cell is
current-(a) -> merge-time-(b) (hidden capture). Resumable.
"""
import json, os, sys, subprocess, base64, re, ast
from collections import defaultdict
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA=os.path.join(HERE,"data"); CACHE=os.path.join(HERE,"identity-company.json")
FILES=os.path.join(HERE,"files-cache.json"); MM=os.path.join(HERE,"module_maintainers.json")
OUT=os.path.join(HERE,"merge-time-sample.json")
NA=int(sys.argv[1]) if len(sys.argv)>1 else 400   # sample size from (a)
NB=int(sys.argv[2]) if len(sys.argv)>2 else 220   # sample size from (b)
MAXMOD=3                                           # cap modules fetched per PR

BOTS={"oca-git-bot","codecov","codecov-io","coveralls","pre-commit-ci","dependabot",
      "mergify","oca-bot","weblate","oca-transbot","github-actions","renovate","oca-ci","sentry-io"}
def isbot(l):
    if not l: return True
    x=l.lower().replace("[bot]","")
    return x in BOTS or x.endswith("-bot") or x.endswith("bot")
VERDICT={"APPROVED","CHANGES_REQUESTED","DISMISSED"}
def la(reviews,author):
    last={}
    for rv in sorted(reviews or [],key=lambda r:r.get("submittedAt") or ""):
        a=(rv.get("author") or {}).get("login"); st=rv.get("state")
        if not a or st not in VERDICT: continue
        last[a]=st
    return {a for a,s in last.items() if s=="APPROVED" and not isbot(a) and a!=author}
NON_MODULE={"setup","docs",".github"}
def modules_of(paths):
    s=set()
    for p in paths or []:
        top=p.split("/",1)[0]
        if not top or top.startswith(".") or top in NON_MODULE or "/" not in p: continue
        s.add(top)
    return s
MK=re.compile(r"['\"]maintainers['\"]\s*:\s*\[([^\]]*)\]",re.S)
def parse_maint(txt):
    try:
        d=ast.literal_eval(txt)
        if isinstance(d,dict):
            m=d.get("maintainers"); return [str(x) for x in m] if isinstance(m,list) else []
    except Exception: pass
    mm=MK.search(txt)
    return re.findall(r"['\"]([^'\"]+)['\"]",mm.group(1)) if mm else []

def gh_mergecommit(repo,n):
    r=subprocess.run(["gh","pr","view",str(n),"-R",f"OCA/{repo}","--json","mergeCommit"],
                     capture_output=True,text=True)
    if r.returncode!=0: return None,(r.stderr or "")
    try: return (json.loads(r.stdout).get("mergeCommit") or {}).get("oid"),""
    except Exception as e: return None,str(e)
def gh_manifest_at(repo,module,ref):
    for fn in ("__manifest__.py","__openerp__.py"):
        r=subprocess.run(["gh","api",f"repos/OCA/{repo}/contents/{module}/{fn}?ref={ref}","--jq",".content"],
                         capture_output=True,text=True)
        if r.returncode==0 and r.stdout.strip():
            try: return base64.b64decode(r.stdout.strip()).decode("utf-8","replace")
            except Exception: pass
    return None

def main():
    ident=json.load(open(CACHE)); files=json.load(open(FILES)); mm=json.load(open(MM))
    def org(l): return (ident.get(l) or {}).get("resolved_org")
    def cur_maintorgs(repo,mod):
        r=mm.get(f"{repo}/{mod}")
        if not (r and r.get("found") and r.get("maintainers")): return None
        return {org(x) for x in r["maintainers"] if org(x)}

    A=[]; B=[]
    for f in os.listdir(DATA):
        if not f.endswith(".json"): continue
        repo=f[:-5]
        for pr in json.load(open(os.path.join(DATA,f))):
            if (pr.get("mergedAt") or "0000")[:4]<"2017": continue
            al=(pr.get("author") or {}).get("login"); ao=org(al)
            if not ao: continue
            appr=la(pr.get("reviews"),al); res=[a for a in appr if org(a)]; unres=len(appr)-len(res)
            out=[a for a in res if org(a)!=ao]
            if not((not appr) or (unres==0 and not out)): continue
            key=f"{repo}#{pr['number']}"
            if key not in files: continue
            touched=[m for m in modules_of(files[key]) if cur_maintorgs(repo,m) is not None]
            if not touched: continue
            owns=any(ao in cur_maintorgs(repo,m) for m in touched)
            others=any(ao not in cur_maintorgs(repo,m) for m in touched)
            rec={"repo":repo,"n":pr["number"],"ao":ao,"al":al,"year":(pr.get("mergedAt") or "")[:4],"mods":touched[:MAXMOD]}
            if owns and not others: A.append(rec)
            elif others: B.append(rec)     # (b) or partial
    def strat(items,N):
        by=defaultdict(list)
        for r in items: by[r["year"]].append(r)
        out=[]
        for y,g in by.items():
            g.sort(key=lambda r:(r["repo"],r["n"]))
            k=max(1,round(N*len(g)/len(items)))
            out+= g if len(g)<=k else [g[int(i*len(g)/k)] for i in range(k)]
        return out
    sa=strat(A,NA); sb=strat(B,NB)
    print(f"current (a)={len(A)} sampled {len(sa)} | (b)={len(B)} sampled {len(sb)}",flush=True)
    done=json.load(open(OUT)) if os.path.exists(OUT) else {}
    sample=[("a",r) for r in sa]+[("b",r) for r in sb]
    fails=0
    for i,(cur,r) in enumerate(sample,1):
        key=f"{r['repo']}#{r['n']}"
        if key in done: continue
        sha,err=gh_mergecommit(r["repo"],r["n"])
        if not sha:
            fails+=1
            if "rate limit" in err.lower() or fails>=25: print(f"stop at {i}: {err[:100]}",flush=True); break
            continue
        fails=0
        mt_owns=False; mt_others=False; mt_any=False
        for m in r["mods"]:
            txt=gh_manifest_at(r["repo"],m,sha)
            if txt is None: continue
            morgs={org(x) for x in parse_maint(txt) if org(x)}
            if not morgs: continue
            mt_any=True
            if r["ao"] in morgs: mt_owns=True
            else: mt_others=True
        if not mt_any: mt="c"
        elif mt_owns and not mt_others: mt="a"
        elif mt_others and not mt_owns: mt="b"
        else: mt="bp"
        done[key]={"cur":cur,"mt":mt,"year":r["year"],"ao":r["ao"]}
        if i%25==0: json.dump(done,open(OUT,"w")); print(f"  {i}/{len(sample)}",flush=True)
    json.dump(done,open(OUT,"w"))
    # transition matrix
    T=defaultdict(lambda:defaultdict(int))
    for v in done.values(): T[v["cur"]][v["mt"]]+=1
    print("="*56); print("TRANSITION  current -> merge-time"); print("="*56)
    for cur in ("a","b"):
        tot=sum(T[cur].values())
        if not tot: continue
        row=" ".join(f"{mt}:{T[cur][mt]}({100*T[cur][mt]//tot}%)" for mt in ("a","b","bp","c"))
        print(f"  current-({cur}) n={tot}: {row}")
    aB=T["a"]["b"]+T["a"]["bp"]; aTot=sum(T["a"].values())
    print(f"\n>>> HIDDEN CAPTURE  current-(a) -> merge-time-(b): {aB}/{aTot} = {100*aB/aTot:.1f}%" if aTot else "no (a) sampled")
    bA=T["b"]["a"]; bTot=sum(T["b"].values())
    print(f">>> FALSE CAPTURE   current-(b) -> merge-time-(a): {bA}/{bTot} = {100*bA/bTot:.1f}%" if bTot else "")

if __name__=="__main__": main()
