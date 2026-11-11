# Pakistan coverage

Generated tables: `artifacts/data_audit/pakistan_coverage.csv` and the `audit_facts.json` sources
section (from `uv run compassio-data audit`). Each count states its **unit**. Counts from
different sources are **not additive**: several are the same projects represented more than once
(`cross_source_overlap.md`).

## By source

| Source | Filter rule | Unit | Pakistan records | Climate-flagged | Notes |
| --- | --- | --- | ---: | ---: | --- |
| research_paper | `Recipient == "Pakistan"` | AidData record | **496** | **76** | 76 = `rio_marker` overall > 0 |
| aiddata | `Recipient ISO-3 == "PAK"` | AidData record | 496 | — | **The same 496 records** as research_paper. 433 are Recommended For Aggregates. |
| adb_pakistan | `recipient-country == "PK"` | IATI activity (instrument) | 193 | — | 143 ADB project numbers. ADB markers are not Rio markers. |
| gcf_projects | `"Pakistan"` in `Countries` | GCF funded project | 11 | 11 | 8 single-country, 3 multi-country. Every GCF project is climate-dedicated. |
| gcf_readiness | `Country == "Pakistan"` | readiness row | 8 | — | Capacity support, not investment |
| gcf_countries | `ISO3 == "PAK"` | country aggregate | 1 | — | `# RP` 9, `# FA` 11, RP $6,136,870.44, FA $331,727,118 |
| gcf_historical | no country field | GCF project | via Ref_N only | — | FP018, FP085 and FP108 are present (2020 snapshot) |
| climate_funds_update | `Country == "Pakistan"` | approved project row | 31 | 31 | Excludes 1 "South Asia" regional row that may include Pakistan |
| climate_project_explorer | `"PAK"` in `Geographies` | project family | 9 | — | 20 document rows |

## Research labels for Pakistan (the model-relevant subset)

- **496 records; 76 climate-positive (15.3%)**, against 6.6% overall. Overall score: 62 principal,
  14 significant. Position 2 (inferred mitigation) is non-zero for 69, and position 3 (inferred
  adaptation) for 41.
- The positives are concentrated in **ENERGY (60 of 76)**. The rest: transport and storage 4,
  other social infrastructure 3, agriculture/forestry/fishing 2, general environmental protection 2,
  and 1 each in debt, education, emergency response, other multisector and water supply.
- Records and positives by commitment year:

  | Year | 2000 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 |
  | --- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
  | Records | 9 | 12 | 4 | 8 | 3 | 27 | 12 | 8 | 10 | 20 | 46 | 18 | 4 | 14 | 16 | 41 | 25 | 47 | 34 | 34 | 69 | 35 |
  | Positive | 0 | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 5 | 7 | 3 | 0 | 3 | 3 | 21 | 6 | 11 | 1 | 1 | 4 | 7 |

- **Evaluation implication:** 76 positives is a small evaluation set. 21 come from 2015 alone,
  and 51 fall in 2015–2021, so any Pakistan metric will have wide confidence intervals and must
  report them.
- Sector dominance means a Pakistan evaluation mostly tests energy-project recognition. Report
  performance excluding ENERGY as well.

## Finance for Pakistan (by type; never summed across types or sources)

| Source | Measure | Value | Caveat |
| --- | --- | ---: | --- |
| aiddata | Commitments, constant 2021 USD, Recommended For Aggregates, records with amounts (318) | $102,852,446,552 | Commitments, not disbursements. Includes loans. |
| gcf_countries | GCF funded-activity financing attributed to Pakistan | $331,727,118 | GCF's own country attribution |
| gcf_projects | `FA Financing`, 8 single-country projects | $258,727,978 | |
| gcf_projects | `FA Financing`, 3 multi-country projects (whole-project) | $628,000,000 | **Not** Pakistan's share |
| adb_pakistan | Commitments (192 transactions) | $32,126,214,330 | Instrument level. ADB's Pakistan file only. |
| adb_pakistan | Disbursements (7,117 transactions) | $21,549,925,013 | History begins 2013-12-31 in this file |

## Consistency checks between Pakistan sources

- GCF country summary `# FA` = 11 equals the 11 Pakistan projects in the export [observed].
- GCF country summary `# RP` = 9, but the readiness export has 8 Pakistan rows [observed]. The
  difference is unexplained and needs review.
- Of the 11 GCF Pakistan projects, all 11 are found in CFU by reference code. 3 list ADB as
  accredited entity, but none has a same-title activity in ADB IATI.

## Limitations

- The research/AidData Pakistan records cover **Chinese** official finance only (2000–2021).
  ADB, GCF and CFU cover other financiers. There is no single complete picture of Pakistan
  climate finance in this inventory.
- No Pakistan source has labels in the research annotation scheme other than research_paper.
  Applying the model to ADB, GCF or CFU Pakistan records is **out-of-source** transfer.
