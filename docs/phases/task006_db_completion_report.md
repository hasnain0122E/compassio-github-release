# Task 006-DB completion report

## Scope

**Branch and boundaries:**

- Branch `main`; base `7f70654`.
- Concurrent ML v2 work is on `feature/ml-v2` in `D:/AI LEARNING/compassio-ml-v2`. That branch
  was **not touched**, and there was no merge, cherry-pick or push.
- **Not modified:**
  - `packages/compassio_ml/**`, `configs/**`;
  - `data/manifests/source_manifest.json` and the nine raw files (hashes re-verified);
  - the frozen research table and splits;
  - the v1 model and evaluation outputs.
- `uv.lock` is unchanged: no dependency was added.

## 1. Preconditions (verified before work)

| Check | Result |
| --- | --- |
| Branch | `main`, clean tree, HEAD contains `7f70654` |
| `compassio-manifest validate` | 9 entries match |
| `compassio-ml verify-frozen` | Matches the lock |
| `compassio-db verify` | Exit 0 |
| Frozen checksums | Plan `c4760503…`, lock `3d5b34d4…` |

## 2. Source counts, before → after (real database `data/db/compassio_dev.sqlite`)

| Table | Before (Task 006) | After |
| --- | ---: | ---: |
| Project rows | 25,623 | **26,499** (+876 GCF readiness grants) |
| Financial observations | 85,765 | **93,881** (+876 readiness, +7,240 GCF API) |
| Climate / source annotations | 25,430 | 26,020 (+590 readiness activity labels) |
| Country rows | 26,321 | 27,430 |
| Warnings | 43,204 | 45,020 |
| Documents | — | 818 (498 families) |
| Country aggregates | — | 620 (155 countries × 4 measures) |
| Historical staging (restricted) | — | 128 |
| Enrichments | — | 379 |

**Unchanged:** AidData 20,985, GCF export 379, CFU 4,066 and ADB 193 rows, with every
pre-existing audited figure still matching.

**First upgrade run:** the core rows were re-written once as "updated". The observation record
gained `country_iso3`, which changes each record's content hash. Counts were unchanged, and the
second full run wrote **nothing** in any of the 9 source keys.

## 3. New source acquired

One snapshot from the official GCF Open Data Library API:

| Field | Value |
| --- | --- |
| Request | `https://api.gcfund.org/v1/projects`, one request |
| Snapshot | `20261109T144534Z` |
| Size / SHA-256 | 2,852,244 bytes, `14624289…a9f3dc` |
| Records | 393 |
| Publisher update date | Not stated |
| Rights | `not_reviewed` |

Details: `docs/data/backend_source_registry.md`.

## 4. GCF date and finance coverage (`compassio-db report gcf-enrichment`)

| Measure | Value |
| --- | --- |
| Matched | 379/379 (by code only); 14 API-only codes reported, not ingested |
| Verified approval dates | **379** (`ApprovalDate`; start and end dates kept separately) |
| Status | **379**, as retrieved; no as-of date is published |
| Currency-stated GCF financing | **379** |
| Official URL | **379** |
| Proposal or document URLs from the API | **0**. Not published; 121 projects have CPE documents instead. |
| Conflicts | 54 within the API (country lines vs total); **0 cross-record** |
| Pakistan | 11/11 complete, including GCF-published Pakistan shares for multi-country FP215, FP254 and FP283 |

**Pakistan GCF funding by approval year** (GCF's own country split, USD):

| Year | Amount |
| ---: | ---: |
| 2016 | 36,960,000 |
| 2018 | 49,000,000 |
| 2019 | 34,990,832 |
| 2022 | 10,000,000 |
| 2023 | 90,000,005 |
| 2024 | 83,276,281 |
| 2025 | 27,500,000 |

These are approvals, not disbursements or opportunities.

**Hazards in the API itself, handled:**

- FP086 and FP103 re-list funding lines under a later Board meeting. They are kept apart, and no
  date is invented for them.
- 40 projects have EUR lines, which are never converted.
- A consistency gate admits only line sets that reproduce GCF's total: 339 funding-line sets and
  325 country-line sets.

## 5. Remaining source integration

| Source | Result |
| --- | --- |
| GCF readiness | 876 rows: 828 with stable codes, 48 by row position. Currency not stated, so metric unavailable. Not counted as funded projects. |
| Climate Project Explorer | 818 documents, 0 project rows. Date type stated (catalogue family date, not approval). |
| GCF country summaries | 620 aggregate rows, snapshot 2026-11-08 (assumed from the file name), never summed with projects |
| GCF historical | Provenance unverified, so **restricted internal staging** (never served). 122 parsed / 5 unparseable / 1 missing in USD thousands. Comparison with the API: 39 equal, 79 differ, 10 not comparable. |

All 7 new audited figures match: readiness 876, countries 155, CPE 818/498, 121 GCF projects
with documents, historical 128/123.

## 6. New relationships

| Relationship | Count |
| --- | --- |
| CFU → GCF links (provenance fields added) | 329 |
| Document → GCF project | 288 links: 280 deterministic, 8 multi-code candidates |
| ADB instrument → project groups | 143 groups / 193 instruments |
| AidData parent packages | 2,299 / 6,416 |
| GCF export ↔ API enrichments | 379 |

Verification states are categorical, never probabilities. Title similarity creates no links.

## 7. Financial reconciliation (`compassio-db report reconciliation`): all checks 0

| Check | Result |
| --- | ---: |
| Duplicate observation keys | 0 |
| Duplicate enrichments | 0 |
| API observations on non-GCF projects | 0 |
| API project totals carrying a currency | 0 |
| Country aggregates in financial observations | 0 |
| Documents counted as projects | 0 |
| Readiness rows counted as funded projects | 0 |

Every metric is single-source, so the GCF export and API amounts are never added together.

## 8. Search and API performance

**Search** used an FTS5 trigram pre-filter plus the unchanged `LIKE`. Results are identical (13
real queries, 0 mismatches).

| Query | Before | After |
| --- | ---: | ---: |
| `solar` | 432 ms | 26 ms |
| `climate resilience` | 467 ms | 29 ms |
| No match | 591 ms | 14 ms |

**Live uvicorn on 127.0.0.1:** 7–32 ms for search, detail, documents, timeline and aggregates.

**Production mode:** 403 on all source-derived routes, while `/health` and `/sources` return 200.

## 9. PostgreSQL

**PENDING.** No PostgreSQL, Docker or WSL is available, and no system install was made.

- Compile-only DDL and SQL checks pass.
- The execution test is reported as **skipped**.

Steps are in `docs/architecture/postgresql_verification.md`.

## 10. Rights

- All 10 sources are `not_reviewed`, and the backend registry cannot express a clearance.
- New fields and routes respect the rights gate:
  - API lines, enrichments and documents are hidden when their own source isn't cleared;
  - `gcf_historical` is never served.
- Only document metadata and URLs are stored. No PDFs or full proposal text are stored.

## 11. Tests

| Test set | Result |
| --- | --- |
| New unit tests (artificial fixtures) | 65 run + 1 skipped: registry 8, enrichment 7, remaining sources 8, FTS 12, discovery/rights 15, PostgreSQL compile-only 15 (+1 execution test skipped) |
| New local-data tests | 7, against real files and the snapshot |
| Full suite and gates | `bash scripts/check.sh`: **494 passed, 1 skipped**; ruff, format (187 files), strict mypy (149 files), web lint, typecheck and build all passed. Also passing: `compassio-manifest validate`, `verify-frozen`, `compassio-db registry`, `compassio-db verify`; raw hashes unchanged. |

## 12. Commands (PowerShell, repository root)

```powershell
uv sync --locked
uv run compassio-db migrate                               # -> 0003
uv run compassio-db fetch --source gcf_api_projects       # optional NEW snapshot
uv run compassio-db registry
uv run compassio-db ingest --source all
uv run compassio-db verify --report artifacts/db/integrity_report.json
uv run compassio-db report gcf-enrichment --out artifacts/db/report_gcf-enrichment.json
uv run compassio-db report reconciliation --out artifacts/db/report_reconciliation.json
uv run compassio-db report historical-comparison --out artifacts/db/report_historical-comparison.json
$env:COMPASSIO_SOURCE_DATA_ACCESS = "local_development"
uv run uvicorn compassio_api.main:app --host 127.0.0.1 --port 8000
```

## 13. Merge and integration notes for `feature/ml-v2`

- **Files touched:** only `apps/api/**`, `tests/api/**`, `tests/test_local_db*.py`, `docs/**`,
  `README.md`, `CLAUDE.md`, `.gitignore`, `data/raw_db/README.md` and
  `data/manifests/backend_source_registry.json` (a **new** file).
- **Likely conflicts:**
  - `CLAUDE.md` "Current stage", `docs/phases/phase_plan.md` and `.gitignore` are shared text
    files. Resolve them by hand.
  - `pyproject.toml` and `uv.lock`: no changes here.
- **GCF API terms:** the snapshot carries `ai-train=no`. If ML v2 wants GCF data for labelling or
  training, it must take its own snapshot, review the terms first, and reconcile by SHA-256.
- **Canonical registration:** registering backend sources in the canonical manifest is a proposal
  (`backend_source_registry.md` §5) for after ML v2 merges.
