# V2 evaluation protocol — PROPOSAL (not frozen)

Status: **proposal for review.** The actual acceptance criteria must be frozen in
`configs/final_evaluation_v2.yaml` with a committed SHA-256 **before** any external-test label
is read (`external_test_access_policy.md`).

## 1. Aspirational targets (not established outcomes)

| Metric (external test, locked threshold) | Target |
| --- | --- |
| F1 (binary `rio_overall > 0`) | ≥ 0.80 |
| Average precision | ≥ 0.85 |
| Non-energy recall | ≥ 0.75 |
| Non-energy precision | ≥ 0.75 |
| Adaptation-only recall | ≥ 0.70 |
| Energy recall | no material regression vs. v1 on the same test: drop ≤ 0.05 and the paired interval excludes a drop > 0.10 |

For reference, the v1 primary final test measured F1 0.670, non-energy recall 0.368 and
adaptation-only recall 0.310 (`docs/research/task005_final_model_evaluation.md`). Those numbers
came from a different population (AidData) and are **not** directly comparable with an
external-test result.

## 2. Mandatory conditions

1. External evaluation on publishers unseen in training/validation (currently World Bank).
   GCF is rights-restricted (`ai-train=no`) and excluded from evaluation and worksheets.
2. Proposal-time validation reported separately where contemporaneous text exists (World
   Bank Pipeline projects; GCF proposals remain excluded pending reviewed permission). If fewer than 30 such labelled
   items exist, report counts only.
3. Per-sector confusion matrices with Wilson or bootstrap intervals; suppress slices with
   < 30 items or < 5 positives.
4. Independent labels: two reviewers, adjudication, and reported Cohen's kappa per objective.
   If binary kappa < 0.60, the labelling guideline is revised and the pilot relabelled before
   any model is scored.
5. No cross-project or cross-document leakage (partition groups, suspected matches reviewed).
6. V1 vs. v2 comparison on the external test exactly once, after v2 model selection.

## 3. Sample size (computed, `compassio_ml.external.partition.SAMPLE_SIZE_POLICY`)

Minimum verified items for a 95 % Wilson half-width target, at an assumed rate:

| Subgroup | Metric | Assumed rate | Half-width | Minimum n |
| --- | --- | ---: | ---: | ---: |
| Non-energy positives | recall | 0.75 | 0.10 | 70 |
| Adaptation-only positives | recall | 0.70 | 0.10 | 78 |
| Energy positives | recall | 0.85 | 0.10 | 49 |
| Predicted positives | precision | 0.80 | 0.07 | 124 |
| Negatives | false-positive rate | 0.10 | 0.05 | 141 |
| Pakistan positives | recall | 0.75 | 0.15 | 30 |

Half-width at smaller n (rate 0.75): n = 20 → ±0.178; 30 → ±0.149; 50 → ±0.117; 80 → ±0.093.

**Implication:** the 300-item pilot cannot meet all minima at once (it needs roughly
≥ 200 positives across the strata **and** ≥ 141 negatives, plus 10–15 % expected
unresolvable items). The pilot is for measuring agreement, prevalence per stratum and label
feasibility. Strong generalization claims require expanding the external test to about
**450–550** reviewed items, sized from the pilot's observed prevalences.
