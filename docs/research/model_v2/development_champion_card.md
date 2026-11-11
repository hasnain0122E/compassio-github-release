# Development champion card: `ml2fast_49317056_c76204127550`

| Field | Value |
| --- | --- |
| Status | **`development_candidate`.** NOT a trusted release, NOT in `configs/trusted_model_releases.json`, NOT served by the API. v1 remains the only approved inference model. |
| Model | Character TF-IDF (`char_wb` 2–5-grams, min_df 3, max_df 0.95, ≤ 300,000 features, sublinear tf, float32) → LogisticRegression (liblinear, C = 2, class_weight balanced, seed 20261110) |
| Input | `title_clean` + `description_clean` (v1 `build_text`, representation `title_description`); no metadata inputs |
| Label | Publisher-reported Rio markers: positive = `donor_rio_overall > 0` (significant or principal, mitigation or adaptation); origin `B_donor_reported_rio`, not human-verified |
| Training data | Combined FCDO + EC v2 **TRAIN** partition: 13,317 activities (4,194 positive); membership SHA-256 `ad128fc332ae35228a235e992d66241432ce742932414f142852bd62250eb103`; audit `quality_7e70e77d22bba416`; build `v2build_a37deb181332` |
| Threshold | **0.44474326842740053**: train out-of-fold maximum F1 (3-fold StratifiedGroupKFold on partition groups). Scores are LR probabilities; no extra calibration. |
| Artifact | `data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/model.joblib` (git-ignored), 1,650,643 bytes |
| Artifact SHA-256 | `654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574` |
| Content fingerprint | `c76204127550fb299c11704de61bd07cce3eae6635193e608a42897c5f995ad2` |
| Plan | `configs/ml_v2_fast_experiment.yaml`, SHA-256 `4931705648939ff8825655f2d74d34c86d2f57a4eeb72955892105bb1a0728e8`; run `ml2fast_49317056_3bf81cd4_20261109T192725Z` at commit `3bf81cd` (clean) |
| Environment | Python 3.12.15, scikit-learn 1.9.1, numpy 2.5.4, joblib 1.6.0 (also in the candidate manifest) |

## Selection rationale (pre-registered, applied once)

1. **Guard:** non-energy precision ≥ 0.60. All 8 combined-population finalists passed.
2. **Primary metric:** non-energy AP on combined VALID. The top value was 0.8145 (E
   publisher-balanced). Five finalists fell within the 0.005 tie window: B, C-LR, C-SVM, E
   publisher-balanced, and combined + AidData.
3. **Tie-breaker 1:** adaptation-only recall. B had the highest, 0.733, so B was chosen.

**Caveat:** B's lead is a tie-breaker, not a significant difference.

- Champion − runner-up non-energy AP: −0.004 [−0.011, +0.002].
- B has the **lowest non-energy precision** of the tied group (0.658, against about 0.71–0.73).
- Its calibration is weaker (ECE 0.080, against 0.027 for word LR).

The escalation candidate F (frozen `intfloat/multilingual-e5-small` + LR) did not meet its
pre-registered replacement rule, so B stands.

## Development-validation performance (2,550 FCDO + EC VALID records; optimistic for the selected model)

| Measure | Value |
| --- | --- |
| AP | 0.839 [0.806, 0.869] |
| F1 | 0.738 [0.701, 0.774] |
| Precision / recall | 0.690 / 0.792 |
| ROC-AUC | 0.891 |
| Brier | 0.123 |
| ECE | 0.080 |
| Non-energy AP | 0.810 |
| Non-energy precision / recall | 0.658 / 0.766 |
| Adaptation-only recall | 0.733 (189 / 258) |
| Energy recall | 0.990 |
| FCDO slice | AP 0.741, P 0.573, R 0.694 |
| EC slice | AP 0.862, P 0.717, R 0.813 |
| Versus fixed v1 on the same records | AP +0.158 [+0.120, +0.198]; non-energy AP +0.162 [+0.120, +0.206] |
| Latency | About 1.5 ms per text (CPU, batch) |

## Reproducibility

`uv run compassio-v2-train reproduce --plan-sha256 4931705648939ff8825655f2d74d34c86d2f57a4eeb72955892105bb1a0728e8 --run-dir data/ml_v2/experiments_v2/fast/ml2fast_49317056_3bf81cd4_20261109T192725Z`
refits from the sanctioned loader. Result:

- **identical** fingerprint;
- **identical** threshold;
- maximum validation score difference **0.0**.

The pickled bytes are not process-stable (scikit-learn's `_stop_words_id`), which is why the
content fingerprint is the reproducibility key.

## Guarded use

```powershell
uv run compassio-v2-train predict --candidate-dir data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550 --title "..." --description "..."
```

`ExperimentalClassifier.load` refuses:

- a missing or foreign manifest schema;
- any status other than `development_candidate`;
- a checksum mismatch, checked **before** unpickling;
- any artifact listed in the trusted release registry;
- a fingerprint mismatch.

Blank input is refused (exit 2). Every prediction carries the limitation text.

## Allowed use and limitations

- **Allowed:** internal development research screening, with human review.
- **No independent evaluation:** there are no human-verified labels. The scores measure
  agreement with publisher-reported markers on development-validation data that was used for
  selection.
- **No external claims:** it is not evidence of unseen-publisher, Pakistan, proposal-time or
  production performance.
- **Over-calls some sectors:** for example transport (precision 0.31). Transport and urban
  slices are too small for claims.
- **Publisher sensitivity:** FCDO precision is lower (0.573). Label-policy differences shift
  thresholds across publishers.
- **Prohibited claims:** climate relevance is not environmental impact, funding approval,
  investment return or an open funding opportunity.
- **Rights:** source rights remain `not_reviewed`; use is internal non-commercial research only.
