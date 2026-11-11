# Task 005: Final held-out evaluation (one shot per protocol)

| Item | Value |
| --- | --- |
| Plan | `configs/final_evaluation_v1.yaml`, committed in `153dce8` **before any test access** |
| Plan SHA-256 | `c4760503f4b8798706e24cccfe7b87a4203751b8722d946984ebf76a47b8b3cb` (`configs/final_evaluation_v1.sha256`) |
| Source code commit (guarded) | `f14f397f`. `final-evaluate` verified that guarded code and configs were unchanged since that commit. |
| Data | table `71fc5a10…`, membership `aba478d9…`, split config `e06de7e2…`, split lock `3d5b34d4…`; verified at run time |
| Test access | One `test_access.json` per protocol, created exclusively and now read-only: primary at 10:59:50 UTC, chronological 11:02:00, Pakistan 11:04:25 (2026-11-09). A second attempt was **refused** (exit 2), as verified. |
| Evidence copies (committed) | `docs/research/final_evaluation_v1/*_results.json`, `*_test_access.json`, `pre_test_development_report.json`, `release_manifest.json` |

## 1. What was evaluated (fixed, not re-tuned)

**Model:** TF-IDF (word 1–2-grams, min_df 2, max_df 0.9, ≤ 200k features, sublinear tf) +
LogisticRegression (C = 16, class_weight = balanced, liblinear). Input is `title_clean` +
`description_clean`; the label is `rio_overall > 0`.

**Fitting:** each protocol's **train partition only**. Validation was not added, which preserves
the validated procedure.

**Thresholds** (all set before test access):

| Protocol | Threshold | Source |
| --- | ---: | --- |
| Primary | **0.4740212723792222** | The Task 004 locked threshold, reproduced bit for bit |
| Chronological | 0.5159941031937899 | Chronological train OOF |
| Pakistan holdout | 0.4968937550158455 | Pakistan-holdout train OOF |

**Primary model identity:** its content fingerprint `3023fe3d…` equals the Task 004 validated
model's, and its validation scores matched exactly (maximum difference 0.0). The calibrated SVM
was not evaluated.

## 2. Primary group-disjoint test

| Measure | Value |
| --- | --- |
| Test rows | 3,142 (202 positive, 2,940 negative), 2,460 leakage groups |
| TP / FP / FN / TN | 127 / 50 / 75 / 2,890 |
| Precision | **0.718** [0.650, 0.790] |
| Recall | **0.629** [0.536, 0.712] |
| F1 | **0.670** [0.599, 0.732] |
| Average precision (PR-AUC) | **0.751** [0.680, 0.815] |
| ROC-AUC | 0.951 |
| Accuracy (secondary) | 0.960 |
| Brier / ECE (10 bins) | 0.0305 / 0.018 (mean score 0.081 vs observed rate 0.064) |
| Keyword baseline (same rows) | AP 0.572 [0.491, 0.650]; F1 0.624 |
| Majority baseline | AP 0.064 (prevalence); F1 0 |
| Model size / latency | 3.53 MB / 327 ms per 1,000 texts (CPU, median of 5) |

Intervals are 95% group bootstrap (2,000 resamples of leakage groups).

**Validation vs test:** validation AP was 0.827 [0.781, 0.868]; test AP is 0.751 [0.680, 0.815].
The drop is consistent with **selection optimism**: the winner was chosen among 30 validation
finalists. The test figure is the unbiased estimate.

**Primary slices (test):**

| Slice | Records | Positives | Precision | Recall | F1 | AP |
| --- | --: | --: | --: | --: | --: | --: |
| ENERGY | 188 | 107 | 0.786 | **0.860** | 0.821 | 0.926 |
| Non-ENERGY | 2,954 | 95 | 0.583 | **0.368** | 0.452 | 0.496 |
| Retrospective warning | 1,578 | 153 | 0.706 | 0.673 | 0.689 | 0.793 |
| No retrospective warning | 1,564 | 49 | 0.774 | 0.490 | 0.600 | 0.610 |
| Years 2000–2005 | 354 | 16 | 0.875 | 0.438 | 0.583 | 0.596 |
| Years 2006–2010 | 583 | 25 | 0.636 | 0.560 | 0.596 | 0.713 |
| Years 2011–2015 | 769 | 77 | 0.758 | 0.649 | 0.699 | 0.793 |
| Years 2016–2021 | 1,436 | 84 | 0.691 | 0.667 | 0.679 | 0.756 |

**Recall among positives, by author annotation (test):**

| Positives annotated as | Count | Recall |
| --- | --: | --: |
| Mitigation-related (mitigation > 0) | 144 | 0.757 |
| Adaptation-related (adaptation > 0) | 100 | 0.520 |
| Adaptation-only | 58 | **0.310** |
| Mitigation-only | 102 | 0.735 |
| Non-ENERGY adaptation-related | 72 | **0.375** |
| Significant (overall 1) | 97 | 0.443 |
| Principal (overall 2) | 105 | 0.800 |

## 3. Chronological test: temporal distribution shift on retrospective text

**This is not prediction at approval time.** The model is fitted on years 2000–2015 (10,461 rows,
670 positive) and tested on 2018–2021. Groups spanning periods are excluded by the frozen split.

| Measure | Value |
| --- | --- |
| Test rows | 6,022 (266 positive, 5,756 negative), 5,334 groups |
| TP / FP / FN / TN | 143 / 49 / 123 / 5,707 |
| Precision | 0.745 [0.673, 0.814] |
| Recall | **0.538** [0.470, 0.601] |
| F1 | 0.625 [0.564, 0.682] |
| AP | **0.674** [0.612, 0.732] |
| ROC-AUC | 0.941 |
| Accuracy (secondary) | 0.971 |
| Brier / ECE | 0.0237 / 0.016 |
| Keyword baseline | AP 0.479 [0.410, 0.546]; F1 0.531 |
| Size / latency | 2.47 MB / 349 ms per 1,000 |

**Chronological slices (test):**

| Slice | Records | Positives | Precision | Recall | F1 | AP |
| --- | --: | --: | --: | --: | --: | --: |
| ENERGY | 207 | 111 | 0.814 | 0.829 | 0.821 | 0.900 |
| Non-ENERGY | 5,815 | 155 | 0.646 | **0.329** | 0.436 | 0.461 |
| Retrospective warning | 2,509 | 164 | 0.726 | 0.646 | 0.684 | 0.734 |
| No retrospective warning | 3,513 | 102 | 0.804 | **0.363** | 0.500 | 0.594 |

**Recall among positives:**

| Positives annotated as | Count | Recall |
| --- | --: | --: |
| Mitigation-related | 186 | 0.624 |
| Adaptation-related | 141 | 0.489 |
| Adaptation-only | 80 | 0.338 |
| Mitigation-only | 125 | 0.592 |
| Significant (overall 1) | 123 | 0.398 |
| Principal (overall 2) | 143 | 0.657 |

All chronological test rows fall in the 2016–2021 band, so the other year bands are empty.

Performance degrades on later commitment years relative to primary: AP 0.674 vs 0.751, and
recall 0.538 vs 0.629.

## 4. Pakistan holdout

See `task005_pakistan_generalization.md`: AP 0.919 [0.844, 0.966], F1 0.865, with ENERGY and
non-ENERGY confusions.

## 5. Pre-registered acceptance (primary test)

| Criterion | Required | Observed | Result |
| --- | --- | --- | --- |
| AP CI lower bound above keyword AP | > 0.572 | 0.680 | pass |
| F1 at 0.474 | ≥ 0.65 | 0.670 | pass |
| ENERGY recall | ≥ 0.85 | 0.860 | pass (narrow) |
| ECE | ≤ 0.05 | 0.018 | pass |
| Non-ENERGY recall (limitation trigger) | < 0.60 requires a limitation | 0.368 | **limitation mandatory** |

**All acceptance criteria passed**, so the model is released internally as *Compassio Climate
Relevance Classifier v1 — MVP Research Screening*, with the mandatory non-energy limitation
(`task005_model_card.md`). Two criteria passed narrowly: F1 is 0.020 above its floor and
ENERGY recall 0.010 above its floor. Both F1's interval [0.599, 0.732] and ENERGY recall's
interval cross their thresholds.

## 6. Calibration

The scores come from class-weighted logistic regression, with no post-hoc calibration fitted.

- **Overall calibration is acceptable:** test ECE is 0.018 (primary), 0.016 (chronological) and
  0.029 (Pakistan).
- **Scores still run high on average** (primary mean 0.081 against observed 0.064), which is
  typical of class weighting.
- **Scores are "model-estimated label scores".** They are not probabilities of funding, approval,
  impact or return.
