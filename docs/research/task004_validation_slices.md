# Task 004: Validation slices (primary protocol)

Source: `experiments/benchmarks/primary__full__seed20260109__cfg2f0656ed/validation_slices.csv`.

- **Partition:** primary **validation** (3,140 records, 239 positive). Slices are descriptive.
  They were not used to tune or select anything.
- **Model:** the provisional winner, `logistic_regression | title_description | word_unibi`,
  with predictions at its train-OOF threshold (0.474). The comparison column is the calibrated
  LinearSVC (unigrams).
- **Suppression:** a slice with fewer than 30 records or fewer than 5 positives shows counts
  only.
- **Recipient slices:** only recipients meeting both minimums are listed.

## 1. Winner by slice

| Slice | Records | Positives | Precision | Recall | F1 | AP | Calibrated SVM F1 |
| --- | --: | --: | --: | --: | --: | --: | --: |
| All | 3,140 | 239 | 0.792 | 0.732 | 0.761 | 0.827 | 0.760 |
| Climate-related (recall) | 239 | 239 | — | 0.732 | — | — | |
| Not climate-related (false-positive rate 0.016) | 2,901 | 0 | — | — | — | — | |
| **ENERGY** | 221 | 142 | 0.867 | **0.965** | **0.913** | 0.973 | 0.920 |
| **Non-ENERGY** | 2,919 | 97 | 0.603 | **0.392** | **0.475** | 0.488 | 0.452 |
| Retrospective warning | 1,546 | 188 | 0.802 | 0.777 | 0.789 | 0.869 | 0.782 |
| No retrospective warning | 1,594 | 51 | 0.744 | 0.569 | 0.644 | 0.648 | 0.674 |
| Amount known | 1,902 | 173 | 0.776 | 0.763 | 0.770 | 0.859 | |
| Amount missing | 1,238 | 66 | 0.843 | 0.652 | 0.735 | 0.745 | |
| Years 2000–2005 | 355 | 17 | 0.800 | 0.706 | 0.750 | 0.766 | |
| Years 2006–2010 | 545 | 27 | 0.750 | 0.778 | 0.764 | 0.794 | |
| Years 2011–2015 | 803 | 89 | 0.857 | 0.742 | 0.795 | 0.889 | |
| Years 2016–2021 | 1,437 | 106 | 0.752 | 0.717 | 0.734 | 0.800 | |
| Pakistan (in primary validation) | 77 | 12 | 0.833 | 0.833 | 0.833 | 0.905 | 0.870 |
| Pakistan × ENERGY | 11 | 11 | suppressed (TP 10, FN 1) | | | | suppressed |
| Pakistan × non-ENERGY | 66 | 1 | suppressed (TP 0, FP 2, FN 1) | | | | suppressed |

**Recipients with at least 30 records and at least 5 positives** (small samples; descriptive
only):

| Recipient | Records | Positives | F1 |
| --- | --: | --: | --: |
| PAK | 77 | 12 | 0.83 |
| LAO | 69 | 17 | 0.91 |
| MMR | 71 | 5 | 0.89 |
| ETH | 54 | 9 | 0.76 |
| KHM | 58 | 5 | 0.67 |
| KEN | 45 | 7 | 0.60 (recall 0.43) |
| ZMB | 41 | 7 | 1.00 |
| BRA | 39 | 5 | 1.00 |
| UZB | 34 | 5 | 0.60 |
| No ISO-3 (regional) | 47 | 10 | 0.80 |

With 5–17 positives per country, these differences are not meaningful.

## 2. What the slices show

1. **The model is mainly an energy-project detector.** ENERGY recall is 0.965, but **non-ENERGY
   recall is 0.392**: 59 of 97 non-energy climate projects (water, agriculture, transport,
   environment and so on) are missed. Headline F1 is driven by ENERGY, where 142 of 221
   validation records are positive. This is the most important limitation of the current
   classical models. The calibrated SVM shows the same pattern (non-ENERGY F1 0.452).
2. **Retrospective wording correlates with detectability.** F1 is 0.789 with a
   `retrospective_text_warning` and 0.644 without; AP 0.869 vs 0.648. The Task 003 confound is
   visible:
   - Positives are more often described after the fact.
   - Projects with contemporaneous-style text are harder.
   - Performance on genuine proposals at application time is expected to be **lower** than
     these numbers and is unmeasured.
3. **Year bands are stable.** F1 ranges 0.73–0.80, with no sign of degradation in the most
   recent band. This is not a chronological test, because these are randomly grouped rows; the
   chronological protocol is separate (`task004_reproducibility.md` §3).
4. **Missing amounts** do not hurt text classification much (F1 0.735 vs 0.770).
5. **Pakistan:** 77 primary-validation records (12 positive) score F1 0.83, but:
   - the model was trained with other Pakistan records in train, so this is **not** a
     country-holdout result;
   - with 12 positives the interval is wide;
   - Pakistan non-ENERGY has a single positive, which was missed.

   The independent Pakistan evaluation is the `pakistan_holdout` protocol, whose test is
   reserved for Task 005.

## 3. Implications for Task 005 and beyond

- Report ENERGY and non-ENERGY separately in every final result. A single headline F1 overstates
  usefulness for non-energy climate finance.
- Non-ENERGY recall is the main target for any future model improvement (richer
  representations, or reviewing the non-energy labels). Any such work needs a new benchmark
  version and must not touch the frozen tests.
