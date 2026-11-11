# Task 006-ML2 completion report: fast-track ML v2 training

| Item | Value |
| --- | --- |
| Branch | `feature/ml-v2-training` (local); base `7e8422b30a53560c1cd56a7fdbf3569ddfff8ec2` |
| Commits | `3bf81cd` (plan + code, before any fit), `7d99628` (escalation addendum, before F was fitted), and the final docs/tests commit |
| Not done | No merge, push or deploy. v1 release, frozen splits, consumed tests, sealed pools and the backend database were untouched. |

## PRE-FLIGHT

| Check | Result |
| --- | --- |
| Starting state | Clean tree at `7e8422b` on `feature/ml-v2-training` |
| Python environment | Isolated `.venv` (`uv sync --locked`) |
| `compassio-manifest validate` | 9 entries match |
| `compassio-ml verify-frozen` | Matches |
| `compassio-v2 verify-baseline` | **11/11 PASS**: v1 manifest, frozen split, plan `c4760503…`, release `53b226f6…`, fingerprint `3023fe3d…`, 3 consumed-test ledgers |
| `compassio-v2 verify-retrievals` | All 5 retrievals OK |

Environment used: `COMPASSIO_DATA_ROOT=<repo>/data`, `COMPASSIO_V1_PROJECT_ROOT=<repo>`,
`COMPASSIO_V2_OUTPUT_ROOT=<repo>/data/ml_v2` and
`COMPASSIO_V2_EXTERNAL_INPUT_ROOT=D:/AI LEARNING/compassio-ml-v2/data/ml_v2/external_raw`, as in
the integration report.

## DATA AND RIGHTS

- **Loader:** `load_eligible_donor_records` re-ran the audit (`quality_7e70e77d22bba416`) and
  reproduced every stated count:

  | Population | Eligible | Positive | Negative |
  | --- | ---: | ---: | ---: |
  | Combined | 15,867 | 5,021 | 10,846 |
  | FCDO | 4,383 | 796 | |
  | EC | 11,484 | | |

  Combined non-energy positives 4,436; adaptation-only 1,366. TRAIN 13,317 / VALID 2,550.
- **Pins:** memberships are hashed and pinned in the plan, and the runner refuses any change.
- **Rights:** FCDO, EC and AidData are `ml_training: permitted_pending_review`, checked in code.
  GCF (restricted) and World Bank (evaluation-only) are refused, which is tested. Source
  `rights_status` remains `not_reviewed`.
- **Isolation:**
  - 0 consumed v1 test records (all **8,592** remain excluded from v2 pools);
  - 0 groups, families or identical texts spanning TRAIN/VALID;
  - 0 cross-publisher families.
- **Never read:** the sealed external pool, the human-review pilot, backend `raw_db`, and any GCF
  record. The v1 consumed tests were not rerun.
- **AidData:** used only as an ablation. The v2 TRAIN partition is 10,184 records, with research
  table SHA-256 `71fc5a10…`.

## MODEL CANDIDATES TRAINED

46 trials, 0 failed, in four populations (FCDO, EC, combined, combined + AidData) plus two
transfer directions:

| Candidate | Description |
| --- | --- |
| A | Word TF-IDF + LR |
| B | Char TF-IDF + LR |
| C | Word+char + LR, and word+char + linear SVM |
| D | Word + Platt-calibrated SVM (train-fold calibration) |
| E | Publisher-balanced and family-inverse sample weights on the best A/B/C model (C-SVM) |
| F | One frozen multilingual encoder (`intfloat/multilingual-e5-small`, MIT, revision `614241f6`, CPU) + LR, under a pre-registered addendum |

Every vectoriser, classifier, calibrator, hyperparameter choice and threshold was fitted on
TRAIN only. See `docs/research/model_v2/fast_benchmark_results.md`.

## ACTUAL METRICS (combined VALID, 2,550 records)

| Model | AP | F1 | Non-energy AP |
| --- | ---: | ---: | ---: |
| **Champion B** | **0.839** [0.806, 0.869] | 0.738 | 0.810 |
| Best AP (combined + AidData C-SVM) | 0.843 | 0.748 | |
| Best F1 (E publisher-balanced) | 0.842 | 0.751 | |
| F | 0.822 | | 0.791 |
| v1 | 0.681 | 0.441 | |
| Keyword | 0.570 | | |
| Majority | 0.324 | | |

**Lexical finalists are mutually indistinguishable:** champion − runner-up AP is −0.004
[−0.009, +0.002].

## NON-ENERGY IMPROVEMENT

| Measure | v1 | Champion |
| --- | ---: | ---: |
| Non-energy recall | 0.259 | **0.766** |
| Non-energy precision | 0.875 | 0.658 |

Non-energy AP improved by **+0.162 [+0.120, +0.206]** (paired, same records). The 0.75
precision target is **not** met. Higher-precision finalists reach 0.71–0.73 precision at
0.70–0.73 recall.

## ADAPTATION IMPROVEMENT

| Measure | v1 | Champion |
| --- | ---: | ---: |
| Adaptation-only recall (of 258) | 0.209 (54 found) | **0.733** [0.647, 0.812] (189 found) |
| Non-energy adaptation-only recall | 0.206 | 0.727 |

## PUBLISHER GENERALIZATION

- **In-domain AP:** FCDO 0.751; EC 0.854.
- **Effect of combined training:** it does not help FCDO (champion FCDO slice 0.741) and helps
  EC slightly (0.862).
- **Transfer:**
  - FCDO → EC AP 0.816, under-calls (recall 0.57);
  - EC → FCDO AP 0.707, over-calls (precision 0.46).

  This reflects about 2× different label prevalence and EC's partly French text.
- **Scope:** this is within-two-donor evidence, not unseen-publisher generalisation.

## V1 HEAD-TO-HEAD COMPARISON

The fixed v1 release (verified loader, threshold 0.474 unchanged) was scored on the identical
2,550 records:

| Population | AP difference (champion − v1) |
| --- | --- |
| All | +0.158 [+0.120, +0.198] |
| FCDO | +0.081 [+0.033, +0.131] |
| EC | +0.141 [+0.098, +0.187] |

Part of the gap is v1's AidData-tuned threshold and label policy. The old v1 test scores were
not used as a comparison.

## CHAMPION SELECTION

The pre-registered rule selected `combined/B_char_lr`:

1. guard: non-energy precision ≥ 0.60;
2. primary metric: non-energy AP;
3. five finalists tied within 0.005, and the adaptation-only recall tie-breaker chose B.

F failed its replacement rule (non-energy AP −0.019 [−0.040, +0.001]; 40× slower).

**Targets:**

| Target | Result |
| --- | --- |
| Non-energy recall ≥ 0.75 | Met as a point estimate |
| Adaptation-only recall ≥ 0.70 | Met as a point estimate |
| F1 ≥ 0.80 | Not met |
| AP ≥ 0.85 | Not met |
| Non-energy precision ≥ 0.75 | Not met |

**v1 remains the approved inference model.** B is a development candidate only.

## MODEL ARTIFACT AND REPRODUCIBILITY

| Item | Value |
| --- | --- |
| Location | `data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/` (git-ignored) |
| Artifact SHA-256 | `654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574` (1,650,643 bytes) |
| Fingerprint | `c76204127550fb299c11704de61bd07cce3eae6635193e608a42897c5f995ad2` |
| Threshold | 0.44474326842740053 |
| `compassio-v2-train reproduce` | Identical fingerprint and threshold; maximum score difference 0.0 |
| Guarded predictor | Works; blank input refused (exit 2) |
| Trusted registry | Not added |

## TEST RESULTS

| Command | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | Clean |
| `uv run mypy` | Strict, 190 files, 0 issues |
| `uv run pytest tests/ml/test_model_v2.py` | 21 passed (artificial fixtures) |
| `uv run pytest tests/test_local_ml_v2_fast.py` | 4 passed (real run integrity) |
| Full suite and gates (`bash scripts/check.sh`) | **646 passed, 2 skipped** (PostgreSQL execution pending; no worksheets issued for this build); web lint, typecheck and build passed |
| `compassio-v2 verify-baseline` / `verify-retrievals` after training | 11/11 PASS / 5 OK |
| Donor audit re-run | Reproduced all 3 pinned outputs byte-for-byte |
| `compassio-manifest validate`, `verify-frozen`, `compassio-db verify` | Pass |

## UNRESOLVED LIMITATIONS

1. **No independent evaluation:** there are no human-verified labels. Every number is agreement
   with publisher markers on development VALID, which was used once for selection (optimistic).
2. **Weak sectors:** transport (15 positives) and urban (12) cannot support claims.
3. **Label policy:** label-policy and language shift between publishers. Per-publisher
   calibration would be needed.
4. **Champion trade-offs:** the champion has lower precision and calibration than tied
   alternatives (ECE 0.080). Grid optima sit at grid edges.
5. **Descriptions:** they are undated and retrospective, so no proposal-time claim is possible.
6. **Embeddings extra:** the optional `embeddings` extra (torch, sentence-transformers) adds
   `uv.lock` entries only; existing resolutions are unchanged. It is not needed for the
   champion.

## READY FOR TASK 007?

**Yes, with v1 as the served model.** Task 007 can expose the trusted v1 release. The v2
champion is a reproducible development candidate. Promoting it would need a separate evaluation
on independent, human-reviewed data from the sealed pool, under its own protocol.
