#!/usr/bin/env python3
"""Tier-1 collection: merged PRs with author, mergedBy, reviews (no comments yet).
Usage:
  python3 scripts/1_collect_prs.py          # pilot 7 repos (quick sanity run)
  python3 scripts/1_collect_prs.py --all    # all OCA repos (full census)
Writes data/{repo}.json (list of PR dicts). Resumable — re-run to continue.
"""
import json, subprocess, sys, os, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

PILOT = ["sale-workflow", "timesheet", "hr", "project",
         "bank-statement-import", "web", "server-tools"]

def gh_json(args):
    r = subprocess.run(["gh"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:400])
    return json.loads(r.stdout)

def all_repos():
    repos, page = [], 1
    while True:
        chunk = gh_json(["api", f"/orgs/OCA/repos?per_page=100&page={page}",
                         "-q", "[.[].name]"])
        if not chunk:
            break
        repos += chunk
        page += 1
    return sorted(repos)

def fetch_repo(repo):
    out = os.path.join(DATA, f"{repo}.json")
    if os.path.exists(out) and os.path.getsize(out) > 2:
        try:
            existing = json.load(open(out))
            return len(existing), True  # already have it
        except Exception:
            pass
    try:
        prs = gh_json(["pr", "list", "-R", f"OCA/{repo}", "--state", "merged",
                       "-L", "200000", "--json",
                       "number,author,createdAt,mergedAt,mergedBy,reviews"])
    except Exception as e:
        print(f"  ! {repo}: {e}")
        return 0, False
    json.dump(prs, open(out, "w"))
    return len(prs), False

def main():
    census = "--all" in sys.argv
    repos = all_repos() if census else PILOT
    print(f"Fetching {len(repos)} repos ({'CENSUS' if census else 'PILOT'})")
    total = 0
    for i, repo in enumerate(repos, 1):
        n, cached = fetch_repo(repo)
        total += n
        tag = "cached" if cached else "fetched"
        print(f"[{i}/{len(repos)}] {repo}: {n} merged PRs ({tag})")
    print(f"TOTAL merged PRs: {total}")

if __name__ == "__main__":
    main()
