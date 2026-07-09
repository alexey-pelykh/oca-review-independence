#!/usr/bin/env python3
"""Build identity->company mapping for every login seen in data/*.json.
Resolvers (priority): profile company field -> non-generic email domain ->
public GH org membership (company-looking) -> username -company suffix.
Caches to identity-company.json; only queries new logins on re-run.
"""
import json, subprocess, os, re, sys, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(HERE, "identity-company.json")

GENERIC = {"gmail.com","hotmail.com","outlook.com","yahoo.com","proton.me",
           "protonmail.com","googlemail.com","live.com","icloud.com","me.com",
           "users.noreply.github.com","noreply.github.com","qq.com","163.com",
           "web.de","gmx.de","gmx.net","yandex.ru","mail.ru","free.fr","hey.com"}

# Canonicalize different surface forms of the same company to one key.
ALIASES = {
    # domain / name / gh-org variants  ->  canonical key
    "tecnativa.com":"tecnativa", "tecnativa s.l.":"tecnativa", "@tecnativa":"tecnativa",
    "camptocamp.com":"camptocamp", "camptocamp sa":"camptocamp",
    "acsone.eu":"acsone", "acsone sa/nv":"acsone",
    "akretion.com":"akretion", "akretion.com.br":"akretion", "akretion do brasil":"akretion",
    "moduon.team":"moduon", "dixmit.com":"dixmit",
    "forgeflow.com":"forgeflow", "eficent":"forgeflow", "eficent.com":"forgeflow",
    "vauxoo.com":"vauxoo", "hibou.io":"hibou", "quartile.co":"quartile", "quartile":"quartile",
    "onestein.nl":"onestein", "onestein.eu":"onestein",
    "sygel.es":"sygel", "apsl.net":"apsl", "aureatic":"aureatic",
    "nextev":"nextev", "trobz.com":"trobz", "sudokeys":"sudokeys",
    "grap.coop":"grap", "lefilament.com":"lefilament", "le filament":"lefilament",
    "coopiteasy.be":"coopiteasy", "coop it easy":"coopiteasy",
    "camptocamp":"camptocamp","tecnativa":"tecnativa","acsone":"acsone",
    "akretion":"akretion","moduon":"moduon","dixmit":"dixmit","vauxoo":"vauxoo",
    "onestein":"onestein","odoo.com":"odoo","odoo sa":"odoo","odoo":"odoo",
}

def canon(s):
    if not s: return None
    x = s.strip().lower().lstrip("@").strip()
    x = re.sub(r"[.,]?\s*(s\.?l\.?u?|s\.?a\.?s?|srl|gmbh|inc|ltd|llc|bv|nv|coop|sarl|sasu|pvt|co\.?)\.?$","",x).strip()
    x = re.sub(r"\s+"," ",x)
    return ALIASES.get(x, ALIASES.get(s.strip().lower().lstrip("@"), x)) or None

def gh(args):
    r = subprocess.run(["gh"]+args, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try: return json.loads(r.stdout)
    except Exception: return None

def collect_logins():
    logins=set()
    for f in os.listdir(DATA):
        if not f.endswith(".json"): continue
        for pr in json.load(open(os.path.join(DATA,f))):
            a=pr.get("author") or {}
            if a.get("login"): logins.add(a["login"])
            m=pr.get("mergedBy") or {}
            if m.get("login"): logins.add(m["login"])
            for rv in pr.get("reviews") or []:
                ra=(rv.get("author") or {}).get("login")
                if ra: logins.add(ra)
    return sorted(logins)

def resolve(login, cache):
    u = gh(["api", f"/users/{login}"])
    orgs = gh(["api", f"/users/{login}/orgs", "-q", "[.[].login]"]) or []
    company = (u or {}).get("company")
    email = (u or {}).get("email")
    dom = email.split("@")[-1].lower() if email and "@" in email else None
    if dom in GENERIC: dom=None
    # username suffix -company  e.g. andrii9090-tecnativa
    suffix = None
    m = re.search(r"-([a-z][a-z0-9]{2,})$", login.lower())
    if m and m.group(1) in {"tecnativa","camptocamp","acsone","moduon","akretion"}:
        suffix = m.group(1)
    org_keys = [canon(o) for o in orgs]
    org_key = None
    for ok in org_keys:  # prefer an org that is a known company alias
        if ok in ALIASES.values(): org_key=ok; break
    method=None; resolved=None
    if canon(company): resolved, method = canon(company), "company_field"
    elif dom: resolved, method = canon(dom) or dom, "email_domain"
    elif org_key: resolved, method = org_key, "gh_org"
    elif suffix: resolved, method = suffix, "username_suffix"
    return {"login":login,"company_raw":company,"email_domain":dom,
            "orgs":orgs,"resolved_org":resolved,"method":method,
            "name":(u or {}).get("name")}

def main():
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    logins = collect_logins()
    todo = [l for l in logins if l not in cache]
    print(f"{len(logins)} unique logins; {len(todo)} to resolve")
    for i,l in enumerate(todo,1):
        cache[l]=resolve(l,cache)
        if i%50==0:
            print(f"  {i}/{len(todo)}"); json.dump(cache,open(CACHE,"w"))
    json.dump(cache,open(CACHE,"w"),indent=0)
    resolved=sum(1 for v in cache.values() if v.get("resolved_org"))
    print(f"resolved {resolved}/{len(cache)} logins ({100*resolved//max(len(cache),1)}%)")
    by={}
    for v in cache.values():
        by[v.get("method")]=by.get(v.get("method"),0)+1
    print("by method:",by)

if __name__=="__main__":
    main()
