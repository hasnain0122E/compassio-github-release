# ML v2 fast-track benchmark results (Task 006-ML2)

**Scope:** this is development validation only. Labels are publisher-reported Rio markers
(`B_donor_reported_rio`), not human-verified. VALID was used **once**, to choose among finalists
by the pre-registered rule, so the chosen model's VALID scores are optimistic. No sealed,
external-test or consumed v1 test record was read.

## 1. Provenance

| Item | Value |
| --- | --- |
| Plan | `configs/ml_v2_fast_experiment.yaml`, SHA-256 `4931705648939ff8825655f2d74d34c86d2f57a4eeb72955892105bb1a0728e8`, committed in `3bf81cd` before any fit |
| Escalation addendum | `configs/ml_v2_fast_escalation.yaml`, SHA-256 `ec0f719d311e17c40de9a0efa1465e2d9d8a3ddc15ea3565e6f1a3f8acff6ff0`, committed in `7d99628` after the main champion was saved and before F was fitted |
| Main run | `data/ml_v2/experiments_v2/fast/ml2fast_49317056_3bf81cd4_20261109T192725Z` (git-ignored), commit `3bf81cd`, `dirty: false`, `test_or_sealed_data_loaded: false` |
| Escalation run | `…__escalation_ec0f719d` |
| Inputs | Audit `quality_7e70e77d22bba416`; build `v2build_a37deb181332`; development parquet `9c25b796…`; membership `4a3f6541…`; rights config `0118fcca…` |
| Loader | Data loaded only via `quality_v2.audit.load_eligible_donor_records` |
| Environment | Python 3.12.15, scikit-learn 1.9.1, numpy 2.5.4, scipy 1.18.1, pandas 3.1.1 |
| Commands | `uv run compassio-v2-train benchmark --plan-sha256 4931705648939ff8825655f2d74d34c86d2f57a4eeb72955892105bb1a0728e8`, then `uv run --all-extras compassio-v2-train escalate --plan-sha256 4931705648939ff8825655f2d74d34c86d2f57a4eeb72955892105bb1a0728e8 --addendum-sha256 ec0f719d311e17c40de9a0efa1465e2d9d8a3ddc15ea3565e6f1a3f8acff6ff0` |

## 2. Populations (verified against the loader and pinned)

| Partition | Records | Positive | Non-energy positive | Adaptation-only | Groups | Positive rate | French share* |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| FCDO TRAIN | 3,511 | 649 | 600 | 226 | 3,310 | 0.185 | 0.000 |
| FCDO VALID | 872 | 147 | 137 | 58 | 831 | 0.169 | 0.000 |
| EC TRAIN | 9,806 | 3,545 | 3,106 | 882 | 1,813 | 0.362 | 0.178 |
| EC VALID | 1,678 | 680 | 593 | 200 | 460 | 0.405 | 0.240 |
| AidData TRAIN (ablation only) | 10,184 | 688 | | | | 0.068 | |

\* Crude indicator: the share of texts containing ≥ 3 common French function words.

**Integrity checks:**

- TRAIN membership SHA-256 `ad128fc3…` (13,317 records / 4,194 positive); VALID `3b001fc0…`
  (2,550 / 827).
- 0 consumed v1 test records.
- 0 partition groups, project families or identical texts span TRAIN and VALID.
- 0 project families span both publishers, so the transfer runs needed no family exclusion
  (0 rows removed).

**Label policy:** EC marks about 36–40% of activities climate-relevant, against 17–18% for FCDO,
and EC is partly French. The publishers differ in **label policy and language**, not only in
topic.

## 3. Trials

All 46 trials succeeded (0 failed; `trials.jsonl`). Hyperparameters were chosen by **train
out-of-fold AP** (3-fold StratifiedGroupKFold on partition groups), and thresholds by train-OOF
maximum F1. Several picks sit at a grid edge (char C = 2, SVM C = 0.1, word-LR without class
weights), so the bounded search may not contain the optimum.

## 4. Finalists on combined VALID (2,550 records, 827 positive)

| Model | AP | F1 | P | R | NE-AP | NE-P | NE-R | Energy R | Adapt-only R | ECE | ms / 1,000 | MB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A word TF-IDF + LR (C = 4) | 0.834 | 0.740 | 0.757 | 0.724 | 0.806 | 0.731 | 0.700 | 0.907 | 0.643 | 0.027 | 254 | 2.5 |
| **B char TF-IDF + LR (C = 2, balanced) — champion** | **0.839** | 0.738 | 0.690 | 0.792 | **0.810** | 0.658 | **0.766** | 0.990 | **0.733** | 0.080 | 1,548 | 1.7 |
| C word+char + LR | 0.840 | 0.747 | 0.746 | 0.748 | 0.811 | 0.718 | 0.723 | 0.938 | 0.682 | 0.040 | 1,733 | 4.2 |
| C word+char + linear SVM | 0.841 | 0.749 | 0.756 | 0.742 | 0.813 | 0.730 | 0.718 | 0.928 | 0.674 | — | 1,750 | 4.1 |
| D word + Platt-calibrated SVM | 0.829 | 0.740 | 0.718 | 0.764 | 0.801 | 0.690 | 0.742 | 0.928 | 0.690 | 0.018 | 205 | 2.5 |
| E publisher-balanced weights (on C-SVM) | 0.842 | 0.751 | 0.743 | 0.761 | 0.815 | 0.715 | 0.734 | 0.959 | 0.690 | — | 1,661 | 4.1 |
| E family-inverse weights (on C-SVM) | 0.834 | 0.749 | 0.718 | 0.782 | 0.804 | 0.689 | 0.759 | 0.959 | 0.705 | — | 1,655 | 4.1 |
| Combined + AidData (C-SVM) | 0.843 | 0.748 | 0.739 | 0.757 | 0.814 | 0.712 | 0.730 | 0.959 | 0.682 | — | 1,827 | 7.1 |
| F frozen multilingual-e5-small + LR (escalation) | 0.822 | 0.750 | 0.731 | 0.769 | 0.791 | 0.703 | 0.744 | 0.959 | 0.659 | 0.106 | 63,498 | 470 + LR |
| v1 release (fixed, threshold 0.474) | 0.681 | 0.441 | 0.887 | 0.294 | 0.649 | 0.875 | 0.259 | 0.557 | 0.209 | 0.171 | 984 (single-record calls) | 3.6 |
| Keyword baseline | 0.570 | 0.577 | 0.735 | 0.475 | 0.535 | 0.703 | 0.458 | 0.608 | 0.469 | — | — | — |
| Majority | 0.324 | 0 | 0 | 0 | 0.300 | 0 | 0 | 0 | 0 | — | — | — |

**Column key:** NE = non-energy; R = recall; P = precision.

**Notes:**

- **ECE** is given only for probabilistic scores. SVM margins are decision scores.
- **Latency** is the median of 3 batch-scoring runs on 1,000 VALID texts on an i7-10750H CPU.
- **Size** is the compressed joblib size. F additionally needs the 470 MB encoder.

**Champion 95% group-bootstrap intervals** (2,000 resamples of partition groups):

| Measure | Interval |
| --- | --- |
| AP | [0.806, 0.869] |
| F1 | [0.701, 0.774] |
| Non-energy AP | [0.772, 0.846] |
| Non-energy precision | [0.607, 0.709] |
| Non-energy recall | [0.716, 0.814] |
| Adaptation-only recall | [0.647, 0.812] |

**Runner-up comparison** (champion − E publisher-balanced, paired):

| Measure | Difference |
| --- | --- |
| AP | −0.004 [−0.009, +0.002] |
| Non-energy AP | −0.004 [−0.011, +0.002] |

**The lexical finalists are statistically indistinguishable on these records.**

## 5. Per-publisher ablations (each trained and validated on one publisher)

| Model | FCDO → FCDO AP / F1 / NE-AP | EC → EC AP / F1 / NE-AP |
| --- | --- | --- |
| A word LR | 0.747 / 0.667 / 0.728 | 0.848 / 0.774 / 0.820 |
| B char LR | 0.744 / 0.614 / 0.723 | 0.850 / 0.760 / 0.821 |
| C word+char LR | **0.751** / 0.667 / 0.731 | **0.854** / 0.770 / 0.824 |
| C word+char SVM | 0.749 / 0.640 / 0.729 | **0.854** / 0.772 / 0.826 |
| D Platt SVM | 0.742 / 0.652 / 0.724 | 0.843 / 0.757 / 0.815 |

**Combined training on each publisher's VALID slice:**

| Publisher | Champion AP | Runner-up AP | Best single-publisher AP |
| --- | ---: | ---: | ---: |
| FCDO | 0.741 | 0.750 | 0.751 |
| EC | 0.862 | 0.863 | 0.854 |

Combined training helps EC slightly and **does not help FCDO**. AidData augmentation (+10,184
records) changed combined AP by +0.002 (C-SVM 0.841 → 0.843), within noise.

## 6. Publisher transfer (no target-publisher family in training; source-OOF thresholds)

| Train → evaluate | Best AP | F1 | P | R | NE-R | In-domain AP of the target |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FCDO → EC VALID | 0.816 (B char) | 0.684 | 0.865 | 0.566 | 0.551 | 0.854 |
| EC → FCDO VALID | 0.707 (D Platt) | 0.579 | 0.462 | 0.776 | 0.759 | 0.751 |

Transfer costs about 0.04–0.05 AP. The threshold shifts the way the label policies differ:
FCDO-trained models under-call EC (recall 0.45–0.57), and EC-trained models over-call FCDO
(precision 0.38–0.46). A deployed screener would need per-publisher calibration. This is
cross-publisher evidence within two donors, **not** unseen-publisher generalisation.
