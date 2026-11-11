# GCF metadata enrichment (Task 006-DB)

**Goal:** add the approval dates, status, currency-stated financing and official URLs that the
registered GCF export (`gcf_projects`, 379 rows) lacks. Nothing is assumed from the export.

## 1. Source and access

- **Endpoint:** the official GCF Open Data Library API, `GET https://api.gcfund.org/v1/projects`.
  It returns structured JSON for all funded projects, so no HTML pages were scraped.
- **Retrieval:** one bounded request, stored as snapshot `20261109T144534Z`
  (`backend_source_registry.md`).
- **What the API does not publish:** proposal or document URLs, and an as-of date for status.
  Neither is invented.

## 2. Matching and precedence

| Topic | Rule |
| --- | --- |
| Identity | **Exact GCF reference code only:** API `ApprovedRef` == export `Ref #`. No title matching. |
| Storage | One `project_enrichments` row per matched export project (relation `enriched_from_official_record`, verification `deterministic_identifier_match`, review `not_reviewed`, last verified = snapshot date) |
| Precedence | **The export row keeps its own values.** API values sit beside them in `enrichments[].values` with their own source. Every disagreement is stored in `conflicts` (`cross_record`). Inconsistencies inside the API record are stored too (`within_api`). Nothing is overwritten. |
| Not imported | `LifeTimeCO2` and beneficiary counts (ex-ante estimates, not verified impact); `*USDeq` fields (GCF conversions at a current exchange rate) |
| API-only records | 14 API codes have no export row: FP006, FP029, FP030, FP038, FP054, FP065, FP093, FP104, FP146, FP221, SAP013, SAP016, SAP054, SAP065. They are **reported, not ingested** as projects, because a new project population needs canonical registration. |

## 3. Dates and status

| Field | Source | Meaning |
| --- | --- | --- |
| `approval_date` | API `ApprovalDate` | **GCF Board approval date**. `StartDate`, `EndDate` and `DateImplementationStart` are kept separately in `values` and never used as approval. |
| `project_status` | API `Status` | As published (`Under Implementation`, `Approved`, `Completed`, `Discontinued`) |
| `status_as_of` | Retrieval time | "The API publishes no as-of date for 'Status'; this is the snapshot retrieval time." |
| `approval_status` | Derived only from the presence of `ApprovalDate` | "approved by the GCF Board (ApprovalDate published)". **Not** an open funding opportunity. |

## 4. Financing (financial_observations owned by `gcf_api_projects`)

| Published item | Stored as | Currency |
| --- | --- | --- |
| `TotalGCFFunding`, `TotalCoFinancing`, `TotalValue` | flows gcf_financing, co_financing, total_project_cost; project level, not components | **NULL, not stated.** These totals mix currencies for projects with EUR lines (they are not the sum of native lines), so they are never summed. |
| `Countries[].Financing` (GCF, CoFinancing, Total) | `financing_type = country_breakdown`, `country_iso3`, `is_component` | **Stated** (all USD) |
| `Funding[]` (source × instrument × Board meeting) | Instrument lines, `is_component` | **Stated** (USD 1,610 lines, EUR 202). EUR is never converted. |
| `Disbursements[]` | Transaction level, dated `DateEffective` | Stated (USD or EUR) |

**Units:** JSON numbers with an explicit `Currency` are treated as currency units. For all 379
matched projects the export's `FA Financing` equals the API `TotalGCFFunding` exactly (0
`gcf_financing_total` conflicts), which supports this.

**Two double-counting hazards inside the API were found and handled:**

1. **Re-listed funding lines:**
   - FP086 and FP103 list the same budget IDs again under a later Board meeting (e.g. B.21 and
     B.46), alongside older lines with the same amounts.
   - Lines are keyed `budget id + Board meeting`, and identical repeats would be stored once.
     This rule is tested, but this snapshot has 0 byte-identical repeats: every repeat differs by
     Board meeting.
   - Lines from another meeting get **no** approval year; no date is invented.
2. **Consistency gate (`recommended_for_aggregates`):** a project's lines may enter a total only
   if they reproduce GCF's published `TotalGCFFunding` exactly.
   - **Funding lines:** all USD and summing to the total. This holds for 339 projects; the 40
     projects with EUR lines are excluded and counted.
   - **Country lines:** summing to the total. 54 projects disagree (`api_total_vs_country_breakdown`
     conflicts) and are excluded and counted.

## 5. Coverage report (real; `uv run compassio-db report gcf-enrichment`)

| Measure | Count |
| --- | ---: |
| Export projects | 379 |
| API records in snapshot | 393 |
| **Matched export projects** | **379** (0 unmatched) |
| With verified approval date (`ApprovalDate`) | **379** |
| With status (as retrieved) | **379** (Under Implementation 343, Approved 27, Completed 8, Discontinued 1) |
| With currency-stated GCF financing (≥ 1 line) | **379** |
| With official project URL | **379** |
| With proposal or document URL from the API | **0** (not published; CPE links in `cross_source_relationships.md`) |
| With any conflict | 54, all `api_total_vs_country_breakdown` (within the API); **0 cross-record conflicts** in title, Board meeting, theme, sector, countries, entity or GCF total |
| API records not in export | 14 (listed above) |

**Pakistan (11 export projects listing Pakistan):**

- 11 matched, with approval date, status, currency-stated financing and a **GCF-published
  Pakistan country line**.
- That includes the 3 multi-country projects FP215, FP254 and FP283. Their Pakistan share
  therefore comes from **GCF's own split**; it is not computed by Compassio.
- Approval years: FP018 2016; FP085 2018; FP108 2019; SAP024 2022; FP207 and FP215 2023; FP229,
  FP254, SAP039 and SAP047 2024; FP283 2025.

**The coverage figures are computed by the report at run time and are not hard-coded.** The tests
check consistency (matched ≤ export; matched + unmatched = 379), not targets.

## 6. Reproduce (PowerShell)

```powershell
uv run compassio-db fetch --source gcf_api_projects    # optional: a NEW snapshot (newest is used)
uv run compassio-db registry
uv run compassio-db ingest --source gcf_api_projects   # needs gcf_projects ingested first
uv run compassio-db report gcf-enrichment --out artifacts/db/report_gcf-enrichment.json
```
