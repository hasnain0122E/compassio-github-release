# C05: Compassio Data Integrity Shield

## The problem (organizer requirement)

> "A 5% sample of the incoming training batch or reference dataset has been corrupted with
> inverted labels to distort decision boundaries. Deploy an automated statistical or
> distance-based anomaly detector that identifies and quarantines the poisoned instances prior
> to model ingestion or fine-tuning."

Compassio screens project descriptions for climate relevance. Its classifier learns from
donor-labelled records (FCDO and EC IATI activities with Rio markers). If someone inverts the
labels of 5% of a new training batch, a retrained model could learn to miss climate projects,
especially adaptation projects, or to invent climate relevance.

## The solution

A **quarantine gate** that every training batch must pass before any model is fitted:

1. **Look at each label with fresh eyes.** The batch is split into 5 group-aware folds, so
   related records never sit on both sides. For each record, a text model trained only on the
   *other* folds predicts its label.
2. **Ask two independent questions.**
   - Does the text model confidently disagree with the supplied label, by the confident-learning
     per-class threshold, computed per publisher?
   - Do the record's 15 most similar records mostly carry the opposite label?
3. **Decide transparently.**
   - Both say "inconsistent" → **quarantined** (excluded from training, label kept for
     investigation).
   - Only one says so → **insufficient evidence** (kept, listed for human review).
   - Neither → **accepted**.
4. **Enforce it.** Training code accepts only the gate's `AcceptedBatch`; passing a raw batch
   raises `GateBypassError`. Labels are never auto-corrected.

Every decision comes with a suspicion score, the numbers behind it and a plain-language reason.
The report says what a flag means: *inconsistent with similar records, not proof of
corruption*.

## Does it work? (measured on real Compassio data: `c05_scorecard.md`)

Three policies, always reported separately:
- **A (deployed):** the two-signal rule above.
- **B (hardened candidate):** adds an independent provenance signal (the donor's DAC purpose
  code) and protects ambiguous positive records.
- **C (analysis only):** the top 5% by suspicion.

| | A deployed | B candidate |
| --- | --- | --- |
| Uniform: poison caught | 36.8% (precision 40.5%) | 24.6% (precision 48.4%) |
| Uniform: clean records wrongly quarantined | 2.85% | 1.38% |
| Uniform: poisoned accepted into training | 421 | 502 |
| Uniform: model F1 (naive 0.7365) | 0.7611 | 0.7552 |
| Targeted: poison caught | 8.4% (precision 12.2%) | 28.1% (precision 54.0%) |
| Targeted: model adaptation-only recall (naive 0.647) | 0.640 | 0.624 |

**Bottom line:**
- The shield finds randomly flipped labels about 8× better than chance and improves the trained
  model's F1.
- Independent provenance makes the targeted attack *detectable* (3.3× A's recall, on 4 seeds)
  and protects genuine climate projects from wrongful quarantine.
- **It does not stop targeted poisoning:** adaptation recall stays below the poisoned baseline,
  and we say so.

## What stays protected

- No canonical file, label, model, registry, database or sealed evaluation is touched.
- All C05 data are immutable experiment copies in the git-ignored
  `data/ml_v2/challenges/c05/`.
- The deployed ML v1 and ML v2 models are unchanged and are not retrained.

## Files

- **Code:** `packages/compassio_ml/src/compassio_ml/challenges/c05/`: `attack`, `detector`,
  `gate`, `policy`, `train`, `experiment`, `addendum`, `report`, `cli`.
- **Configs:** `configs/c05_poison_quarantine.yaml` and `configs/c05_hardening_addendum.yaml`.
- **Tests:** `tests/ml/test_c05_quarantine.py` (fast, artificial data) and
  `tests/test_local_c05.py` (the real run).
- **Docs:**
  - `c05_threat_model.md`
  - `c05_experiment_protocol.md`
  - `c05_results.md`
  - `c05_scorecard.md`
  - `c05_judge_demo.md`
  - `c05_experiment_summary.json`
  - `c05_reproducibility_manifest.json`
