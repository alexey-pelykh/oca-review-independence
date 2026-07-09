#!/usr/bin/env python3
"""CORRECTED module-level reclassification — ORG-level maintainership (not login).

Conflict-of-interest question is whether the author's ORG has maintainership standing on
the touched module, not whether the individual login is a maintainer. (a) author's org
maintains it (a colleague counts); (b) module is confirmed OTHER orgs' turf and author's
org maintains none; (c) module has no resolved-org maintainer. Aggregate + people-gated
leaderboard + (b) by year + (b)-confidence.
"""
import json, os, sys
from collections import defaultdict
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA=os.path.join(HERE,"data"); CACHE=os.path.join(HERE,"identity-company.json")
FILES=os.path.join(HERE,"files-cache.json"); MM=os.path.join(HERE,"module_maintainers.json")
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

def main():
    ident=json.load(open(CACHE)); files=json.load(open(FILES)); mm=json.load(open(MM))
    def org(l): return (ident.get(l) or {}).get("resolved_org")
    def maintorgs(repo,mod):
        r=mm.get(f"{repo}/{mod}")
        if not (r and r.get("found") and r.get("maintainers")): return None
        return {org(x) for x in r["maintainers"] if org(x)}   # resolved maintainer orgs

    # aggregate
    agg=defaultdict(int); by_year=defaultdict(lambda:defaultdict(int)); b_allres=0
    # per-org
    people=defaultdict(set); authored=defaultdict(int); captured=defaultdict(int)
    A=defaultdict(int); Bc=defaultdict(int); Cc=defaultdict(int); struct=defaultdict(int); struct_base=defaultdict(int)

    for f in os.listdir(DATA):
        if not f.endswith(".json"): continue
        repo=f[:-5]
        for pr in json.load(open(os.path.join(DATA,f))):
            if (pr.get("mergedAt") or "0000")[:4]<"2017": continue
            al=(pr.get("author") or {}).get("login"); ao=org(al)
            if not ao: continue
            authored[ao]+=1; people[ao].add(al)
            appr=la(pr.get("reviews"),al); res=[a for a in appr if org(a)]; unres=len(appr)-len(res)
            out=[a for a in res if org(a)!=ao]
            if not((not appr) or (unres==0 and not out)): continue    # captured only
            captured[ao]+=1
            y=(pr.get("mergedAt") or "----")[:4]
            key=f"{repo}#{pr['number']}"
            if key not in files: agg["x_uncached"]+=1; continue
            touched=modules_of(files[key])
            mods_m=[m for m in touched if maintorgs(repo,m) is not None]  # has >=1 resolved-org maintainer
            has_realmod=any((mm.get(f'{repo}/{m}') or {}).get('found') for m in touched)
            if not mods_m:
                agg["c_no_resolved_maint"]+=1
                if has_realmod: Cc[ao]+=1
                else: agg["x_no_module"]+=1
                continue
            owns=False; others=False; allres=True
            for m in mods_m:
                mo=maintorgs(repo,m)
                if ao in mo: owns=True
                else: others=True
                # structural: module solely maintained by author's org
                if mo=={ao}: struct[ao]+=1  # counted per PR below via flag
            struct_base[ao]+=1
            # structural flag (any touched module solely author-org maintained)
            solely=any(maintorgs(repo,m)=={ao} for m in mods_m)
            if owns and not others: agg["a"]+=1; A[ao]+=1; bucket="a"
            elif others and not owns: agg["b"]+=1; Bc[ao]+=1; bucket="b"; b_allres+=1
            else: agg["bp"]+=1; Bc[ao]+=1; bucket="b"     # partial folded into concerning
            by_year[y][bucket]+=1
    # fix struct double count: recompute struct as PRs with a solely-owned module
    # (above increments per module; redo cleanly)
    struct=defaultdict(int)
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
            mods_m=[m for m in modules_of(files[key]) if maintorgs(repo,m) is not None]
            if mods_m and any(maintorgs(repo,m)=={ao} for m in mods_m): struct[ao]+=1

    tot_capt=sum(captured.values())
    base=agg["a"]+agg["b"]+agg["bp"]+agg["c_no_resolved_maint"]-agg["x_no_module"]
    B=agg["b"]+agg["bp"]
    def pct(a,b): return f"{100*a/b:.1f}%" if b else "n/a"
    print("="*72)
    print(f"CORRECTED (org-level) — captured {tot_capt} PRs")
    print("="*72)
    print(f"  (x) no real module touched:        {agg['x_no_module']}")
    print(f"  (a) author-ORG maintains (EXCUSED):{agg['a']:6d}")
    print(f"  (c) no resolved-org maintainer:    {agg['c_no_resolved_maint']-agg['x_no_module']:6d}")
    print(f"  (b) other-org turf, no indep review:{B:6d}   <- SURVIVING capture (org-level)")
    print(f"       of which all-maintainers-resolved (high-conf): {b_allres}")
    denom=agg['a']+B+(agg['c_no_resolved_maint']-agg['x_no_module'])
    print(f"  (b) as % of module-touching captured: {pct(B,denom)}   | (a) {pct(agg['a'],denom)} | (c) {pct(agg['c_no_resolved_maint']-agg['x_no_module'],denom)}")
    print()
    print("PEOPLE-GATED LEADERBOARD (>=5 ppl, >=200 authored) — org-level (b):")
    print(f"  {'org':26s} {'ppl':>4s} {'auth':>6s} {'capt':>6s} {'(b)':>5s} {'b/auth':>7s} {'b/capt':>7s} {'struct%':>7s}")
    rows=[]
    for o in authored:
        if len(people[o])<5 or authored[o]<200: continue
        b=Bc[o]; rows.append((o,len(people[o]),authored[o],captured[o],b,
            100*b/authored[o],100*b/captured[o] if captured[o] else 0,
            100*struct[o]/struct_base[o] if struct_base[o] else 0))
    for o,pp,au,ca,b,ba,bc,st in sorted(rows,key=lambda r:-r[5]):
        print(f"  {o:26s} {pp:4d} {au:6d} {ca:6d} {b:5d} {ba:6.1f}% {bc:6.1f}% {st:6.1f}%")
    print()
    print("SURVIVING (b) by year (org-level):")
    for y in sorted(by_year):
        d=by_year[y]; print(f"  {y}: {d['b']:5d}")
    json.dump({"captured":tot_capt,"b_orglevel":B,"a":agg['a'],
               "c":agg['c_no_resolved_maint']-agg['x_no_module'],"b_allres":b_allres},
              open(os.path.join(HERE,"module-final-metrics.json"),"w"),indent=1)

if __name__=="__main__": main()
