# Label mapping specification (v2.0)

Machine-readable version: `configs/label_mapping_v2.yaml`. Five label categories exist. They
are **not interchangeable**, and no code path converts one into another.

| Cat. | Origin | Assigning authority | Scale | Negatives? | Compatibility with target | Allowed use in v2 |
| --- | --- | --- | --- | --- | --- | --- |
| A | Qi et al. 2026 annotations on AidData text | Researchers (cross-checked with ClimateBERT) | 0/1/2 × 2 objectives | Yes | Defines the v1 target | Training; v1 validation → v2 validation; consumed v1 tests → **excluded** |
| B | IATI DAC policy markers 6/7 (FCDO, EC INTPA) | Reporting donor, self-assessed | 0/1/2 × 2 objectives | Explicit 0 only | Same scale and definitions, different annotator | Training/validation candidates with `label_origin`; human spot-check audit |
| C | GCF `Theme` | GCF | Mitigation / Adaptation / Cross-cutting | **No** | Not Rio; positive-only | **Not used** (GCF rights-restricted at the review gate); never a label |
| D | World Bank theme tags (Adaptation/Mitigation under Climate Change) | World Bank | Presence only, no % | **No** (absence ≠ 0) | Not Rio | Stratification metadata; adjudicator context; never a label |
| E | Human review (two reviewers + adjudication) | Compassio reviewers | 0/1/2 × 2 objectives | Yes | Same as A | External test (sealed); training-label audit |

## Evidence for each mapping (observed in this task)

- **B**: FCDO activity XML contains `<policy-marker vocabulary="1" code="6|7" significance="0|1|2">`,
  including explicit zeros. In the acquired files, explicit markers appear on programmes
  (hierarchy 1); components (hierarchy 2) carry none (see the FCDO inspection report).
- **C**: GCF ODL rows carry `Theme`; the population is climate-dedicated, so there is no
  negative class.
- **D**: World Bank API returns `themev2_level3_exact` values without percentages, and only a
  minority of projects carry the v2 theme taxonomy (see the World Bank inspection report).

## Rules

1. **Absent ≠ negative.** A missing donor marker, a missing World Bank theme or an
   unlabelled component is `unknown`.
2. **No inheritance.** Components do not inherit their parent programme's markers.
3. **GCF is restricted reference only.** Its records and themes enter neither training,
   automated evaluation nor human-review worksheets pending reviewed permission (`ai-train=no`).
4. **Proposals are not labels.** Donor values appear in master records as
   `proposed_rio_*` with `proposed_label_origin = B_donor_reported_rio`; they are hidden from
   reviewers and never copied into final labels.
5. **Mixing A and B in training** requires the experiment to record `label_origin`, report
   per-origin validation metrics, and test an A-only baseline (see `experiment_design.md`).

## Unresolved cases

See `unresolved` in `configs/label_mapping_v2.yaml`: strictness of donor "significant",
component labels, GCF cross-cutting objectives, World Bank tag significance, and OECD CRS
(not acquired).
