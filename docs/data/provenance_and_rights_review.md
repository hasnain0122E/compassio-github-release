# Provenance and rights review (Task 003)

Committed record: `data/manifests/source_manifest.json`, schema v2 with two fields added in
Task 003:

- `publisher_reference_url`: the publisher landing or record page;
- `published_license_notes`: terms noted for human review.

Definitions live in `compassio_ml.data.sources`. **Rights status for all nine sources remains
`not_reviewed`.** Access to a file is not permission to redistribute it, and published terms
are recorded here for a person to review. Nothing is authorised.

## Field semantics

| Field | Meaning | Filled when |
| --- | --- | --- |
| `source_url` | Exact URL the file was downloaded from | Only if the downloader recorded it. **Null for all nine**: not recorded. |
| `publisher_reference_url` | Publisher's landing or record page | Known reference; **not** evidence of the exact download location |
| `acquisition_date` | When the file was downloaded | **Null for all nine**. File timestamps are not evidence, and no approximate date is substituted. |
| `inspected_at` | When `compassio-manifest write` measured the file | Always (a measured fact) |

## Per source

| Source | Publisher reference | Evidence linking our file to the publisher | Published terms noted (not reviewed) |
| --- | --- | --- | --- |
| research_paper | https://doi.org/10.6084/m9.figshare.30015124 | **Strong:** both workbooks are byte-identical to Figshare v1. Their MD5s `7fd6e1d1…` and `488f213d…` match the Figshare API, checked 2026-11-09; published 2026-02-20. | Figshare API licence: **CC0**. The article is CC BY 4.0. Cite Qi et al. 2026. |
| aiddata | https://www.aiddata.org/data/aiddatas-global-chinese-development-finance-dataset-version-3-0 | The page offers a download with the identical filename. The workbook states release 2023-11-07; the page says 2023-11-06. | Workbook `License` sheet: **ODC-By 1.0**, attribution required, and the licence must be stated on redistribution. The page states no licence. |
| adb_pakistan | https://data.adb.org/dataset/adb-projects-pakistan | IATI `reporting-org` XM-DAC-46004, generated 2026-10-21 | **Not verified**: the page returned HTTP 403 to automated access |
| gcf_projects | https://data.greenclimate.fund/public/data/projects | GCF FP/SAP codes. The workbooks were written by openpyxl. | The page states no licence or terms ("© 2026 – Green Climate Fund") |
| gcf_readiness | https://data.greenclimate.fund/public/data/readiness | Readiness `*-RS-nnn` codes | Not separately checked; same portal |
| gcf_countries | https://data.greenclimate.fund/public/data/countries | `# RP` / `# FA` aggregates | Not separately checked; same portal |
| climate_funds_update | https://climatefundsupdate.org/data-dashboard/ | The dashboard links a file with the identical name `CFU-Website-Master-2025.xlsx` | No licence stated ("© Copyright Climate Funds Update 2026") |
| climate_project_explorer | https://climateprojectexplorer.org | All URLs in the file are on this domain | Not checked |
| gcf_historical | none known | Filename pattern only (`mjcszv9t52-1`) | Unknown |

## Handling rules in force

- No raw or processed dataset is committed, published or exposed. `data/raw/*`,
  `data/processed/*` and `artifacts/` are git-ignored, which is verified in the completion report.
- Docs contain aggregate counts and record IDs only. The conflicting-label review CSV, which
  holds project titles, stays in the git-ignored `artifacts/` directory.
- Any public display requires a human rights review per source, entered as `rights_status` with
  `rights_evidence`; the manifest model enforces that evidence.
- Any public display must also give attribution:
  - AidData: ODC-By plus the official citation;
  - the research paper: cite Qi et al. 2026.

## Open actions for a person

1. Record the actual download URL and date for each file, if known.
2. Review the ADB, GCF, CFU and CPE terms of use; automated access could not confirm them.
3. Confirm whether the research data's CC0 dedication covers the AidData-derived text fields,
   which AidData licenses under ODC-By. Until clarified, the stricter ODC-By attribution applies.
