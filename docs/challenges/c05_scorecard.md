# C05 scorecard

**Data and setup.** Real FCDO/EC batch of 13,317 records, with 666 labels inverted (5.001%,
final seed 20261112). Benchmark: the ML v2 development-validation partition (2,550 records). It
is a development benchmark, not a sealed test.

**Runs.**
- Base run `c05_acbd465eef5a`.
- Hardening addendum `addendum_80ef1619158b` (config `configs/c05_hardening_addendum.yaml`,
  code `43528b6`, `manifest.sha256` `d0a39a76…`).
- Both re-verify by hash: `cli verify`.

**Oracle use.** The answer key is used only **after** each decision, to score it.

## The three policies, never mixed

| Label | Policy | Status |
| --- | --- | --- |
| **A** | Two-signal: quarantine when the text model **and** the 15 nearest neighbours both contradict the label | **Deployed** (detector `compassio-c05-detector-1.0.0`) |
| **B** | Hardened. Adds a second route, text model **and** independent provenance (the publisher's DAC purpose code is climate/environment-intrinsic but the label is 0). Protects positives the code corroborates, and positive non-energy records without strong evidence (sent to review) | **Candidate** (c05-1.1.0), designed on development seed 101 only |
| **C** | Quarantine the top 5% by suspicion score | **Analysis only**, not deployed |

## Detection (final seed)

| Attack | Policy | Precision | Recall | False-quarantine rate | Clean positives wrongly quarantined | Poisoned accepted into training |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Uniform | **A deployed** | 40.5% | 36.8% | 2.85% | 290 | 421 |
| Uniform | B candidate | 48.4% | 24.6% | 1.38% | 52 | 502 |
| Uniform | C analysis | 40.5% | 40.5% | 3.13% | 312 | 396 |
| Targeted | **A deployed** | 12.2% | 8.4% | 3.18% | 370 | 610 |
| Targeted | B candidate | 54.0% | 28.1% | 1.26% | 79 | 479 |
| Targeted | C analysis | 17.6% | 17.6% | 4.34% | 488 | 549 |

"Poisoned accepted into training" counts every poisoned record that was not quarantined,
including records sent to review: under the accept-and-review policy those still train the model.

**Where the 666 poisoned labels went:**

| Attack | Policy | Quarantined | Review (kept for training) | Accepted silently |
| --- | --- | ---: | ---: | ---: |
| Uniform | A | 245 | 181 | 240 |
| Uniform | B | 164 | 278 | 224 |
| Targeted | A | 56 | 275 | 335 |
| Targeted | B | 187 | 200 | 279 |

**Batch outcome:**

| Attack | Policy | Accepted | Review | Quarantined |
| --- | --- | ---: | ---: | ---: |
| Uniform | A | 11,575 | 1,137 | 605 |
| Uniform | B | 11,400 | 1,578 | 339 |
| Targeted | A | 11,704 | 1,155 | 458 |
| Targeted | B | 11,460 | 1,511 | 346 |

**No attack at all** (false-alarm floor), quarantined / review:

| Policy | Quarantined | Review | Clean positives quarantined | Clean adaptation-only positives quarantined |
| --- | ---: | ---: | ---: | ---: |
| A | 374 | 934 | 293 | 90 |
| B | 195 | 1,291 | 73 | 27 |
| C | 666 | 0 | 523 | 152 |

**Robustness: three fresh seeds** (20261113–15, never used before; detection only),
precision / recall:

| Attack | A deployed | B candidate | C analysis |
| --- | --- | --- | --- |
| Uniform | 0.43–0.44 / 0.36–0.38 | 0.43–0.49 / 0.22–0.27 | 0.43 / 0.43 |
| Targeted | 0.10–0.17 / 0.07–0.11 | 0.51–0.54 / 0.28–0.29 | 0.16–0.20 / 0.16–0.20 |

## Model trade-offs (disposable model trained on the accepted records)

Same model family (char TF-IDF + logistic regression) and the same settings in every row; the
threshold is chosen on the labels each model is trained with.

| Attack | Training data | Records | PR-AUC | F1 | Precision | Recall | Non-energy recall | Adaptation-only recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none | Clean reference | 13,317 | 0.8387 | 0.7376 | 0.6902 | 0.7920 | 0.7658 | 0.7326 |
| Uniform | Naive (poisoned) | 13,317 | 0.8357 | 0.7365 | 0.6957 | 0.7823 | 0.7562 | 0.7054 |
| Uniform | **After A (deployed)** | 12,712 | 0.8357 | **0.7611** | 0.7795 | 0.7437 | 0.7178 | 0.6783 |
| Uniform | After B (candidate) | 12,978 | **0.8387** | 0.7552 | 0.7227 | **0.7908** | **0.7671** | **0.7248** |
| Uniform | After C (analysis) | 12,651 | 0.8365 | 0.7577 | 0.7325 | 0.7848 | 0.7603 | 0.7171 |
| Targeted | Naive (poisoned) | 13,317 | 0.8305 | 0.7424 | 0.7668 | 0.7195 | 0.6918 | **0.6473** |
| Targeted | **After A (deployed)** | 12,859 | 0.8302 | 0.7396 | 0.7706 | 0.7110 | 0.6822 | 0.6395 |
| Targeted | After B (candidate) | 12,971 | **0.8379** | **0.7493** | **0.8192** | 0.6904 | 0.6603 | 0.6240 |
| Targeted | After C (analysis) | 12,651 | 0.8292 | 0.7445 | 0.7827 | 0.7098 | 0.6808 | 0.6473 |

## The targeted-attack limitation (stated plainly)

- **Policy A (deployed) does not protect against the targeted attack.** It catches 8.4% of the
  flips, and the model after A is no better than the naive one.
- **Policy B mitigates it partially**, reproducibly across 4 seeds:
  - detection recall 28% at 54% precision;
  - the model's ranking quality is almost back to clean (PR-AUC 0.8379 vs 0.8387);
  - F1 is better than naive.
- **B does not restore what the attacker targeted.** Recall stays below naive (0.690 vs 0.720),
  and so does adaptation-only recall (0.624 vs 0.647). Most poisoned positives (479 of 666) still
  reach training, and the model's threshold is still tuned on poisoned labels.
- **Compassio therefore does not claim protection against targeted label poisoning.** It claims:
  - a measurable detection signal (3.3× A's recall);
  - fewer wrongful quarantines of genuine climate projects (B: 79 vs A: 370 clean positives).

## Recommendation

- Keep **A as the deployed default** for the demo: it is the configuration evaluated end to end.
- Present **B as the hardened candidate**:
  - it halves wrongful quarantines and is the only policy that detects the targeted attack;
  - its costs are +81 poisoned labels accepted under the uniform attack and a larger review
    queue (about 1,500 records).
- Never present C's numbers as the deployed policy.
