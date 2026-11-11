# Task 004: Reproducibility

## 1. Pinned inputs

| Input | How it is pinned |
| --- | --- |
| Raw sources | `data/manifests/source_manifest.json` (SHA-256 per file); `uv run compassio-manifest validate` |
| Research table and splits | `configs/research_split_v1.lock.json`: table `71fc5a10…`, membership `aba478d9…`, split config `e06de7e2…`, plus counts per protocol. Checked by `uv run compassio-ml verify-frozen` and at the start of every benchmark run. |
| Benchmark definition | `configs/ml_benchmark_v1.yaml`. Config hash `2f0656ed…` is embedded in every run id. |
| Software | `uv.lock` (scikit-learn 1.9.1, scipy 1.18.1, numpy 2.5.4, pandas 3.1.1, pyarrow 26.0.1, joblib 1.6.0). Its SHA-256 is recorded in each `run_manifest.json`. |
| Randomness | seed 20260109 for `StratifiedGroupKFold`, LinearSVC, LogisticRegression and the group bootstrap |

## 2. Regenerate

```powershell
uv sync --locked
uv run compassio-manifest validate
uv run compassio-research build --check-reproducible    # only if data/processed is absent
uv run compassio-ml verify-frozen
uv run compassio-ml benchmark --protocol primary --suite full            # ~1 h on 12 CPU cores
uv run compassio-ml benchmark --protocol chronological --suite fast      # ~7 min
uv run compassio-ml benchmark --protocol pakistan_holdout --suite fast   # ~7 min
uv run compassio-ml benchmark --protocol primary --suite fast --overwrite --check-reproducible
uv run compassio-ml predict --model-dir experiments/benchmarks/primary__full__seed20260109__cfg2f0656ed/model `
    --title "..." --description "..."
```

Existing run directories are never overwritten without `--overwrite`.

## 3. Runs performed in Task 004

| Run id | Partitions (records / positives) | Trials | Result |
| --- | --- | --- | --- |
| `primary__full__seed20260109__cfg2f0656ed` | train 14,654 / 918; validation 3,140 / 239 | 102 completed, 0 failed | Benchmark of record (`task004_model_comparison.md`) |
| `primary__fast__seed20260109__cfg2f0656ed` | same | 9 completed, 0 failed | Smoke and reproducibility suite |
| `chronological__fast__seed20260109__cfg2f0656ed` | train (2000–2015) 10,461 / 670; validation (2016–17) 2,277 / 185 | completed | Validation AP: SVM 0.740 [0.672, 0.803]; LR 0.727; calibrated SVM 0.726; keyword 0.625; NB 0.505; majority 0.081 |
| `pakistan_holdout__fast__seed20260109__cfg2f0656ed` | train 17,309 / 1,086; validation 3,057 / 197 (**no Pakistan rows in either**) | completed | Validation AP: SVM 0.792 [0.725, 0.848]; calibrated SVM 0.787; LR 0.786; NB 0.580; keyword 0.540; majority 0.064 |

**Protocol notes:**

- The chronological and Pakistan figures are each **protocol's own validation partition**, from
  models fitted separately under that protocol. They are not comparable to primary as a single
  score, and they are not test results.
- Chronological validation AP is about 0.10 lower than primary, consistent with a shift across
  commitment-year cohorts.
- The Pakistan-holdout validation contains no Pakistan records. The Pakistan **test** (496
  records, 76 positive) is untouched.
- The fast suite has one grid point per algorithm, so it is not a tuned comparison. Its winners
  (calibrated SVM on primary, LR elsewhere) differ from the full suite's for that reason.

## 4. Determinism check (actually run)

`uv run compassio-ml benchmark --protocol primary --suite fast --overwrite --check-reproducible`
ran the suite twice, in separate directories. It reported:

> **Reproducible: 5 outputs byte-identical across two runs**

The five outputs are `metrics_deterministic.json`, `validation_slices.csv`, `reliability.csv`,
`winner_validation_predictions.parquet` and `model/model.joblib`.

The re-run also reproduced every metric of the first fast run exactly. The full suite was run
once (about 1 h); it uses the same deterministic code paths. Timing columns (fit seconds,
latency, peak memory) vary between runs and are excluded from the comparison.

## 5. Integrity checks in force

- **Frozen inputs:** the lock check fails on any change to the table, membership, split config
  or counts. This is tested on artificial data and verified on the real files
  (`tests/test_local_ml.py`).
- **No test access:** `load_partitions(..., "test")` raises `FinalTestAccessError`. Every run
  manifest records `test_partition_loaded: false`, and a test spies on the benchmark's data
  access.
- **Artifact integrity:** `ClimateRelevanceClassifier.load` refuses a model whose SHA-256 differs
  from `model_metadata.json`. joblib uses pickle, so only artifacts produced by this repository
  may be loaded.
- **Failed trials** are kept as `status: failed` records (tested by fault injection). None
  occurred in the real runs.

## 6. Known reproducibility caveats

- **Uncommitted code:** the runs were made with Task 004 code not yet committed (git
  `9c176c9`, `dirty: true`). Before Task 005 cites them, commit the code and re-run the chosen
  configuration from the commit.
- **Bit-identical floats** are expected only on the same platform and BLAS. Another OS or CPU may
  differ in the last digits.
- **`tracemalloc` peaks** count Python-tracked allocations only. They are not whole-process RSS.
