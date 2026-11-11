# Task 004: Model comparison (primary protocol, validation partition)

**Run:** `primary__full__seed20260109__cfg2f0656ed`, from
`uv run compassio-ml benchmark --protocol primary --suite full`.

| Item | Value |
| --- | --- |
| Data | table `71fc5a10…`, membership `aba478d9…`, split config `e06de7e2…`; verified against the lock at run start |
| Code | git `9c176c9` plus uncommitted Task 004 code (`dirty: true`) |
| Trials | 102 started, 102 completed, 0 failed (72 inner-CV + 30 finalists) |
| Train | 14,654 records, 918 positive (6.26%), 11,344 groups |
| Validation | 3,140 records, 239 positive (7.61%), 2,546 groups |
| Test | **Not loaded** |

All numbers are validation-partition results under the primary protocol. They are not test
results and not Pakistan-holdout results. Intervals are 95% group-bootstrap intervals over
leakage groups (2,000 resamples).

## 1. Ranked finalists (validation average precision)

"Thr" is the decision threshold chosen on train-OOF scores. "Tied" means the paired AP-difference
interval against the top finalist includes 0.

| # | Model | Rep. | TF-IDF | Chosen params | Val AP [95% CI] | F1 @thr [95% CI] | P | R | Tied |
| --: | --- | --- | --- | --- | --- | --- | --: | --: | :-: |
| 1 | Calibrated LinearSVC | title+desc | uni | C 0.5, unweighted | **0.838** [0.794, 0.878] | 0.760 [0.710, 0.807] | 0.801 | 0.724 | top |
| 2 | LinearSVC | title+desc | uni+bi | C 0.5, unweighted | 0.836 [0.791, 0.877] | 0.760 [0.711, 0.806] | 0.786 | 0.736 | ✓ |
| 3 | LinearSVC | title+desc | uni | C 0.5, unweighted | 0.833 [0.786, 0.877] | 0.743 [0.697, 0.787] | 0.730 | 0.757 | ✓ |
| 4 | Calibrated LinearSVC | title+desc | uni+bi | C 0.5, unweighted | 0.833 [0.788, 0.873] | 0.745 [0.692, 0.795] | 0.816 | 0.686 | ✓ |
| **5** | **LogisticRegression** | title+desc | uni+bi | C 16, balanced | **0.827** [0.781, 0.868] | **0.761** [0.711, 0.808] | 0.792 | 0.732 | ✓ **winner** |
| 6 | Calibrated LinearSVC | desc | uni | C 0.5, unweighted | 0.827 [0.779, 0.870] | 0.753 | 0.795 | 0.715 | ✗ |
| 7 | LinearSVC | desc | uni+bi | C 0.5, unweighted | 0.824 [0.776, 0.866] | 0.737 | 0.730 | 0.745 | ✓ |
| 8 | Calibrated LinearSVC | desc | uni+bi | C 0.5, unweighted | 0.820 [0.771, 0.863] | 0.734 | 0.773 | 0.699 | ✓ |
| 9 | LinearSVC | desc | uni | C 0.5, unweighted | 0.820 | 0.752 | 0.755 | 0.749 | ✗ |
| 10 | LogisticRegression | title+desc | uni | C 16, balanced | 0.815 | 0.760 | 0.795 | 0.728 | ✗ |
| 11 | LogisticRegression | desc | uni+bi | C 16, balanced | 0.813 | 0.739 | 0.763 | 0.715 | ✗ |
| 12 | LogisticRegression | desc | uni | C 16, balanced | 0.802 | 0.753 | 0.789 | 0.720 | ✗ |
| 13–18 | SVM / calibrated SVM / LR | title only | both | — | 0.774–0.788 | 0.708–0.729 | | | ✗ |
| 19–24 | MultinomialNB | all | both | α 0.1 | 0.642–0.714 | 0.568–0.657 | | | ✗ |
| 25 | Keyword rule | title+desc | — | fixed | 0.586 [0.513, 0.656] | 0.632 | 0.646 | 0.619 | ✗ |
| 26 | Keyword rule | desc | — | fixed | 0.568 | 0.634 | 0.649 | 0.619 | ✗ |
| 27 | Keyword rule | title | — | fixed | 0.446 | 0.596 | 0.906 | 0.444 | ✗ |
| 28–30 | Majority class | any | — | — | 0.076 (= prevalence) | 0.000 | 0 | 0 | ✗ |

The tie set (ranks 1–5, 7, 8) is decided by noisy bootstrap boundaries. Ranks 6 and 9 fall just
outside it (lower bounds 0.004 and 0.004), so the AP ordering among ranks 1–12 should be read as
"not reliably different".

## 2. Confusion matrices at the train-OOF threshold (3,140 validation records)

| Model | Thr | TP | FP | FN | TN | Accuracy (secondary) |
| --- | --: | --: | --: | --: | --: | --: |
| **LogisticRegression (winner)** | 0.474 | 175 | 46 | 64 | 2,855 | 0.965 |
| Calibrated LinearSVC, uni (top AP) | 0.285 | 173 | 43 | 66 | 2,858 | 0.965 |
| LinearSVC, uni+bi | −0.393 (margin) | 176 | 48 | 63 | 2,853 | 0.965 |
| MultinomialNB, title | 0.246 | 152 | 72 | 87 | 2,829 | 0.949 |
| Keyword rule | ≥ 1 hit | 148 | 81 | 91 | 2,820 | 0.945 |
| Majority class | — | 0 | 0 | 239 | 2,901 | **0.924** |

The majority class reaches 92.4% accuracy while finding no climate project. This is why accuracy
is not a selection metric.

## 3. Thresholds and calibration

| Model | F1 @0.5 (P / R) | F1 @train-OOF thr | F1 @val-optimal (reference only) | Brier | ECE (10 bins) |
| --- | --- | --: | --: | --: | --: |
| LogisticRegression (winner) | 0.752 (0.792 / 0.715) | 0.761 | 0.763 | 0.0285 | 0.0151 |
| Calibrated LinearSVC, uni | 0.747 (0.859 / 0.661) | 0.760 | 0.764 | **0.0267** | **0.0058** |
| Calibrated LinearSVC, uni+bi | 0.729 | 0.745 | 0.756 | 0.0276 | 0.0077 |
| MultinomialNB, title+desc uni+bi | 0.493 (0.824 / 0.351) | 0.619 | 0.638 | 0.0489 | 0.0467 |

- **Training-OOF thresholds transfer well.** They land within 0.002–0.011 F1 of the
  validation-optimal threshold for LR and SVM, and 0.019 for MultinomialNB.
- **Class weighting:** inner CV picked `class_weight = balanced` (C = 16) for logistic
  regression and unweighted C = 0.5 for LinearSVC.
- **Calibration:** balanced LR probabilities are reasonably calibrated here (ECE 0.015). The
  sigmoid-calibrated SVM is better calibrated (ECE 0.006).
- **SVM margins** (e.g. threshold −0.39) are decision scores and are never reported as
  probabilities.

## 4. Cost

| Model | Latency (ms / 1,000 texts, CPU) | Serialized size | Fit time | Peak fit memory | TF-IDF features | Train matrix |
| --- | --: | --: | --: | --: | --: | --: |
| LogisticRegression, uni+bi (winner) | 310 | 3.5 MB | 24.6 s | 176 MB | 192,160 | 35.2 MB |
| Calibrated LinearSVC, uni | 413 | 1.1 MB | 25.8 s | 33 MB | 21,728 (per fold) | 13.9 MB |
| LinearSVC, uni+bi | 267 | 3.4 MB | 17.9 s | 176 MB | 192,160 | 35.2 MB |
| LinearSVC, uni | 141 | 0.46 MB | 5.5 s | 41 MB | 27,198 | 14.1 MB |
| Keyword rule | 111 | 0.3 KB | — | — | — | — |

These are timings on one developer workstation, measured with `tracemalloc` (Python
allocations), including tracing overhead. All candidates are CPU-only and well under 1 ms per
text.

## 5. Provisional validation winner

**`logistic_regression | title_description | word_unibi` (C = 16, class_weight = balanced,
threshold 0.474)**

The artifact's SHA-256 is `111a7341…`, recorded in `model/model_metadata.json`.

**Why it leads under the pre-registered rule:**

- It is in the AP tie set with the top model (paired difference interval [−0.004, 0.026]).
- It provides genuine probabilities.
- Among the tied probabilistic models it has the lowest complexity tier: one model, against
  calibrated SVM's 3-model ensemble.
- It has the highest validation F1 at its pre-selected threshold (0.761).

**What the rule traded away, stated plainly:** the calibrated LinearSVC (unigrams) has the
highest point AP (0.838 vs 0.827), better calibration (ECE 0.006 vs 0.015) and a smaller file
(1.1 MB vs 3.5 MB), at slightly higher latency. Neither difference is statistically
distinguishable on validation. Either is a defensible Task 005 candidate.

It is called a **provisional validation winner**. It is not a final or production model, and no
test partition has been evaluated.

## 6. Findings that matter more than the ranking

- **Learning beats the lexicon substantially:** AP 0.827 against the keyword rule's 0.586, an
  improvement of about 0.24 with non-overlapping intervals.
- **Representation:** title plus description ≥ description > title alone (about 0.79).
  Unigrams versus bigrams make little difference.
- **MultinomialNB** is clearly weaker (AP ≤ 0.71) and poorly calibrated.
- **Generalisation is uneven:** see `task004_validation_slices.md`. Non-ENERGY recall is about
  0.39 for the winner.
