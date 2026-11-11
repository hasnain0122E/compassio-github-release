# Task 008 final integration report

Audit of the Task 008 decision engine (`feature/task008-decision-engine`, `830f8be`) before a
fast-forward into `main`. Date: 2026-11-10. Machine: Windows 11 Pro, Intel Core i7-10750H
(12 logical CPUs), 15.8 GB RAM, Python 3.12.15, uv 0.13.0, Node 24.19.0, pnpm 11.21.0.

## 1. Git state before integration

| Check | Result |
| --- | --- |
| `main` | `12f536a5f8a36bf167852798e1b13fc4930a1677` (unchanged since Task 007 integration) |
| Task 008 commit | `830f8be`; parent `12f536a`; `git merge-base --is-ancestor main HEAD` → true |
| Working tree | clean (`git status --porcelain` → 0 lines) |
| Safety branch | `safety/task008-pre-promotion-main-12f536a` at `12f536a` |

## 2. Audit findings

### 2.1 Confirmed defect (fixed): same-package AidData pair summed in a comparison

`POST /decision/compare` with `["gcf_projects:FP085", "aiddata:35266", "aiddata:54087"]`
returned:

- `selection_total` **"1024000000"** (448,000,000 + 576,000,000 USD nominal) and
  "1185503772.195523" (constant 2021 USD), status `available`;
- **and** a `duplicate_warnings` entry `same_source_record_group` for the same two records
  (AidData parent package `aiddata_parent:1648`).

Both records carry `recommended_for_aggregates = 1`, so the arithmetic matched an independent
SQL sum and `aggregate` accepted it. But the response presented that sum as a user-facing total
while simultaneously warning that the records are one source package, which a reader could take
as an aggregate of the package (possibly incomplete or double counted at package level).

**Fix (`compassio-comparison-1.1.0`):** in `services/decision/compare.py`, a comparison group's
`selection_total` is withheld (`null`, `unavailable`, reason "At least two of these records
belong to the same source record group …") whenever two contributing records share a
`group_key` (AidData parent package or ADB project number). Each record's own figure is still
shown. The duplicate-warning text and `RULES` in `methodology.py` state the rule.

**Regression tests:**
- `tests/test_local_decision_engine.py::test_real_same_package_pair_is_never_summed` (real DB,
  read-only): both AidData groups `null`, reason present, both cells shown, warning lists the pair.
- `tests/api/test_decision_engine.py::test_missing_amounts_are_counted_not_added` (artificial
  ADB records sharing one project number): total withheld with the same reason. The positive
  case (`aiddata:1` + `aiddata:2`, different packages) still sums exactly (`200.20`, `400.50`).

**Docs updated:** `docs/architecture/decision_engine_contract.md` §3,
`docs/api/decision_engine_endpoints.md` (example marked as changed in 1.1.0),
`docs/phases/task008_completion_report.md` (AidData highlight superseded).

### 2.2 Reviewed, no defect

- **Routes and rights.** 12 Task 008 routes; all but `GET /decision/methodology` depend on
  `DataPolicyDep` (rights matrix test: 11 routes × {public, production} → 403).
- **Financial meaning.** Pledges, total project cost and repayments are `is_funding_flow=false`;
  approved/disbursed pairing uses reported amounts only; country totals equal `/analytics/trends`
  totals (real-DB tests, 5 metrics); ADB PAK disbursements equal an independent SQL sum
  (21,549,925,012.94 USD).
- **Cross-source links** cluster into one `project_key`, so `aggregate` refuses to add them.
- **Determinism.** Prioritization fingerprint and scenario hashes reproduced byte-identically
  on the live replay (section 4).

## 3. Protected assets

| Asset | Check | Result |
| --- | --- | --- |
| `services/finance.py`, `db/` (models, migrations), `packages/`, `configs/`, `data/manifests/` | `git diff main --stat -- …` | no changes |
| Hash-pinned files | `test_frozen_sources_labels_finance_and_release_code_match_checkpoint` | pass |
| SQLite DB | `uv run compassio-hash data/db/compassio_dev.sqlite` (before and after all tests and the live server) | `d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385` |
| DB integrity | `uv run compassio-db verify` | 27/27 audited comparisons match; structural checks ok; `restricted_internal_sources: [gcf_historical]`; `sources_cleared_for_public_display: []` |
| ML v1 | `compassio-hash models/compassio_ccrc_v1/model.joblib` | `53b226f6…3656` (= `configs/inference_models.yaml`) |
| ML v2 | `compassio-hash data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/model.joblib` | `654336052b…8574` (= registry) |
| Frozen split | `uv run compassio-ml verify-frozen` | "Frozen inputs match lock" |
| Sealed evaluations | `uv run compassio-v2 verify-baseline` | 2 consumed tests PASS, "v1 baseline intact" (not re-run) |
| Retrievals | `uv run compassio-v2 verify-retrievals` (full output, exit 0) | **5 snapshots OK**: gcf_project_pages 20261109T143506Z, iati_ec_intpa 20261109T161101Z and 20261109T161933Z, iati_fcdo 20261109T143506Z, worldbank_projects 20261109T143438Z |

## 4. Live reproduction of the Task 008 API examples

`uvicorn compassio_api.main:app --host 127.0.0.1 --port 8018` with
`COMPASSIO_SOURCE_DATA_ACCESS=local_development`; the 15 documented requests were replayed and
compared field by field with the original capture (ignoring timings):

- 11 responses identical (all analytics, prioritization incl. fingerprint, both scenarios,
  both 422s);
- 4 differ only as intended: `methodology_version` / `comparison_version` 1.0.0 → 1.1.0, the new
  rule, and the two AidData `selection_total`s now `null` with the reason.

## 5. Gates (`bash scripts/check.sh`, ML v2 env set)

| Gate | Result |
| --- | --- |
| uv sync --locked, ruff check, ruff format --check | pass |
| mypy (strict) | Success: no issues found in 216 source files |
| pytest | **749 passed, 2 skipped** in 444 s (skips: PostgreSQL execution pending; no human worksheets issued) |
| `scripts/generate_api_types.py --check` | up to date |
| web: pnpm install --frozen-lockfile, lint, typecheck, build | pass |

Task 008 tests: 78 passed (65 artificial, 13 real DB read-only).

**Erratum (retrievals).** An interim progress message said "verify-retrievals 3 OK". That
figure came from viewing the command through `tail -3`, not from the command's result. The full
output (re-run on 2026-11-10, exit 0) lists 5 OK snapshots, the same as the Task 008 report.
No retrieval changed.

## 6. Promotion

All gates passed and `main` had not advanced, so `main` was fast-forwarded (`git merge
--ff-only`) from `12f536a` to `62a1a17` (Task 008 integration commit). No push, no deployment.
