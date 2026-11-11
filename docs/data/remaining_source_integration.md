# Remaining registered sources (Task 006-DB)

All four sources are read through the audited loaders (`compassio_ml.audit.loaders.SourceData`)
with **no ML-package changes**. Each run re-hashes the raw files against the canonical manifest.

| Source | Stored in | Rows | Audit figure | Match |
| --- | --- | ---: | ---: | --- |
| `gcf_readiness` | `projects` (`record_level = gcf_readiness_grant`) | 876 | 876 (financial_fields_audit §1) | yes |
| `gcf_countries` | `country_aggregates` (4 measures × 155 countries) | 620 | 155 countries | yes |
| `climate_project_explorer` | `documents` (+ `document_links`) | 818 documents / 498 families | 818 / 498 (cross_source_overlap §5) | yes |
| `gcf_historical` | `historical_staging` (**restricted**) | 128 (123 matched to the export) | 128 / 123 (§3) | yes |

## A. GCF readiness → readiness-grant rows

- **Identity:**
  - `gcf_readiness:<Ref #>` where `Ref #` is a unique readiness code (`XXX-RS-NNN`): 828 rows;
  - otherwise `gcf_readiness:row-<n>`: 48 rows whose `Ref #` is blank, repeated or a roster name
    such as "PwC" (warning `no_stable_readiness_reference`).
- **Not funded projects:** a separate `source_id` and `record_level` mean they are **never
  counted as GCF funded projects** (reconciliation check = 0).
- **Fields:** country (ISO3 via the GCF countries export), region, delivery partner, status,
  `Approved Date` (parsed as a day-precision approval date), NAP/SIDS/LDC flags, and activity as
  a source classification.
- **Financing:** `readiness_grant`, **currency and unit not stated** (`not_stated_in_source`).
  Metric `gcf_readiness_grants` is always `unavailable`, and GCF's API has no readiness endpoint
  to verify it. 16 amounts ≤ 1 are flagged `placeholder_amount`.

## B. Climate Project Explorer → documents

- **Identity:** `climate_project_explorer:<document URL slug>`, one row per catalogue document.
  Families are recorded as `family_id`. **No project rows are created** (check = 0).
- **Date:** `document_date` is the CPE **family publication date**. Its `document_date_type`
  says so explicitly: "not the document's own date and not a project approval date".
- **Links:** to GCF projects **only** through a GCF code (`FP###` or `SAP###`) in a
  **GCF-sourced** document's own family name, title or summary. GEF, AF and CIF documents are
  never linked to GCF codes.

  | Link type | Count |
  | --- | ---: |
  | Single-code, `deterministic_identifier_match` | 280 |
  | Documents citing several codes, `candidate_requires_review` | 8 links (4 documents) |
  | GCF projects with ≥ 1 document | **121** (as the audit found) |
  | Families linked | 119 |

- **Rights:** only catalogue metadata and URLs are stored. **No document content is downloaded,
  stored or committed.**

## C. GCF country summaries → country_aggregates

- **Measures:**
  - `readiness_count`, `funded_activity_count` (counts);
  - `readiness_financing`, `funded_activity_financing` (USD, from the `$` header).
- **Snapshot date:** 2026-11-08, decoded from the export file name's ms epoch and labelled as an
  assumption.
- **Isolation:** a separate table, so the figures are **never** in `financial_observations`
  (check = 0). The API states the rule "never add them to project-level observations or to each
  other".
- **Example (PAK):** funded-activity financing USD 331,727,118 across 11 funded activities. This
  is GCF's own country attribution, distinct from the project rows.

## D. GCF historical archive → restricted staging

- **Restriction:** provenance is unconfirmed (the Mendeley ID returned 404; `source_rights_matrix.md`).
  The source has `access_tier = restricted_internal`: **never served by any API route, in any
  mode** (tested), and not a project row.
- **Units:** `Tot_Fin` is kept raw and parsed in **USD thousands**, documented by the archive's
  `TO READ` sheet. 122 parse, 5 are text such as "USD 220 000,00" (`unparseable`), 1 is missing.
- **Comparison** (`uv run compassio-db report historical-comparison`, internal only): `Tot_Fin` ×
  1000 equals API `TotalValue` for 39 projects, differs for 79, and 10 are not comparable.
  Differences are expected for a 2020 snapshot. **They are never summed or substituted.**

## Reproduce

```powershell
uv run compassio-db ingest --source gcf_readiness
uv run compassio-db ingest --source gcf_countries
uv run compassio-db ingest --source climate_project_explorer
uv run compassio-db ingest --source gcf_historical
uv run compassio-db report reconciliation --out artifacts/db/report_reconciliation.json
```
