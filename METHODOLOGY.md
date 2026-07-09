# How OCA Code Gets Reviewed: Data & Methodology

*A reproducible analysis of review independence across the Odoo Community Association's entire GitHub history.*

Snapshot: **8 July 2026**. Author: Alexey Pelykh. All source data is public.

---

## 1. The question

For every code change merged into OCA, **who approved it** — an independent reviewer from a different company, a colleague at the author's own company, or nobody at all? And does that pattern change with the size of the company contributing?

This is a question about **review provenance**, measured from the public record. It is **not** a claim about the quality, intent, or content of any change. See §9 for what this analysis explicitly cannot say.

## 2. Data source

100% of the underlying data is public and comes from the GitHub REST/GraphQL API via the official `gh` CLI. No private data, no scraping of anything behind auth.

- **Scope:** all 261 repositories in the `OCA` GitHub organization.
- **Population:** every *merged* pull request in each repo, over the project's full lifetime.
- **Collected per PR:** number, author login, `createdAt`, `mergedAt`, `mergedBy`, and the full review list (each review's author, state, and `submittedAt`). For the subset with no cross-company approval, also the list of changed file paths.
- **Total collected:** 68,214 merged PRs across all years; **61,337** merged in 2017 or later (the analysis window).

### Why 2017+

GitHub's Pull Request **Reviews API did not exist before September 2016**. PRs merged before then carry zero review objects *by construction* — not because they went unreviewed. Including them would fabricate a "100% unreviewed" prehistory that is a data artifact, not a finding. Every rate in this analysis is therefore computed over **PRs merged 2017 or later**, where review data is complete.

## 3. Attributing a contributor to a company

OCA's own charter states members participate "as individuals … [so that] affiliations do not cloud the personal contributions." That is an ideal; this analysis measures the empirical reality, which requires linking a GitHub login to an employer. There is no canonical map (by design — see §6), so each login is resolved by **triangulation** of public signals, in priority order:

1. GitHub **profile `company` field** (primary; ~92% of resolved logins).
2. **Commit-author email domain** (e.g. `@tecnativa.com`).
3. **Username suffix** convention (e.g. `-tecnativa`, `-forgeflow`).
4. Public GitHub **organization membership**.

Company names are canonicalized (e.g. `Tecnativa S.L.` → `tecnativa`; `Eficent` → `forgeflow` after the known rebrand).

- **Coverage:** 79.3% of 2017+ merged PRs have a resolved author company (48,647 of 61,337).
- **Conservative rule — this is the load-bearing safeguard:** a login that cannot be resolved is treated as **`unknown`** and is **never** counted as sharing an author's company. An approval by an unknown reviewer counts as *independent/indeterminate*, never as self-serving. This means every "self-served review" figure is a **lower bound** — misattribution can only *understate* it.
- **Aggregate robustness:** because figures are org-level over thousands of PRs, a handful of individual misattributions cannot move a company's rate materially. A 55% self-serve rate over 10,148 PRs does not hinge on any one person's employer.

## 4. Definitions

For a merged PR authored by a contributor at company **X**, its review provenance is exactly one of:

| Category | Definition |
|---|---|
| **No review** | Zero approving reviews (excluding the author, excluding bots). |
| **Self-served** | ≥1 approving review, **every** approver resolved, **all** from company **X**, none external. |
| **Independent** | ≥1 approving reviewer from a company **other than X**. |
| **Indeterminate** | ≥1 approver whose company is `unknown` (cannot classify; excluded from rates). |

- **Approving review** = a GitHub review whose *latest verdict-bearing* state by that reviewer is `APPROVED`. A reviewer who approves and later leaves a plain `COMMENT` still counts as approving (the comment does not retract the approval). `COMMENTED`/`PENDING` states never count as approvals.
- **No independent review** = *No review* + *Self-served* (the change reached `main` without any outside company signing off).
- **Bots** (`oca-git-bot`, CI accounts, etc.) are excluded from all review counts.
- **Self-of-reviewed** = *Self-served* ÷ (*Self-served* + *Independent*): of the PRs that got *any* review, what share was colleague-only.

### Company-size gradient
Company size = count of distinct contributor logins resolved to that company. Orgs are bucketed (1 / 2–4 / 5–9 / 10–19 / 20+ people) and the self-serve rate reported per bucket. A one-person "company" cannot self-serve by definition (no colleague to approve).

### Concentration
For authorship and for approving-reviews separately: each company's share of the total, the top-1 and top-5 shares, the number of companies accounting for 50%, and the **Gini coefficient** (0 = perfectly even across all companies, 1 = one company does everything).

## 5. Module maintainership control (the fairness check)

A company reviewing its own PR is *expected and legitimate* when the PR touches a module that company **maintains** — OCA grants maintainers merge rights over their modules. To avoid mislabeling legitimate maintenance as capture, every no-independent-review PR was reclassified at **module** granularity:

- Each PR's changed files → the module(s) it touched → each module's **declared maintainers** (the `maintainers` key in the module's `__manifest__.py`) → those maintainers' companies.
- **(a) Excused:** the author's company maintains every touched module (a colleague-maintainer counts — this is an *org-level* test, not a login test).
- **(b) Other-org turf:** the author's company maintains *none* of the touched modules; they are another company's declared territory. This is the only bucket that could indicate reviewing outside one's remit.
- **(c) No declared maintainer:** the touched module declares no maintainer at all (~50% of cases; mostly older modules).

Result: of no-independent-review PRs, (a) excused ≈ 37%, (c) ambiguous ≈ 50%, **(b) other-org turf ≈ 14%** — with **no** company standing out as an outlier once maintainership is credited. The self-serve finding in §4 is a fact about *provenance*; this control shows most of it is legitimate territory maintenance, not cross-company imposition.

## 6. How an OCA merge actually works (sourced)

The reviewed-ness of a merge is a **social convention, not a mechanical gate**:

- `APPROVALS_REQUIRED` (default **2**) only sets the `approved` **label**; it is not referenced in the bot's merge task. — `OCA/oca-github-bot/.../config.py`
- `/ocabot merge` checks exactly two things: **green CI** and that the triggering user has **push access OR is a declared maintainer of all modified addons**. **No approval count. No author-≠-merger check.** — `OCA/oca-github-bot/.../tasks/merge_bot.py`
- CONTRIBUTING prose: "At least one of the review[s] above must be from a member of the PSC or having write access on the repository." — a norm, not enforced. — `OCA/odoo-community.org/.../CONTRIBUTING.rst`
- No canonical login→company map is published, by charter design. — `OCA/odoo-community.org/.../Organization.rst`

A contributor with push access or self-declared maintainership can therefore merge their own PR with zero external approvals, and the tooling permits it.

## 7. Corrections applied (adversarial review)

The first-pass numbers were wrong in four ways, each caught and fixed before publication. They are listed here because a methodology that hides its own error history is not trustworthy:

1. **Pre-2017 removal** — see §2. Dropped a 6,900-PR artifact era.
2. **Approve-then-comment** — a reviewer who approved then commented was wrongly un-counted (~3.7% of PRs). Fixed to latest-verdict-bearing state.
3. **Login → org maintainership** — a PR merged by one employee into a module maintained by a *colleague* was first mis-scored as "other-org turf." Corrected to an org-level test (§5), which moved ~1,140 PRs from (b) to (a) and roughly halved the apparent per-company capture.
4. **Current-snapshot maintainers** — see §8.

## 8. Merge-time verification

The maintainer list in a module's manifest is read at its *current* state, which could mask history: a company that merged another's module in 2019, then became its maintainer by 2026, would read as "excused" today. To test this, a stratified sample of **621** PRs (400 excused + 221 other-org-turf) was reclassified using each module's manifest **as it existed at that PR's actual merge commit**.

- **Hidden capture** (current-excused that was really other-org-turf at merge time): **1.5%** (95% CI ≤ ~3.2%).
- **False capture** (current-other-org-turf that was the company's own module at merge time): 4.1%.

The current-snapshot method is, if anything, slightly *generous* to the capture narrative — it does not hide it. The compression in §5 is real.

## 9. What this analysis CANNOT say

- **Nothing about the content or intent of any change.** "Self-served review" describes who approved, not whether the change was good, self-interested, or agenda-driven. Provenance ≠ motive.
- **Nothing about individuals.** All published figures are company-level aggregates. No per-person data is released.
- **21% of PRs are unattributed** (`unknown` company) and excluded from company rates.
- **Self-review is often legitimate** — see §5. High self-serve ≠ wrongdoing; it frequently reflects a company maintaining its own modules.
- **Correlation, not causation**, on the size gradient: large companies *can* self-review (they have colleagues); this does not establish that they do so to avoid scrutiny.

## 10. Reproduce it

Every figure derives from public GitHub data. To rebuild from scratch:
1. `gh pr list -R OCA/<repo> --state merged -L 200000 --json number,author,createdAt,mergedAt,mergedBy,reviews` for each of the 261 repos.
2. Resolve author/reviewer companies by the triangulation in §3.
3. Apply the definitions in §4 over PRs with `mergedAt` year ≥ 2017.
The aggregate outputs are in the accompanying CSVs (§11).

## 11. Data dictionary

- **`oca-review-by-org.csv`** — per company (≥30 authored PRs, 109 companies): contributors, authored PRs, and the % breakdown across no-review / self-served / external, plus the module-controlled other-org-turf count.
- **`oca-review-by-year.csv`** — per year: merged PRs and the % self-served / external / <2-approvals / zero-review. The erosion trend.
- **`oca-selfserve-by-orgsize.csv`** — per company-size bucket: the self-serve rate. The size gradient.
- **`oca-concentration.csv`** — authorship vs approving-reviews: top-1/top-5 share, companies-for-50%, Gini.
