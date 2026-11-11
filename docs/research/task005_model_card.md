# Model card: Compassio Climate Relevance Classifier v1 — MVP Research Screening

| Field | Value |
| --- | --- |
| Version | `compassio-ccrc-1.0.0-mvp-research-screening` |
| Status | **Internal MVP research screening**: all pre-registered acceptance criteria passed; not a production or public service |
| Artifact | `models/compassio_ccrc_v1/model.joblib` (git-ignored) |
| Artifact SHA-256 | `53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656`, pinned in the committed `configs/trusted_model_releases.json` |
| Content fingerprint | `3023fe3d148b605c3ed9079c93f07296193fd2d8d5f77b8a82a163e58ccdc495`. This is the same model as the Task 004 validation winner and the primary final-test model. |
| Manifest | `models/compassio_ccrc_v1/release_manifest.json` (committed copy: `docs/research/final_evaluation_v1/release_manifest.json`) |
| Evaluation plan | `configs/final_evaluation_v1.yaml`, SHA-256 `c4760503…b8b3cb` |

## Model

- **Pipeline:** TF-IDF (word 1–2-grams, min_df 2, max_df 0.9, ≤ 200,000 features, sublinear tf,
  lowercase, no stemming) → LogisticRegression (L2, C = 16, class_weight = balanced, liblinear,
  seed 20260109).
- **Input:** `title` + `description` (cleaned as in `docs/data/research_cleaning_spec.md`).
- **Output:** `is_climate_related` (label score ≥ **0.4740**), plus `label_score` in [0, 1].
- **Training data:** primary-protocol TRAIN partition, 14,654 records (918 positive), from
  research_split_v1:
  - text from AidData GCDF 3.0 (ODC-By 1.0);
  - labels from Qi et al. 2026 (*Sci Data* 13:277):
    `is_climate_related = rio_overall > 0`, the authors' annotations, cross-verified with
    ClimateBERT by the authors.

## Intended use

Human-reviewed screening of whether a project description resembles text that the research
authors annotated as having a significant or principal climate objective. It supports reviewers
in prioritising reading. **Every output requires human review.**

## Prohibited claims

The model must **not** be described as:

- predicting investment returns;
- predicting funding approval;
- verifying environmental impact;
- detecting fraud;
- performing reliable proposal-time classification without external validation;
- reliably classifying all adaptation or non-energy project types.

The score is **not** a probability of success, approval or impact.

## Evaluation (one-shot frozen tests)

| Protocol | Rows (pos) | AP [95% CI] | F1 [95% CI] | Precision | Recall | ECE |
| --- | --- | --- | --- | --: | --: | --: |
| Primary (group-disjoint) | 3,142 (202) | 0.751 [0.680, 0.815] | 0.670 [0.599, 0.732] | 0.718 | 0.629 | 0.018 |
| Chronological (2000–15 → 2018–21; distribution shift) | 6,022 (266) | 0.674 [0.612, 0.732] | 0.625 [0.564, 0.682] | 0.745 | 0.538 | 0.016 |
| Pakistan holdout (no Pakistan in training) | 496 (76) | 0.919 [0.844, 0.966] | 0.865 [0.764, 0.936] | 0.938 | 0.803 | 0.029 |

Primary test ENERGY recall is **0.860**, against **0.368** for non-ENERGY. Pakistan non-ENERGY:
6 of 16 positives found.

Details: `task005_final_model_evaluation.md`, `task005_pakistan_generalization.md`.

## Known limitations

1. **Weak outside energy.** Most adaptation, water, agriculture, transport, emergency and
   governance climate projects are missed (adaptation-only recall 0.31; "significant" labels
   0.44). A negative result does not mean "not climate-relevant".
2. **Retrospective text.** The model is trained and tested on after-the-fact descriptions, and
   retrospective wording raises scores. Proposal-time performance is **unmeasured** and likely
   lower.
3. **Temporal shift.** Recall falls to 0.54 on 2018–2021 commitments when the model is trained
   on 2000–2015.
4. **Source style.** Trained only on AidData's Chinese official-finance descriptions. It is
   untested on GCF, ADB, World Bank or other publishers' text.
5. **Label noise.** The labels are author annotations, with inconsistencies across financing
   components of one project. There are no per-record agreement scores.
6. **Narrow acceptance.** F1 and ENERGY recall passed their floors by 0.02 and 0.01; their
   intervals cross the floors.
7. **Pakistan.** Results are dominated by energy (60 of 76 positives). Family selection was not
   fully blind to Pakistan.

## Operational details

- **Loading:** `compassio_ml.modeling.release.ReleasedClassifier.load(release_dir, trusted_registry)`
  checks the manifest schema and version, the manifest checksum and the committed trusted
  registry **before** unpickling, then the content fingerprint. It needs no training data.
- **Blank input** (both fields empty) raises `EmptyInputError`.
- **Unknown versions** raise `ReleaseError`.
- **Size and speed:** 3.53 MB; about 0.33 ms per text on CPU.
- **Dependencies:** recorded in the manifest (scikit-learn 1.9.1, numpy 2.5.4, scipy 1.18.1,
  joblib 1.6.0; Python 3.12.15). Loading needs the same scikit-learn version.

## Attribution

- **Labels:** Qi, J., Tang, Y., Zhang, Z., Wang, Y. & Qian, H. (2026). *A Benchmark Dataset of
  Chinese Development Finance with Climate Relevance and SDG Annotations from 2000–2021.*
  Scientific Data 13, 277. doi:10.1038/s41597-026-06605-9; data doi:10.6084/m9.figshare.30015124
  (CC0).
- **Text:** AidData's Global Chinese Development Finance Dataset, Version 3.0 (ODC-By 1.0;
  attribution required).
- **Rights:** source rights remain `not_reviewed` (`docs/data/source_rights_matrix.md`). The
  model must not be distributed publicly until they are confirmed.
