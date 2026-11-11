---
name: compassio-data-auditor
description: Review, inspect or audit Compassio source datasets (research paper labels, AidData, ADB IATI, GCF, Climate Funds Update, Climate Project Explorer). Use when registering raw files, checking counts, labels, funding fields, duplicates, Pakistan or year coverage, or cross-source overlap, and before any cleaning or modelling that depends on these sources.
---

# Compassio data auditor

Evidence-first review of Compassio's source data. Each conclusion must trace back to a command
you ran on a registered file. Background: `docs/data/data_integrity_policy.md`; current findings:
`docs/data/data_quality_audit.md`.

## 1. Start from the registered inventory

```bash
uv run compassio-manifest validate        # hashes in data/manifests match data/raw
uv run compassio-data audit               # regenerates artifacts/data_audit/*
```

- If validation fails or a source is missing, **stop and report it**. Never re-download,
  substitute or fabricate data.
- Raw files are immutable. Read them only through `compassio_ml.safety` (safe ZIP/XML/XLSX
  readers) and never write into `data/raw/`.
- Rights: `rights_status` stays `not_reviewed` unless a human has recorded written evidence.
  A licence statement found inside a file is a *confirmed fact*, not an approval.

## 2. Name the unit of observation before you count

| Source | Count this | Not this |
| --- | --- | --- |
| research_paper / aiddata | AidData record (`AidData_Record_ID`) | linked packages (`AidData Parent ID`) are related, not duplicates |
| adb_pakistan | IATI activity = loan/grant instrument; project = ADB project number | transactions (mostly repayments) |
| gcf_projects / gcf_historical | FP/SAP reference | multi-country rows are one project |
| gcf_readiness | row (Ref # is not unique) | not investment projects |
| gcf_countries, CFU Fund Status/Pledges | aggregates | never add to project totals |
| climate_project_explorer | family (`Family URL`) | document rows |

Always state the unit next to the number ("193 IATI activities", not "193 projects").

## 3. Climate label semantics

- The research label is `rio_marker` = `"overall,mitigation,adaptation"`, each 0 = not
  targeted, 1 = significant objective, 2 = principal objective. This is **documented** by Qi et al.
  2026 (*Sci Data* 13:277), Table 1 header and Methods › Data processing. Parse it only with
  `compassio_ml.research.labels.parse_rio_marker`, which gives `rio_overall`, `rio_mitigation`,
  `rio_adaptation` and `is_climate_related`. `overall = max(...)` holds in the data but is
  *checked*, not assumed.
- These are the authors' annotations, cross-verified with ClimateBERT, with no per-record
  agreement column. Never call them independent ground truth.
- The binary target is `is_climate_related = rio_overall > 0`. SDG13, ADB policy markers (vocabulary 99), GCF
  `Theme` and CFU `Theme/Objective` are **different schemes**. Never treat them as the research label.
- "Climate-relevant" describes text. It is not evidence of environmental impact.

## 4. Financial distinctions

- Keep commitments, approvals, disbursements, repayments (interest/principal), pledges,
  deposits, total project cost and readiness grants apart. Never sum across them.
- Record unit and currency for every field (CFU is USD *millions*, the GCF historical file is USD
  *thousands*, AidData has original currency plus constant-2021 USD). Never convert currency
  without a documented, registered rate source.
- Blank is not zero. Placeholder values (e.g. readiness `Financing = 1`) are missing values.
- Multi-country amounts must not be attributed wholly to one country.

## 5. Duplicates and overlap

- Match on stable IDs first (`AidData_Record_ID`, GCF `Ref #`/`Ref_N`, GCF codes such as
  `(FP085)` embedded in CFU names and CPE text). Name-only matches are
  `possible_match_requires_review`. **Never merge on names.**
- Known repeated representations: the research workbooks re-publish AidData rows; CFU GCF rows
  repeat the GCF exports; CPE GCF families describe GCF projects.

## 6. Point-in-time and leakage warnings

- AidData descriptions are retrospective. They include implementation, achievements and later
  years, so never claim a description was available at commitment time.
- Group near-duplicate descriptions, AidData Parent IDs and ADB project numbers into the same
  split fold. Exclude label-bearing or label-correlated fields (rio_marker, SDG columns, staff
  comments) from model inputs.
- Use `Commitment_Year` for chronological evaluation and say that it tests year shift, not
  real-time forecasting.

## 7. Research dataset (Task 003)

- Use `data/processed/research_projects.parquet` and `research_split_membership_v1.parquet`, built
  by `uv run compassio-research build`. Never re-derive splits ad hoc.
- Model inputs come only from `compassio_ml.research.inputs.model_input_columns()`.
- Respect `eligibility_status`: quarantined records keep their labels but stay out of training and
  headline metrics.

## 8. Reporting

For each claim, give the number, its unit, the command that produced it, and the source hash
prefix. Label each claim as **observed**, **documented** (by the publisher/paper), **inferred** or
**unknown**. Do not report a figure you
did not recompute. Hypotheses from earlier audits stay hypotheses until reproduced.
