# Model evaluation protocol (frozen for Task 004)

**Status:** splits frozen in `configs/research_split_v1.yaml` and materialised in
`data/processed/research_split_membership_v1.parquet`. **No model has been trained.** This
document fixes what Task 004 may and may not do, before any result exists.

## 1. What the model predicts

| | |
| --- | --- |
| Task | Binary text classification |
| Target | `is_climate_related` = `rio_overall > 0`: the paper authors' annotated Rio Marker (Qi et al. 2026) |
| Inputs | Only `compassio_ml.research.inputs.model_input_columns()`: `title_clean`, `description_clean`; optionally `sector_name`, `flow_type`, `funding_agencies_type`, `recipient_region`, reported with and without |
| Never inputs | Any `rio_*` field, `is_climate_related`, SDG fields, AidData staff comments, implementation or completion fields, retrospective flags, `commitment_year`, status, group, split or eligibility fields, record IDs and hashes (enforced by tests) |
| Population | `eligibility_status == "eligible"`: 20,936 of 20,985 records (49 quarantined, 0 analytics-only) |
| Meaning of a positive prediction | "The text resembles text the authors annotated as having a significant or principal climate objective." Not environmental impact, not funding quality, not approval likelihood. |

## 2. Protocols

All three protocols are **group-disjoint** on `leakage_group_id` (`docs/data/leakage_group_audit.md`).
Disjointness is verified at build time and by tests. Seed: `20260109`. Assignment is a
deterministic, greedy, group-level stratified allocation, with SHA-256 ordering and strata
"group contains a positive" versus not.

### A. Primary group-disjoint evaluation (70 / 15 / 15 of eligible rows)

| Split | Records | Groups | Positive | Positive share | Pakistan records |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | 14,654 | 11,344 | 918 | 6.26% | 365 |
| validation | 3,140 | 2,546 | 239 | 7.61% | 77 |
| test | 3,142 | 2,460 | 202 | 6.43% | 54 |

- Every preprocessing fit (vocabulary, TF-IDF statistics, class weights, feature selection,
  calibration) uses **train only**.
- **Validation** is for model and hyperparameter selection.
- **Test** is opened **once**, after the final model is chosen.
- The shares differ because whole groups move together. The constraint is never relaxed for
  balance.

### B. Chronological evaluation (temporal distribution shift)

| Split | Commitment years | Records | Positive | Positive share |
| --- | --- | ---: | ---: | ---: |
| train | 2000–2015 | 10,461 | 670 | 6.40% |
| validation | 2016–2017 | 2,277 | 185 | 8.12% |
| test | 2018–2021 | 6,022 | 266 | 4.42% |
| excluded (group spans periods) | — | 2,176 | 238 | 10.94% |

- **Spanning policy:** a leakage group whose eligible members fall in more than one period is
  excluded from this protocol entirely. It is never split across a boundary and never moved
  into a later period.
- The cost of this policy is that the excluded records are positive-rich (10.9%), which biases
  the evaluated population towards single-period projects. Report it.
- **Interpretation:** commitment year is the year of the funding agreement. It is **not** a
  publication timestamp of the description, and descriptions are retrospective (§5). This
  protocol tests **shift across commitment-year cohorts on retrospective text**. It does not
  test prediction at approval time.

### C. Pakistan generalisation (country holdout)

| Split | Records | Positive | ENERGY records (positive) | non-ENERGY records (positive) |
| --- | ---: | ---: | --- | --- |
| train (no Pakistan) | 17,309 | 1,086 | — | — |
| validation (no Pakistan) | 3,057 | 197 | — | — |
| **test = all eligible Pakistan records** | **496** | **76** | 86 (60) | 410 (16) |
| excluded: non-Pakistan members of groups containing Pakistan records | 74 | 0 | — | — |

- Pakistan records never appear in fitting, tuning or model selection for this protocol, and
  neither does any record sharing a leakage group with them. Both are verified by tests.
- Model selection uses only the non-Pakistan validation split. The Pakistan test is evaluated
  once.
- **Uncertainty warning:** only 76 positives, 60 of them ENERGY. Non-ENERGY Pakistan has
  **16 positives**, so its recall estimates will be very wide. Results must report ENERGY and
  non-ENERGY separately, with intervals, and must not promise stable Pakistan performance.
- The Pakistan rows inside primary-protocol splits (365 / 77 / 54) are **not** a country-holdout
  experiment and must never be reported as one.

## 3. Experiments for Task 004 (planned; none run)

| # | Model | Notes |
| --- | --- | --- |
| 0 | Majority class | Lower bound (precision undefined; recall 0) |
| 1 | Keyword baseline | A fixed, pre-registered climate lexicon chosen **before** looking at validation errors; measures what learning adds over lexical cues |
| 2 | TF-IDF + logistic regression | Class-weighted. Primary simple candidate. |
| 3 | TF-IDF + multinomial Naive Bayes | Fast baseline |
| 4 | TF-IDF + linear SVM | Platt or isotonic calibration on train-internal folds if probabilities are needed |
| 5 | Gradient boosting | Only on a representation that justifies it (e.g. TF-IDF + context features). Not by default. |
| 6 | Transformer (e.g. ClimateBERT, multilingual model) | Only if compute and data quality allow. **ClimateBERT took part in the authors' label cross-verification**, so its agreement with the labels is partly circular and must be reported as such. |

Hyperparameters are tuned with group-aware cross-validation **inside train**, or on validation.
The test split is never used for tuning.

## 4. Metrics and uncertainty

- **Primary selection metric:** PR-AUC (average precision) on validation, because positives are
  about 6.5%. **Accuracy is not a selection metric.**
- **Always reported:**
  - precision, recall and F1 at a threshold chosen on validation;
  - the confusion matrix;
  - PR-AUC and ROC-AUC;
  - for probabilistic models, calibration: reliability curve, Brier score, expected calibration
    error;
  - latency per 1,000 descriptions on CPU, and model size and training cost.
- **Confidence intervals:** cluster (group) bootstrap that resamples `leakage_group_id`s, not
  records, with at least 2,000 resamples and percentile intervals. For Pakistan, report the same
  plus exact counts (TP/FP/FN/TN), because n is small.
- **Slices:**
  - Pakistan ENERGY / non-ENERGY;
  - flow type;
  - `retrospective_text_warning` true/false;
  - `label_revealing_terms` true/false;
  - description length band;
  - mitigation-only / adaptation-only / both, as descriptive recall.

## 5. Retrospective text: what the results can and cannot claim

| Population | Records | With `retrospective_text_warning` |
| --- | ---: | ---: |
| Eligible | 20,936 | 10,615 (50.7%) |
| Eligible positives | 1,359 | 1,027 (75.6%) |
| Eligible negatives | 19,577 | 9,588 (49.0%) |
| Eligible Pakistan | 496 | 268 (54.0%) |
| Eligible Pakistan positives | 76 | 61 (80.3%) |

Positives are **much more likely** to contain retrospective wording such as completion and
disbursement updates, because built infrastructure gets described as built. A model can
therefore learn post-commitment cues. Task 004 must:

1. report performance separately for warned and unwarned records;
2. run an ablation that masks year tokens and the matched retrospective phrases;
3. state that results apply to **retrospective project descriptions**.

**Screening proposals at application time** requires a separately collected and validated set
of contemporaneous proposal texts. No such set exists in the current inventory. Until it does,
Compassio must not claim application-time accuracy.

## 6. Model choice principle

Prefer the simplest model whose validation PR-AUC lies within the cluster-bootstrap interval of
the best model. A TF-IDF linear model that is statistically indistinguishable from a transformer
is preferred, because it:

- runs in milliseconds on CPU;
- is cheap to retrain;
- exposes per-term evidence that Compassio can show reviewers;
- carries far less deployment risk.

No particular model or score is promised.

## 7. Rules that protect the final test

1. The split version is frozen. Any change creates `research_split_v2`, and v1 results remain
   reported.
2. Each test split (primary, chronological, Pakistan) is evaluated once per final candidate.
   Every evaluation is logged with the git commit, the config hash and the data checksums from
   `artifacts/research_v1/checksums.json`.
3. Quarantined records are never used for training or for headline metrics. They may be
   analysed separately once they have been reviewed.
