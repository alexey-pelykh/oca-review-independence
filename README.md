# OCA Review Independence

**How communal is review in the [Odoo Community Association](https://odoo-community.org/), really? A reproducible measurement.**

I contribute to OCA myself, so I wanted a number instead of a hunch: when a change gets merged, who approved it? An independent reviewer from a *different* company, a colleague at the author's *own* company, or *nobody* at all? And does that shift with the size of the company contributing?

This repository is that measurement with its work shown — the full collection, company-attribution, and analysis pipeline plus the aggregate dataset, so anyone can rebuild every figure from public GitHub data and check the math.

It measures review **provenance**, not **quality**: who signed off, never whether the change was good, self-interested, or agenda-driven. Mechanism, not motive. See [What this cannot say](#what-this-cannot-say).

---

## What the data shows

All figures are over PRs merged **2017 or later** (the GitHub Reviews API did not exist before then — see [METHODOLOGY.md §2](METHODOLOGY.md)). Population: **68,214** merged PRs across all 261 OCA repositories; **61,337** merged 2017+; **48,647** (79.3%) with a resolvable author company.

**1. Sign-off is a social convention, not a mechanical gate.** `/ocabot merge` checks exactly two things: green CI, and that the triggering user has push access or is a declared maintainer of the touched modules. No approval count. No author-≠-merger check. A contributor with push access, or who maintains the touched module, can merge their own PR with zero external approvals, and the tooling permits it. *(Sourced to OCA's own bot code — [METHODOLOGY.md §6](METHODOLOGY.md).)*

**2. Self-review scales with company size.** The share of a company's own PRs approved only by its own people, by company headcount:

| Company size (distinct contributors) | Self-served share of *reviewed* PRs |
|---|---|
| 1 person | 0.1% |
| 2–4 | 3.8% |
| 5–9 | 15.1% |
| 10–19 | 16.1% |
| **20+** | **55.6%** |

A one-person company *cannot* self-serve — it has no colleague to approve. The largest firms review their own work internally more than half the time. *(`dataset/oca-selfserve-by-orgsize.csv`)*

**3. A handful of companies hold the keys.** Across 634 contributing companies, five wrote almost half of everything merged:

| Company | Merged PRs | Self-review rate | On others' turf |
|---|---|---|---|
| Tecnativa | 10,148 | 66.7% | 5.8% |
| ForgeFlow | 4,646 | 28.3% | 2.2% |
| Akretion | 4,006 | 8.4% | 0.8% |
| Camptocamp | 2,308 | 11.5% | 3.3% |
| Acsone | 2,306 | 8.3% | 1.9% |

*Self-review rate = share of the company's reviewed PRs approved only by its own people. On others' turf = share of its own PRs merged with no outside review onto a module another company maintains.*

The top 5 account for **48%** of all authorship (Gini 0.91); across 496 reviewing companies, the top 5 cast **51%** of all approvals (Gini 0.93). Six companies produce half of everything merged. Tecnativa alone authored over 10,000 — more than double the next contributor — and self-reviews 66.7% of its *reviewed* PRs, but just 5.8% of its merges land on modules another company maintains: self-review at scale, overwhelmingly its own code. Attribution is by GitHub org name, so a few firms contributing under more than one appear split, and these per-name totals run conservative. *(`dataset/oca-review-by-org.csv`, `dataset/oca-concentration.csv`)*

**4. Independent review used to be the norm. Now it's a coin flip.** The share of merged PRs with an approver from an outside company slid from **67.5% in 2017** to a trough of **40.8% in 2023**, then recovered to **47.8% in 2025** — still well below the clear majority it once was. (2026 is a partial year, excluded from the trend.) *(`dataset/oca-review-by-year.csv`)*

**5. Most self-review is legitimate maintenance — not turf capture.** OCA grants module maintainers merge rights over their own modules, so a company approving its own PR on a module *it maintains* is expected and legitimate. Controlling for declared maintainership at module granularity, only **~14%** of no-independent-review PRs touch another company's turf; ~37% are the author's own maintained modules and ~50% touch modules with no declared maintainer at all. Once maintainership is credited, **no single company stands out as an outlier**. *(See [METHODOLOGY.md §5](METHODOLOGY.md); verified at merge-time in §8.)*

### The one-line version

Independent review holds for most of OCA, but it thins out at scale: the largest firms review far more of their own work internally, and the tooling permits it. Whether that is a *problem* is a governance question for OCA. This data measures the mechanism, not the motive.

---

## What this cannot say

- **Nothing about the content or intent of any change.** "Self-served review" describes who approved, not whether the change was good or self-interested. Provenance ≠ motive.
- **Nothing about individuals.** Every published figure is a company-level aggregate. No per-person data is released.
- **21% of PRs are unattributed** (author company could not be resolved) and are excluded from company rates. A login that cannot be resolved is *never* counted as sharing an author's company — so every self-serve figure is a **lower bound**.
- **Correlation, not causation**, on the size gradient. Large companies *can* self-review because they have colleagues; this does not establish that they do so to avoid scrutiny.

Full caveats: [METHODOLOGY.md §9](METHODOLOGY.md).

---

## The dataset

Four aggregate CSVs in [`dataset/`](dataset/), all company-level (no personal data):

| File | What it holds |
|---|---|
| `oca-review-by-org.csv` | Per company (≥30 authored PRs, 109 companies): contributors, authored PRs, and the % breakdown across no-review / self-served / externally-reviewed, plus the module-controlled other-org-turf count. |
| `oca-review-by-year.csv` | Per year: merged PRs and the % self-served / externally-reviewed / <2-approvals / zero-review. The erosion trend. |
| `oca-selfserve-by-orgsize.csv` | Per company-size bucket: the self-serve rate. The size gradient. |
| `oca-concentration.csv` | Authorship vs approving-reviews: top-1 / top-5 share, companies-for-50%, Gini coefficient. |

Plus [`dataset/OCA-Review-Methodology.pdf`](dataset/OCA-Review-Methodology.pdf) — the full methodology as a standalone document.

---

## Reproduce it

Everything derives from public GitHub data via the official `gh` CLI. No private data, no scraping behind auth.

### Prerequisites

- [`gh`](https://cli.github.com/) authenticated (`gh auth login`)
- Python 3.9+ (standard library only — no third-party packages needed for the pipeline)

### Run order

```bash
python3 scripts/1_collect_prs.py         # → data/{repo}.json     (every merged PR + its reviews)
python3 scripts/2_attribute_companies.py # → identity-company.json (login → company, by triangulation)
python3 scripts/3_collect_files.py       # → files-cache.json      (changed paths for no-ext-review PRs)
python3 scripts/4_collect_maintainers.py # → module_maintainers.json (each module's declared maintainers)
python3 scripts/5_analyze.py             # prints the headline classification
python3 scripts/6_make_dataset.py        # → dataset/*.csv         (the four aggregate CSVs)
python3 scripts/7_verify_merge_time.py   # merge-time verification of the maintainership control
```

Steps 1, 3, and 4 hit the GitHub API across 261 repositories and take hours; all three are **resumable** (re-run to continue from cache). Steps 5 and 6 are local and take seconds. `6_make_dataset.py` regenerates the exact CSVs committed here.

The raw per-PR data (`data/`) and the intermediate caches are **not** committed — they contain per-login information, and the scripts regenerate them from scratch. See [`.gitignore`](.gitignore).

---

## Companion article

**[How Communal Is OCA Review, Really?](https://alexey-pelykh.com/blog/oca-review-independence/)** — a written walkthrough of these findings: what they mean for OCA governance, and how the analysis survived its own corrections.

---

## Honesty about corrections

The first-pass numbers were wrong in four ways, each caught and fixed before publication — a pre-2017 data artifact, an approve-then-comment miscount, a login-vs-company maintainership bug, and a current-snapshot maintainer question resolved by merge-time verification. They are documented in [METHODOLOGY.md §7](METHODOLOGY.md), because a methodology that hides its own error history is not one you should trust.

---

## License

- **Code** (everything in `scripts/`): [MIT](LICENSE).
- **Data** (`dataset/*.csv`, `dataset/*.pdf`) and **`METHODOLOGY.md`**: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — use it, cite it as *"Alexey Pelykh, OCA Review Independence (2026)."*

All underlying data is public and belongs to its respective GitHub authors and the OCA.
