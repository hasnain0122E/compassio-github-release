# Source register

**Status (Task 002): all nine sources are present in `data/raw/<source_id>/` and registered in
`data/manifests/source_manifest.json`.** This register gives each source's role. Verified facts
are in the manifest and in `source_inventory.md`, and audit findings in the other `docs/data/`
files.

The `source_id` is the folder name under `data/raw/`. The curated metadata (publisher, unit,
confirmed facts versus assumptions) lives in `compassio_ml.data.sources`.

| `source_id` | Source | Publisher | Role in Compassio | Unit of observation (count) | Rights |
| --- | --- | --- | --- | --- | --- |
| `research_paper` | *A Benchmark Dataset of Chinese Development Finance with Climate Relevance and SDG Annotations from 2000–2021* (Scientific Data, 2026) data | Paper authors | **Supervised labels** (`rio_marker`), plus SDG annotations | AidData record (20,985) | not_reviewed |
| `aiddata` | AidData Global Chinese Development Finance Dataset v3.0 | AidData (William & Mary) | Full record context (dates, amounts, status, linkage) for the labelled rows | project/activity record (20,985) | not_reviewed (file states ODC-By 1.0) |
| `adb_pakistan` | ADB IATI activities, Pakistan | Asian Development Bank | Pakistan explorer: instruments, commitments, disbursements | IATI activity (193; 143 projects); transactions (30,962) | not_reviewed |
| `gcf_projects` | GCF Open Data Library funded projects | Green Climate Fund | Climate-dedicated project list | FP/SAP project (379) | not_reviewed |
| `gcf_readiness` | GCF readiness activities | Green Climate Fund | Readiness context (not investment) | readiness row (876) | not_reviewed |
| `gcf_countries` | GCF country summaries | Green Climate Fund | Country-level totals (aggregate only) | country (155) | not_reviewed |
| `climate_funds_update` | CFU website master workbook 2025 | Climate Funds Update | Multi-fund approvals and trends | approved project row (4,066); pledges (564); funds (30) | not_reviewed |
| `climate_project_explorer` | CPE search-results export | Climate Project Explorer | Project documents (GCF, GEF, AF, CIF) | family (498); documents (818) | not_reviewed |
| `gcf_historical` | T20 GCF co-financing database V2.1 (2020) | Research dataset authors | Historical co-financing structure | GCF project (128) | not_reviewed |

## Verified overlaps

These were hypotheses in Task 001 and have now been tested (`cross_source_overlap.md`):

- **research_paper ↔ aiddata:** the same 20,985 records, confirmed by stable ID. The research
  workbooks are a re-representation of AidData, not an independent source.
- **gcf_projects ↔ climate_funds_update:** 329 GCF projects are linked by the FP/SAP code embedded
  in CFU names (probable matches).
- **gcf_projects ↔ climate_project_explorer:** 121 links by reference code and 2 by name only.
- **gcf_projects ↔ gcf_historical:** 123 matches by reference number; 5 historical references are
  absent from the current export.
- **gcf_projects ↔ gcf_countries:** the country rows aggregate the project-level data. They are
  never summed with it.
- **adb_pakistan ↔ gcf_projects:** 3 GCF Pakistan projects list ADB as accredited entity, but no
  same-title ADB activity exists. Unconfirmed.

## Earlier exploratory audit figures

The figures 20,985 / 1,383 / 496 / 76 were **reproduced exactly** in Task 002 from the registered
research file (`research_label_audit.md` §2). The earlier preliminary classification baseline has
**not** been reproduced and must not be quoted.
