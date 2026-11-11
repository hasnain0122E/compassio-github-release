# External validation protocol (design only; no data collected)

**Purpose:** measure how the frozen classifier generalises to independent, mostly contemporaneous
project text. The focus is non-energy adaptation, which Task 004 validation showed to be weak
(non-ENERGY recall 0.392).

This is a **plan**. No external examples exist yet, and the target sizes below are not claims
that such examples are available.

## 1. Independence rules

1. **Separate from every frozen partition.** External examples are never added to the research
   table, any split, the primary, chronological or Pakistan tests, or any training data.
2. **No training on it.** It is an evaluation set. A future decision to train on external data
   needs a new benchmark version and a new, separate evaluation set.
3. **No duplicates of training projects.** Check each candidate against the research table by:
   - exact source identifier where shared;
   - normalized title and description (`compassio_ml.data.parsing.normalize_text`);
   - manual review of near matches.

   Any project financed by Chinese official finance in 2000–2021 needs extra scrutiny against
   AidData. Excluded candidates are logged with the reason.
4. **Frozen model and threshold:** evaluate the Task 005-selected artifact at its locked
   threshold, once.

## 2. Target composition (planning target: about 150–300 inspectable examples)

| Stratum | Target share | Candidate sources | Label route |
| --- | ---: | --- | --- |
| Adaptation: water supply and sanitation resilience | 12% | GCF proposals, World Bank PDOs | Human Rio labelling |
| Adaptation: agriculture and food systems | 12% | GCF, World Bank, OECD CRS | Human; or CRS marker plus human check |
| Adaptation: flood, drought and disaster resilience | 12% | GCF, World Bank | Human |
| Climate-resilient infrastructure and transport | 10% | World Bank, OECD CRS | Human |
| Non-energy mitigation (transport, forestry, waste, industry efficiency) | 10% | GCF, OECD CRS | Human |
| Renewable-energy mitigation (comparison stratum) | 10% | GCF, OECD CRS | Human |
| **Negative controls**: health, education, governance, conventional roads, fossil energy | **34%** | World Bank, OECD CRS (marker 0 reviewed by a human) | Human, confirming *not targeted* |

**Pakistan:** at least 30% of every stratum where candidates exist. It is reported separately.

**Why stratified:** a convenience sample of GCF proposals would be 100% positive. Precision,
false-positive rate and calibration could not be measured, and adaptation would be
over-represented in an uncontrolled way.

## 3. Labelling

- **Scheme:** the research definitions exactly (Qi et al. 2026). Each of `rio_mitigation` and
  `rio_adaptation` is scored 0/1/2; `rio_overall` is the maximum, recorded as such; and
  `is_climate_related = rio_overall > 0`.
- **Two independent reviewers per example,** plus adjudication by a third on disagreement. Record
  agreement statistics. The research data lacks these; Task 003 finding.
- **Required fields per example:**
  - `external_id`, `source_id`, `source_record_id`, `source_url`, `retrieved_at`, `text_date`
    and `text_type` (proposal / PDO / CRS description);
  - `title`, `description` (verbatim, with SHA-256), `country_iso3`, `sector`;
  - per reviewer: the label, `confidence` (low / medium / high) and a short rationale;
  - the final label, `adjudicated_by`, `duplicate_check_result` and `licence_note`.
- **Source labels are context, not truth.** GCF Theme, CRS markers and World Bank themes are
  shown to the adjudicator only after the independent labels are recorded. Incompatible or
  ambiguous cases go to `needs_review` and are excluded from headline metrics.

## 4. Metrics and reporting

- Report per stratum and overall: recall, precision, F1, average precision and the confusion
  matrix, at the locked threshold.
- **Intervals:** bootstrap over examples (or over projects, where several texts describe one
  project).
- With 20–60 examples per stratum, intervals will be wide. Report counts and do not rank
  strata.
- Compare against the same model's validation figures. Agreement between external labels and
  the research labels is **not** expected to be perfect, because the annotators differ.

## 5. Practical acquisition steps

1. Approve the sources and licences (`source_rights_matrix.md`). Register each downloaded file
   through the existing manifest workflow (`data/raw/<source_id>/`).
2. Pull bounded candidate pools:
   - World Bank Projects API, Pakistan plus comparison countries;
   - GCF project pages for selected FP/SAP codes;
   - an OECD CRS microdata slice.
3. Sample stratified candidates with a fixed seed, run the duplicate check, then label.
4. Freeze `external_eval_v1` with its own lock file before any model is scored on it.

**Effort estimate:** about 200 examples × 2 reviewers at 3–5 minutes each, plus adjudication,
comes to roughly 25–35 reviewer-hours.
