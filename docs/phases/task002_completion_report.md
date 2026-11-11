# Task 002: Completion report (Phase 1A: dataset registration, inspection and audit)

Date: 2026-11-09 · Machine: developer workstation (Windows 11, Python 3.12.15, uv 0.13.0, Node 24.19.0,
pnpm 11.21.0) · Result: **all gates pass; data registered and audited; not yet ready for feature
engineering (see §14)**

## 0. Foundation preserved

- Baseline before changes: `bash scripts/check.sh` → all checks passed (67 tests, strict mypy,
  web lint, typecheck and build).
- First local commit `f948bcb` "Phase 0 foundation…" contains 79 files. Raw files were present
  and verified **not staged**: the largest staged file was `pnpm-lock.yaml` at 136 KB. Nothing
  was pushed, and no remote is configured.
- **Tagline corrected to exactly "Give Funding a Better Direction."** in `core/config.py`,
  `apps/web/src/lib/brand.ts`, the API test, README and CLAUDE.md, with a correction note in the
  Task 001 report. Verification:
  - live `GET /api/v1/meta` returned `"tagline":"Give Funding a Better Direction."`;
  - the built `index.html` contains it 4 times and contains the old wording 0 times;
  - the new test `tests/api/test_brand_consistency.py` keeps the API and web strings identical.
- The API endpoints and frontend behaviour are otherwise unchanged.

## 1. Original source files discovered

All 9 expected sources are present, including the optional GCF historical ZIP
(`docs/data/source_inventory.md`).

## 2. Distinct files

**9 files, 9 distinct SHA-256 values, no duplicate copies.** Archive members were listed from the
central directory and nothing was extracted. AidData's 10 `__MACOSX` entries and 2 `.DS_Store`
files are flagged as junk.

## 3. Hashes

| source_id | SHA-256 |
| --- | --- |
| research_paper | `f4420394676e17be8d78d2b8ddbb5293a7fcf0d4c0633edd7a34a0a3f539557d` |
| aiddata | `290da2887a6984beaa6d269d2171798951e0644cae579497dafb8bd78646e097` |
| adb_pakistan | `58f1dca29b4be3790cf7790fc578e723fda798a8f75755358fa69918efac6862` |
| gcf_projects | `dd7c0ee238b9557a3dbacf31c3061e1e8161796636a08f4674783a86cb18635f` |
| gcf_readiness | `ee4c75c16a3308856c9922f35b01051e58622d885bab22f82aaa762517a2189c` |
| gcf_countries | `0d0c3b027a9a3e9b6b55c7611706ebfbafe567a32b432e57dc7e3b7288b566bf` |
| climate_funds_update | `7b3cf06b948365da99a164d21bbb1d176db0e938ff70af9f2b391f070c14e099` |
| climate_project_explorer | `9850111cdcbcc55b71e36f0f1ba0745cb423cc241f2c4e53dc4df2f6de7ff5ea` |
| gcf_historical | `dbbf4aae107e664037f35c01d6c21a6b80722c181a9a262e43110df1ea1d0778` |

**Immutability:** hashes, sizes and modification times taken before any Task 002 code ran are
identical to those taken at the end (`diff` of both snapshots: no differences).

## 4. Research project count

**20,985 records**, one per AidData GCDF 3.0 record. All 20,985 `AidData_Record_ID` values are
unique, and every one matches AidData v3.0. This reproduces the earlier hypothesis exactly.

## 5. Climate-positive / negative

**1,383 positive (overall score > 0, 6.59%); 19,602 negative (`0,0,0`); 0 missing or invalid.**
Overall score: 568 significant (1), 815 principal (2). This reproduces the hypothesised 1,383.

## 6. Pakistan counts

| Unit | Count |
| --- | ---: |
| Research/AidData records (`Recipient == Pakistan`) | **496** (reproduces the hypothesis); 433 Recommended For Aggregates |
| Pakistan climate-positive research records | **76** (reproduces the hypothesis); 60 of them ENERGY |
| ADB IATI activities / ADB project numbers | 193 / 143 |
| GCF funded projects | 11 (8 single-country) |
| GCF readiness rows | 8 (country summary says 9) |
| CFU project rows | 31 |
| CPE families | 9 |

These counts are not additive (`docs/data/pakistan_coverage.md`).

## 7. 2026 coverage

**No verified project approved in 2026.** The only 2026 commitment is one ADB grant instrument,
`XM-DAC-46004-57223-002-GRNT4685`, started 2026-04-23. The other 2026 dates are not approvals:
3,130 ADB transactions dated 2026 (644 disbursements and 2,486 repayments) and 126 CPE families
with a 2026 publication date. GCF projects can't be dated from the file (`docs/data/2026_project_coverage.md`).

## 8. Climate-label field definitions

- `rio_marker` = `"a,b,c"`, each 0, 1 or 2.
  - **Confirmed:** `a = max(b, c)` in all 20,985 rows.
  - **Inferred, not documented in the archive:** `a` is the overall score, `b` mitigation, `c`
    adaptation, and 0/1/2 = not targeted / significant / principal (OECD Rio convention).
- Separate annotation: the SDG workbook (Centralized and Extended, `SDG1`–`SDG17`). SDG13 is
  correlated with the climate label, so it must be excluded from inputs.

Details: `docs/data/research_label_audit.md`.

## 9. Funding-field definitions and limitations

Every amount is classified by flow kind, level, unit and currency in
`docs/data/financial_fields_audit.md`:

- research and AidData amounts are commitments;
- ADB transactions are split into commitment, disbursement, interest and principal, and are 76%
  repayments;
- CFU amounts are approvals and cumulative disbursements in USD millions;
- GCF historical `Tot_Fin` is total cost in USD thousands;
- GCF units are assumed.

No currency conversion or cross-type summing was done.

## 10. Missing-data findings (highlights)

- Research/AidData: amount missing for 8,186; implementation start missing for 9,222; grant
  element missing for 18,090.
- CFU: `Summary` blank for 2,115 of 4,066; `Approved year` blank for 45.
- GCF exports: no dates and no descriptions.
- CPE: `Document Type` blank for 380 of 818.

Details: `docs/data/data_quality_audit.md`.

## 11. Duplication and cross-source concerns

- **The research workbooks are a re-representation of AidData**, the same 20,985 records. Titles
  are truncated to 255 characters in 12 rows, and one description dropped the word "null".
- **Leakage-relevant duplicates:** 1,351 rows share a normalized description, and 15 of those
  groups carry conflicting labels. 6,066 records sit in 1,949 AidData Parent-ID packages.
  Descriptions are retrospective: 8,699 mention a later year than the commitment year.
- **GCF ↔ CFU:** 329 GCF projects are found in CFU by the embedded FP/SAP code, so their totals
  must never be summed.
- **GCF ↔ GCF historical:** 123 of 128 references match; 5 historical references are absent from
  the current export.
- **GCF ↔ CPE:** 121 links by reference code and 2 by name only.
- **ADB:** 95 instruments share titles. The 3 ADB-entity GCF Pakistan projects have no same-title
  ADB activity.
- Nothing was merged (`docs/data/cross_source_overlap.md`, row-level evidence in
  `source_overlap_review.csv`).

## 12. Permission status

**All 9 sources: `not_reviewed`.** AidData's file states ODC-By 1.0, recorded as a confirmed fact
only. Two provenance caveats: the GCF exports were written by openpyxl, and the CFU workbook's
author is an individual. Download URLs and acquisition dates were not recorded, so they are null
or listed as assumptions in the manifest.

## 13. Tests and builds (commands actually run)

| Command | Result |
| --- | --- |
| `uv sync --locked` | ok (43 packages) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 64 files already formatted |
| `uv run mypy` | Success: no issues found in 54 source files |
| `uv run pytest` | **168 passed** (165 unit tests + 3 `local_data` integration tests) |
| `uv run pytest -m local_data` | 3 passed (real files: inventory clean, manifest matches, research ⊂ AidData) |
| `pnpm lint` / `pnpm typecheck` / `pnpm build` | passed; `/` prerendered |
| `bash scripts/check.sh` | All checks passed |
| `uv run compassio-data inventory` | 9 files, 9 distinct, 0 errors |
| `uv run compassio-manifest write` | 9 entries written |
| `uv run compassio-manifest validate` | Manifest valid: 9 entries; hashes and sizes match `data/raw` |
| `uv run compassio-data audit --check-reproducible` | **Reproducible: 11 deterministic files identical across two runs** (about 6 min) |
| `git status` / `git check-ignore` | raw files and `artifacts/` ignored; manifest and skill trackable; Task 002 changes uncommitted |

The new tests cover:

- **Hashing and manifests:** file hashes; manifest v2 validation (rights evidence, paths,
  facts/assumptions disjoint, duplicate hashes); manifest write, validate and tamper detection.
- **Inventory and formats:** missing sources and folders; unsupported, mismatched and macro
  formats; misplaced or unregistered files.
- **Archive safety:** corrupt, truncated and CRC-failing ZIPs; traversal, absolute, drive-letter
  and backslash paths; symlinks; encrypted members; ZIP-bomb ratio; size and count limits.
- **XML and spreadsheets:** invalid XML, entity expansion and external entities; spreadsheet
  reading (types, duplicate headers, empty rows).
- **Source logic:** missing and invalid labels; duplicate project IDs; missing currencies; unknown
  transaction types; ADB, CPE and readiness counting units; Pakistan filters (whitespace,
  multi-country, ISO lists); amount, year and date parsing; GCF reference-code matching.

All fixtures are artificial and labelled `example`.

**Warnings handled, not ignored:** Starlette's `httpx` deprecation was already resolved in Task 001.
pytest runs with `filterwarnings = error`. uv's "failed to hardlink" notice is an
environment-level message and not a code warning.

## 14. Ready for feature engineering?

**Not yet. Two blockers remain, and both can be resolved quickly:**

1. **Label semantics must be confirmed against the paper text.** The archive has no codebook. The
   binary target is safe; mitigation and adaptation claims are not.
2. **Leakage controls must be designed first**: grouping keys (normalized description, title
   series, AidData Parent ID), and an explicit statement that chronological evaluation uses
   retrospective text.

Recommended before any public use: record the download URLs, acquisition dates and a human rights
review for each source.

## 15. Recommended scope for Task 003: research dataset construction (no training)

1. Obtain the paper text (or its supplementary codebook), register it, and confirm the
   `rio_marker` positions and score meanings. Update `research/labels.py` names only if confirmed.
2. Build a **cleaned research table** in `data/processed/` with documented transforms only: whitespace,
   HTML-free text, the 255-character title note, and provenance columns (`source_id`, record ID,
   input sha256).
3. Compute and store **grouping keys** for leakage control, and design (but do not train on) the
   split protocol: grouped random, grouped chronological by `Commitment_Year`, and a held-out
   Pakistan slice. Freeze it in `configs/`.
4. Define the baseline evaluation plan: keyword baseline, TF-IDF + linear model, metrics with
   confidence intervals, and a Pakistan ENERGY / non-ENERGY breakdown.
5. Optional, reviewed: a link table for GCF ↔ CFU by reference code (gives approval years for
   GCF projects) and ADB project-number grouping. No merging into a consolidated project table yet.

Out of scope: model training, the production database, API project endpoints, and dashboards.

## Files created or changed in Task 002

- **New code:** `compassio_ml/safety/{archive,xml,spreadsheet}.py`;
  `data/{formats,parsing,sources,inventory,manifest_io}.py`; `research/labels.py`;
  `audit/{models,loaders,profiling,inspectors,research_audit,overlap,reports}.py`;
  `cli/{common,data_cli,manifest_cli}.py`.
- **Changed code:** `data/manifest.py` (schema v2), `pyproject.toml` files (dependencies, entry
  points, pytest marker), `uv.lock`, `.gitignore` (`artifacts/`), API config and web brand (tagline).
- **Tests:** `tests/ml/{conftest,test_archive_safety,test_xml_and_spreadsheet_safety,test_formats_and_parsing,test_inventory_and_manifest_io,test_inspectors}.py`,
  `tests/test_local_data.py`, `tests/api/test_brand_consistency.py`; updated `tests/ml/test_manifest.py`
  and `tests/api/test_system_endpoints.py`.
- **Data:** `data/manifests/source_manifest.json` (committed provenance; 16 KB).
- **Skill:** `.claude/skills/compassio-data-auditor/SKILL.md`.
- **Docs:** `docs/data/{source_inventory,source_schemas,data_quality_audit,research_label_audit,financial_fields_audit,cross_source_overlap,pakistan_coverage,2026_project_coverage}.md`;
  updated `source_register.md`, `data_contracts.md`, CLAUDE.md files, README, tech stack, system
  overview and phase plan.

## Dependencies added (resolved via `uv.lock`)

- **Runtime (compassio-ml):** pandas 3.1.1, numpy 2.5.4, openpyxl 3.1.5 (et-xmlfile 2.0.0),
  defusedxml 0.7.1, python-dateutil 4.0.0, tzdata 2026.6.
- **Dev:** pandas-stubs 3.1.0.261029, types-openpyxl 3.1.5.20261017, types-defusedxml 0.7.0.20260504.
- **No ML training libraries were installed.**

## Regenerate everything

```powershell
uv sync --locked
uv run compassio-manifest validate
uv run compassio-data audit --check-reproducible   # writes artifacts/data_audit/*
uv run pytest
```
