# Task 008 — Green Finance Decision Engine and Financial Intelligence Backend

| Item | Value |
| --- | --- |
| Branch | `feature/task008-decision-engine`, created from verified `main` `12f536a5f8a36bf167852798e1b13fc4930a1677` (Task 007 integrated; clean tree) |
| Date | 2026-11-10 |
| Not done | No merge to `main`, no push, no deployment. No data acquisition, no model training, no dashboard UI |
| Database | `data/db/compassio_dev.sqlite`, SHA-256 `d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385`, unchanged before and after all work and tests |

## 1. Implemented features

| Area | Files |
| --- | --- |
| Evidence | `services/decision/evidence.py`: labelled financial facts, provenance, verified approval (GCF API), links, documents, completeness, limitations |
| Comparison | `services/decision/compare.py` |
| Funding intelligence | `services/decision/insights.py` |
| Prioritization | `services/decision/prioritize.py` |
| Budget scenarios | `services/decision/scenario.py` |
| Versions and rules | `services/decision/methodology.py` |
| Input errors | `services/decision/errors.py` |
| Finance helpers | `services/finance_rows.py` (see section 6) |
| Contracts and routes | `schemas/decision.py`, `api/v1/decision.py`; registered in `api/v1/__init__.py` and `api/errors.py` |
| Tests | `tests/api/test_decision_engine.py` (artificial fixture DB) and `tests/test_local_decision_engine.py` (real DB, read-only, `local_data`). `tests/api/test_system_endpoints.py` lists the new paths |
| Generated types | `apps/web/src/lib/api-types.ts` |
| Docs | `docs/product/financial_decision_workflow.md`, `docs/architecture/decision_engine_contract.md`, `docs/api/decision_engine_endpoints.md`. Updated: `api_contracts.md`, `phase_plan.md`, root and API `CLAUDE.md` |

**Endpoints** (all under `/api/v1`):
- `GET /decision/methodology`
- `GET /decision/evidence/{project_id}`
- `POST /decision/compare`, `POST /decision/prioritize`, `POST /decision/scenarios`
- `GET /analytics/funding-by-country`, `/analytics/funding-by-sector`, `/analytics/institutions`
- `GET /analytics/approved-vs-disbursed`, `/analytics/climate-distribution`, `/analytics/coverage`
- `GET /analytics/country-profile/{iso3}`

## 2. Project comparison

- **Side by side.** 2–10 records. Each record has:
  - title and identifier, source and publisher, rights status;
  - countries with mapping method, sector, institutions with roles;
  - description, year, source status, verified approval;
  - climate label or classification;
  - headline and breakdown facts, links, documents, warnings and a completeness map.
- **Comparable groups.** Figures are grouped by exact comparability key (source, flow, level,
  currency, price basis, row selection).
- **Totals.** A selection total is computed only through `aggregate`, and only when it is safe.
  Otherwise the total is `null` with a reason.
- **Summed and missing counts** are explicit for every group.
- **Duplicates.** Cross-source links get the same project key, so `aggregate` refuses to add
  them, and a `duplicate_warnings` entry is raised. Source record groups (AidData parent
  packages, ADB instruments) are flagged; AidData's "not recommended for aggregates" blocks a
  total.
- **Multi-country records** stay whole-project values. GCF's own country lines are shown as
  breakdown only.

## 3. Funding analytics

Every response declares:
- the metric, universe and financial meaning;
- currency, unit and price basis;
- whether the figure is funding;
- the known exclusions, with excluded-record counts by reason.

| Insight | What it does |
| --- | --- |
| By country / sector | Single-country records or GCF's own country lines; undated and multi-country rows are excluded and counted |
| Institutions | Record counts by role: funder, fund, implementer, delivery partner. No money |
| Approved vs disbursed | Only records reporting both in USD (paired); ratio within the pair set |
| Climate distribution | Rio-marker objective and strength; CFU, GCF and readiness themes as published |
| Coverage and freshness | Per-source rows, years, rights, latest completed import that wrote or re-verified the rows |
| Country profile | PAK profile: counts, every metric's all-years total, sectors, climate |

## 4. Prioritization

- **Seven user-weighted criteria:**
  - climate relevance (a label, not impact);
  - evidence completeness and funding completeness;
  - sector match and country match;
  - documentation;
  - review uncertainty.
- **Score.** Exact Decimal arithmetic. Each item carries its component values, contributions
  and evidence strings. Ties break by id.
- **Missing components.** The policy is explicit: `score_zero` or `exclude_from_denominator`.
- **Three distinctions per item.** Matches the search; has documented historical funding
  (repayments, pledges and total cost excluded); current opportunity is `not_determinable`.
- **Stable pagination.** A `ranking_fingerprint` plus a cache keyed on the data version.
- **Size limit.** The candidate set is capped at 2,000, with an explicit 422 above that.

## 5. Budget scenarios

- **Budget.** An exact budget with currency and unit.
- **Methods.** `equal`, `sector_priority` or `priority_score`.
- **Constraints.** Minimum and maximum per project, and maximum shares per sector and per
  country. Multi-country records form their own group.
- **Algorithm.** Water-filling at 50-digit precision, then deterministic cent rounding.
- **Conservation.** `allocated + unallocated == budget` holds exactly.
- **Statuses.** `allocated`, `partially_allocated` or `infeasible`.
- **Transparency.** An arithmetic trace, feasibility warnings, assumptions and disclosures.
- **Reproducibility.** Request and result SHA-256 and the data version.
- **Rejected objectives.** Return, emissions, cost-per-tonne, impact, risk-reduction and
  full-cost objectives get 422 `objective_not_supported`, with the reason the data cannot
  support them.

## 6. Financial integrity

`apps/api/src/compassio_api/services/finance.py` is **byte-identical to `main`**. It is
hash-pinned in `configs/task006_integration_reference.json`.

An earlier draft refactored it. The protected-file checkpoint test caught that, and the change
was reverted. The new helpers live in `services/finance_rows.py`, which reuses the protected
`_exclusion_reason` and sums only through `compassio_ml.finance.aggregate`.

The helpers' row selection cannot silently differ from the trends query, because two sets of
tests compare their totals:
- `test_insight_totals_never_drift_from_trend_totals` (artificial data, every metric, three
  countries);
- `test_country_totals_equal_existing_trend_totals` (real data, five metrics, PAK).

**Paths unchanged versus `main`:**
- `configs/`, `data/manifests/`, `packages/`;
- `apps/api/src/compassio_api/db/`;
- `services/finance.py`.

`git diff --stat main -- …` printed nothing for them.

## 7. Rights and security

- **Data access.** Every source-derived route uses `DataPolicyDep`. Public and production
  modes return 403 `source_rights_not_cleared`; this is tested for all 11 routes in both modes.
- **Methodology** is public, because it contains no source data.
- **Restricted records.** `restricted_internal` sources (`gcf_historical`) and non-visible
  records return 404.
- **No model inference, no writes.** The decision engine never runs a model and never writes.
  `financial_observations` checksums are equal before and after calling every endpoint, and the
  real DB file hash is unchanged.
- **Task 007 untouched.** Screening, review, ML v2 `development_candidate` status, the v1
  fallback and the sealed-evaluation protections are unchanged; the Task 007 tests pass.

## 8. API contracts

- Typed Pydantic models with `extra=forbid` on requests.
- Explicit `{code, message}` errors.
- OpenAPI summaries.
- Versioned methodologies.
- Stable pagination.
- Validated filters (ISO3 patterns, year ranges, bounded sizes).
- Generated TypeScript types, with a freshness test.

## 9. Real database verification

The real request and response examples are in `docs/api/decision_engine_endpoints.md`. They
were captured from a live `uvicorn` on 127.0.0.1:8018 in `local_development` mode.

**Highlights:**
- **AidData pair.** 35266 (448,000,000 USD) and 54087 (576,000,000 USD) nominal commitments are
  flagged as the same parent package. *Superseded by the Task 008 integration audit:* the 1.0.0
  comparison also returned their sum (1,024,000,000) as `selection_total`; since
  `compassio-comparison-1.1.0` that total is withheld (see
  `docs/phases/task008_final_integration_report.md`).
- **Cross-source pair.** CFU r10 and GCF FP005 are flagged; nothing is summed.
- **PAK approved vs disbursed (paired records):**

  | Source | Ratio | Records |
  | --- | ---: | ---: |
  | CFU | 0.3479 | 27 |
  | GCF API | 0.3883 | 6 |
  | ADB (commitments) | 0.6826 | 188 |

- **Disbursement totals.** ADB PAK disbursements are 21,549,925,012.94 USD, equal to an
  independent SQL sum of reported rows.
- **Ranking.** 31 CFU PAK candidates, top score 0.8667, fingerprint `149e0721…`.
- **Scenario.** 5,000,000 USD over 3 records: 1,666,666.67 + 1,666,666.67 + 1,666,666.66, with
  0.00 unallocated.

## 10. Automated test results

### Final gate run

Command: `bash scripts/check.sh`, run with the ML v2 environment variables of the combined
checkout. It exited 0:

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 282 files already formatted |
| `uv run mypy` (strict) | Success: no issues found in 216 source files |
| `uv run pytest` | **749 passed, 2 skipped** in 535.73 s |
| Web | `pnpm install --frozen-lockfile`, `pnpm lint`, `pnpm typecheck` and `pnpm build` all pass; routes `/` and `/screening` |

The two skips are expected and unchanged since Task 007:
- PostgreSQL is pending;
- no worksheets have been issued for this build.

Without the ML v2 environment variables, an earlier run had 6 extra environment-dependent
skips in `tests/test_local_ml_v2.py`.

### Task 008 tests

`uv run pytest tests/api/test_decision_engine.py tests/test_local_decision_engine.py` gave
**78 passed**: 65 on the artificial fixture database and 13 on the real database, read-only.

**What they cover:**
- **Comparison:** real comparisons, every flow kind, currency and unit incompatibility,
  double-counting prevention (cross-source links and source groups), multi-country and
  country-line handling, and missing dates and amounts.
- **Insights:** country and sector aggregation, and no drift from the trend totals.
- **Prioritization:** determinism, decomposition and pagination.
- **Scenarios:** budget conservation (including a 25-case seeded property check), caps,
  infeasibility and rejected objectives.
- **Rights and integrity:** 11 routes × public and production modes; restricted records;
  `financial_observations` unchanged; the real DB file hash unchanged.
- **Contracts:** OpenAPI paths and generated-type freshness.
- **Task 007:** compatibility, through the full suite.

### Integrity commands

| Command | Result |
| --- | --- |
| `uv run compassio-ml verify-frozen` | Frozen inputs match lock |
| `uv run compassio-v2 verify-baseline` | 11 PASS, "v1 baseline intact". Consumed tests are verified by hash only; no consumed-test evaluation was re-run |
| `uv run compassio-v2 verify-retrievals` | 5 OK |
| `uv run compassio-hash models/compassio_ccrc_v1/model.joblib` | `53b226f6…3656` (v1, unchanged) |
| `uv run compassio-hash data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/model.joblib` | `65433605…8574` (v2, unchanged) |
| `uv run compassio-db verify` | exit 0; 27 `match: true`, 0 `match: false` |
| `uv run compassio-hash data/db/compassio_dev.sqlite` | `d2b39add…d385`, unchanged after all tests |

### Issues found and fixed during the task

- **Protected file.** An earlier draft edited `services/finance.py`; `test_integration_boundaries`
  caught it. The file was restored and the helpers were moved to `services/finance_rows.py`.
- **Generated type names.** The TypeScript generator emitted `Budget-Input`, which is invalid
  TypeScript (FastAPI separates input and output schemas). Names are now sanitized to
  `Budget_Input`.
- **Pairing.** In approved vs disbursed, pairing counted rows with `not_reported` amounts. It
  now requires reported amounts.
- **Pledges.** A pledge was counted as documented funding. Pledges are now
  `is_funding_flow = false`.
- **Rounding.** Scenario rounding could leave 0.01 unallocated on an equal split of 100 three
  ways. The rounding target is now the budget minus the exact remainder.
- **Sector cap grouping.** Caps grouped sectors case-sensitively while priorities matched
  case-insensitively. Both are now case-insensitive.

## 11. Remaining limitations

- **Rights.** All sources are `not_reviewed`, so nothing is publicly displayable. Only
  `/decision/methodology` is public-safe.
- **No opportunity data.** There is no currently-open-funding data;
  `current_funding_opportunity` is always `not_determinable`.
- **Sector vocabularies** differ by source (AidData CRS, CFU OECD; none for GCF or ADB). Sector
  matching is case-insensitive substring or exact-name matching; no taxonomy mapping exists.
- **Prioritization performance.** About 2 s for roughly 740 candidates on first call (cached
  afterwards), with a cap of 2,000.
- **Approved vs disbursed timing.** The comparison mixes reporting cut-offs. CFU disbursement
  is cumulative at its update, and GCF disbursement lags approval.
- **Decimal precision.** Totals keep the source's own decimal precision, so some long decimals
  appear (for example CFU rows). They are exact, not rounded.
- **PostgreSQL** verification is still pending; the queries use only portable SQLAlchemy
  constructs.
