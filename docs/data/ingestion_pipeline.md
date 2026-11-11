# Ingestion pipeline (Task 006)

```powershell
uv run compassio-db migrate                               # alembic upgrade head
uv run compassio-db ingest --source all                   # or research_paper | gcf_projects | climate_funds_update | adb_pakistan
uv run compassio-db status                                # table counts + recent import runs
uv run compassio-db verify --report artifacts/db/integrity_report.json
```

Use `--database-url` to override `COMPASSIO_DATABASE_URL` and `--data-dir` to override
`COMPASSIO_DATA_DIR`. The code lives in `compassio_api.ingest`, which runs offline and is never
imported by the API process (tested).

## 1. Steps (`ingest/runner.py`)

1. **Verify inputs.** `compassio_ml.data.manifest_io.validate_manifest` re-hashes all 9 raw files
   against the committed manifest. Any mismatch is refused (exit 2).
   - **Research table:** `data/processed/research_projects.parquet` must also match the
     committed Task 003 lock (`configs/research_split_v1.lock.json`, table SHA-256 `71fc5a10…`).
2. **Sync source metadata** from the manifest and the registry into `sources`, including
   `rights_status` and evidence, which are copied and never changed.
3. **Build records.** Pure functions turn frames into records:
   - the frames come from the **audited loaders** (`compassio_ml.audit.loaders.SourceData`,
     which uses the safe ZIP/XML/XLSX readers) and the Task 003 table;
   - there are **no new parsers**.
4. **Validate every amount** through `compassio_ml.finance.MonetaryAmount`. A violation (e.g. a
   negative project-level amount or a negative commitment) is stored as `invalid` with a
   warning, never coerced.
5. **Write idempotently** (`ingest/loader.py`), keyed on `<source_id>:<source_project_id>` and a
   SHA-256 of the record's full content:

   | Case | Outcome |
   | --- | --- |
   | New ID | **inserted** |
   | Same ID, same hash | **unchanged** (nothing written) |
   | Same ID, different hash | **updated** (row and children replaced in one transaction) |
   | Empty ID or title, or ID repeated within the file | **rejected**, with the reason recorded in `import_runs.message` |
   | In the database but no longer in the file | **removed** (reported) |

6. **Rebuild cross-source links** (`rebuild_reference_code_links`), deterministically, after every
   run.
7. **Record the run** in `import_runs`: input hashes and counts, status `completed`, or
   `failed` (rolled back, error recorded).

## 2. Sources

### A. `research_paper` → project rows `aiddata:<AidData Record ID>`

- **Input:** the verified Task 003 table, plus `research_text_originals.parquet` for the title
  and description **as AidData publishes them**. The training-cleaned text is not used for
  display.
- **Rows:** one per AidData record (20,985). The research workbook is the same population, so it
  contributes the **annotation**, not a second row.
- **Annotation:** `rio_marker_qi_et_al_2026`, kind `research_annotation`, `is_model_prediction =
  false`; overall, mitigation and adaptation scores plus the raw marker text. Unparseable labels
  are not invented (warning instead).
- **Amounts:** two observations per record:
  - `Amount (Original Currency)`: nominal, in its own currency (102 currencies);
  - `Amount (Constant USD 2021)`: AidData's own conversion, not re-derived.

  Flow kind is `pledge` for status "Pipeline: Pledge", otherwise `commitment`. Missing amounts
  are `not_reported` with NULL amount. The estimate flag and `recommended_for_aggregates` are
  kept.
- **Dates:** commitment date (precision day, estimated flag kept) and commitment year.
- **Grouping:** AidData Parent ID → `group_key aiddata_parent:<id>`.
- **Countries:** ISO3 from AidData; regional recipients have `iso3 = NULL` and
  `multi_country = true`.
- **Not ingested:** split membership and test partitions. The frozen ML tests are untouched.

### B. `gcf_projects` → `gcf_projects:<Ref #>` (379)

- **Countries:** split by comma. ISO3 and region come **only** from an exact name match in GCF's
  own `gcf_countries` export (all 137 names matched).
- **Multi-country (96):** `multi_country = true`; the amount is whole-project.
- **`FA Financing`:** flow `gcf_financing`, `currency = NULL`, `unit = NULL`, `unit_status =
  not_stated_in_source`. The audit marks USD as assumed, so it is kept unknown.
- **No description, approval date or status in the export:** the board meeting code is kept as
  an attribute and is not converted to a date.
- **Annotation:** GCF theme, kind `source_classification`.
- **Attributes:** modality, entity, sector type, size, ESS category.

### C. `climate_funds_update` → `climate_funds_update:projects-r<row>` (4,066)

- **Identity:** row number, because no ID is published; warning `no_source_identifier`.
- **Countries:** exact-name lookup from two registered sources, GCF countries then AidData
  recipient–ISO3 pairs (names the two disagree on are dropped).

  | Outcome | Rows |
  | --- | ---: |
  | Mapped via GCF | 3,025 |
  | Mapped via AidData | 245 |
  | Multi-country, global or regional labels (`multi_country = true`) | 563 |
  | **Unmatched**, kept as published with ISO3 NULL (e.g. "Lao PDR", "Vietnam", "Congo, Dem. Rep."; 14 distinct names) | 233 |

  ISO3 codes are not guessed.
- **Amounts (USD millions, as stated):**
  - approval total;
  - instrument components flagged `is_component = true`;
  - cumulative disbursement, undated (snapshot).

  Whitespace-only cells are `not_reported`. One negative disbursement (−0.01075722) is
  `invalid`.
- **GCF codes:** a GCF code in the name becomes `attributes.gcf_reference_code` (335 rows) plus a
  link (§3).

### D. `adb_pakistan` → `adb_pakistan:<IATI identifier>` (193 instruments)

- **Grouping:** under the ADB project number from the identifier (143 groups).
- **Transactions:** each is one transaction-level observation:

  | IATI type | Flow kind | Count |
  | --- | --- | ---: |
  | 2 | commitment | 192 |
  | 3 | disbursement | 7,117 |
  | 5 | repayment_interest | 14,062 |
  | 6 | repayment_principal | 9,591 |

  Signs are kept as published (31 negative disbursements and 6 negative interest values are
  legitimate transaction-level reversals).
- **Currency:** the transaction's own, else the activity's declared `default-currency`
  (`unit_status = declared_default_currency`).
- **Year:** actual start, else planned start (`year_type` records which).
- **Status:** IATI ActivityStatus code label.

## 3. Cross-source relationships

| Link | Status | Count |
| --- | --- | ---: |
| CFU row → GCF project, by GCF code in the CFU name | `probable_match_reference_code`, `human_reviewed = false` | **329** |

- **Unresolved codes:** 6 CFU codes have no GCF export row (FP093, FP221, SAP013, SAP016, SAP054,
  SAP065, as in the audit).
- **One-to-one:** no GCF project is linked from more than one CFU row (verified).
- **ADB ↔ GCF** (FP085, FP215, FP283): `possible_match_requires_review` in the audit with no ADB
  key, so **no link is created**.

## 4. Real run (2026-11-09, `data/db/compassio_dev.sqlite`)

| Run | Source | Inserted | Updated | Unchanged | Rejected | Removed |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | research_paper (→ aiddata) | 20,985 | 0 | 0 | 0 | 0 |
| 2 | gcf_projects | 379 | 0 | 0 | 0 | 0 |
| 3 | climate_funds_update | 4,066 | 0 | 0 | 0 | 0 |
| 4 | adb_pakistan | 193 | 0 | 0 | 0 | 0 |
| 5 | research_paper (re-run) | 0 | 0 | **20,985** | 0 | 0 |

- **Rows written:** 25,623 projects, 26,321 country rows, 25,430 annotations, **85,765 financial
  observations**, 329 relationships, 43,204 warnings.
- **Duration:** full ingestion of all four sources takes about 45 s on this workstation.
- **Verification:** see `docs/phases/task006_completion_report.md` (all 20 audited figures
  match).
