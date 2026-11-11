# Decision-engine contract (Task 008)

**Code:** `apps/api/src/compassio_api/services/decision/`. **Schemas:**
`schemas/decision.py`. **Routes:** `api/v1/decision.py`.

**Methodology versions:**
- `compassio-comparison-1.1.0` (1.1.0, Task 008 integration audit: no total across records of the same source group)
- `compassio-priority-1.0.0`
- `compassio-scenario-1.0.0`

`GET /api/v1/decision/methodology` serves them. Bump a version whenever behaviour changes.

This contract **extends** the financial data contract (`financial_data_contract.md`) and the
aggregation policy (`../data/financial_aggregation_policy.md`). It does not replace them, and
it adds no second calculation system.

- Every money total goes through `services.finance_rows.safe_total`, which calls
  `compassio_ml.finance.aggregate`.
- Every metric row is selected by `services.finance_rows.metric_statement` (the same filters
  as the trends query) and checked by the protected `services.finance._exclusion_reason`.
  `services/finance.py` itself is unchanged; it is hash-pinned in
  `configs/task006_integration_reference.json`. Tests assert that the insight totals equal the
  `/analytics/trends` totals, so the two selections cannot drift apart.

## 1. Financial distinctions the engine enforces

| Distinction | How it is enforced |
| --- | --- |
| Historical funding vs current opportunity | Every evidence card, priority item and scenario carries `current_funding_opportunity: "not_determinable"`. No data on open calls exists, and none is inferred. |
| Approved vs disbursed | Different `flow_kind`, so they get different `comparability_key`s and are never added. `/analytics/approved-vs-disbursed` reports both, side by side, over the same paired records only. |
| Commitment vs repayment | Repayments have `financial_meaning = repayment_not_funding` and `is_funding_flow = false`. They are never counted as documented funding. |
| Pledge vs commitment | A pledge is `pledge_not_commitment`, with `is_funding_flow = false`. |
| Project financing vs country aggregates | Country aggregates (`country_aggregates`) are never mixed in. Country totals use only single-country records, or the source's own published country lines. |
| Fund-level vs project-level | Each metric has one `level`; `aggregate` refuses aggregate levels. |
| Currencies and price bases | They are part of the `comparability_key`. There is no conversion and no inflation adjustment; AidData constant 2021 USD is AidData's own published figure. |
| Source-reported vs derived | `fact_type` is either `source_reported` or `derived_sum_of_source_transactions`. Derived means one record's own transactions for one flow, currency and basis, summed through `aggregate`. |
| AI screening vs outcomes | `climate_relevance.is_model_prediction = false` and states "not measured environmental impact". Model screening is only available through the Task 007 endpoints. |

## 2. Financial facts

`FinancialFact` is one stored observation, labelled with what it means:
- `financial_meaning`, `is_funding_flow`, `meaning_label`;
- `amount` (exact source value) and `amount_in_units` (scaled by unit), with `unit`, `currency`
  and `price_basis`;
- the date and its meaning;
- `country_attribution`, which is one of:
  - `single_country_project`
  - `whole_project_value_not_attributable_to_one_country`
  - `source_published_country_line`
  - `no_mapped_country`
- `recommended_for_aggregates`, `source_reference`;
- `comparability_key = source|flow_kind|level|currency|price_basis|row_selection`.

There are two kinds of fact list:
- **Headline facts** are stated totals, plus derived per-flow transaction sums (for example
  ADB and GCF disbursements).
- **Breakdown facts** are instrument components and the source's own country lines. They are
  never added to headline totals.

Missing values are `null` with `value_status`. They are listed in `completeness.missing` and
never imputed.

## 3. Comparison rules

1. Figures are grouped by exact `comparability_key`. Different sources never share a group,
   because every metric is single-source.
2. A `selection_total` is computed only when **all** of the following hold:
   - at least two selected records report the figure;
   - each record has exactly one figure of this kind;
   - the source does not mark any of them `recommended_for_aggregates = false`;
   - no two of the contributing records belong to the same source record group (an AidData
     parent package or an ADB project number); since `compassio-comparison-1.1.0` such records
     are shown side by side and flagged, never added, even when the source recommends each
     figure for aggregates;
   - the currency is stated;
   - `aggregate` accepts the set: no multi-country value, and no duplicate project key.

   Otherwise the total is `null`, with `selection_total_reason`.
3. Records explicitly linked as probably the same project get one `project_key` cluster, so
   `aggregate` refuses to add them. They are also listed in `duplicate_warnings`. Records in
   the same source group (for example an AidData parent package) are flagged too.
4. `selection_summed_records` and `selection_missing_records` make partial totals explicit.

## 4. Prioritization (`compassio-priority-1.0.0`)

- **Score.** `score = Σ(weight × value) / Σ(applied weights)`. It is rounded to 4 dp with
  banker's rounding, using exact Decimal arithmetic.
- **Ordering.** Ties are broken by `project_id`.
- **Components.** Each component has a value in [0, 1], a status, a contribution and a
  human-readable `evidence` string. Each is computed from the same `ProjectEvidence` the API
  returns. The criteria are defined in `PRIORITY_CRITERIA`.
- **Missing data.** `missing_component_policy` decides how an unavailable component counts:
  - `score_zero` (the default) adds its weight with a value of 0;
  - `exclude_from_denominator` leaves its weight out.
- **Distinctions.** Each item separates three things:
  - `matches_search` together with `matched_filters`;
  - `has_documented_historical_funding`, which counts a reported funding-flow amount only
    (not repayments, pledges or total cost);
  - `current_funding_opportunity: not_determinable`.
- **Reproducibility.** `ranking_fingerprint = sha256(methodology, canonical request without
  pagination, data_version)`. Results are cached per data version, so pagination is stable.
- **Size limit.** The candidate set is capped at 2,000. Larger requests return 422
  `candidate_set_too_large` rather than ranking an arbitrary subset.

## 5. Scenarios (`compassio-scenario-1.0.0`)

- **Inputs.** A budget (exact Decimal, ISO 4217 currency, unit) and 1–50 records.
- **Methods.** `equal`, `sector_priority` (case-insensitive sector names) or `priority_score`.
- **Constraints.** `min_per_project`, `max_per_project`, `max_share_per_sector` and
  `max_share_per_country`. Multi-country records form their own country group; no country
  share is invented.
- **Algorithm.** Exact Decimal water-filling at 50-digit precision:
  1. Give every record its minimum.
  2. Distribute the remainder by weight.
  3. Scale each round down to the first cap that would be broken.
  4. Retire saturated records and repeat.
  5. Round every allocation down to 0.01.
  6. Hand out leftover cents by largest remainder (ties by id), never breaking a cap.
- **Conservation.** `allocated_total + unallocated == budget` holds exactly, and
  `conservation_check` states it.
- **Statuses.** `allocated`, `partially_allocated` (caps or zero weights) or `infeasible`
  (the minimums exceed the budget, so nothing is allocated).
- **Objectives.** Only `allocate_by_weights` is supported. Return, emissions, cost-per-tonne,
  impact, risk-reduction and full-cost objectives are rejected with 422
  `objective_not_supported` and the reason the data cannot support them.
- **Context, not costs.** `reference_facts` are historical figures for context only. A warning
  appears when an allocation exceeds a recorded figure in the same currency, and when no
  recorded figure is in the budget currency.
- **Reproducibility.** `request_sha256`, `result_sha256` and `data_version`.

## 6. Rights and access

- **Source-derived routes.** Every route except `/decision/methodology` depends on
  `DataPolicyDep`. With no rights clearance, public and production modes return 403
  `source_rights_not_cleared`.
- **Restricted and unknown records.** Restricted (`restricted_internal`, for example
  `gcf_historical`) and non-visible records return 404, the same as missing ones.
- **No writes.** No decision endpoint writes to any database. The project database is opened
  read-only. Tests prove that `financial_observations` and the real DB file hash are unchanged.
- **Task 007 is unaffected.** The decision engine never invokes models. The ML v2 status, the
  v1 fallback, the review store and the sealed-evaluation protections are untouched.
