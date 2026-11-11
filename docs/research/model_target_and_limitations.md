# Model target and limitations

**No model exists yet (as of Task 003).** The target below is now fixed:
`is_climate_related = rio_overall > 0` (definitions verified against Qi et al. 2026, see
`docs/data/research_label_audit.md` §0). Splits are frozen in `model_evaluation_protocol.md`.
This document records the target and the evaluation rules, fixed before any model exists.

## Target

- **Input:** a project's textual description (title + description fields as provided by the source).
- **Output:** `is_climate_related` (`rio_overall > 0`) plus a calibrated probability. The
  mitigation/adaptation components are reported descriptively only (not separate targets in v1).
- SDG annotations are a possible secondary target; not in the initial scope.

## What a prediction means

"The description resembles descriptions the annotators labelled climate-relevant." Nothing more.

## What a prediction does not mean

- Not evidence the project delivered environmental benefit.
- Not a measure of funding success, financial return or investment quality.
- Not a statement that the project is open to new funding.
- Not an objective ranking of projects.

## Known risks

| Risk | Mitigation (planned) |
| --- | --- |
| **Leakage** from near-duplicate descriptions (multi-tranche loans, repeated boilerplate) across train/test — the earlier exploratory baseline may be affected | Text normalization + near-duplicate detection; group-aware splits |
| Label distribution tied to one financier population | Report performance per source; dedicated out-of-source evaluation |
| Distribution shift to Pakistan and other publishers' writing styles | Held-out Pakistan-related evaluation; manual review sample of non-training sources |
| Short / empty / templated descriptions | Report performance by description length; abstain or flag low-information inputs |
| Language mixing / translation artefacts | Record language; evaluate per language |
| Annotation scheme differs from other sources' "climate" tags (e.g. Rio markers, fund themes) | Never treat other sources' tags as the paper's labels without explicit mapping and justification |
| Over-confident scores | Calibration (reliability curves, Brier score); expose uncertainty in the UI |

## Evaluation protocol (to apply in the modelling task)

1. Freeze split definitions (with seed and group keys) in `configs/` before training.
2. Baselines first: majority class, keyword rules, TF-IDF + linear model.
3. Metrics: per-class precision/recall/F1, macro-F1, PR-AUC, calibration; confidence intervals.
4. Separate reports: in-distribution test, out-of-source, Pakistan-related.
5. Every metric reported with data manifest hashes, config, command and library versions.
6. Error analysis on a sample before any claim of usefulness.
