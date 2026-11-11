# Decision-engine endpoints (Task 008)

All routes live under `/api/v1`. TypeScript types are generated into
`apps/web/src/lib/api-types.ts` (`uv run python scripts/generate_api_types.py`). Errors use the
existing `{code, message}` shape.

**Conventions:**
- Money is a Decimal string, `null` means not reported, and nothing is ever 0 by default.
- Every source-derived response carries `access`.

## Public vs local

| Route | Public-safe? |
| --- | --- |
| `GET /decision/methodology` | **Yes.** It holds no source data. |
| Every other route below | **No.** Source-derived: served only with `COMPASSIO_SOURCE_DATA_ACCESS=local_development` outside production, otherwise 403 `source_rights_not_cleared`. |

Public display of any data needs a written rights clearance for that source, recorded in the
manifest. Today no source has one.

## Endpoints

| Method | Path | Request | Response | Errors |
| --- | --- | --- | --- | --- |
| GET | `/decision/methodology` | – | `MethodologyResponse` | – |
| GET | `/decision/evidence/{project_id}` | – | `EvidenceResponse` | 403, 404, 422 |
| POST | `/decision/compare` | `CompareRequest {project_ids: 2–10 unique}` | `CompareResponse` | 403, 404, 422 |
| POST | `/decision/prioritize` | `PrioritizeRequest {filters, weights, sectors_of_interest, countries_of_interest, missing_component_policy, page, page_size}` | `PrioritizeResponse` | 403, 404, 422 `candidate_set_too_large` / `no_criteria_weighted` / `invalid_year_range` / `unknown_or_restricted_source` |
| POST | `/decision/scenarios` | `ScenarioRequest {budget, project_ids 1–50, method, objective, sector_priorities, unlisted_sector_weight, priority_weights, constraints, scenario_label}` | `ScenarioResponse` | 403, 404, 422 `objective_not_supported` / `invalid_constraints` / `missing_sector_priorities` |
| GET | `/analytics/funding-by-country?metric=&year_from=&year_to=&limit=` | – | `GroupedFundingResponse` | 403, 404 `unknown_metric`, 422 |
| GET | `/analytics/funding-by-sector?metric=…` | – | `GroupedFundingResponse` | as above |
| GET | `/analytics/institutions?country=&limit=` | – | `InstitutionsResponse` (record counts by role) | 403, 422 |
| GET | `/analytics/approved-vs-disbursed?country=` | – | `ApprovedDisbursedResponse` | 403, 422 |
| GET | `/analytics/climate-distribution?country=` | – | `ClimateDistributionResponse` | 403, 422 |
| GET | `/analytics/coverage` | – | `CoverageResponse` (per-source rows, years, rights, freshness) | 403 |
| GET | `/analytics/country-profile/{iso3}` | – | `CountryProfileResponse` (use `PAK` for Pakistan) | 403, 422 |

These reuse the existing endpoints:
- `/analytics/metrics` lists the metric ids;
- `/analytics/trends` gives the per-year series;
- `/analytics/country-aggregates` gives GCF's own country summaries, which are never summed;
- `/projects` is the search used to find records to compare.

## Real examples (live local server, real database, 2026-11-10)

**Server:** `COMPASSIO_SOURCE_DATA_ACCESS=local_development uv run uvicorn
compassio_api.main:app --port 8018`.

**Data:** registered sources, rights `not_reviewed`, local inspection only. Responses below are
trimmed, but every value shown is exactly as returned.

### Evidence: `GET /decision/evidence/gcf_projects:FP085` (200, 67 ms)

Record: "Green BRT Karachi".

**`verified_approval`:**
- `approval_date` 2018-10-20, `project_status` "Under Implementation";
- `verified_by_source_id` "gcf_api_projects", `verification_state`
  "deterministic_identifier_match".

**`headline_facts`:**

| Source | Flow | Amount | Currency | Fact type |
| --- | --- | ---: | --- | --- |
| gcf_projects | gcf_financing | 49000000 | null | source_reported |
| gcf_api_projects | gcf_financing | 49000000 | null | source_reported |
| gcf_api_projects | co_financing | 534500000 | null | source_reported |
| gcf_api_projects | total_project_cost | 583500000 | null | source_reported |
| gcf_api_projects | disbursement | 1850000 | USD | derived_sum_of_source_transactions |

**`completeness.missing`:** `has_description`, `has_sector`, `has_year`,
`has_source_status`, `has_documents`.

### Compare: `POST /decision/compare`

Request: `{"project_ids":["gcf_projects:FP085","aiddata:35266","aiddata:54087"]}` (200, 19 ms).

| Group (comparability key) | Result |
| --- | --- |
| `aiddata\|commitment\|project\|USD\|nominal\|stated_total` | cells 448,000,000 and 576,000,000; `selection_total` **null**, `unavailable`: "At least two of these records belong to the same source record group …" |
| `aiddata\|commitment\|project\|USD\|constant_2021_usd\|stated_total` | cells shown; `selection_total` **null** (same reason) |
| Every GCF group | `unavailable`: "Fewer than two selected projects report this figure; nothing to compare." |

`duplicate_warnings`: `same_source_record_group` for `[aiddata:35266, aiddata:54087]` (AidData
parent package 1648; both are recommended for aggregates by AidData).

> **Changed in `compassio-comparison-1.1.0` (Task 008 integration audit).** The 1.0.0 response
> returned `selection_total` "1024000000" for this pair while also warning that both records
> belong to one parent package. That sum is no longer presented as a user-facing total: records
> of the same source group are shown and flagged, never added.

A second request, `{"project_ids":["climate_funds_update:projects-r10","gcf_projects:FP005"]}`,
gives:
- `duplicate_warnings[0]`: `relation_type` "cross_source_reference_code", "These records are
  linked as probably the same real-world project in different sources; their amounts are never
  added";
- every `selection_total` is `null`.

### Prioritize: `POST /decision/prioritize`

Request: `{"filters":{"country":"PAK","source":"climate_funds_update"},
"sectors_of_interest":["energy"],"countries_of_interest":["PAK"],"page_size":3}` (200, 76 ms).

- `candidates` 31, `ranking_fingerprint` `149e0721…bc2e`, `data_version` [23, 23].
- Rank 1 is `climate_funds_update:projects-r1115`, with score "0.8667". Its components:

| Criterion | Weight | Value | Contribution | Evidence |
| --- | ---: | ---: | ---: | --- |
| climate_relevance | 3 | 1 | 3.0000 | listed_by_climate_fund |
| evidence_completeness | 2 | 0.8333 | 1.6666 | 5/6 present; missing: source status |
| funding_completeness | 2 | 1 | 2.0000 | Approval (project level): 3.44 millions USD |
| sector_match | 1 | 1 | 1.0000 | 'Energy generation, renewable sources' contains 'energy' |
| country_match | 1 | 1 | 1.0000 | single-country record in PAK |
| documentation | 1 | 0 | 0 | no linked documents |
| review_uncertainty | 0 | 0 | 0 | – |

Check: (3 + 1.6666 + 2 + 1 + 1 + 0 + 0) / 10 = 0.8667.

### Scenario: `POST /decision/scenarios`

Request: budget 5,000,000 USD (units) over the top 3 records, `method` "priority_score",
`max_per_project` 2,000,000 (200, 16 ms).

**Allocations:**

| Record | Allocation |
| --- | ---: |
| `projects-r1115` | 1666666.67 |
| `projects-r300` | 1666666.67 |
| `projects-r315` | 1666666.66 |

**`conservation_check`:** "5000000.00 + 0.00 = 5000000.00 (equals the budget)".

**`arithmetic`:**
- "Round 1: share 5000000.000000 by weight over 3 records (sum of weights 2.4999); scale
  1.000000; placed 5000000.000000."
- "Rounding: … 2 cent(s) redistributed by largest remainder (ties by project id)."

**Every allocation's warnings** include "Whether this record can receive new funding is not
determinable from the data."

**Disclosures** begin "HYPOTHETICAL PLANNING SIMULATION: not a statement that funding is
available…".

### Rejections

| Request | Response |
| --- | --- |
| Scenario with `objective: "maximize_emission_reductions"` | 422 `objective_not_supported`: "No measured emission reductions are stored. Supported objectives: allocate_by_weights." |
| Prioritize with no filters | 422 `candidate_set_too_large`: "26499 records match; narrow the filters to at most 2000 …" |

### Insights (PAK)

**`GET /analytics/approved-vs-disbursed?country=PAK`** (332 ms). Paired records only:

| Source | Paired | Approved / committed (USD) | Disbursed (USD) | Ratio |
| --- | ---: | ---: | ---: | ---: |
| climate_funds_update | 27 | 307,254,915.44 | 106,901,546.78 | 0.3479 |
| gcf_api_projects | 6 | 205,727,978 | 79,882,949 | 0.3883 |
| adb_pakistan (commitments) | 188 | 31,571,214,330 | 21,549,925,012.94 | 0.6826 |

**`GET /analytics/funding-by-country?metric=gcf_api_gcf_funding_by_country_usd&limit=5`**
(57 ms). 136 countries. The top five:

| Country | USD |
| --- | ---: |
| IND | 1,083,573,793.89 |
| BRA | 1,009,640,219.70 |
| ZAF | 559,101,636.40 |
| IDN | 526,440,314.39 |
| MNG | 486,205,086.89 |

Excluded: `country_lines_inconsistent_with_published_total` 208.

**`GET /analytics/country-profile/PAK`** (968 ms, uncached). All-years totals per metric. Each
is single-metric and never added to another:

| Metric | Total | Records | Years |
| --- | ---: | ---: | --- |
| `aiddata_commitments_constant_2021_usd` | 102,852,446,551.66 (exact: 102852446551.65715952412) | 318 | 2000–2021 |
| `cfu_approvals_usd` | 316,574,915.44 | 31 | |
| `adb_commitments_usd` | 32,126,214,330 | | |
| `adb_disbursements_usd` | 21,549,925,012.94 | | |
| `adb_principal_repayments_usd` (`is_funding: false`) | 6,331,731,168.62 | | |
| `gcf_api_gcf_funding_by_country_usd` | 331,727,118 | | |
| `gcf_api_disbursements_usd` | 79,882,949 | | |

`gcf_financing` and `gcf_readiness_grants` are `unavailable` (no currency or unit is stated by
the source).

## Frontend notes (Task 010)

- Render `meaning_label`, `currency`, `unit` and `price_basis` next to every amount.
- Never sum amounts client-side; use `selection_total` and its reason.
- Show `completeness.missing` and `duplicate_warnings` prominently.
- Show `current_funding_opportunity` as "not determinable", never as "open".
- Use `ranking_fingerprint` and `result_sha256` to detect stale cached views.
