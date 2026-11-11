# C05 results: poisoned training batch quarantine

**Run** `c05_acbd465eef5a`, finished 2026-11-10T21:55:42Z, total 1,116 s (18 m 41 s wall clock).
- Command: `uv run python -m compassio_ml.challenges.c05.cli run`.
- Config `configs/c05_poison_quarantine.yaml`, SHA-256 `acbd465eef5a…`; ML v2 plan SHA-256
  `493170564893…`.
- Experiment code at commit `be4d67a`. The later commits change only the memory helper, the
  live-demo printout, tests and docs; with the final code the detector reproduces the stored
  decisions exactly (section 5).
- `manifest.sha256` = `5a9de741…c972c9`.
- Machine-readable copies: `docs/challenges/c05_experiment_summary.json` and
  `docs/challenges/c05_reproducibility_manifest.json`. The full run (12 files, including the
  private oracle) is git-ignored under `data/ml_v2/challenges/c05/c05_acbd465eef5a/`.

**Setup:**
- Incoming batch: 13,317 FCDO/EC records (4,194 climate-positive). Fingerprint `ad128fc3…` =
  the ML v2 plan's TRAIN pin.
- Attack: 666 labels inverted (5.001%), seed 20261112.
- Benchmark: the ML v2 development-validation partition (2,550 records, 827 positive). It is a
  challenge development benchmark, not a sealed test.

## 1. Detector: what it caught (oracle used only after the decision)

| | Uniform random flips | Targeted: climate-positive non-energy 1 → 0 |
| --- | ---: | ---: |
| Injected poison | 666 (464 were 0 → 1, 202 were 1 → 0) | 666 (all 1 → 0) |
| Quarantined | 605 | 458 |
| True positives (poison caught) | **245** | **56** |
| False positives (clean quarantined) | 360 | 402 |
| False negatives (poison missed) | 421 | 610 |
| **Detection precision** | **40.5%** | **12.2%** |
| **Detection recall** | **36.8%** | **8.4%** |
| **False-quarantine rate** (FP ÷ clean records) | **2.85%** | **3.18%** |
| Clean records retained | 12,291 of 12,651 | 12,249 of 12,651 |
| Clean climate-positive records quarantined | 290 of 3,992 (7.3%) | 370 of 3,528 (10.5%) |
| Clean adaptation-only positives quarantined | 83 of 1,052 (7.9%) | 106 of 922 (11.5%) |
| Insufficient evidence (kept, sent to review) | 1,137 (181 poisoned) | 1,155 (275 poisoned) |
| Poisoned records that still reached training | 421 | 610 |
| Recall by original label | 0 → 1 flips: 44.0%; 1 → 0 flips: 20.3% | 1 → 0 flips: 8.4% |

**No-attack floor:** on the unpoisoned batch the same detector quarantines **374 records
(2.81%)** and sends 934 to review. These are records whose donor Rio marker disagrees with
similar records: natural label noise or genuinely ambiguous projects. Under the uniform attack
360 clean records are quarantined, close to that floor. Most "false positives" are therefore
records the method would flag anyway, not damage caused by the attack.

**Threshold trade-off.** Instead of the two-signal rule, quarantine the top share of records by
suspicion score:

| Top share quarantined | Uniform precision | Uniform recall | Targeted precision | Targeted recall |
| ---: | ---: | ---: | ---: | ---: |
| 2% | 57.9% | 23.1% | 13.5% | 5.4% |
| 3% | 50.0% | 30.0% | 17.0% | 10.2% |
| 5% | 40.5% | 40.5% | 17.6% | 17.6% |
| 7.5% | 35.4% | 53.2% | 16.7% | 25.1% |
| 10% | 30.7% | 61.4% | 17.4% | 34.8% |

Against uniform flips, the suspicion score ranks poisoned labels about 8× above chance: 40.5%
precision at a 5% base rate. Against the targeted attack it is barely above chance (about 3.5×).

## 2. Model protection (same model family and settings, same benchmark)

| Training run | Records | PR-AUC (AP) | F1 | Precision | Recall | Non-energy recall | Adaptation-only recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Clean reference | 13,317 | 0.8387 | 0.7376 | 0.6902 | 0.7920 | 0.7658 | 0.7326 |
| **Uniform:** naive on poisoned | 13,317 | 0.8357 | 0.7365 | 0.6957 | 0.7823 | 0.7562 | 0.7054 |
| **Uniform:** protected after quarantine | 12,712 | 0.8357 | **0.7611** | **0.7795** | 0.7437 | 0.7178 | 0.6783 |
| Uniform: strict variant (also drops review) | 11,575 | 0.8247 | 0.7428 | 0.7419 | 0.7437 | 0.7192 | 0.6783 |
| **Targeted:** naive on poisoned | 13,317 | 0.8305 | 0.7424 | 0.7668 | 0.7195 | 0.6918 | 0.6473 |
| **Targeted:** protected after quarantine | 12,859 | 0.8302 | 0.7396 | 0.7706 | 0.7110 | 0.6822 | 0.6395 |

Adaptation-only support: 258 benchmark positives. Non-energy positives: 730.

## 3. What this shows, honestly

1. **The attack works mainly when targeted.** Uniform 5% flips barely move this linear text
   model (AP 0.8387 → 0.8357; recall 0.792 → 0.782). The targeted attack does real damage
   where Compassio is already weakest:
   - adaptation-only recall 0.733 → 0.647;
   - non-energy recall 0.766 → 0.692.
2. **Against uniform flips, quarantine helps partially.**
   - It removes 245 of 666 poisoned labels (37%) and wrongly removes 2.85% of clean records.
   - The protected model has the best F1 (0.7611 vs 0.7365 naive and 0.7376 clean) and the
     best precision (0.78), with the same AP.
   - The cost is recall: −0.04 overall, −0.04 non-energy, −0.03 adaptation-only. Excluding
     contested records makes the model more conservative.
   - The strict variant (also dropping review records) loses AP (0.8247), so the default
     "accept and review" policy is the better trade-off.
3. **Against the targeted attack, this detector does not protect the model.**
   - It catches 56 of 666 flips (8.4%), and the protected model is no better than the naive one.
   - The reason: the attacker flips exactly the non-energy climate projects whose text the model
     already finds ambiguous, so a consistency check sees nothing unusual. This is a real
     limitation, measured here rather than hidden.
4. **A flag is not proof.** With no attack the detector still quarantines 2.81% of records.
   Quarantined records keep their original labels and need human review.

## 4. Runtime and memory

| Stage | Seconds |
| --- | ---: |
| Load and verify the cohort (re-runs the ML v2 audit) | 98.2 |
| Detector on the clean batch (5 folds: TF-IDF + LR + kNN) | 48.5 |
| Detector on a poisoned batch (re-run with the final code) | 34.0 (uniform) / 31.6 (targeted) |
| Disposable training, per model (3 OOF folds + final char model) | 128–150 |
| Live demo (3,001-record subsample, detector + gate) | 7.2 |

**Peak memory:**
- Not captured in the run itself: the first Windows memory call returned no value (fixed
  afterwards, with a regression test).
- Measured separately with the final code: **1,718.8 MB** peak working set for a process that
  ran the detector twice on 13,317 records.
- Disposable training memory was not measured.

**Machine:** Intel Core i7-10750H, Windows 11, Python 3.12.15, scikit-learn 1.9.1.

## 5. Reproducibility checks

- `cli verify`: 12 files match `manifest.json`, and `manifest.json` matches `manifest.sha256`.
- Re-running the gate with the final code on the stored poisoned batches gave **identical
  quarantine sets (605 / 458) and byte-identical gate reports**.
- `tests/test_local_c05.py` re-derives TP, FP and FN from the stored oracle and gate reports.
  It also checks:
  - exactly 666 changed labels per attack;
  - accepted ∩ quarantined = ∅;
  - the clean batch equals the plan pin;
  - the benchmark is disjoint from the batch;
  - the database, ML v1 and ML v2 hashes are unchanged.

## 6. Hardening addendum (c05-1.1.0): independent provenance and safer handling

Run `addendum_80ef1619158b` (config `configs/c05_hardening_addendum.yaml`, code `43528b6`,
18 m 30 s; `manifest.sha256` `d0a39a76…`). Machine-readable copies:
`docs/challenges/c05_addendum_summary.json` (record-level examples removed) and
`c05_addendum_manifest.json`. The base run above is unchanged, and the addendum re-reads its
poisoned batches, so all policies are compared on identical inputs. Policy A in the addendum
reproduces the base run exactly (tested).

**1. Independent provenance evidence found.**
- **Signal:** the publisher's OECD DAC purpose codes (`sector_codes`). This is source metadata
  in the same IATI record, outside the Rio-marker label channel the attacker controls.
- **Code list:** 20 climate/environment-intrinsic codes (environment protection 410xx, renewable
  energy 2321x–2327x, energy efficiency, disaster risk reduction, forestry, water conservation),
  fixed a priori from the DAC definitions. 1,933 records (14.5%) carry one.
- **Not used:** the hash-verified raw Rio markers would catch everything, but they *are* the
  clean labels, so they are excluded by design. `other_dac_markers` lists marker codes without
  significance, so it was rejected as evidence.

**2. Safer handling evaluated** (policy B). Positives that the purpose code corroborates are
never quarantined. Positive non-energy records need strong evidence from both signals (at most
1 of 15 neighbours agrees, and P(other) ≥ threshold + 0.10). Otherwise they go to review.

**3. Results:** see `c05_scorecard.md` for every table, each labelled A (deployed), B (candidate)
or C (analysis only).
- Uniform attack, B vs A:
  - false-quarantine rate 1.38% vs 2.85%;
  - clean climate positives wrongly quarantined 52 vs 290 (adaptation-only 19 vs 83);
  - **poisoned records accepted into training 502 vs 421 (+81)**;
  - model PR-AUC 0.8387 (= clean) vs 0.8357, F1 0.7552 vs 0.7611, recall 0.7908 vs 0.7437.
- Targeted attack, B vs A:
  - detection recall 28.1% vs 8.4%, precision 54.0% vs 12.2%, reproduced on 3 fresh seeds
    (recall 0.28–0.29, precision 0.51–0.54);
  - model PR-AUC 0.8379 vs 0.8302 (naive 0.8305), F1 0.7493 vs 0.7396;
  - **adaptation-only recall 0.624, still below naive 0.647 and clean 0.733.** This is partial
    mitigation, not protection.
- No attack: B quarantines 195 records vs A 374, and its review queue is larger (1,291 vs 934).

Peak memory of the addendum process: 2,337.8 MB (measured).
