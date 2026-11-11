# Task 005: Post-hoc error analysis of the final test errors

**Done after all three test metrics were frozen and the access records completed.**

```
uv run compassio-ml final-error-analysis --protocol <p>
```

The command refuses unless the protocol's access record is `completed`. Outputs go to
`experiments/final_error_analysis_v1/<p>/` (git-ignored, record-level). **None of these findings
changed the model, threshold, data or splits.** Tags are descriptive evidence categories, not
causes.

## 1. Primary test (FN 75, FP 50)

| False negatives | Count | Share |
| --- | --: | --: |
| Non-ENERGY | **60** | 80% |
| "Significant" (score 1) label | 54 | 72% |
| No pre-registered climate keyword | 47 | 63% |
| Adaptation-only label | 40 | 53% |
| Mitigation-only label | 27 | 36% |
| ENERGY | 15 | 20% |
| Description shorter than 300 characters | 3 | 4% |

| False positives | Count | Share |
| --- | --: | --: |
| Retrospective wording | 43 | **86%** |
| ENERGY | 25 | 50% |
| Non-ENERGY | 25 | 50% (water 9, transport 6, agriculture 2, …) |

**Recall of positives by sector (test):**

| Sector | Caught | Recall |
| --- | --- | --: |
| ENERGY | 92 of 107 | 0.86 |
| Water supply and sanitation | 18 of 26 | 0.69 |
| General environmental protection | 5 of 9 | 0.56 |
| **Transport** | 4 of 14 | 0.29 |
| **Agriculture** | 2 of 11 | 0.18 |
| Other multisector | 1 of 8 | 0.13 |
| Government and civil society | 0 of 6 | 0.00 |
| Emergency response | 0 of 5 | 0.00 |
| Industry | 0 of 5 | 0.00 |

## 2. Chronological test (FN 123, FP 49)

- **Misses:** 104 of 123 are non-ENERGY. 72 contain no climate keyword; 53 are adaptation-only.
- **Recall by sector:**
  - transport **0 of 18**;
  - agriculture 3 of 19;
  - emergency response 0 of 8;
  - disaster prevention 1 of 6;
  - industry 6 of 16;
  - water 23 of 37.
- **ENERGY errors:** 19 missed and 21 false positives.
- **False positives:** 82% carry retrospective wording.

## 3. Pakistan holdout (FN 15, FP 4)

- **Misses:** 14 of 15 contain no climate keyword, and 10 are non-ENERGY (transport 4 of 4
  missed, agriculture 2 of 2). 5 are ENERGY.
- **False positives:** all 4 carry retrospective wording (water 2, energy 1, education 1).

## 4. Cross-cutting findings

1. **Non-energy and adaptation misses dominate every protocol.** Transport, agriculture,
   emergency response and governance projects that the authors scored as climate-relevant are
   rarely detected.
2. **Missing climate terminology:** 59–93% of misses contain none of the pre-registered keywords.
   The model has little to go on when the climate purpose is implicit (e.g. "irrigation
   rehabilitation", "urban transit").
3. **Retrospective-text effect:**
   - false positives are 82–100% retrospective across protocols, against about 47% of
     negatives on validation;
   - recall without retrospective wording is much lower (primary 0.49, chronological 0.36).

   Long after-the-fact narratives push scores up in both directions.
4. **Generic or short descriptions are not a major cause:** only 0–4 misses per protocol are
   under 300 characters.
5. **Possibly inconsistent author annotations:** 21 of 75 primary misses and 12 of 50 primary
   false positives belong to leakage groups whose related records carry *different* labels.
   This is consistent with the Task 004.5 finding that financing components of one project were
   sometimes labelled differently. It is not proof that any individual label is wrong.
6. **"Significant" labels are hard:** primary recall is 0.44 for score 1 against 0.80 for
   score 2. Many score-1 projects have only secondary climate co-benefits.

## 5. Proposals for v2, which need a new dataset version and a NEW independent evaluation

- Collect and label more non-energy positives (transport, agriculture, water and resilience) and
  contemporaneous proposal texts (GCF proposals, World Bank PDOs), following
  `external_validation_protocol.md`.
- Resolve the conflicting and inconsistent labels with human review, using a documented gas/LNG
  and financing-component policy (`docs/data/conflicting_label_review.md`).
- Consider representations that capture purpose rather than technology words, and
  sector-specific reliability reporting. Evaluate them only on new held-out data.

**The v1 tests are consumed and must not be reused to select v2.**
