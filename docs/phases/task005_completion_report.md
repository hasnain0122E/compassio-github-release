# Task 005 completion report: final held-out evaluation and MVP release

## Outcome

The selected configuration was fixed and not re-tuned:

- TF-IDF word 1–2-grams + LogisticRegression, C = 16, balanced class weights;
- input is title + description;
- the label is `rio_overall > 0`;
- the primary threshold is 0.474.

Each of the three frozen test partitions was evaluated **exactly once**, under a plan
pre-registered and committed before any test access. All pre-registered acceptance criteria
passed on the primary test, so the model is released internally as **Compassio Climate
Relevance Classifier v1 — MVP Research Screening**, with a mandatory non-energy limitation.

| Protocol | Rows (pos) | AP [95% CI] | F1 | Precision | Recall | ECE |
| --- | --- | --- | --: | --: | --: | --: |
| Primary | 3,142 (202) | 0.751 [0.680, 0.815] | 0.670 | 0.718 | 0.629 | 0.018 |
| Chronological | 6,022 (266) | 0.674 [0.612, 0.732] | 0.625 | 0.745 | 0.538 | 0.016 |
| Pakistan holdout | 496 (76) | 0.919 [0.844, 0.966] | 0.865 | 0.938 | 0.803 | 0.029 |

Details:

- `docs/research/task005_final_model_evaluation.md`
- `docs/research/task005_pakistan_generalization.md`
- `docs/research/task005_error_analysis.md`
- `docs/research/task005_model_card.md`
- `docs/research/task005_reproducibility.md`

## Commits (local only, not pushed)

| Commit | Content |
| --- | --- |
| `17a2c71` | Task 004.5 checkpoint |
| `6bb4668` | One-shot final evaluation module and CLI |
| `f14f397` | Fingerprint, release builder, safe loader. This is the plan's guarded source commit. |
| `153dce8` | Frozen plan `configs/final_evaluation_v1.yaml` + SHA-256 + pre-test development report |
| Final Task 005 commit | Post-hoc error-analysis command, CLI error handling, local integrity tests, docs, committed aggregate results, trusted release registry |

**Guarded-code ordering:** guarded code (`packages/compassio_ml/src`) was changed **only after
all three evaluations had completed**. Two changes were made:

- a post-hoc `final-error-analysis` command, which reads completed predictions only;
- a clean exit 2 from `release-predict` on blank or untrusted input.

Neither change affects any model, threshold or metric.

## Commands run (real output summarised)

| Command | Result |
| --- | --- |
| `compassio-ml final-evaluate --protocol primary --plan-sha256 c4760503…` | Completed. Second attempt refused, exit 2. |
| `… --protocol chronological …` | Completed |
| `… --protocol pakistan_holdout …` | Completed |
| `compassio-ml final-error-analysis --protocol {primary, chronological, pakistan_holdout}` | Completed |
| `compassio-ml release --plan-sha256 c4760503…` | Status `mvp_research_screening`, artifact `53b226f6…` |
| `compassio-ml release-predict` (example solar-PV text) | `is_climate_related: true`, with the limitation message |
| `compassio-ml release-predict` (blank input) | Refused, exit 2 |
| `uv sync --locked` | OK |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 121 files already formatted |
| `mypy` | No issues in 91 source files |
| `pytest` | **326 passed** |
| `compassio-manifest validate` | 9 entries; hashes and sizes match |
| `compassio-ml verify-frozen` | Frozen inputs match the lock |
| `bash scripts/check.sh` | All checks passed, including web lint, typecheck and build |
| Raw-file SHA-256 before vs after | All 9 identical; raw data unchanged |

## Not committed (git-ignored, local)

- `experiments/final_evaluation_v1/`: per-protocol models, record-level predictions, access records;
- `experiments/final_error_analysis_v1/`;
- `models/compassio_ccrc_v1/`;
- `data/`.

Committed copies contain **aggregate metrics only**; it was checked that no record IDs appear.

## Assumptions

- **Acceptance thresholds** (F1 ≥ 0.65, ENERGY recall ≥ 0.85, ECE ≤ 0.05, AP CI lower bound
  above the keyword AP) were set in the pre-registered plan from validation evidence, before
  test access.
- **"Internal MVP research screening"** means a local artifact for human-reviewed screening. It
  does not mean a public service.

## Blockers and caveats

- Source rights remain `not_reviewed`, so the model must not be distributed publicly.
- Proposal-time and cross-publisher performance is unmeasured.
- The v1 test partitions are consumed. A future model needs new independent test data.
