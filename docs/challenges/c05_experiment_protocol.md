# C05 experiment protocol

Configuration: `configs/c05_poison_quarantine.yaml` (`c05-1.0.0`, detector
`compassio-c05-detector-1.0.0`), frozen before the final run. Code:
`packages/compassio_ml/src/compassio_ml/challenges/c05/`.

## 1. Data

- **Incoming batch (A, clean):** the eligible ML v2 TRAIN cohort, loaded only through
  `compassio_ml.model_v2.data.load_development`, which re-checks the plan pins, the ML rights
  (`iati_fcdo` and `iati_ec_intpa`: `ml_training` and `automated_evaluation` permitted pending
  review), the absence of consumed v1 test records and TRAIN/VALID isolation (no group, family
  or identical text spans both).
  - 13,317 records, 4,194 climate-positive (EC 9,806 at 36.2% positive; FCDO 3,511 at 18.5%).
  - Label: `donor_rio_overall > 0` (publisher Rio markers). Model input: title + description only.
  - Fingerprint (sorted `id|label`, SHA-256) `ad128fc3…` = the plan's pinned TRAIN membership.
- **Benchmark:** the ML v2 development-validation partition (2,550 records, 827 positive),
  labelled a **challenge development benchmark**. It is not independent: it was used once to
  select the ML v2 champion. The sealed ML v1 tests, the external human test and every
  consumed evaluation are never read.

## 2. Batches

| Batch | Construction | Stored as |
| --- | --- | --- |
| A clean | the cohort, unchanged | `batch_A_clean.jsonl` (+ SHA-256 in the manifest) |
| B poisoned | A with exactly 666 labels inverted (seed 20261112) | `batch_B_poisoned_<mode>.jsonl`; oracle in `private_oracle/oracle_<mode>.json` |
| C protected | the records of B accepted by the gate | `batch_C_protected_<mode>.jsonl`; gate report `gate/<mode>_report.json` |

The original arrays are read-only. The attack returns a new batch, and the gate never rewrites
a label.

## 3. Detector (out-of-fold, group-aware)

1. `StratifiedGroupKFold` (5 folds, seed 20261111) on the **supplied** labels, grouped by
   `partition_group_id`. A group never spans the training folds and the held-out fold.
2. Per fold, fitted on the training folds only:
   - word TF-IDF (1–2-grams), then logistic regression (C = 4, balanced), predicting the
     held-out fold;
   - cosine k-nearest neighbours (k = 15) of each held-out record among the training-fold
     records, in the same fold-fitted space.
3. **Text-model signal (confident learning).** Threshold `t_c` = the mean out-of-fold
   probability of class `c` over records supplied with label `c`. It is computed per publisher
   when that publisher has ≥ 50 records of the class, otherwise batch-wide (EC and FCDO mark
   Rio objectives differently). A record supplied with label `i` is flagged when
   P(other label) ≥ `t_other`.
4. **Neighbour signal.** Flagged when at most 20% of the 15 neighbours share the supplied label
   and their mean similarity is at least 0.10. Below that similarity there is no neighbour
   evidence.
5. **Decision:**
   - `quarantined` when both signals flag;
   - `insufficient_evidence` when exactly one does, or when neighbours are too far
     (policy `accept_and_review`: kept for training, listed for review);
   - otherwise `accepted`.
   - If a class has fewer than 50 records in the batch, nothing is quarantined and every record
     is `insufficient_evidence`.
6. **Suspicion score** (0–1, for ranking and the threshold sweep only) = 0.5 × P(other label)
   + 0.5 × the share of neighbours that disagree.

`cleanlab` was considered. It is not installed, and adding it would change the locked
environment for one function, so the confident-learning threshold rule is implemented directly
(about 30 lines, `detector._thresholds`).

## 4. Downstream comparison (disposable models)

Same settings for every run:
- **Model:** the ML v2 champion family (char_wb 2–5 TF-IDF + logistic regression, C = 2,
  balanced).
- **Threshold:** max-F1 on 3 group-aware out-of-fold folds of the labels the model is trained
  with. A real pipeline cannot see clean labels.
- **Seed:** 20261110.

| Run | Trained on |
| --- | --- |
| Clean reference | A (true labels) |
| Naive | B (all poisoned labels) |
| Protected | `AcceptedBatch` from the gate (C) |
| Strict variant (uniform only) | B minus quarantined and insufficient-evidence records |

**Metrics on the benchmark:** average precision (PR-AUC), F1, precision, recall, non-energy
recall and adaptation-only recall (258 adaptation-only positives).

**Detector metrics, computed against the oracle after the decision:**
- injected count; true positives (TP), false positives (FP) and false negatives (FN);
- precision and recall;
- false-quarantine rate (FP ÷ clean records);
- clean records retained;
- clean climate-positive and clean adaptation-only positives quarantined;
- poisoned records accepted;
- a suspicion-rank sweep (top 2–10%).

The detector also runs on the **unpoisoned** batch A, to measure its natural false-alarm floor.

## 5. Seeds and development history

The detector was developed with attack seeds 20261111 and 101 on TRAIN only (no benchmark
scoring). Those runs showed text-model AP for the flipped labels of 0.37. A word + char model
reached 0.38, so the cheaper word model was kept. The final attack seed **20261112** was fixed
in the config before the final run and was not used during development. No threshold was
changed after the final run.

## 6. Reproduce

```powershell
# ML v2 environment (the cohort loader needs the v2 inputs)
$env:COMPASSIO_DATA_ROOT = "$PWD\data"; $env:COMPASSIO_V1_PROJECT_ROOT = "$PWD"
$env:COMPASSIO_V2_OUTPUT_ROOT = "$PWD\data\ml_v2"
$env:COMPASSIO_V2_EXTERNAL_INPUT_ROOT = "<ml worktree>\data\ml_v2\external_raw"
uv run python -m compassio_ml.challenges.c05.cli run      # full experiment (immutable run dir)
uv run python -m compassio_ml.challenges.c05.cli verify   # re-hash every output
uv run python -m compassio_ml.challenges.c05.cli show     # results + judge_report.html
uv run pytest tests/ml/test_c05_quarantine.py tests/test_local_c05.py
```

The run directory is `data/ml_v2/challenges/c05/c05_<first 12 hex of the config SHA-256>/`.
A second `run` with the same config refuses to overwrite it.

## 7. Hardening addendum (c05-1.1.0)

- **Config:** `configs/c05_hardening_addendum.yaml`, frozen before evaluation on the final seed.
- **Design data:** policy B was designed only on development seed 101 (detection-only analysis
  of TRAIN; no benchmark scoring).
- **Inputs:**
  - the base run's verified clean batch, poisoned batches, oracles and benchmark;
  - the publisher purpose codes, via `load_eligible_donor_records` after `check_pins` and
    `check_rights`, with the cohort fingerprint checked against the plan pin.
- **Policies:** A (deployed), B (hardened candidate) and C (top 5%, analysis only), all applied
  to the same detector output.
- **Evaluation:**
  - the final seed 20261112, the same flips as the base run;
  - fresh robustness seeds 20261113–20261115, detection only;
  - the no-attack batch;
  - disposable models for B and C with the base-run downstream settings.
- **Reproduce:** `uv run python -m compassio_ml.challenges.c05.cli addendum` (needs the ML v2
  environment), then `cli verify` and `cli show`. The addendum directory is immutable.
