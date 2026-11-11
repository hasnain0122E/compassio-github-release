# Cross-source overlap

**Nothing has been merged.** This document records which records in different files describe the
same real-world project, and how confident each link is. Row-level evidence:
`artifacts/data_audit/source_overlap_review.csv` (from `uv run compassio-data audit`).

Status vocabulary used in the CSV:

| Status | Meaning | May be used to link? |
| --- | --- | --- |
| `same_record_stable_id` | Shared stable identifier; the same record re-published | Yes, with source kept |
| `same_record_text_differs` | Stable ID matches but a text field differs | Yes; record which text is authoritative |
| `probable_match_reference_code` | A source reference code (e.g. `FP085`) appears in the other source's text | After review |
| `possible_match_requires_review` | Names agree after normalization; **not** proof | Only after human review |
| `related_not_same` | Linked but distinct records (tranches, packages) | Never merge; group for splits |

## 1. Duplicate files

9 raw files with 9 distinct SHA-256 values: **no repeated archive copies** (only one AidData
archive was supplied).

## 2. Research paper ↔ AidData v3.0 (known repeated representation)

| Check | Result |
| --- | --- |
| Research `AidData_Record_ID` found in AidData | **20,985 / 20,985** (0 unmatched either way) |
| Commitment year, recipient, sector, flow type identical | 20,985 / 20,985 each |
| Title identical | 20,973. **12 research titles are truncated to 255 characters.** |
| Description identical | 20,984. The one difference (record 54013) is a dropped word "null". |
| Amount equal to `Amount (Constant USD 2021)` within $0.005 | 20,985 |

**Conclusion:** the research climate workbook is AidData GCDF 3.0: 14 of AidData's 126 columns,
plus a new sequential `ID` and the `rio_marker` label. The two must be treated as one population: never count both,
and never use AidData as "independent" validation of the research labels.

**Within AidData:** 6,066 records sit in 1,949 multi-record `AidData Parent ID` packages
(`related_not_same`). 1,789 are umbrella agreements, and 3,028 are "Not Recommended For
Aggregates".

## 3. GCF funded projects ↔ GCF historical research dataset (T20, 2020)

- 123 of the 128 historical `Ref_N` values match current `Ref #` values (`same_record_stable_id`),
  and the theme is identical for all 123.
- 5 historical references are **absent from the current export**: FP038, FP088, FP093, FP104 and
  SAP013. Possible reasons, such as withdrawal or a scope difference, need review. No reason is
  asserted.
- The historical file is a 2020 snapshot with co-financing detail. The current export is
  authoritative for the project list.

## 4. GCF funded projects ↔ Climate Funds Update

- CFU contains 1,196 rows from GCF funds (`GCF-1`, `GCF-2`, `GCF IRM`), of which 714 are outside
  the IRM fund line.
- CFU project names embed GCF codes, e.g. `(FP001) Building the Resilience of Wetlands…`.
  - **329 of 379** GCF projects are found in CFU by reference code
    (`probable_match_reference_code`).
  - 0 more are found by name alone.
  - No GCF project matches more than one CFU row.
- 6 GCF codes in CFU are absent from the GCF export: FP093, FP221, SAP013, SAP016, SAP054 and
  SAP065.
- **Consequence:** CFU's GCF rows and the GCF exports must never be summed. CFU's
  `Approved year` could supply approval years for those 329 GCF projects, which the GCF export
  lacks. That would be a cross-source attribution and needs explicit review (Task 003).
- **GCF readiness ↔ CFU:** only 2 of 876 readiness rows share title and country with a CFU GCF
  row. Readiness titles are generic ("NDA Strengthening"), so these are possible matches only.

## 5. Climate Project Explorer ↔ GCF funded projects

- CPE has 134 GCF families (and 251 GEF, 59 AF and 54 CIF families).
- 121 links come from GCF reference codes found in CPE family names, document titles or summaries
  (`probable_match_reference_code`).
- 2 come from family-name equality alone (`possible_match_requires_review`).
- CPE rows are **documents** (818) describing **families** (498). Counting rows would inflate
  projects 1.6×.

## 6. ADB IATI: activities, project numbers and titles

- The 193 activities are financing instruments under 143 ADB project numbers (`37218-013` in
  `XM-DAC-46004-37218-013-LN2202`).
- 95 activities share a title with another activity (44 groups) (`related_not_same`). Only 1 title
  group spans more than one project number.
- **ADB ↔ GCF Pakistan:** 3 GCF Pakistan projects list ADB as accredited entity: FP085 Green BRT
  Karachi, FP215 Community Resilience Partnership Program and FP283 Glaciers to Farms. **None has
  a same-title ADB IATI activity.** ADB's own co-financing may be reported under different titles,
  so these are recorded as `possible_match_requires_review` with no ADB key.

## 7. Independent vs repeated representations

| Population | Independent source | Repeated representations |
| --- | --- | --- |
| Chinese development finance 2000–2021 | AidData GCDF 3.0 (20,985 records) | Research climate and SDG workbooks (same 20,985) |
| GCF funded projects | GCF export (379) | GCF historical (123 of 128), CFU GCF rows (329 coded), CPE GCF families (≥ 121) |
| GCF readiness | GCF readiness export (876 rows) | CFU GCF IRM rows (partly) |
| ADB Pakistan finance | ADB IATI (193 instruments / 143 projects) | Possibly co-financing within GCF FP085, FP215 and FP283 (unconfirmed) |
| Other climate funds (GEF, AF, CIF, …) | CFU rows for those funds; CPE families | CPE ↔ CFU for non-GCF funds was **not examined** in this audit |

## 8. Proposed linkage rules for Task 003 (not implemented)

1. Link only by stable ID or reference code. Keep a separate `links` table with `method`,
   `status`, `reviewed_by` and `reviewed_at`.
2. Never infer identity from names. Name-only candidates go to a human review queue.
3. Keep every source's own amounts and dates; select one source per view and state it.
