# API contracts (v1, Task 006)

- **Interactive schema:** `http://127.0.0.1:8000/docs`. The OpenAPI JSON is at `/openapi.json`.
- **Schemas:** `compassio_api.schemas.data`, Pydantic, frozen.
- **Handlers are thin:** validate, call a typed service in `compassio_api.services`, return the
  schema.
- **Methods:** all routes are `GET`; CORS allows only the listed origins and `GET`.
- **No ML prediction endpoints exist** (Task 007).

## 1. Endpoint summary (from the running app's OpenAPI)

| Route | Purpose | Data class | Errors |
| --- | --- | --- | --- |
| `GET /health` | Liveness (unchanged) | none | — |
| `GET /api/v1/meta` | Product identity (unchanged) | none | — |
| `GET /api/v1/sources` | Registered sources: checksum, rights status and evidence, audited count, imported rows, `served_in_current_mode`, `public_display_permitted` | metadata (always served) | 503 |
| `GET /api/v1/projects` | Search, filter, sort and paginate project records | **source-derived** | 403, 422, 503 |
| `GET /api/v1/projects/{project_id}` | One record with source, annotations, finance, warnings, group and relationships | **source-derived** | 403, 404, 503 |
| `GET /api/v1/filters` | Countries (ISO3), sectors (per source vocabulary), year ranges per source, sort options | **source-derived** | 403, 503 |
| `GET /api/v1/analytics/overview` | Per-source rows, groups, coverage, Pakistan rows, observations by flow and status, annotations, warnings, links; counting rules; disclaimers | **source-derived** | 403, 503 |
| `GET /api/v1/analytics/metrics` | Catalogue of single-source financial metrics | **source-derived** | 403, 503 |
| `GET /api/v1/analytics/trends` | Yearly totals for one metric, with per-year exclusions or "unavailable" | **source-derived** | 403, 404, 422, 503 |

**"Source-derived" routes are LOCAL-DEVELOPMENT-ONLY** until a source's rights are cleared with
evidence (`docs/security/source_rights_access_policy.md`). In `public` mode and in production
they return **403 `source_rights_not_cleared`**. Every `/api/v1` response carries the header
`X-Compassio-Data-Access: local_development|public`. Data responses also contain an `access`
object `{mode, notice}`.

## 2. `GET /api/v1/projects`

| Parameter | Type / validation | Meaning |
| --- | --- | --- |
| `page` | int, 1–100,000 (default 1) | Page number |
| `page_size` | int, 1–**100** (default 25) | Upper bound enforced |
| `q` | string, 1–200 characters | **Literal**, case-insensitive containment in title or description. `%`, `_` and `\` are escaped; the value is a bound parameter (no SQL injection). |
| `country` | `^[A-Z]{3}$` | ISO3 from `project_countries`. Records without a mapped ISO3 (regional, multi-country labels, unmatched names) do not match. |
| `sector` | string, ≤ 200 characters | Exact `sector_name` as published (vocabularies differ by source; see `/filters`) |
| `source` | `^[a-z0-9_]{1,80}$` | e.g. `aiddata`, `gcf_projects`, `climate_funds_update`, `adb_pakistan` |
| `year_from`, `year_to` | int, 1900–2100; `year_from ≤ year_to`, else 422 `invalid_year_range` | Filters on `projects.year`, whose meaning is in `year_type` |
| `climate_related` | bool | Filters on the **Qi et al. 2026 Rio-marker research annotation** (AidData records only). Not a model prediction. Records without that annotation are excluded when it is set. |
| `sort` | `id`, `-id`, `year`, `-year`, `title`, `-title` | Deterministic: `id` breaks ties; NULL years sort last |

**Response `ProjectPage`:**

- `items[ProjectSummary]`: id, source, record level, title, 280-character description excerpt,
  countries, multi_country, region, sector, year and `year_type`, status, climate annotations;
- `pagination {page, page_size, total_items, total_pages}`;
- `applied_filters`, `sort`, `access`;
- `empty_result_message`: set when nothing matches, or when the page is past the last one.

**Implementation:**

- **Deferred join:** one indexed query returns the page's IDs plus `COUNT() OVER ()` for the
  total.
- **No N+1 queries:** a second query loads those rows, and countries and annotations are fetched
  with `selectinload`.
- **No full-table loading:** the table is never loaded into Python.

## 3. `GET /api/v1/projects/{project_id}` → `ProjectDetail`

| Field | Contents |
| --- | --- |
| `source` | `{source_id, name, publisher, rights_status, reference_url}` |
| Record fields | All §1 fields plus `date_value`, `date_precision`, `date_estimated`, `source_reference` and source-specific `attributes` |
| `climate_annotations[]` | `is_model_prediction: false` always; `kind`, `scheme`, values, `raw_value`, `provenance` |
| `financial_observations[]` | Each published amount (below) |
| `data_quality_warnings[]` | `{code, field, message}` |
| `group` | `{group_key, meaning, member_count, member_ids (≤ 50)}` for AidData parent packages and ADB project numbers |
| `relationships[]` | Explicit links with direction, other record, status, method, evidence and `human_reviewed` |
| `disclaimers[]` | The 5 mandatory finance disclaimers |

**Each `financial_observations[]` entry contains:**

- `flow_kind` and `metric_label`, a human label that marks repayments "not funding" and
  components "component of the stated total";
- `level`, `financing_type`, `is_component`;
- `amount`: an exact decimal **string**, or `null`;
- `raw_value` and `value_status` (`reported`, `not_reported`, `unparseable` or `invalid`);
- `unit`, `currency`, `unit_status`, `price_basis`;
- `effective_date`, `effective_year`, `date_meaning`;
- `multi_country`, `estimated`, `recommended_for_aggregates`, `source_reference`.

**Access and errors:**

- A missing ID returns **404 `project_not_found`**.
- A record from a source that may not be served is indistinguishable from a missing one (404).
- Links and annotations from sources that may not be served are omitted.

## 4. Analytics

### `/analytics/metrics`

Each metric is **single-source** and has one flow kind, level, currency and price basis:

| Metric | Source | Funding? |
| --- | --- | --- |
| `aiddata_commitments_constant_2021_usd` | AidData; recommended-for-aggregates only; AidData's constant 2021 USD | yes |
| `cfu_approvals_usd` | CFU total approvals, components excluded, USD millions scaled to USD | yes |
| `adb_commitments_usd` | ADB type 2 | yes |
| `adb_disbursements_usd` | ADB type 3 | yes |
| `adb_principal_repayments_usd` | ADB type 6 | **no** (`is_funding: false`; inflow to ADB) |
| `gcf_financing` | GCF | always `unavailable`: no currency, unit or date in the export |

### `/analytics/trends?metric=…&country=ISO3&year_from=&year_to=`

**Response `TrendsResponse`:**

- `points[]`: each with `{year, status, total (decimal string), unit, summed_records,
  missing_value_records, estimated_records, excluded_records{reason: n}, unavailable_reason}`;
- `undated_records`, `excluded_outside_rules`;
- `aggregation_limitations`, `disclaimers`.

**Rules:**

- A year that cannot be computed safely is `"status": "unavailable"` with the reason, **never
  0**.
- Totals come from `compassio_ml.finance.aggregate`; see
  `docs/data/financial_aggregation_policy.md`.

## 5. Errors

| Status | Body | When |
| --- | --- | --- |
| 403 | `{"code": "source_rights_not_cleared", "message"}` | No source may be served in the current mode, or the metric's source may not |
| 404 | `{"code": "project_not_found" \| "unknown_metric", "message"}` | Unknown ID or metric |
| 422 | `{"code": "invalid_year_range", "message"}` | Domain validation |
| 422 | FastAPI's standard `{"detail": [...]}` | Parameter validation (bounds, patterns, types) |
| 503 | `{"code": "database_not_ready", "message"}` | Database file missing or not migrated (`/health` still returns 200) |

## 6. Measured latency (real database, this workstation)

| Measurement | Value |
| --- | --- |
| Setup | SQLite, 25,623 projects / 85,765 observations; in-process TestClient, median of warm calls (2026-11-09) |
| Live uvicorn requests | Similar: 5–150 ms for list/detail queries |

| Request | Latency |
| --- | --- |
| List, 25 rows, no filter (count over all rows) | ~200 ms |
| Deep page (`page=839`) | ~183 ms (was 1.44 s before the deferred join) |
| `country=PAK&q=hydropower` | ~42 ms |
| `climate_related=true&country=PAK` | ~70 ms |
| Free-text `q=solar` (full `LIKE` scan) | ~206 ms |
| Detail | ~19–30 ms |
| `/filters`, `/analytics/overview`, AidData global trend: first call | 0.5–1.4 s |
| Same, cached | ~13 ms |

The cache is keyed on the latest completed import run, access mode and visible sources, so it
is invalidated by any ingestion and is never shared across access modes.

Elasticsearch or a vector index is **not** justified at this size. If search latency matters
later, use PostgreSQL `pg_trgm` or SQLite FTS5.

## 7. Frontend notes (types)

- **Money:** treat as strings. Do not parse amounts to JS numbers for arithmetic.
- **Missing values:** `null` means "not reported", never 0.
- **Labels:** always show `metric_label`, `date_meaning`, `unit` and `currency`, the
  `access.notice`, and the `disclaimers`.
- **Type generation:** generated TypeScript types belong in `packages/shared` (planned).

## 8. Task 006-DB additions

All routes below are source-derived (local development only; 403 `source_rights_not_cleared` in
public mode and in production). Each numeric aggregate carries a `MeasureMeta` block: `dataset`,
`source_id`, `unit_of_observation`, `measure`, `currency`, `unit`, `date_meaning`,
`missing_count`, `excluded_count`, `deduplication_policy`.

| Route | Purpose |
| --- | --- |
| `GET /api/v1/documents` | Catalogue documents (metadata only). Params: `project_id`, `fund` (`^[A-Z]{2,6}$`), `q`, `linked_only`, `page`, `page_size` ≤ 100. Each item has `linked_project_ids` and a `rights_notice` |
| `GET /api/v1/analytics/data-quality` | Per source: rows; field coverage (description, year, date, sector, status, region, country ISO3); top warnings |
| `GET /api/v1/analytics/financing-completeness` | Per source × flow: observations, reported, not reported, unparseable, invalid, reported without currency or unit, component lines (**counts only, no sums**) |
| `GET /api/v1/analytics/gcf-timeline?country=` | GCF projects approved per year (API `ApprovalDate`) with current status as published, plus `gcf_funding` from metric `gcf_api_gcf_funding_by_country_usd` |
| `GET /api/v1/analytics/country-aggregates?iso3=` | GCF country summaries: source-published snapshots with the rule "never add to project-level observations" |
| `GET /api/v1/analytics/relationships` | Counts by relation type, table, verification state and asserting source, plus the linking policy |

**Changes to existing routes:**

- **`ProjectDetail`** gains:
  - `enrichments[]`: approval date and type, status with its as-of meaning, official URL,
    published `values`, `conflicts`, `precedence`, match method, evidence and verification;
  - `documents[]`: linked documents with link method and verification.

  Observations, enrichments and documents from sources that may not be served are omitted.
- **`/analytics/metrics`** adds:
  - `gcf_api_gcf_funding_by_country_usd` (complete series; GCF's own country split);
  - `gcf_api_gcf_funding_usd` (instrument lines; consistent USD projects only);
  - `gcf_api_disbursements_usd`;
  - `gcf_readiness_grants` (always `unavailable`: currency not stated).

  `MetricOut` gains `deduplication_policy` and `row_selection`.
- **Search** results are unchanged (§2). SQLite now uses an FTS5 trigram pre-filter
  (`search_performance.md`).


## 9. Task 007 screening endpoints (local only)

See `docs/phases/task007_completion_report.md` for real request/response examples. Summary:

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/models` | `ModelsResponse`: per-model identity, SHA-256, fingerprint, threshold, status, evaluation provenance (`independent_generalization_evidence`), operational mode |
| GET | `/api/v1/models/comparison` | `ComparisonResponse` from the committed `docs/research/model_v2/fast_benchmark_aggregates.json` (same 2,550 development-validation records; used for selection) |
| POST | `/api/v1/screening/text` | `TextScreeningRequest` → `ScreeningResponse`; 403 `inference_not_authorized` / `ml_v2_demo_not_authorized`; 422 `empty_input` / `invalid_text` / `text_too_long`; 503 `model_unavailable` |
| POST | `/api/v1/screening/projects/{project_id}` | as above + `source_evidence`; 403 `source_not_permitted_for_model_input`; 404 `project_not_found` |
| POST | `/api/v1/reviews` | `X-Compassio-Review-Token` required (403 `review_writes_disabled`, 401 `invalid_review_token`); 404 `screening_not_found` |
| GET | `/api/v1/reviews/{screening_id}` | review decisions + `chain_valid` |

TypeScript types are generated: `uv run python scripts/generate_api_types.py` → `apps/web/src/lib/api-types.ts`.

## 10. Task 008 decision engine (local only except `/decision/methodology`)

See `docs/api/decision_engine_endpoints.md` (endpoints, real examples, public vs local) and
`docs/architecture/decision_engine_contract.md` (financial distinctions, comparison, ranking and
scenario rules). New error codes (422): `candidate_set_too_large`, `no_criteria_weighted`,
`unknown_or_restricted_source`, `objective_not_supported`, `invalid_constraints`,
`missing_sector_priorities`.
