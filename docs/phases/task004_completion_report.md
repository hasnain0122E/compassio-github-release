# Task 004: Completion report (Phase 2–3A: leakage-safe features and model benchmarking)

Date: 2026-11-09 · Result:

- the classical benchmark ran on the real frozen data;
- a provisional validation winner was selected by the pre-registered rule;
- **no frozen test partition was loaded or evaluated**;
- all gates pass.

## 0. Preservation

- Task 003 was committed locally as `9c176c9` (38 files, no data or artifacts). Nothing was
  pushed.
- The Task 003 outputs were verified independently before locking:
  - the Parquet SHA-256s equal the Task 003 build checksums;
  - 20,985 rows, 20,936 eligible, 49 quarantined, 16,358 groups;
  - the split counts are re-derived from the files.

  The lock `configs/research_split_v1.lock.json` now makes any change fail. The raw files are
  unchanged against the Task 002 snapshot.

## 1. Candidates evaluated

Majority class, a fixed keyword rule, TF-IDF + MultinomialNB, TF-IDF + LogisticRegression,
TF-IDF + LinearSVC, and sigmoid-calibrated LinearSVC.

Each was tried on 3 text representations (title / description / title + description) and 2
TF-IDF presets (unigrams; unigrams + bigrams).

**Not run:**

- boosting, which would need densified sparse TF-IDF;
- embedding and transformer models, which need downloads and GPU stacks. A ClimateBERT
  challenger would not be independent of the labels.

## 2. Samples (primary protocol)

| Partition | Records | Positives | Groups |
| --- | ---: | ---: | ---: |
| Train | 14,654 | 918 (6.26%) | 11,344 |
| Validation | 3,140 | 239 (7.61%) | 2,546 |
| Test | **not loaded** | | |

The chronological and Pakistan-holdout train/validation sizes are in
`docs/research/task004_reproducibility.md` §3.

## 3–4. Features and hyperparameter search

- TF-IDF (lowercase, `\b\w\w+\b` tokens, no stemming), with min_df 2, max_df 0.9 and sublinear
  tf:
  - unigrams: ≤ 100k features (≈ 27k actual on title + description);
  - unigrams + bigrams: ≤ 200k (≈ 192k actual).
- Fitted inside the Pipeline on train only; this is tested.
- **Search:** 72 inner-CV trials. Each grid point was scored by 3-fold `StratifiedGroupKFold`
  on leakage groups inside train, using mean average precision.
- **Grids:** NB α ∈ {0.1, 0.5, 1.0}; LR 5 points of (C, class_weight); SVM 4 points.
- **Chosen by inner CV:** LR C = 16 balanced; SVM C = 0.5 unweighted; NB α = 0.1.

## 5–7. Metrics, confusion matrices and intervals

The full table for all 30 finalists is in `docs/research/task004_model_comparison.md`. Leading
results, validation partition, with 95% group-bootstrap intervals:

| Model | Val AP | F1 @train-OOF thr | P / R | TP / FP / FN / TN | Brier / ECE |
| --- | --- | --- | --- | --- | --- |
| Calibrated SVM, title+desc, uni | 0.838 [0.794, 0.878] | 0.760 [0.710, 0.807] | 0.801 / 0.724 | 173 / 43 / 66 / 2,858 | 0.027 / 0.006 |
| LinearSVC, title+desc, uni+bi | 0.836 [0.791, 0.877] | 0.760 | 0.786 / 0.736 | 176 / 48 / 63 / 2,853 | margins only |
| **LogReg, title+desc, uni+bi (winner)** | **0.827 [0.781, 0.868]** | **0.761 [0.711, 0.808]** | 0.792 / 0.732 | 175 / 46 / 64 / 2,855 | 0.028 / 0.015 |
| Best MultinomialNB (title) | 0.714 | 0.657 | 0.679 / 0.636 | 152 / 72 / 87 / 2,829 | 0.037 / 0.016 |
| Keyword rule | 0.586 [0.513, 0.656] | 0.632 | 0.646 / 0.619 | 148 / 81 / 91 / 2,820 | — |
| Majority class | 0.076 | 0.000 | 0 / 0 | 0 / 0 / 239 / 2,901 | accuracy 0.924 |

The seven leading TF-IDF linear finalists are statistically tied, by paired AP difference.

## 8. Validation slices (winner)

| Slice | F1 | Detail |
| --- | --: | --- |
| ENERGY | 0.913 | recall 0.965 |
| **Non-ENERGY** | **0.475** | **recall 0.392**: 59 of 97 non-energy climate projects missed |
| Retrospective warning | 0.789 | |
| No retrospective warning | 0.644 | |
| Year bands | 0.73–0.80 | |
| Pakistan in primary validation | 0.833 | 77 records, 12 positive. **Not a holdout.** Pakistan × sector suppressed for small n. |

Details: `docs/research/task004_validation_slices.md`.

## 9. Runtime and artifact sizes

Winner:

- 310 ms per 1,000 texts on CPU;
- 3.5 MB serialized;
- 24.6 s fit;
- 176 MB peak (tracemalloc).

The calibrated SVM (uni) is 1.1 MB and 413 ms per 1,000.

## 10. Provisional validation winner

**`logistic_regression | title_description | word_unibi`** (C 16, balanced, threshold 0.474,
artifact SHA-256 `111a7341…`).

**Reason:** it is in the AP tie set, it provides probabilities, and it is in the lowest
complexity tier among the tied probabilistic models.

**Honest alternative:** the calibrated SVM has the highest point AP, the best calibration and a
smaller file, and is not distinguishable from the winner. Both are reasonable Task 005
candidates.

The winner is **not** a final or production model.

## 11. Calibration limitations

- Class-weighted LR probabilities are shifted by the weighting (ECE 0.015). The calibrated SVM
  is better (ECE 0.006).
- Calibration is measured on validation data whose positive rate (7.6%) is near train's (6.3%).
  It may not hold for other sources or for proposal-time text.
- SVM margins are never presented as probabilities.

## 12. Final tests untouched

- `load_partitions` refuses `test` (tested).
- Every `run_manifest.json` records `test_partition_loaded: false`.
- No primary-protocol model is used for the Pakistan holdout. The Pakistan protocol was fitted
  separately, without Pakistan rows.

## 13. Reproducibility

`--check-reproducible` produced **5 outputs byte-identical across two runs**, including
`model.joblib` and the validation predictions.

**Caveat:** the runs were made from git `9c176c9` with uncommitted Task 004 code. Commit, then
re-run from the commit before Task 005 cites them.

## 14. Failed experiments

**None in the real runs:** 102 of 102 trials completed in the full run, and every trial in the
fast runs completed. Failure recording is tested by fault injection.

Two fixture bugs (a validation split with no positives, and single-class calibration folds) and
one slice bug (empty label masks) were caught by the new tests and fixed. They affected no real
run.

## 15. Tests and build (commands actually run)

| Command | Result |
| --- | --- |
| `uv sync --locked` | ok (52 packages) |
| `uv run ruff check .` / `ruff format --check .` | All checks passed / 99 files already formatted |
| `uv run mypy` | Success: no issues found in 81 source files |
| `uv run pytest` | **281 passed** (42 new: 35 modeling unit + 7 real-data ML) |
| `pnpm lint` / `pnpm typecheck` / `pnpm build` | passed |
| `uv run compassio-ml verify-frozen` | Frozen inputs match lock |
| `uv run compassio-manifest validate` | 9 entries valid; raw hashes unchanged |
| `uv run compassio-ml benchmark` ×4 (primary full, primary fast, chronological fast, Pakistan fast) | all completed, 0 failed trials |
| `uv run compassio-ml predict --model-dir … ` | artifact loaded (checksum verified); probability returned |
| `git status` | experiments, models and data are not visible to git; Task 004 code and docs uncommitted |

New tests cover:

- **Features:** allowlisted features; text construction; train-only TF-IDF fitting; no target
  fields in features.
- **Configuration and fitting:** invalid config and estimator parameters; group-aware folds;
  train/validation group disjointness.
- **Metrics:** threshold selection; confusion matrix and metric values; calibration;
  whole-group bootstrap.
- **Tracking and artifacts:** frozen-lock tamper detection; experiment registry and failed-trial
  recording; overwrite refusal; seeded reproducibility.
- **Inference and test access:** model loading and inference; empty input; artifact tampering;
  a spy proving the test partition is never requested.

## 16. Recommended next actions (Task 005)

1. Commit the Task 004 code, then re-run `primary --suite full` from the commit, so that
   `dirty: false`.
2. Choose one configuration for final evaluation. The rule picks LR. Document whether the
   calibrated SVM is also evaluated, and if so declare it **before** opening any test.
3. Refit that configuration separately under each protocol and evaluate each frozen test
   **once**. Report:
   - group-bootstrap intervals;
   - ENERGY / non-ENERGY;
   - retrospective / no warning;
   - for Pakistan, exact counts.
4. Treat non-ENERGY recall as the primary improvement target in a later, versioned benchmark.
