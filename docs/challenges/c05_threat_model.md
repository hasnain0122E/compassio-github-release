# C05 threat model: poisoned training labels

## The attack

An attacker corrupts the **labels** of an incoming training batch before Compassio's
climate-relevance classifier is trained or fine-tuned on it.

| Property | Value |
| --- | --- |
| What is changed | The binary label (climate-relevant 1 / not 0) of exactly 5% of records: `floor(n × 0.05 + 0.5)`, i.e. 666 of the 13,317-record batch |
| How | Inversion: 0 → 1 or 1 → 0 |
| Variant 1: uniform | 666 records chosen uniformly at random (both directions) |
| Variant 2: targeted | 666 climate-positive, non-energy records flipped 1 → 0: the attacker tries to teach the model that adaptation and other non-energy climate projects are "not climate" (the weakness the ML v2 card already reports) |
| Goal | Distort the decision boundary so the trained screener misses or invents climate relevance |

## What the attacker does NOT control

- Project titles and descriptions (no fabricated text).
- Record ids, publisher (`source_id`) and the group/family ids used for group-aware folds.
- Trusted code, the detector configuration (`configs/c05_poison_quarantine.yaml`) and its seeds.
- The model registry (`configs/inference_models.yaml`, `configs/trusted_model_releases.json`),
  evaluation records and source provenance.

## Defender assumptions

- The defender does **not** know which labels were flipped. The flip positions (the *oracle*)
  exist only in a private evaluation file and are used **after** the gate has decided, to
  measure the detector. `detector.py` and `gate.py` never import the attack module (tested).
- Donor labels are themselves imperfect: Rio markers are publisher-reported and not
  human-verified. Some clean records will legitimately look inconsistent. So a flag is
  evidence for review, never proof of corruption.
- A poisoning rate of 5% does not mean "quarantine exactly 5%"; the threshold is explicit and its
  trade-off is measured.

## What is protected

The canonical data, the ML v1 release, the ML v2 development candidate, the SQLite database and
the sealed/consumed evaluations are **never touched**. The experiment uses immutable copies
under the git-ignored `data/ml_v2/challenges/c05/` directory. Its disposable models are never
registered or served.

## Out of scope

- Text poisoning (backdoor phrases), feature-space or gradient attacks, and attacks on the
  detector's own configuration.
- Adaptive attackers who know the detector and choose flips that look consistent with
  neighbours (they would evade a consistency check; see the results' limitations).

## Independent evidence the defender may use (addendum c05-1.1.0)

The attacker controls the Rio-marker labels only. The publisher's DAC purpose codes travel in
the same record but are not attacker-controlled under this model, so policy B uses them as an
independent second signal. An attacker who could also rewrite purpose codes would defeat that
signal; this is out of scope here. The raw source's own Rio markers are deliberately **not**
used: they are the clean labels.
