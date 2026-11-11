# Task 004.5: Completion report (pre-release integrity audit)

Date: 2026-11-09 · Result:

- the audit is complete on validation data only;
- **no model retrained, no threshold changed, no frozen data or split changed, no test
  partition opened**;
- all gates pass.

## Preservation

- Task 004 is committed locally as `35dac13` (28 files; no raw data, models, experiments,
  predictions or secrets). Nothing was pushed.
- Verified the source manifest (9 entries), the frozen lock, and raw hashes unchanged since
  Task 002.
- Every run manifest records `test_partition_loaded: false`.

## 1. Concerns resolved

- **The weakness is now explained by evidence** (`pre_release_model_risk_review.md`):
  - 59 of 64 validation FN are non-ENERGY;
  - 70% contain no climate keyword;
  - 67% are "significant" (score 1) labels;
  - transport recall is 0.20, and multisector and emergency response 0/11.

  The model keys mainly on energy-technology vocabulary, with some sensitivity to
  writing-convention terms ("was loan").
- **The conflict groups are categorised** (`conflicting_label_review.md`), with source IDs and the
  evidence needed for each:
  - 7 of 15 look like inconsistent labels across lenders or tranches of the same project;
  - 4 are significant-vs-not ambiguity;
  - 2 are distinct components;
  - 1 is a distinct project;
  - 1 has insufficient evidence.
- **Financial semantics** are implemented and tested (`compassio_ml.finance`, 14 tests) and
  documented (`financial_data_contract.md`).
- **Rights evidence was gathered per source:**
  - research data CC0 (Figshare API);
  - AidData ODC-By 1.0 (in the file);
  - **GCF Terms and conditions read**: non-commercial and research use with attribution;
    commercial use needs consent.

  All sources remain `not_reviewed` (`source_rights_matrix.md`).

## 2. Concerns remaining

- **Non-ENERGY recall:** R01, High.
- **Retrospective confound:** R02, High.
- **Pakistan non-ENERGY performance unknown:** R04, High.
- **Label inconsistency:** R03, needs a human reviewer.
- **Rights review:** R09, needs legal and human review.
- **No dated GCF approvals in the registered export:** R10.
- **Benchmark runs from a dirty tree:** R06. The code is now committed; re-run before citing.

Full register: `docs/research/risk_register.csv`.

## 3. External sources

| Source | Usable? | For what |
| --- | --- | --- |
| OECD CRS / Rio markers | Most promising (same 0/1/2 scheme, donor-assigned) | External evaluation. The project-level text fields were **not verified** (JS-only page; the SDMX structure could not be read); manual retrieval steps are documented. |
| GCF project pages | Yes [verified on FP085] | Contemporaneous approved proposals, approval dates and financing breakdowns. Positives only. Non-commercial terms. |
| World Bank Projects API | Yes [verified]: open, 640 Pakistan projects, `pdo` and `project_abstract` | Proposal-stage text, discovery, candidate negatives. Labels must come from humans. |
| IATI Datastore | Needs an API key [verified] | Discovery; labels only where publishers use DAC vocabulary-1 markers |

No new data was downloaded or registered (`external_validation_sources.md`).

## 4. Are more labelled training examples necessary now?

**Not first.** The immediate need is an **independent, adaptation-rich evaluation set**, so the
gap can be measured honestly. More non-ENERGY training labels are the likely remedy afterwards
(about 374 non-ENERGY training positives, spread thinly across sectors), in a versioned
benchmark.

## 5. Obtaining an independent adaptation-focused test set

Follow `external_validation_protocol.md`:

- about 150–300 stratified examples, 34% of them negative controls, and at least 30% Pakistan
  where available;
- sources: GCF proposals, World Bank PDOs and OECD CRS;
- 2 independent reviewers plus adjudication, under the paper's Rio definitions;
- a duplicate check against the research table;
- a separate lock;
- no training on it.

Estimated effort: about 25–35 reviewer-hours.

## 6. Model selection

**Unchanged.** Logistic regression (title + description, uni+bi TF-IDF, C 16, balanced,
threshold 0.474) remains the **provisional validation winner**. The calibrated SVM remains a
statistically tied alternative with the same sector pattern. Before Task 005, declare which
configuration or configurations will be evaluated.

## 7. Financial rules for the product

- Sum only within one flow kind, currency, price basis and level.
- Never sum aggregates or multi-country values.
- Deduplicate cross-source representations first.
- An unknown currency blocks aggregation.
- A missing value is shown and counted, never treated as 0.
- No conversions.
- Five mandatory disclaimers.

Details: `financial_data_contract.md`.

## 8. Rights and attribution

- Not legally cleared for public redistribution.
- Internal research use only, until a human review updates `rights_status` with evidence.
- Attribution set prepared: AidData ODC-By plus citation; Qi et al. 2026; "First published by
  the Green Climate Fund".

## 9. MVP feasibility (`docs/product/mvp_feature_contract.md`)

| Feature | Feasible now? |
| --- | --- |
| Historical explorer | Yes (research data) |
| Project detail and provenance | Yes |
| Evidence flags | Yes |
| Rule-based review queue | Yes |
| Hypothetical scenario planner | Yes |
| Comparison | Yes, within one source |
| Screening | Yes for research-style text, with warnings |
| Current portfolio | Partial (GCF dates need a new source) |
| Trends | Partial |
| Available-to-fund opportunities | **No source** |

**Everything is blocked for public display by rights.**

## 10. Tests and checks (actually run)

| Check | Result |
| --- | --- |
| `bash scripts/check.sh` | All checks passed: ruff clean, 110 files formatted, mypy OK on 86 files, **305 tests passed**, web lint, typecheck and build OK |
| `uv run compassio-manifest write` / `validate` | 9 entries valid (licence notes updated; rights unchanged) |
| `uv run compassio-ml verify-frozen` | Inputs match lock |
| Raw hashes | Unchanged since the Task 002 snapshot |
| `uv run compassio-ml error-analysis --run-dir …primary__full…` | TP 175 / FP 46 / FN 64 / TN 2,855 (matches Task 004) |
| Run manifests | `test_partition_loaded: false` for all 4 runs |

**New tests (24):**

- the financial contract (14);
- the error taxonomy and validation-only enforcement (5);
- the analysis loader refusing non-validation rows, among other cases.

## 11. Can Task 005 proceed without compromising research integrity?

**Yes, with conditions:**

1. Re-run the selected configuration from a committed tree (`dirty: false`).
2. Pre-declare the configuration or configurations to evaluate and the reporting slices:
   ENERGY / non-ENERGY, retrospective / not, Pakistan counts.
3. Evaluate each frozen test once.
4. Present results with the Task 004.5 limitations, and do not claim adaptation or proposal-time
   accuracy until external validation exists.

## Files

- **New code:** `compassio_ml/finance/{__init__,contract}.py`, `modeling/error_analysis.py`, and
  the `compassio-ml error-analysis` subcommand.
- **Changed code:** `data/sources.py` (GCF licence notes).
- **Committed provenance:** `data/manifests/source_manifest.json`, regenerated.
- **Tests:** `tests/ml/test_finance_contract.py`, `tests/ml/test_error_analysis.py`.
- **Docs:**
  - `docs/research/{pre_release_model_risk_review,external_validation_sources,external_validation_protocol}.md`
    and `docs/research/risk_register.csv`;
  - `docs/data/{conflicting_label_review,source_rights_matrix}.md`;
  - `docs/architecture/financial_data_contract.md`;
  - `docs/product/mvp_feature_contract.md`;
  - this report.
