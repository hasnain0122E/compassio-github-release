# Task 004: Experiment design (validation stage)

Code: `compassio_ml.modeling`. Config: `configs/ml_benchmark_v1.yaml`, declared before any
result. Command: `uv run compassio-ml benchmark --protocol <p> --suite <fast|full>`.
**No frozen test partition is loaded by any Task 004 code path.**

## 1. Target and inputs

| | |
| --- | --- |
| Target | `is_climate_related = rio_overall > 0`: the authors' annotation (Qi et al. 2026); positive class = 1 |
| Population | `eligibility_status == "eligible"` (20,936 records; quarantined records are excluded) |
| Inputs | Text only, from `model_input_columns()`: `title_clean`, `description_clean` |
| Representations | A `title`; B `description`; C `title_description` (title, separator, description) |
| Not inputs (used only for slices) | amount, country, sector, commitment year, retrospective flag |

Enforcement:

- `load_partitions` reads feature columns only from the allowlist and rejects forbidden names.
- It returns slice metadata in a separate frame that never reaches an estimator.
- It raises `FinalTestAccessError` for `test`.

## 2. Frozen inputs

`configs/research_split_v1.lock.json` (committed) pins:

| Item | SHA-256 |
| --- | --- |
| `research_projects.parquet` | `71fc5a10…` |
| `research_split_membership_v1.parquet` | `aba478d9…` |
| `research_split_v1.yaml` | `e06de7e2…` |

The lock also pins the split counts per protocol.

The Parquet hashes were checked against the Task 003 build's own checksums before locking. The
counts were re-derived from the files: 20,985 rows, 20,936 eligible, 49 quarantined, 16,358
groups. Every run calls `require_frozen()` and refuses to proceed on any difference; this is
tested.

## 3. Pipeline and fitting discipline

- **Estimator:** each learned model is one sklearn `Pipeline(TfidfVectorizer → classifier)`,
  so the vocabulary and IDF are computed only from the rows passed to `fit`. No corpus
  statistics are computed before splitting.
- **Hyperparameter search:** for each representation, TF-IDF preset and algorithm, every grid
  point is scored by **3-fold `StratifiedGroupKFold` inside the training partition**
  (`leakage_group_id` groups, seed 20260109; fold-group disjointness is asserted). The score is
  mean fold average precision. The best grid point per algorithm is the finalist.
- **Threshold:** the max-F1 threshold on the finalist's out-of-fold **train** scores.
  Validation labels never choose a threshold. A validation-optimal threshold is computed and
  reported only as an optimistic reference (`*_oracle_not_for_selection`).
- **Refit:** the finalist is refit on the full training partition and scored on validation.
- **Calibrated SVM:** `CalibratedClassifierCV(sigmoid)` over the best LinearSVC. Its
  calibration folds are the same training-only group folds, and each fold refits TF-IDF. Its
  threshold uses nested OOF probabilities (calibration folds within each outer fold).
- **Imbalance:** handled by `class_weight ∈ {None, balanced}` inside the grid, by threshold
  selection, and by AP/F1-centred metrics. No resampling or synthetic text.

## 4. Candidates and grid (full suite)

| Algorithm | Grid | Notes |
| --- | --- | --- |
| Majority class | — | Always predicts the training majority (negative) |
| Keyword rule | — | ≥ 1 hit from a fixed 24-pattern lexicon (`features.KEYWORD_LEXICON`) |
| TF-IDF + MultinomialNB | α ∈ {0.1, 0.5, 1.0} | |
| TF-IDF + LogisticRegression (liblinear, L2) | (C, class_weight) ∈ {(1, None), (4, None), (1, bal), (4, bal), (16, bal)} | |
| TF-IDF + LinearSVC | (C, class_weight) ∈ {(0.5, None), (0.1, bal), (0.5, bal), (2, bal)} | Margins are decision scores, never probabilities |
| Calibrated LinearSVC | The best SVM's parameters | Genuine probabilities |

TF-IDF presets:

- `word_uni`: (1,1)-grams, min_df 2, max_df 0.9, ≤ 100k features, sublinear tf.
- `word_unibi`: (1,2)-grams, the same settings, ≤ 200k features.

Total: 3 representations × 2 presets × 12 grid points = **72 inner-CV trials**, plus 30
finalists.

**Keyword lexicon caveat:** the lexicon was written before any Task 004 metric. However, Task 002
examined the label association of a few of its words over the whole dataset, so this baseline
is not fully blind.

**Not run:**

- **Tree/boosting models:** they would need dense or engineered features, and the spec forbids
  densifying sparse TF-IDF.
- **Sentence-embedding and transformer models:** no large downloads or GPU frameworks in this
  task.
- **A ClimateBERT challenger, if ever run, is not an independent comparison**, because the
  paper's labels were cross-verified with ClimateBERT.

## 5. Selection rule (pre-registered)

1. Rank finalists by validation average precision.
2. **Tie set:** finalists whose paired group-bootstrap 95% interval for
   (top AP − candidate AP) includes 0. The bootstrap uses 2,000 resamples of whole leakage
   groups, with identical resamples across models.
3. Within the tie set, prefer, in order:
   1. genuine probabilities;
   2. lower complexity tier (baselines 0; NB/LR/SVM 1; calibrated SVM 2, a 3-model ensemble);
   3. higher validation F1 at the train-OOF threshold;
   4. lower latency.

## 6. Tracking

Each run writes `experiments/benchmarks/<protocol>__<suite>__seed<seed>__cfg<hash8>/`, which is
git-ignored. An existing directory is refused without `--overwrite`.

| File | Contents |
| --- | --- |
| `run_manifest.json` | Config and config hash, frozen lock (dataset and split hashes), git commit and dirty flag, package versions, `uv.lock` and source-manifest SHA-256, partition sizes, `test_partition_loaded: false` |
| `trials.jsonl` | One `started` and one `completed`/`failed` record per trial, with id, params, timings and CV metrics |
| `finalists.csv` | All validation metrics, intervals, timing, size and feature counts |
| `metrics_deterministic.json` | The same without timing (for reproducibility checks) |
| `validation_slices.csv`, `reliability.csv`, `winner_validation_predictions.parquet` | Slice metrics, reliability tables and the winner's validation predictions |
| `model/model.joblib`, `model/model_metadata.json` | The winner and its metadata. Metadata includes the artifact SHA-256, threshold, representation, TF-IDF settings and dataset hashes. |

Memory is measured as the peak `tracemalloc` allocation during the final fit.

## 7. Protocols

- **primary** (full suite): the benchmark of record.
- **chronological** and **pakistan_holdout** (fast suite): training and validation only. Each
  model is fitted separately under its own protocol. The Pakistan protocol's train/validation
  contain **no Pakistan records**, and its validation is non-Pakistan.
- Metrics are never combined across protocols.
