# Research dataset cleaning specification (v1)

Implementation: `compassio_ml.research` (`dataset.py`, `text.py`, `labels.py`,
`retrospective.py`). Build command: `uv run compassio-research build`. Observed counts below are
from `artifacts/research_v1/build_summary.json`.

## 1. Inputs and preconditions

| Input | Registered file | Required check |
| --- | --- | --- |
| Research climate annotations | `research_paper/30015124.zip` → `Chinese_Climate_Finance_2000-2021.xlsx` | Manifest SHA-256 matches |
| AidData GCDF 3.0 | `aiddata/…Version_3_0.zip` → `AidDatasGlobalChineseDevelopmentFinanceDataset_v3.0.xlsx`, sheet `GCDF_3.0` | Manifest SHA-256 matches |

The build **refuses to run** if `compassio-manifest validate` fails, for example because a file
is missing, changed, unregistered or refused. Files are read only through the Task 002 safety
layer, and nothing is written into `data/raw`.

## 2. Join (one-to-one, exact)

- Key: research `AidData_Record_ID` == AidData `AidData Record ID`, as an exact string. **No
  fuzzy matching.**
- Both keys must be present and unique; otherwise `JoinIntegrityError` is raised. The merge uses
  `validate="one_to_one"`.

**Observed:**

| Check | Value |
| --- | --- |
| Research rows / AidData rows | 20,985 / 20,985 |
| Keys unique on both sides | yes / yes |
| Matched / research-only / AidData-only | 20,985 / 0 / 0 |
| Joined rows | 20,985 |

**Field mismatches (exact):** `Title` 12, `Funding_Agencies` 7, `Funding_Agencies_Type` 1,
`Description` 1. The following match in every row: `Commitment_Year`, `Recipient`,
`Recipient_Region`, `Sector_Name`, `Flow_Type`. Amounts beyond $0.005 differ in 0 rows.

**Cause of the mismatches [observed]:** every `Title` and `Funding_Agencies*` difference is a
research value **truncated to 255 characters** where AidData holds the full value. The one
`Description` difference is the dropped word "null".

The two sources are representations of the same 20,985 projects. The output has one row per
AidData record, never stacked.

## 3. Source vs normalized columns

Source values are never overwritten:

- `data/processed/research_text_originals.parquet` holds the four untouched source texts per
  record: `title_aiddata_src`, `description_aiddata_src`, `title_research_src` and
  `description_research_src`.
- The main table keeps SHA-256 hashes of the AidData source text (`title_source_sha256`,
  `description_source_sha256`) and every `*_src` value it parses (`commitment_year_src`,
  `amount_original_src`, `rio_marker_src`).
- **Text source decision:** cleaned text is derived from **AidData** (upstream and untruncated).
  `research_title_differs` / `research_title_truncated_255` (12 rows) and
  `research_description_differs` (1 row) flag where the annotated copy differs.

## 4. Text transformations (applied in this order; each recorded per row only if it changed the text)

| # | Step id | Rule | Titles changed | Descriptions changed |
| --- | --- | --- | ---: | ---: |
| 1 | `sentinel_to_null` | Blank or `nan`/`null`/`none`/`n/a`/`na`/`-` (case-insensitive, whole value) → null | 0 | 0 |
| 2 | `unicode_nfc` | Unicode **NFC** composition | 0 | 1 |
| 3 | `html_markup_removed` | If an HTML tag is present: keep text nodes only, using the standard-library `HTMLParser` (no network, no execution, `<script>`/`<style>` content dropped, block tags become spaces) | 0 | 0 |
| 3b | `html_entities_unescaped` | If entities but no tags: `html.unescape` | 0 | 0 |
| 4 | `zero_width_removed` | Remove U+200B/200C/200D/2060/FEFF | 6 | 231 |
| 5 | `whitespace_normalized` | NBSP/figure/narrow-NBSP, tab, CR, LF, VT and FF → space; collapse runs of spaces; trim | 1,045 | 14,305 |

**Deliberately not done:**

- **NFKC** normalization, which would rewrite `²`, full-width punctuation and similar characters.
  1,821 descriptions contain Chinese characters, and NFKC would alter 639 descriptions.
- Lower-casing, spelling correction, translation, summarisation or LLM rewriting.
- Truncation. The longest description, 25,936 characters, is kept in full.
- Removing duplicates, outliers or "unusual" amounts.

Cleaning is idempotent: cleaning a cleaned value changes nothing (tested).

## 5. Other parsing (validated, no inference)

| Field | Rule | On failure |
| --- | --- | --- |
| `commitment_year` | Integer 1950–2100 from AidData `Commitment Year` | null + `commitment_year_error`, and the record is quarantined (0 occurred) |
| `commitment_date` | ISO date from `Commitment Date (MM/DD/YYYY)`; `commitment_date_estimated` kept as published (`Yes` for 11,782) | null |
| Yes/No fields | `Yes`/`No` → boolean; blank → null (never `No`) | error |
| `amount_original`, `amount_constant_usd_2021` | Decimal → float. `amount_currency` from `Original Currency`; `amount_unit` = "units of amount_currency"; `amount_kind` = commitment or pledge | null. **Never imputed** (8,186 records have no amount). |
| `rio_marker_src` → `rio_overall`, `rio_mitigation`, `rio_adaptation`, `is_climate_related` | Three integers in {0,1,2}; `is_climate_related = rio_overall > 0`; `rio_overall_is_max` checked | null + `label_error`, and the record is quarantined (0 occurred) |

## 6. Derived diagnostic columns (warnings only; never used to drop records)

- **`retrospective_text_warning`** and **`retrospective_signals`** cover four lexical signals:
  - a mention of a year after the commitment year and ≤ 2023, AidData's implementation-tracking
    horizon. Later years are treated as contractual schedules, not events;
  - completion language ("was completed", "handover ceremony", "put into operation" …);
  - disbursement or repayment language;
  - status-outcome language ("was cancelled/suspended", "never materialised", "as of <date> 20xx").
- **`label_revealing_terms`** flags explicit climate vocabulary ("climate change", "greenhouse
  gas", "low-carbon", "renewable energy" …). It is a lexical-leakage indicator, separate from
  the retrospective warning.

**Limitations:** lexical patterns miss paraphrase and cannot date the text. A flag is a warning,
and its absence does not show that the text predates the commitment.

## 7. Eligibility (mutually exclusive `eligibility_status`, with pipe-joined `exclusion_reasons`)

| Status | Rule (first matching tier wins) |
| --- | --- |
| `quarantined` | `invalid_or_missing_rio_marker`, `rio_overall_not_max_of_components`, `conflicting_label_same_description` (all members of a normalized-description group whose members disagree on `is_climate_related`), or `invalid_commitment_year` |
| `analytics_only` | `insufficient_description`: null, under 40 characters or under 6 words. Such a record is **not** treated as a negative. |
| `eligible` | Everything else. Missing amounts, an estimated date, "Not Recommended For Aggregates" or a retrospective warning do **not** block text classification. |

Nothing is deleted: quarantined and analytics-only records stay in the table with their
original labels.

## 8. Output tables (git-ignored; regenerable; byte-reproducible)

| File | Rows | Contents |
| --- | ---: | --- |
| `data/processed/research_projects.parquet` | 20,985 | 58 columns: ids and provenance hashes, cleaned text and cleaning steps, context, finance, label, diagnostics, eligibility, `leakage_group_id`/`leakage_group_size` |
| `data/processed/research_text_originals.parquet` | 20,985 | untouched source text, both copies |
| `data/processed/research_split_membership_v1.parquet` | 20,985 | split membership per protocol (`model_evaluation_protocol.md`) |

**Limitations carried with the data** (also in `research_projects` columns):

- Descriptions are retrospective.
- Amounts are commitments or pledges, not disbursements.
- Labels are the authors' annotations, with no per-record agreement score.
- Coverage is Chinese official finance, 2000–2021, only.
