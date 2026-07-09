#!/usr/bin/env python3
"""Generate the PUBLIC, reproducible aggregate dataset behind the OCA governance piece.
Org-LEVEL only (no individual logins — analysing company behaviour, not individuals).
Outputs CSVs: by-org, by-year, by-size, concentration. Every figure traces to raw GitHub
data in data/*.json + the identity/module caches, via the definitions in METHODOLOGY.md.
"""
import json, os, csv
from collections import defaultdict
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA=os.path.join(HERE,"data"); CACHE=os.path.join(HERE,"identity-company.json")
FILES=os.path.join(HERE,"files-cache.json"); MM=os.path.join(HERE,"module_maintainers.json")
OUTDIR=os.path.join(HERE,"dataset"); os.makedirs(OUTDIR,exist_ok=True)
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

ident=json.load(open(CACHE)); files=json.load(open(FILES)); mm=json.load(open(MM))
def org(l): return (ident.get(l) or {}).get("resolved_org")
def maintorgs(repo,mod):
    r=mm.get(f"{repo}/{mod}")
    if not (r and r.get("found") and r.get("maintainers")): return None
    return {org(x) for x in r["maintainers"] if org(x)}

people=defaultdict(set); authored=defaultdict(int)
selfserved=defaultdict(int); external=defaultdict(int); zero=defaultdict(int); indet=defaultdict(int)
Bcap=defaultdict(int)                       # module-controlled other-org-turf capture
revcredit=defaultdict(int)                  # approvals cast
by_year=defaultdict(lambda:defaultdict(int))
tot_auth=tot_rev=0

for f in os.listdir(DATA):
    if not f.endswith(".json"): continue
    repo=f[:-5]
    for pr in json.load(open(os.path.join(DATA,f))):
        y=(pr.get("mergedAt") or "----")[:4]
        if y<"2017": continue
        al=(pr.get("author") or {}).get("login"); ao=org(al)
        appr=la(pr.get("reviews"),al)
        for a in appr:
            ro=org(a)
            if ro: revcredit[ro]+=1; tot_rev+=1
        by_year[y]["total"]+=1
        if len(appr)<2: by_year[y]["lt2"]+=1
        if not ao: continue
        tot_auth+=1; authored[ao]+=1; people[ao].add(al)
        res=[a for a in appr if org(a)]; unres=len(appr)-len(res)
        out=[a for a in res if org(a)!=ao]
        if not appr: zero[ao]+=1; by_year[y]["zero"]+=1
        elif out: external[ao]+=1; by_year[y]["external"]+=1
        elif unres==0: selfserved[ao]+=1; by_year[y]["selfserved"]+=1
        else: indet[ao]+=1
        # module-controlled other-org-turf (b)
        if (not appr) or (unres==0 and not out):
            key=f"{repo}#{pr['number']}"
            if key in files:
                mods=[m for m in modules_of(files[key]) if maintorgs(repo,m) is not None]
                if mods:
                    owns=any(ao in maintorgs(repo,m) for m in mods)
                    others=any(ao not in maintorgs(repo,m) for m in mods)
                    if others and not owns: Bcap[ao]+=1

# by-org CSV (>=30 authored, org-level aggregates)
with open(os.path.join(OUTDIR,"oca-review-by-org.csv"),"w",newline="") as fh:
    w=csv.writer(fh,lineterminator="\n")
    w.writerow(["org","contributors","authored_prs","no_review_pct","self_served_pct",
                "external_reviewed_pct","self_of_reviewed_pct","other_org_turf_capture_prs","b_pct_of_authored"])
    for o in sorted(authored,key=lambda k:-authored[k]):
        au=authored[o]
        if au<30: continue
        ss=selfserved[o]; ex=external[o]; ze=zero[o]; revd=ss+ex
        w.writerow([o,len(people[o]),au,f"{100*ze/au:.1f}",f"{100*ss/au:.1f}",
                    f"{100*ex/au:.1f}",f"{100*ss/revd:.1f}" if revd else "0.0",Bcap[o],f"{100*Bcap[o]/au:.1f}"])

# by-year CSV
with open(os.path.join(OUTDIR,"oca-review-by-year.csv"),"w",newline="") as fh:
    w=csv.writer(fh,lineterminator="\n"); w.writerow(["year","merged_prs","pct_lt2_approvals","pct_zero_review","pct_self_served","pct_external_reviewed"])
    for y in sorted(by_year):
        d=by_year[y]; t=d["total"]; rt=d["zero"]+d["selfserved"]+d["external"]+0
        def pp(k,base): return f"{100*d[k]/base:.1f}" if base else "0.0"
        w.writerow([y,t,pp("lt2",t),pp("zero",t),pp("selfserved",t),pp("external",t)])

# by-size CSV
with open(os.path.join(OUTDIR,"oca-selfserve-by-orgsize.csv"),"w",newline="") as fh:
    w=csv.writer(fh,lineterminator="\n"); w.writerow(["org_size","n_orgs","authored_prs","self_served_pct_of_authored","self_served_pct_of_reviewed"])
    for name,lo,hi in [("1",1,1),("2-4",2,4),("5-9",5,9),("10-19",10,19),("20+",20,99999)]:
        A=SS=EX=0; norg=0
        for o in authored:
            n=len(people[o])
            if lo<=n<=hi and authored[o]>=20:
                A+=authored[o]; SS+=selfserved[o]; EX+=external[o]; norg+=1
        revd=SS+EX
        w.writerow([name,norg,A,f"{100*SS/A:.1f}" if A else "0.0",f"{100*SS/revd:.1f}" if revd else "0.0"])

# concentration CSV
def conc(d,tot):
    rows=sorted(d.values(),reverse=True); s=sum(rows); n=len(rows)
    top1=100*rows[0]/tot; top5=100*sum(rows[:5])/tot
    cum=0; n50=0
    for i,v in enumerate(sorted(d.values()),1):
        pass
    cum=0; n50=None
    for i,v in enumerate(sorted(d.values(),reverse=True),1):
        cum+=v
        if cum>=0.5*tot: n50=i; break
    vals=sorted(d.values()); gini=(2*sum((i+1)*v for i,v in enumerate(vals))/(n*s))-(n+1)/n
    return top1,top5,n50,gini,n
with open(os.path.join(OUTDIR,"oca-concentration.csv"),"w",newline="") as fh:
    w=csv.writer(fh,lineterminator="\n"); w.writerow(["dimension","total_events","distinct_orgs","top1_org_pct","top5_orgs_pct","orgs_for_50pct","gini"])
    t1,t5,n50,g,no=conc(authored,tot_auth); w.writerow(["authorship",tot_auth,no,f"{t1:.1f}",f"{t5:.1f}",n50,f"{g:.2f}"])
    t1,t5,n50,g,no=conc(revcredit,tot_rev); w.writerow(["approving_reviews",tot_rev,no,f"{t1:.1f}",f"{t5:.1f}",n50,f"{g:.2f}"])

print("wrote:", os.listdir(OUTDIR))
print("by-org rows (>=30 authored):", sum(1 for o in authored if authored[o]>=30))
print(f"totals: authored={tot_auth}  approvals={tot_rev}")
