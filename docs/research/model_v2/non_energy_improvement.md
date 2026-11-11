# Non-energy and adaptation improvement: fixed v1 vs ML v2 champion (identical records)

Both models scored **the same 2,550 eligible v2 development-validation records** (827 positive;
730 non-energy positive; 258 adaptation-only), all FCDO and EC IATI activities.

- **v1:** the trusted release `compassio-ccrc-1.0.0-mvp-research-screening`, loaded with
  `ReleasedClassifier.load`. The artifact SHA-256 `53b226f6…` and fingerprint `3023fe3d…` were
  verified, and its threshold of 0.474 was not changed. It was called per record with the
  original `title_clean` and `description_clean`.
- **v2 champion:** `combined/B_char_lr`, trained on the TRAIN partition only.
- **Pairing:** differences are paired, with a group bootstrap over partition groups (2,000
  resamples, 95%).

**The v1 Task 005 test results (AP 0.751, non-energy recall 0.368, on AidData text) are not
comparable and are not used here.**

## 1. Head-to-head

| Measure | v1 (fixed) | v2 champion | Paired difference (95% CI) |
| --- | ---: | ---: | --- |
| AP, all | 0.681 [0.631, 0.730] | **0.839** [0.806, 0.869] | **+0.158 [+0.120, +0.198]** |
| AP, non-energy | 0.649 [0.594, 0.703] | **0.810** [0.772, 0.846] | **+0.162 [+0.120, +0.206]** |
| AP, FCDO slice | 0.660 | 0.741 | +0.081 [+0.033, +0.131] |
| AP, EC slice | 0.721 | 0.862 | +0.141 [+0.098, +0.187] |
| F1 | 0.441 | 0.738 | |
| Precision / recall | 0.887 / 0.294 | 0.690 / 0.792 | |
| Non-energy precision / recall | 0.875 / **0.259** | 0.658 / **0.766** | |
| Adaptation-only recall (258 positives) | **0.209** (54 found) | **0.733** (189 found) | |
| Adaptation-only non-energy recall (253) | 0.206 | 0.727 | |
| Mitigation-only recall (146) | 0.390 | 0.877 | |
| Energy recall (97) | 0.557 | 0.990 | |
| Confusion (TP / FP / FN / TN) | 243 / 31 / 584 / 1,692 | 655 / 294 / 172 / 1,429 | |
| ECE (10 bins) | 0.171 | 0.080 | |

**The v2 champion's AP improvement over v1 is significant on these records.** v1 is
conservative on this population: it is precise but misses about 70% of positives. Its threshold
was set for AidData's 6–8% prevalence and label policy, so part of the gap is a population and
label-policy shift. That makes this a fair answer to "which model screens FCDO and EC
descriptions better". It does **not** show that v1 is a worse model on its own population.

## 2. Sector slices (champion; slices with < 15 positives or < 30 records are suppressed)

| Sector family | Records | Positives | v2 P / R / AP | v1 R / AP |
| --- | ---: | ---: | --- | --- |
| Agriculture, forestry, fishing | 179 | 146 | 0.863 / 0.904 / 0.947 | 0.336 / 0.909 |
| Environment, ecosystems | 126 | 110 | 0.898 / 0.882 / 0.947 | 0.418 / 0.932 |
| Water, sanitation, waste | 94 | 52 | 0.613 / 0.885 / 0.801 | 0.327 / 0.730 |
| Disaster risk & emergency | 117 | 32 | 0.758 / 0.781 / 0.840 | 0.406 / 0.739 |
| Transport | 59 | 15 | 0.306 / 0.733 / 0.588 | 0.067 / 0.403 |
| Urban development | 21 | 12 | **suppressed** | **suppressed** |
| Energy | 113 | 97 | 0.960 / 0.990 / 0.991 | 0.557 / 0.945 |

**Transport has exactly the minimum 15 positives and urban is suppressed.** Neither supports a
performance claim. Transport precision is poor (0.31), so the model over-calls transport
projects.

## 3. Against the aspirational development targets (combined VALID; not used for selection)

| Target | Required | Champion | Met? |
| --- | ---: | ---: | --- |
| Overall F1 | ≥ 0.80 | 0.738 [0.701, 0.774] | **No** |
| AP | ≥ 0.85 | 0.839 [0.806, 0.869] | **No** (CI includes 0.85) |
| Non-energy recall | ≥ 0.75 | 0.766 [0.716, 0.814] | Yes (point estimate; CI includes 0.75) |
| Non-energy precision | ≥ 0.75 | 0.658 [0.607, 0.709] | **No** |
| Adaptation-only recall | ≥ 0.70 | 0.733 [0.647, 0.812] | Yes (point estimate; CI includes 0.70) |

**No finalist meets every target.** The finalists with higher non-energy precision (0.71–0.73:
word LR, word+char, publisher-balanced) have lower non-energy recall (0.70–0.73). This is a
threshold trade-off on an AP plateau of about 0.80–0.81 non-energy AP.

## 4. Why the ceiling is about 0.84 AP

These are evidence, not proof:

1. **Label noise and policy differences:**
   - the donor audit flags 207 identical-description label conflicts and 6,940 records with
     within-family label variation;
   - EC and FCDO label prevalence differs about 2×.
2. **Representation plateau:** all eight lexical finalists fall within 0.014 AP. The frozen
   multilingual encoder (F) was **not** better: non-energy AP −0.019 [−0.040, +0.001].
3. **Undated, retrospective publisher descriptions:** these are not proposal-time texts.
