# Cleaned research dataset: coverage and completeness (v1)

Table: `data/processed/research_projects.parquet`, built by `uv run compassio-research build`.
Machine-readable breakdowns: `artifacts/research_v1/field_completeness.csv` (by all, label,
Pakistan, year, sector and recipient) and `eligibility_report.csv`.

## 1. Populations

| Population | Records | Climate-related | Pakistan | Pakistan climate-related |
| --- | ---: | ---: | ---: | ---: |
| All cleaned records (one per AidData record) | **20,985** | 1,383 | 496 | 76 |
| **A. Eligible supervised** | **20,936** | 1,359 | 496 | 76 |
| **B. Quarantined (review required)** | **49** | 24 | 0 | 0 |
| **C. Analytics-only** | **0** | — | — | — |

- **B** consists entirely of `conflicting_label_same_description`: 15 description groups.
  No label is invalid or missing, no `rio_overall ≠ max` case exists, and no commitment year is
  invalid.
- **C** is empty because every description is at least 68 characters, above the 40-character /
  6-word floor. The rule exists so that future records with thin text are never silently
  treated as negatives.
- Quarantined records span commitment years 2007–2021, and none is Pakistani.
- All 20,985 records remain usable for **historical analytics** (discovery, counts and trends,
  subject to AidData's "Recommended For Aggregates" flag for financial totals). Eligibility
  governs supervised learning only.

## 2. Field completeness (all records)

| Field | Present | Missing | Present share |
| --- | ---: | ---: | ---: |
| `record_id` (source ID) | 20,985 | 0 | 100% |
| `title_clean` | 20,985 | 0 | 100% |
| `description_clean` | 20,985 | 0 | 100% |
| `parent_id` | 6,416 | 14,569 | 30.6% |
| `commitment_year` | 20,985 | 0 | 100% |
| `recipient` | 20,985 | 0 | 100% |
| `recipient_iso3` | 20,702 | 283 | 98.7% (283 regional or multi-region records have no ISO-3 code) |
| `sector_name` | 20,985 | 0 | 100% |
| `rio_marker_src` (label) | 20,985 | 0 | 100% |
| `amount_original` / `amount_currency` | 12,799 | 8,186 | 61.0% (always both present or both absent) |
| `amount_constant_usd_2021` | 12,799 | 8,186 | 61.0% |

## 3. Missingness breakdowns (financial fields; text and labels are complete everywhere)

| Breakdown | Amount present | Parent ID present |
| --- | ---: | ---: |
| Climate-related (1,383) | **76.8%** | 44.5% |
| Not climate-related (19,602) | 59.9% | 29.6% |
| Pakistan (496) | 72.2% | 29.2% |
| Non-Pakistan (20,489) | 60.7% | 30.6% |

- **By commitment year:** amount coverage falls from 76–80% in 2000–2002 to 48–50% in
  2018–2019, then recovers to 59–60% in 2020–2021.
- **By sector:**
  - lowest: EDUCATION 26.6% (2,826 records), OTHER COMMODITY ASSISTANCE 35.3%, GOVERNMENT AND
    CIVIL SOCIETY 48.9%, HEALTH 52.2%;
  - highest: BANKING AND FINANCIAL SERVICES 96.5%, GENERAL BUDGET SUPPORT 97.7%.

- **By simplified flow type:** Loan 91.8%, Grant 50.4%, Vague 22.4%, Debt Rescheduling 0.5%.

**Implication:** missing amounts are **not random**. They concentrate in grants and in-kind
sectors and are rarer among climate-relevant projects. Never impute them. A financial view must
state its coverage, and an amount is never required for text classification.

## 4. Pakistan subset

- 496 records, identified by `recipient_iso3 == "PAK"`, which is identical to `Recipient ==
  "Pakistan"`. All are eligible.
- 76 are climate-related: 60 in ENERGY, 16 in other sectors.
- **Top sectors:** ENERGY 86, EMERGENCY RESPONSE 82, HEALTH 53, EDUCATION 51, GENERAL BUDGET
  SUPPORT 43.
- **The 283 records without ISO-3 are not counted as Pakistan.** They include 54 "Asia,
  regional" records, some of which may involve Pakistan.

## 5. Diagnostics carried in the table

| Column | Records flagged |
| --- | ---: |
| `retrospective_text_warning` | 10,664 (50.8%) |
| `label_revealing_terms` | 133 |
| `research_title_truncated_255` | 12 |
| `research_description_differs` | 1 |
| `commitment_date_estimated` | 11,782 |
| `recommended_for_aggregates = False` | 3,028 |
