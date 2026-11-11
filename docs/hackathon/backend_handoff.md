# Backend handoff for Task 010 (frontend at the venue)

The single entry point for frontend developers. Start the backend with
`docs/hackathon/local_demo_runbook.md`, then build the screens in
`docs/hackathon/frontend_blueprint.md`.

| Need | Where |
| --- | --- |
| OpenAPI 3 spec (committed, freshness-tested) | `docs/api/openapi.json`; live at `http://127.0.0.1:8000/openapi.json`, interactive at `/docs` |
| TypeScript types (generated, never hand-edited) | `apps/web/src/lib/api-types.ts` (`uv run python scripts/generate_api_types.py`) |
| Real request/response examples | `docs/hackathon/demo_api_examples.md` |
| Data permission and attribution | `docs/hackathon/data_permission_scope.md` |
| Detailed contracts | `docs/architecture/api_contracts.md`, `docs/architecture/decision_engine_contract.md`, `docs/api/decision_engine_endpoints.md` |

Base URL: `http://127.0.0.1:8000`. All data routes are under `/api/v1`. JSON only. CORS allows
`http://localhost:3000` and `http://127.0.0.1:3000` (methods GET, POST; headers `Content-Type`,
`X-Compassio-Review-Token`).

## 1. Endpoints (33 paths, 33 operations)

| Method | Path | Purpose | Source data? |
| --- | --- | --- | --- |
| GET | `/health` | Liveness (unversioned) | no |
| GET | `/api/v1/meta` | Product name, tagline, API version | no |
| GET | `/api/v1/sources` | Sources with publisher, URL, version, rights status, licence notes | metadata only |
| GET | `/api/v1/filters` | Filter options (sources, countries, sectors, years, statuses) | yes |
| GET | `/api/v1/projects` | Search and list (paginated) | yes |
| GET | `/api/v1/projects/{project_id}` | Detail: financial observations, annotations, links, group, enrichments, documents | yes |
| GET | `/api/v1/documents` | Climate Project Explorer documents | yes |
| GET | `/api/v1/analytics/overview` | Record counts and coverage | yes |
| GET | `/api/v1/analytics/metrics` | The 11 registered money metrics and their meaning | yes |
| GET | `/api/v1/analytics/trends?metric=` | Yearly totals for one metric (optional `country`, years) | yes |
| GET | `/api/v1/analytics/data-quality` | Data-quality warnings | yes |
| GET | `/api/v1/analytics/financing-completeness` | Which money fields are reported | yes |
| GET | `/api/v1/analytics/gcf-timeline` | GCF approval timeline | yes |
| GET | `/api/v1/analytics/country-aggregates` | GCF country summaries (aggregates, not project sums) | yes |
| GET | `/api/v1/analytics/relationships` | Cross-source link statistics | yes |
| GET | `/api/v1/analytics/funding-by-country?metric=` | Totals per country with metric declaration | yes |
| GET | `/api/v1/analytics/funding-by-sector?metric=` | Totals per sector | yes |
| GET | `/api/v1/analytics/institutions` | Institutions by role (counts only) | yes |
| GET | `/api/v1/analytics/approved-vs-disbursed` | Paired approved vs disbursed, per source | yes |
| GET | `/api/v1/analytics/climate-distribution` | Rio markers and fund themes | yes |
| GET | `/api/v1/analytics/coverage` | Per-source coverage and freshness | yes |
| GET | `/api/v1/analytics/country-profile/{iso3}` | One-country summary (e.g. `PAK`) | yes |
| GET | `/api/v1/decision/methodology` | Versions, criteria, rules, disclaimers | no (public-safe) |
| GET | `/api/v1/decision/evidence/{project_id}` | Normalized evidence: facts, institutions, completeness | yes |
| POST | `/api/v1/decision/compare` | Side-by-side comparison of 2–10 records | yes |
| POST | `/api/v1/decision/prioritize` | Deterministic, explainable ranking | yes |
| POST | `/api/v1/decision/scenarios` | Hypothetical budget allocation | yes |
| GET | `/api/v1/models` | Models, statuses, operational mode | no |
| GET | `/api/v1/models/comparison` | Fixed v1 vs v2 development-validation aggregates | no |
| POST | `/api/v1/screening/text` | Screen title/description text | model only |
| POST | `/api/v1/screening/projects/{project_id}` | Screen a DB record (AidData only) | yes |
| POST | `/api/v1/reviews` | Record a human review (token required) | writes review store |
| GET | `/api/v1/reviews/{screening_id}` | Reviews of a saved screening (token required) | review store |

Every `/api/v1` response carries the header `X-Compassio-Data-Access`
(`hackathon_event` | `local_development` | `public`). Source-derived bodies include
`access: {mode, notice}`: **show the notice**.

## 2. Identifiers

- **Project id:** `<source_id>:<source record id>`, e.g. `aiddata:35266`,
  `gcf_projects:FP085`, `adb_pakistan:XM-DAC-46004-54097-001-LN4745`,
  `climate_funds_update:projects-r10`. URL-encode it in paths.
- **Field name:** `/projects` and `/projects/{id}` call it `id`; the decision, screening and
  analytics responses call the same value `project_id`. They are interchangeable.
- **Stability:** ids are stable for the pinned database (SHA-256 `d2b39add…d385`). CFU ids are
  row positions in the CFU export and would change if that source were re-imported.
- `screening_id` is a UUID (36 characters), only for saved screenings.

## 3. Pagination, filters, sorting

- **`/projects`:** `page` (≥ 1, default 1), `page_size` (1–100, default 25),
  `sort` ∈ `id`, `-id`, `year`, `-year`, `title`, `-title` (default `id`; ties broken by id;
  nulls last). Filters: `q` (literal, case-insensitive text search, 1–200 chars),
  `country` (ISO3, e.g. `PAK`), `source`, `sector`, `year_from`, `year_to`,
  `climate_related` (true/false, AidData research annotation). Response: `items`,
  `pagination {page, page_size, total_items, total_pages}`, `applied_filters`, `sort`,
  `access`, `empty_result_message` (set when nothing matches or the page is past the end).
- **`/decision/prioritize`:** filters in the body (`filters: {q, country, source, sector,
  year_from, year_to, project_ids}`); `page`, `page_size` (≤ 100) in the body. At most 2,000
  candidates (else 422 `candidate_set_too_large`). Ordering is by score, then `project_id`.
  `ranking_fingerprint` identifies the exact ranking: if it changes between pages, re-query.
- **Analytics:** `metric` from `/analytics/metrics`; optional `country`, `year_from`, `year_to`,
  `limit` where documented in OpenAPI.

## 4. Errors

Every error body has `code` and `message`. Validation errors (422 `invalid_request`) also carry
`detail: [{loc, msg, type}]`; submitted values are never echoed.

| HTTP | `code` | Meaning / UI action |
| --- | --- | --- |
| 400 | `invalid_content_length` | Malformed request |
| 401 | `invalid_review_token` | Review token missing or wrong |
| 403 | `source_rights_not_cleared` | Mode serves no source data (public/production, or event window inactive) |
| 403 | `event_access_local_only` | Event mode: client is not on this machine |
| 403 | `inference_not_authorized` | Screening disabled in this mode |
| 403 | `ml_v2_demo_not_authorized` | ML v2 requested without the demo flag |
| 403 | `source_not_permitted_for_model_input` | That source may not be sent to a model (only AidData may) |
| 403 | `review_writes_disabled` | No review token configured |
| 404 | `project_not_found` | Unknown id, or a source not visible in this mode (indistinguishable by design) |
| 404 | `screening_not_found` | Unknown saved screening |
| 404 | `unknown_metric` | Use an id from `/analytics/metrics` |
| 413 | `request_too_large` | Body over 262,144 bytes |
| 422 | `invalid_request` | Schema validation failed (unknown field, wrong type, out of range) |
| 422 | `invalid_query` / `invalid_year_range` | Bad query combination |
| 422 | `duplicate_project_ids` | Same id twice in compare/scenario |
| 422 | `candidate_set_too_large` | Narrow the prioritization filters |
| 422 | `no_criteria_weighted` | All priority weights are 0 |
| 422 | `objective_not_supported` | Scenario objective the data cannot support (returns, emissions, impact) |
| 422 | `invalid_constraints` / `missing_sector_priorities` | Scenario inputs inconsistent |
| 422 | `empty_input` / `invalid_text` / `text_too_long` | Screening text problems |
| 429 | `rate_limited` | Over 60 screening requests/min from this client; honour `Retry-After` |
| 500 | `internal_error` | Unexpected; no details are exposed |
| 503 | `database_not_ready` | DB missing or not migrated |
| 503 | `model_unavailable` | Model file missing or failed its integrity check |

## 5. Financial definitions (what a number means)

- **Amounts are decimal strings** (exact `Decimal`), with `currency` (ISO), `unit`
  (`units`/`thousands`/`millions`) and `price_basis` (`nominal` or `constant_2021_usd`).
  Never parse them to float for arithmetic, never add them client-side.
- **Flow meanings** (`financial_meaning`, `is_funding_flow`):

| Flow | Meaning | Funding flow? |
| --- | --- | --- |
| commitment | Historical commitment (not a disbursement) | yes |
| approval / gcf_financing | Approved funding (not necessarily disbursed); GCF excludes co-financing | yes |
| disbursement | Disbursed as published | yes |
| co_financing | Other financiers' money (not GCF) | yes |
| readiness_grant | GCF readiness capacity support | yes |
| deposit | Deposit into a fund (not project funding) | yes |
| pledge | A promise, not a commitment | **no** |
| total_project_cost | Cost as published | **no** |
| repayment_principal / repayment_interest | Paid back to the lender | **no** |

- **`fact_type`:** `source_reported` (stated by the source) vs
  `derived_sum_of_source_transactions` (Compassio summed that record's own transactions).
- **Totals** exist only via the protected finance contract (`compassio_ml.finance.aggregate`):
  single source, same flow, level, currency and price basis, no multi-country values, no
  duplicate project. Otherwise `total: null` with `status: "unavailable"` and a reason. A
  missing value is counted (`missing_value_records`), never treated as 0.
- **Comparisons** never add cross-source linked records, nor records of one source group (an
  AidData parent package or an ADB project number); `duplicate_warnings` explains why.
- **Never display** a total as available funding, return, impact or eligibility. Every metric
  response includes a `declaration` (universe, meaning, currency, exclusions): show it.
- `current_funding_opportunity` is always `not_determinable`: no data on open calls exists.

## 6. ML screening fields

| Field | Meaning |
| --- | --- |
| `model.model_key` / `engine_label` | `ml_v2` "Compassio Climate Intelligence — ML v2" or `ml_v1` |
| `model.status` | `development_candidate` (v2) or `trusted_research_release` (v1): show it |
| `operational_mode` | `authorized_local_demo` (v2 default, v1 fallback) or `standard_local_research` |
| `fallback_used` | true when the default engine was unavailable and v1 answered |
| `prediction.label_score` | Model score in [0, 1]: agreement with climate annotations, **not** a probability of approval, impact or return |
| `prediction.threshold`, `is_climate_related` | Decision at the model's frozen threshold |
| `prediction.band` | `clearly_flagged`, `borderline` (within 0.10 of the threshold), `not_flagged` |
| `explanation` | Word and feature contributions toward the score (faithful to the linear model) |
| `source_evidence` | For DB screening: record id, source reference, rights status, `model_input_permission` |
| `limitations`, `not_predicted`, `guidance` | Show them next to the result |
| `input_sha256` | Hash of the prepared text; the text itself is not stored unless saved with a token |

**Example screening text** (written for the demo; not source data):
`{"title": "Example solar mini-grid for rural health clinics", "description": "Example text:
install solar photovoltaic panels and battery storage to replace diesel generators at district
health facilities."}`. Real result: ML v2 0.789 (`clearly_flagged`), ML v1 0.966.

## 7. Demo identifiers (real, verified on 2026-11-10)

| Use | Ids |
| --- | --- |
| Detail, evidence, ML screening (AidData is the only model-input source) | `aiddata:35266` (Neelum-Jhelum hydropower, PAK; ML v2 0.5945), `aiddata:54087`, `aiddata:53988` (100 MW solar, PAK) |
| GCF Pakistan | `gcf_projects:FP085` (Green BRT Karachi), `gcf_projects:FP018` (GLOF risk reduction), `gcf_projects:FP108`, `gcf_projects:FP207` |
| ADB Pakistan | `adb_pakistan:XM-DAC-46004-54097-001-LN4745` (Sindh Coastal Resilience), `adb_pakistan:XM-DAC-46004-48098-003-LN4696` |
| Comparison: same source package (no total) | `aiddata:35266` + `aiddata:54087` (+ `gcf_projects:FP085`) |
| Comparison: cross-source link (no total) | `climate_funds_update:projects-r10` + `gcf_projects:FP005` |
| Screening refused (source not permitted as model input) | `gcf_projects:FP085` |
| Country profile | `PAK` |

## 8. Example requests

```json
POST /api/v1/decision/compare
{"project_ids": ["gcf_projects:FP085", "aiddata:35266", "aiddata:54087"]}

POST /api/v1/decision/prioritize
{"filters": {"country": "PAK", "source": "climate_funds_update"},
 "sectors_of_interest": ["energy"], "countries_of_interest": ["PAK"], "page_size": 5}
// -> 31 candidates, top score 0.8667, ranking_fingerprint 149e0721bece…

POST /api/v1/decision/scenarios
{"budget": {"amount": "1000000", "currency": "USD"},
 "project_ids": ["climate_funds_update:projects-r1115", "climate_funds_update:projects-r300",
                 "climate_funds_update:projects-r315"],
 "method": "equal"}
// -> 333333.34 + 333333.33 + 333333.33, unallocated 0.00, status "allocated"
```

Priority weights (0–10 each; defaults): `climate_relevance` 3, `evidence_completeness` 2,
`funding_completeness` 2, `sector_match` 1, `country_match` 1, `documentation` 1,
`review_uncertainty` 0. Scenario methods: `equal`, `sector_priority` (needs
`sector_priorities`), `priority_score`; constraints `min_per_project`, `max_per_project`,
`max_share_per_sector`, `max_share_per_country`; budget `unit` `units`/`thousands`/`millions`.
Full responses: `docs/hackathon/demo_api_examples.md`.

## 9. Access policy for the demo

Run in `hackathon_event` mode (`scripts/start_api.ps1`): the organizer authorization reported
by the team, loopback clients only, no `gcf_historical`, never in production. It is **not** a
licence clearance (`docs/hackathon/data_permission_scope.md`). Do not deploy publicly, do not
publish record-level screenshots outside the event, and show attributions.
