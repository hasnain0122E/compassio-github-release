# Task 003: Completion report (Phase 1B: research dataset, label verification, evaluation design)

Date: 2026-11-09 · Result: **cleaned dataset and frozen splits built from the real registered
files, reproducibly; all gates pass; no model trained.**

## 0. Preservation

- Baseline before changes: 168 tests passed. The Task 002 work, which had been uncommitted, was
  committed locally as `606b1ad`, with 59 files and no raw data or artifacts staged. Nothing was
  pushed.
- Raw files are unchanged. All nine hashes are identical to the snapshot taken before Task 002,
  and `compassio-manifest validate` passes.

## 1. Cleaned project rows

**20,985**: one row per AidData GCDF 3.0 record, from an exact one-to-one join (§3 of
`research_cleaning_spec.md`):

- 20,985 matched, 0 research-only, 0 AidData-only;
- keys unique on both sides;
- the two sources are never stacked.

## 2–4. Populations

| Population | Records | Climate-related | Pakistan |
| --- | ---: | ---: | ---: |
| A. Eligible supervised | **20,936** | 1,359 | 496 (76 positive) |
| B. Quarantined (`conflicting_label_same_description`) | **49** (15 groups) | 24 | 0 |
| C. Analytics-only | **0** | — | — |

Nothing was deleted, and the quarantined records keep their original labels.

## 5. Rio Marker definitions (verified)

Source: Qi, J., Tang, Y., Zhang, Z., Wang, Y. & Qian, H. (2026), *Sci Data* 13:277,
https://doi.org/10.1038/s41597-026-06605-9.

- **Order:** Table 1 header "Rio Marker (Overall, Mitigation, Adaptation)", with examples `2,0,2`
  and `2,2,0`.
- **Scale:** Methods › Data processing: 0 = "not targeted", 1 = "significant objective",
  2 = "principal objective".
- **Fields:** `rio_overall`, `rio_mitigation`, `rio_adaptation`, and `is_climate_related =
  rio_overall > 0`. The original string is preserved as `rio_marker_src`.
- `overall = max(…)` holds in 20,985 of 20,985 rows. The paper doesn't document it, so it is
  checked rather than assumed.
- **Caveats:**
  - the labels are the authors' annotations, cross-verified with ClimateBERT;
  - the paper says agreement statistics are included, but no agreement column exists;
  - the workbooks are byte-identical to Figshare v1, verified by MD5.

## 6. Text cleaning

Transformations, in order, each recorded per row only if applied:

| Step | Descriptions changed | Titles changed |
| --- | ---: | ---: |
| `unicode_nfc` (NFC; NFKC deliberately rejected) | 1 | 0 |
| `zero_width_removed` | 231 | 6 |
| `whitespace_normalized` (NBSP and control whitespace to space, collapse, trim) | 14,305 | 1,045 |
| `html_markup_removed` / `html_entities_unescaped` / `sentinel_to_null` (implemented and tested) | 0 | 0 |

- Text is not truncated, lower-cased or rewritten.
- Cleaned text is derived from AidData's untruncated originals. The research copy truncates
  `Title` (12 rows) and `Funding_Agencies` (7) at 255 characters.
- Both copies are kept in `research_text_originals.parquet`.

## 7. Leakage groups

Groups are transitive components over Parent ID, normalized description, normalized title and a
restricted title-series rule. The broad series rule was rejected, with the evidence in
`leakage_group_audit.md` §1.

| Statistic | Value |
| --- | --- |
| Groups | 16,358 (2,164 multi-record, covering 6,791 records) |
| Largest group | 82 |
| Records without Parent ID | 14,569 |
| Cross-recipient groups | 80 |
| Cross-year groups | 1,131 |
| A naive random split would leak | **4,686 records in 1,268 groups** |
| Group-disjoint protocols leak | **0** in every protocol |

## 8. Conflicting labels

The 15 groups have identical descriptions, but in **all 15 the titles differ**. The amounts
differ in 10 and the agencies in 8. 13 groups are borderline 0-vs-1 ("significant") disagreements.
They are **not assumed to be errors**; they are quarantined for human review (CSV in
`artifacts/research_v1/`).

## 9. Retrospective descriptions

- `retrospective_text_warning` is set on 10,664 records (50.8%): 75.6% of eligible positives
  against 49.0% of eligible negatives, and 61 of 76 Pakistan positives.
- These are lexical warnings, not proof. Records are flagged, never deleted.
- The chronological protocol is a **distribution-shift test on retrospective text**.
  Application-time screening needs a separately collected set of contemporaneous proposals.

## 10–12. Split protocols (frozen: `configs/research_split_v1.yaml`, seed 20260109)

| Protocol | Train (pos) | Validation (pos) | Test (pos) | Excluded |
| --- | --- | --- | --- | --- |
| A. Primary, group-disjoint 70/15/15 | 14,654 (918) | 3,140 (239) | 3,142 (202) | — |
| B. Chronological: ≤2015 / 2016–17 / 2018–21 | 10,461 (670) | 2,277 (185) | 6,022 (266) | 2,176 (238) in period-spanning groups |
| C. Pakistan holdout | 17,309 (1,086), no Pakistan | 3,057 (197), no Pakistan | **496 (76): ENERGY 86 (60), non-ENERGY 410 (16)** | 74 non-Pakistan group-mates |

Non-ENERGY Pakistan has only 16 positives, so its intervals will be wide and no stable result is
promised. The evaluation plan is in `docs/research/model_evaluation_protocol.md`.

## 13. Field completeness

Complete for every record: record ID, title, description, commitment year, recipient, sector
and label.

Partial:

- Parent ID: 30.6%;
- recipient ISO-3: 98.7%. The 283 records without it are regional and are never counted as
  Pakistan;
- amount and currency: 61.0%, or 76.8% for positives versus 59.9% for negatives. Loans have
  91.8% coverage and grants 50.4%.

Missing amounts are never imputed (`cleaned_research_coverage.md`).

## 14. Provenance and rights

- Publisher reference URLs are recorded for 8 sources. `gcf_historical`'s origin is unconfirmed.
- No exact download URL and no acquisition date was recorded for any source, so all are null.
- **Every source is `not_reviewed`.** Licence notes recorded for review:
  - research data: CC0 (Figshare API);
  - AidData: ODC-By 1.0 (in the workbook);
  - ADB: unverifiable (HTTP 403);
  - GCF and CFU: no licence stated on their pages.

Details: `provenance_and_rights_review.md`.

## 15. Tests and commands (actually run)

| Command | Result |
| --- | --- |
| `uv sync --locked` | ok |
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 78 files already formatted |
| `uv run mypy` | Success: no issues found in 66 source files |
| `uv run pytest` | **239 passed** (227 unit + 12 `local_data`) |
| `uv run pytest -m local_data` | 12 passed (real dataset: IDs, labels, originals, disjointness, Pakistan isolation, chronological cutoffs, allowlist, raw unchanged) |
| `bash scripts/check.sh` (Python + web lint, typecheck and build) | All checks passed |
| `uv run compassio-manifest write` / `validate` | 9 entries / valid |
| `uv run compassio-research build --check-reproducible` | **12 output files byte-identical across two builds**; 0 disjointness violations |
| `uv run compassio-data audit` | regenerated (label field names updated) |
| `git status` / `git check-ignore` | Parquet, raw files and artifacts ignored; config and manifest trackable |

The 71 new tests cover:

- Rio parsing and field order, using the paper's own examples;
- invalid and missing labels, and the max relationship being checked rather than assumed;
- NFC, HTML, entity, zero-width, sentinel and whitespace handling, with no truncation and
  idempotence;
- the retrospective signals;
- parent components, transitive grouping, exact and generic titles, the restricted series rule,
  and stable order-independent IDs;
- the one-to-one join and its duplicate and missing keys, and that originals are preserved;
- conflict quarantine, and analytics-only records not becoming negatives;
- group-disjoint, chronological-cutoff, Pakistan-isolation, reproducibility and seed tests;
- config validation;
- the input allowlist.

## 16. May Task 004 begin?

**Yes, legitimate feature engineering and model comparison can begin**, using only:

- the eligible population;
- `model_input_columns()`;
- the frozen v1 splits;

and following the protocol rules:

- fit on train only;
- select on validation;
- open each test once;
- cluster-bootstrap intervals;
- report retrospective and ENERGY slices.

Not blockers, but they must be carried forward:

- human review of the 15 conflicting groups;
- human rights review before any public display;
- for application-time claims, a contemporaneous proposal dataset.

## Files

- **New code:** `research/{text,grouping,retrospective,inputs,dataset,splits,pipeline}.py` and
  `cli/research_cli.py`.
- **Changed code:** `research/labels.py` (paper field names), `data/{sources,manifest,manifest_io,parsing}.py`
  and `audit/{inspectors,research_audit}.py`.
- **Config:** `configs/research_split_v1.yaml`.
- **Dependencies:** pyarrow 26.0.1, pyyaml 6.0.3; dev: types-pyyaml 6.0.12.20261103.
- **Tests:** `tests/ml/test_research_{labels_text,grouping,dataset_splits}.py`,
  `tests/test_local_research_dataset.py`.
- **Docs:** `docs/data/{research_cleaning_spec,leakage_group_audit,cleaned_research_coverage,provenance_and_rights_review}.md`
  and `docs/research/model_evaluation_protocol.md`. Updated: `research_label_audit.md`,
  `model_target_and_limitations.md`, `data_contracts.md`, phase plan, CLAUDE.md, README and the skill.
- **Committed provenance:** `data/manifests/source_manifest.json`, regenerated with reference URLs
  and licence notes.

## Regenerate

```powershell
uv sync --locked
uv run compassio-manifest validate
uv run compassio-research build --check-reproducible   # data/processed/*.parquet + artifacts/research_v1/*
uv run pytest
```
