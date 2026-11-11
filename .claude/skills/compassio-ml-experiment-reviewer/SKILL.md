---
name: compassio-ml-experiment-reviewer
description: Review Compassio model experiments, benchmarks and reported metrics for leakage, frozen-split integrity, test-set misuse, label provenance, imbalance handling, uncertainty and honest reporting. Use before trusting, reporting or extending any result from `compassio-ml benchmark` or any new training/evaluation code.
---

# Compassio ML experiment reviewer

Every metric must trace to one run directory (`experiments/benchmarks/<run_id>/`) produced by a
committed command. Protocol rules: `docs/research/model_evaluation_protocol.md`; design:
`docs/research/task004_experiment_design.md`.

## 1. Frozen inputs and splits

- `uv run compassio-ml verify-frozen` must pass. The lock `configs/research_split_v1.lock.json`
  pins the table, membership and split-config SHA-256 and split counts.
- A changed split needs a new version (`research_split_v2`) and a new lock. **Never** regenerate
  or edit membership to get better scores; never `write-lock --force` for v1.
- Check `run_manifest.json`: `frozen_lock`, `config_hash`, git commit and `dirty` flag. Results
  from a dirty tree must be re-run from a commit before they are cited.

## 2. Leakage

- Features come only from `compassio_ml.research.inputs.model_input_columns()` (text-only:
  `title_clean`, `description_clean`). No `rio_*`, `is_climate_related`, SDG, staff comments,
  year, country, sector, amount, status, group, split or eligibility columns as inputs.
- Every fitted step (TF-IDF vocabulary/IDF, class weights, calibration, thresholds) is fitted on
  the protocol's **train** partition or train-internal folds. Inner folds must be group-aware
  (`StratifiedGroupKFold` on `leakage_group_id`); plain stratified folds split related projects.
- The label is the authors' annotation (Qi et al. 2026) cross-verified with ClimateBERT: a
  ClimateBERT challenger is not an independent comparison.

## 3. Validation vs test

- Task 004 code must never load a `test` partition (`load_partitions` raises
  `FinalTestAccessError`). Check `run_manifest.json` → `test_partition_loaded: false`.
- Validation picks among finalists **once** with the pre-registered rule in
  `configs/ml_benchmark_v1.yaml`. Changing the grid or rule after seeing validation results is
  a new config version and must be disclosed.
- A primary-protocol model that saw Pakistan rows is never a Pakistan-holdout result; Pakistan
  results come only from `--protocol pakistan_holdout`.

## 4. Metrics and imbalance

- Positives are about 6–8%: select on average precision, report precision/recall/F1 at the
  train-OOF threshold, the confusion matrix, ROC-AUC secondary, accuracy last.
- Compare against `majority` and `keyword` baselines in the same run.
- Probabilities only for `score_kind == "probability"`; LinearSVC margins are decision scores.
  Report Brier/ECE for probabilistic models; class-weighted models are often miscalibrated.
- Never oversample/undersample or synthesise text outside training-only operations.

## 5. Uncertainty and slices

- Use the group-bootstrap intervals (`*_ci_low/high`) and the paired AP-difference interval;
  overlapping intervals mean "not distinguishable", not "winner".
- Read `validation_slices.csv`: `suppressed = true` slices have no conclusions. Always report
  ENERGY vs non-ENERGY and retrospective-warning vs not; strong overall scores can hide weak
  non-ENERGY recall.
- Pakistan: ~76 positives in the holdout, 16 non-ENERGY. Report counts and intervals; never
  promise stable Pakistan performance.

## 6. Reproducibility and honesty

- `compassio-ml benchmark ... --check-reproducible` must report byte-identical outputs.
- Failed trials stay in `trials.jsonl` with `status: failed`; report them.
- Call the selected model a **provisional validation winner** until the frozen tests are
  evaluated once (Task 005). It is decision support — never funding approval, impact or
  return scoring. Never quote metrics from artificial test fixtures.
