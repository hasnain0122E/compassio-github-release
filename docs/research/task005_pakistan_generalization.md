# Task 005: Pakistan country-holdout evaluation

Source: `docs/research/final_evaluation_v1/pakistan_holdout_results.json`, a one-shot run at
2026-11-09 11:04:25 UTC under plan `c4760503…`.

## Isolation

- **Training data:** the Pakistan-holdout train partition only, 17,309 records (1,086 positive).
  It contains **no Pakistan records** and no member of any leakage group that contains a Pakistan
  record. The evaluator checked this at run time and refuses if it is violated; this is tested.
- **Threshold:** 0.4969, from out-of-fold predictions on that training partition only, before
  test access.
- **Excluded:** 74 non-Pakistan group-mates (frozen split).
- **Disclosure:** the **model family and hyperparameters were selected on the primary
  validation split, which contained 77 Pakistan records**. Family selection was therefore not
  fully blind to Pakistan. The Pakistan model itself never saw a Pakistan record.

## Results (test = all 496 eligible Pakistan records, 372 groups)

| Subset | Records | Positives | TP | FP | FN | TN | Precision | Recall | F1 |
| --- | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| **All Pakistan** | 496 | 76 | 61 | 4 | 15 | 416 | 0.938 | 0.803 | 0.865 |
| **ENERGY** | 86 | 60 | 55 | 1 | 5 | 25 | 0.982 | 0.917 | 0.948 |
| **Non-ENERGY** | 410 | 16 | 6 | 3 | 10 | 391 | 0.667 | **0.375** | 0.480 |

Counts were recomputed from the frozen data by the evaluator, not hard-coded.

**All Pakistan:**

| Measure | Value |
| --- | --- |
| AP | 0.919 [0.844, 0.966] |
| ROC-AUC | 0.970 |
| Precision | [0.868, 0.988] |
| Recall | [0.656, 0.917] |
| F1 | [0.764, 0.936] |
| Brier / ECE | 0.034 / 0.029 |
| Keyword baseline | AP 0.681 [0.519, 0.825]; F1 0.726 |

Intervals are group bootstrap, 2,000 resamples.

**Among positives:**

| Positives annotated as | Count | Recall |
| --- | --: | --: |
| Principal (overall 2) | 62 | 0.903 |
| Significant (overall 1) | 14 | **0.357** |
| Adaptation-only | 7 | 0.286 |
| Non-ENERGY adaptation-related | 10 | 0.500 |

## Interpretation and uncertainty

- **The high headline numbers reflect Pakistan's sector mix, not general strength.** 60 of the
  76 Pakistan positives are ENERGY (hydropower, solar, wind), where the model is strongest.
  Pakistan's positive rate (15.3%) is also higher than the training rate (6.3%), which raises AP
  on its own.
- **Non-ENERGY Pakistan: 6 of 16 climate projects found (recall 0.375).** With 16 positives, the
  plausible range is very wide: a simple binomial 95% interval for 6/16 is roughly 0.15–0.65.
  **No robust conclusion about non-energy Pakistan performance is possible**, except that it is
  clearly much weaker than energy.
- **Significant-level and adaptation-only positives** (14 and 7 cases) are mostly missed, the
  same pattern as in primary.
- **What can be said:** the classifier transfers to unseen Pakistan *energy* projects
  described in AidData's style. It should not be presented as a reliable screener of Pakistan
  adaptation, water, agriculture or transport projects.
