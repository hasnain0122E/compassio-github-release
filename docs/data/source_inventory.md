# Source inventory

Status: **Task 002, 2026-11-09.** Every value below was produced by the commands in
[Regenerate](#regenerate) on the files in `data/raw/`. The committed provenance record is
`data/manifests/source_manifest.json`, and the machine-readable inventory is
`artifacts/data_audit/source_inventory.json`, which is git-ignored and regenerable.

## Files discovered

**9 files, 9 distinct SHA-256 hashes, 0 duplicate-content copies.** All 9 expected sources are
present, so no critical source is missing. The optional historical GCF archive is also present.

| `source_id` (folder) | Original filename | Format | Bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
| `research_paper` | `30015124.zip` | zip | 23,003,237 | `f4420394676e17be8d78d2b8ddbb5293a7fcf0d4c0633edd7a34a0a3f539557d` |
| `aiddata` | `AidDatas_Global_Chinese_Development_Finance_Dataset_Version_3_0.zip` | zip | 28,561,122 | `290da2887a6984beaa6d269d2171798951e0644cae579497dafb8bd78646e097` |
| `adb_pakistan` | `ADB Project in Pakistan.xml` | xml | 14,346,227 | `58f1dca29b4be3790cf7790fc578e723fda798a8f75755358fa69918efac6862` |
| `gcf_projects` | `ODL-Export-projects-1794139775112.xlsx` | xlsx | 42,151 | `dd7c0ee238b9557a3dbacf31c3061e1e8161796636a08f4674783a86cb18635f` |
| `gcf_readiness` | `ODL-Export-readiness-1794139579990.xlsx` | xlsx | 83,951 | `ee4c75c16a3308856c9922f35b01051e58622d885bab22f82aaa762517a2189c` |
| `gcf_countries` | `ODL-Export-countries-1794139570848.xlsx` | xlsx | 15,994 | `0d0c3b027a9a3e9b6b55c7611706ebfbafe567a32b432e57dc7e3b7288b566bf` |
| `climate_funds_update` | `CFU-Website-Master-2025.xlsx` | xlsx | 880,100 | `7b3cf06b948365da99a164d21bbb1d176db0e938ff70af9f2b391f070c14e099` |
| `climate_project_explorer` | `search_results.csv` | csv | 1,391,967 | `9850111cdcbcc55b71e36f0f1ba0745cb423cc241f2c4e53dc4df2f6de7ff5ea` |
| `gcf_historical` | `mjcszv9t52-1.zip` | zip | 3,914,398 | `dbbf4aae107e664037f35c01d6c21a6b80722c181a9a262e43110df1ea1d0778` |

These hashes are identical to the ones computed before any Task 002 code ran, which shows the raw
bytes were not modified (see the completion report).

## Archive contents (read from the ZIP central directory; nothing was extracted)

| Archive | Data members | Ignored members |
| --- | --- | --- |
| `research_paper` | `Chinese_Climate_Finance_2000-2021.xlsx` (9.2 MB), `Chinese_Development_Finance_SDG_Categorizations_2000-2021.xlsx` (13.8 MB) | none |
| `aiddata` | `AidDatasGlobalChineseDevelopmentFinanceDataset_v3.0.xlsx` (26.4 MB), `ADM Location Data/GCDF_3.0_ADM1_Locations.csv`, `…ADM2_Locations.csv`, 3 PDFs (`TUFF Methodology 3.0.pdf`, `Field Definitions_GCDF 3.0.pdf`, `GCDF3.0 ADM Files README.pdf`) | 10 `__MACOSX/` resource forks and 2 `.DS_Store` files (12 of 18 file members), flagged as junk |
| `gcf_historical` | `mjcszv9t52-1/T20- DataBase V2.1 AG 250320.xlsx` (9.5 MB) | none |

All archives passed the CRC check. None contains traversal or absolute paths, symlinks or
encrypted members. The highest compression ratio is 34.5 (a 6 KB `.DS_Store`), well below the
200 limit.

## Mapping files to publishers (evidence)

| `source_id` | Publisher | Evidence that maps the file to its publisher | Primary unit (count) |
| --- | --- | --- | --- |
| `research_paper` | Scientific Data paper authors | Workbook names match the paper title. All 20,985 `AidData_Record_ID`s join AidData v3.0. Workbook author metadata shows the same individual for both files (created 2025-08). | AidData record (20,985) |
| `aiddata` | AidData, William & Mary | `Contents` sheet: "AidData's Global Chinese Development Finance Dataset, Version 3.0, Released November 07, 2023" | project/activity record (20,985) |
| `adb_pakistan` | Asian Development Bank | IATI `reporting-org ref="XM-DAC-46004"` (narrative "Asian Development Bank"), version 2.03, generated 2026-10-21 | IATI activity (193) |
| `gcf_projects` | Green Climate Fund | FP/SAP reference numbers, GCF-specific columns (BM, ESS Category, FA Financing) | funded project (379) |
| `gcf_readiness` | Green Climate Fund | `*-RS-nnn` readiness reference numbers | readiness row (876) |
| `gcf_countries` | Green Climate Fund | `# RP`, `# FA`, `RP/FA Financing $` columns | country aggregate (155) |
| `climate_funds_update` | Climate Funds Update | Filename. Sheets `Fund Status`, `Pledges`, `Projects` covering the funds CFU tracks. | approved project row (4,066) |
| `climate_project_explorer` | Climate Project Explorer | Every family and document URL is on `climateprojectexplorer.org` | project family (498) |
| `gcf_historical` | Research dataset authors (T20 study) | `TO READ` sheet. GCF FP/SAP `Ref_N`, 123 of which match the current GCF export. | GCF project (128) |

## Provenance caveats (confirmed observations)

- **The three GCF exports were written by `openpyxl`** (core properties creator "openpyxl",
  2026-11-08), and every cell is stored as text. They may be the GCF Open Data Library's own export
  format, or they may have been re-saved by a script. The bytes alone can't tell us which.
  **Action:** record the download URL and confirm.
- **The CFU workbook's author metadata names an individual** (created 2026-02-06, modified
  2026-03-18), not the publisher. **Action:** record the download URL.
- **Acquisition dates were not recorded.** File-system timestamps are not evidence of the download
  date, so `acquisition_date` is left null in the manifest.
- **The source URLs are unconfirmed** for 8 of the 9 sources. The filename patterns `30015124`
  (Figshare-like) and `mjcszv9t52-1` (Mendeley-Data-like) are recorded only as **assumptions**.

## Rights status

**All nine sources: `not_reviewed`.** AidData's `License` sheet states ODC-By 1.0. That is
recorded as a confirmed fact, but no human licence review has been done, so no permission is
claimed. Raw data is never committed or redistributed.

## Regenerate

```powershell
uv run compassio-data inventory            # hashes, formats, archive members -> artifacts/data_audit/source_inventory.json
uv run compassio-manifest write            # rebuild data/manifests/source_manifest.json (runs the audit for record counts)
uv run compassio-manifest validate         # re-hash data/raw and compare with the manifest
uv run compassio-data audit --check-reproducible   # all reports, twice, byte-compared
```
