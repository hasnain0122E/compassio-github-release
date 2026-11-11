# 2026 project coverage

Generated table: `artifacts/data_audit/year_2026_coverage.csv` (from `uv run compassio-data audit`).
"2026" here means a date field whose value falls in calendar year 2026. Each row states **what that
date means**. A 2026 transaction, publication date or planned end date is **not** a 2026 project.

## Summary

**No source verifies any project *approved* in 2026. The only 2026 commitment is one ADB grant
instrument.** The evidence:

- **ADB IATI (Pakistan):** **1 activity with an actual start in 2026** (2026-04-23):
  `XM-DAC-46004-57223-002-GRNT4685`, a grant. It is also the only activity with a 2026 commitment
  transaction. Treat it as **one 2026 financing instrument** under ADB project `57223-002`, not
  as proof of a new *project*.
- **Climate Project Explorer:** 126 families (192 documents) have a 2026 *publication date on the
  explorer*. That is when CPE published them, not an approval date.
- **GCF funded projects:** **cannot be determined from the file.** The export has board-meeting
  codes (B.11–B.46) but no dates. Mapping board meetings to dates would need a separately
  registered GCF reference.

## By source

| Source | Date field | Meaning | 2026 records | Notes |
| --- | --- | --- | ---: | --- |
| research_paper | `Commitment_Year` | commitment year | 0 | Coverage is 2000–2021 |
| aiddata | `Commitment Year` | commitment year | 0 | Released 2023-11-07; coverage 2000–2021 |
| aiddata | `Planned Completion Date` | planned completion (forecast) | 11 | A forecast, not an event |
| aiddata | `First / Last Loan Repayment Date` | contractual schedule | 27 / 165 | Scheduled repayments, not projects |
| adb_pakistan | activity-date type 2 | actual start | **1** | Instrument level |
| adb_pakistan | activity-date type 3 / 4 | planned end / actual end | 14 / 7 | Lifecycle events of older instruments |
| adb_pakistan | transaction type 2 | commitment | **1** | |
| adb_pakistan | transaction type 3 | disbursement | 644 | Payments on existing loans and grants |
| adb_pakistan | transaction types 5 / 6 | interest / principal repayment | 1,412 / 1,074 | Inflows to ADB, not funding |
| gcf_projects | `BM` | board meeting code | **unknown** | No dates in the export |
| gcf_readiness | `Approved Date` | approval date | 0 | Latest approval 2025-05-30 |
| gcf_countries | — | aggregate snapshot | n/a | No dates |
| gcf_historical | — | 2020 snapshot | n/a | No dates; workbook modified 2020-03-26 |
| climate_funds_update | `Approved year` | approval year | 0 | Latest year 2025 (271 rows); 45 rows have no year |
| climate_project_explorer | `Family Publication Date` | explorer publication date | 126 families | Not approval; range 2024-02-13 to 2026-10-05 |

## File-level freshness (metadata, not record dates)

| Source | Evidence of recency |
| --- | --- |
| adb_pakistan | `generated-datetime` 2026-10-21. All activities `last-updated` 2026-10-21. Transactions run to 2026-09-30. |
| gcf_* exports | Filename suffixes read as export timestamps 2026-11-08 **[assumption]** |
| climate_funds_update | Workbook modified 2026-03-18; the data runs to 2025 |
| climate_project_explorer | Latest publication date 2026-10-05 |

## Implications

- A "2026 projects" view cannot be built from the current inventory. The honest options are:
  1. show ADB's 2026 instrument and 2026 transactions *as transactions*;
  2. show CPE documents published in 2026 *as publications*;
  3. obtain a dated GCF project source, or the board-meeting dates as a registered reference, and
     register it.
- The research model's training data ends in 2021. Any 2026 records shown in Compassio are out of
  the model's time range, and screening them is extrapolation (see `research_label_audit.md` §9).
