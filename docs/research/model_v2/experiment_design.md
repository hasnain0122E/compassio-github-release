# V2 experiment design (plan only — nothing trained in Task 006-ML)

**No improvement is claimed or guaranteed.** Every candidate is compared under identical v2
development partitions and predeclared metrics. The v1 final tests are never used.

## 1. Data for experiments

- Fit on `training_candidate`. Select on `validation_candidate`. Both come from one
  `build_id`, recorded in every run manifest, and are loaded through
  `compassio_ml.external.development`. All consumed v1 test records are excluded from
  training, validation, calibration, thresholds and tuning; there is no consumed-test ablation.
- Labels: A (researcher) and B (donor, explicit both markers). Every run reports metrics
  separately for A-validation and B-validation, and includes an **A-only** training ablation,
  so donor labels cannot silently change the target.
- Group-aware inner folds: `StratifiedGroupKFold` on `partition_group_id`.

## 2. Candidates (in order of cost)

| # | Candidate | Notes |
| --- | --- | --- |
| R | **V1 release** (`compassio-ccrc-1.0.0`) | Fixed reference, scored as-is on v2 validation |
| 1 | Majority + keyword baselines | Required comparators |
| 2 | TF-IDF word 1–2-gram + logistic regression (balanced) | v1 recipe refit on v2 training |
| 3 | TF-IDF word + **character 3–5-gram**, LR / linear SVM (calibrated) | Morphology, spelling variants |
| 4 | Sector-aware variants: per-sector-family class weights; sector-family indicator **only if** sector is a legitimate input at application time (it is known before approval) | Must be predeclared |
| 5 | Training-only reweighting / resampling (by label origin, sector family, length band) | Never applied to validation |
| 6 | Sentence embeddings (frozen encoder) + logistic regression | Needs `sentence-transformers` + PyTorch |
| 7 | Small transformer fine-tuning (≤ ~110 M parameters, e.g. DistilRoBERTa/MiniLM class) | Needs PyTorch + `transformers` |
| 8 | Multi-task heads for mitigation and adaptation | Only if B labels prove consistent in the audit |

Calibration: Platt or isotonic fitted on training out-of-fold predictions; report Brier and
10-bin ECE on validation. Uncertainty: group bootstrap (2,000 resamples) over
`partition_group_id`.

## 3. Hardware and runtime (measured hardware; runtimes are to be measured)

Observed on 2026-11-09: Intel i7-10750H (6 cores / 12 threads), 15.8 GB RAM, NVIDIA GTX 1650 Ti
with 4 GB VRAM (driver 617.42), 388 GB free disk.

- Candidates 1–5: CPU only; Task 004 ran comparable TF-IDF suites locally.
- Candidate 6: a frozen small encoder fits in 4 GB VRAM; embedding cost must be **measured on
  1,000 validation texts** before the full run and recorded.
- Candidate 7: fine-tuning ≤ 110 M-parameter encoders on 4 GB VRAM needs small batches,
  sequence length ≤ 256 and mixed precision; larger models are out of scope on this machine.
- **No heavy dependency is installed in Task 006-ML.** Installing PyTorch/transformers is a
  Task 007-ML decision, after this plan is approved (adds roughly 2–3 GB to the environment;
  CUDA build must match the driver).

## 4. Predeclared selection rule

1. Primary selection metric: validation **average precision** on A-validation, with the
   paired group-bootstrap AP difference vs. candidate 2.
2. A candidate is preferred only if its AP-difference interval excludes 0 **and** it does
   not reduce ENERGY recall by more than 0.05 (point estimate) at its threshold.
3. Threshold: max-F1 on training out-of-fold predictions (as in v1), then reported on
   validation.
4. Changing this rule after viewing validation results creates a new config version, which
   is disclosed.

## 5. Required reporting per run

Per-class precision/recall/F1, AP, ROC-AUC (secondary), Brier, ECE, confusion matrix; slices
by ENERGY vs non-ENERGY, adaptation-only, mitigation-only, label origin, sector family,
Pakistan, length band and text timing; intervals for all; run manifest with build ID, data
hashes, seed, library versions and git state.
