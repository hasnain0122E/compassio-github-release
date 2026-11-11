# Frontend implementation blueprint (Task 010)

Short plan for the eight screens to build at the venue. Every screen uses only the existing
backend (`docs/hackathon/backend_handoff.md`); no screen needs a new endpoint. Types come from
`apps/web/src/lib/api-types.ts` (generated, never hand-edited). Base URL:
`process.env.NEXT_PUBLIC_COMPASSIO_API_URL ?? "http://127.0.0.1:8000"` (as in
`apps/web/src/app/screening/workbench.tsx`).

## Rules for every screen

- **Show `access.notice`** and the source attribution (`docs/hackathon/data_permission_scope.md`
  section 4) on every page that shows source data.
- **Money:** amounts are decimal strings. Render them with the `currency`, `unit` and
  `price_basis` they carry; never add two amounts in the browser, and never convert a `null`
  total into 0. Show `total_status = "unavailable"` with its `reason`.
- **Wording:** "historical commitment / approval / disbursement", never "available funding",
  "return", "impact" or "eligible". Rankings are "priority under your weights", never "best".
- **ML:** label results "AI screening (`engine_label`)"; show `model_status` (ML v2 is a
  development candidate); never call a score "probability of climate impact".
- **Errors:** every error body is `{code, message}`; switch on `code`
  (`docs/hackathon/backend_handoff.md` error catalog).

## 1. Landing page (`/`)

Product name, tagline "Give Funding a Better Direction", three entry cards (Explore projects,
Screen a project, Plan a budget). Calls: `GET /api/v1/meta`, `GET /health`. Shows the current
data-access mode from the `X-Compassio-Data-Access` header.

## 2. Overview dashboard (`/overview`)

KPI tiles and two charts. Calls: `GET /api/v1/analytics/overview`,
`GET /api/v1/analytics/coverage`, `GET /api/v1/analytics/funding-by-country?metric=…`
(Pakistan highlighted), `GET /api/v1/analytics/climate-distribution`. Each tile shows its
metric declaration (universe, meaning, currency, exclusions) in a tooltip.

## 3. Project explorer and search (`/projects`)

Search box, filters (source, country, year range, sector, status), paginated table. Calls:
`GET /api/v1/filters` (filter options), `GET /api/v1/projects?q=&source_id=&country=&…&page=&page_size=`.
Row checkboxes feed comparison (2–10 ids) and the candidate list for prioritization.

## 4. Project detail with source evidence (`/projects/[id]`)

Header (title, source, country, status, years), financial facts table (meaning, amount,
currency, price basis, `fact_type` source-reported vs derived), source evidence and links,
related records (cross-source links, same group), documents, completeness checklist.
Calls: `GET /api/v1/projects/{id}`, `GET /api/v1/decision/evidence/{id}`.
"Screen this project" button → screen 5 with the id.

## 5. Compassio Climate Intelligence: ML v2 screening (`/screening`, exists)

Existing workbench: free text or project id; shows engine, model status, ranked labels with
scores and threshold, limitations, `model_input_permission`. Calls: `GET /api/v1/models`,
`POST /api/v1/screening/text`, `POST /api/v1/screening/projects/{id}`,
`GET /api/v1/models/comparison`. Optional save + review (needs the review token; keep it in
server-side env, never in browser code shipped to users).

## 6. Financial analytics and comparisons (`/analytics`, `/compare`)

Tabs: by country, by sector, institutions, approved vs disbursed, Pakistan profile.
Calls: `GET /api/v1/analytics/funding-by-country|funding-by-sector|institutions|approved-vs-disbursed`,
`GET /api/v1/analytics/country-profile/PAK`. Compare view: `POST /api/v1/decision/compare`;
render one column per project, one row group per `comparability_key`, the
`selection_total` only when `available`, and every `duplicate_warnings` entry as a banner.

## 7. Prioritization workspace (`/prioritize`)

Left: filters (`candidate_filters`) and seven weight sliders (`weights`). Right: ranked list
with score bars decomposed into `components`, each with its evidence text, plus the three
distinctions (matches search / documented historical funding / funding opportunity
`not_determinable`). Calls: `POST /api/v1/decision/prioritize`; show `ranking_fingerprint`
and `methodology_version` in the footer. A 422 `candidate_set_too_large` asks the user to
narrow filters.

## 8. Hypothetical budget scenario planner (`/scenarios`)

Inputs: budget (amount + currency), method (equal / sector priority / priority score),
constraints (min/max per project, sector and country caps), candidate ids (from screen 3 or 7).
Output: allocation table, status (`allocated` / `partially_allocated` / `infeasible`),
the arithmetic trace, warnings, `request_sha256` / `result_sha256`. Banner: "Hypothetical
planning simulation, not a funding recommendation." Calls: `POST /api/v1/decision/scenarios`.
Unsupported objectives (return, emissions, impact) return 422 `objective_not_supported`;
show the message verbatim.

## Suggested build order at the venue

1. Shared API client + error handling + notice/attribution footer (1 h).
2. Explorer and detail (screens 3–4).
3. Screening (screen 5, already working) linked from detail.
4. Compare and analytics (screen 6), then overview (screen 2).
5. Prioritization (7) and scenarios (8).
6. Landing page polish (1).
