# Automated donor-label quality support (Task 006-ML-AUTO)

This workflow permits exploratory development with **source-reported** labels without pretending
that a person reviewed them. It does not replace the reserved independent human evaluation.
No classifier is trained by these commands. No provider is contacted by this implementation.

## Local audit

```powershell
uv run compassio-v2-quality audit --build-id v2build_9911d9b6caca
uv run compassio-v2-quality assessment-demo
```

Outputs stay in git-ignored `data/ml_v2/automated_quality/quality_<hash>/`:

- `quality_report.json`: population, source/partition/sector counts, training-only vocabulary
  associations, rights evidence, input/source-code hashes and readiness conditions.
- `record_quality.jsonl`: immutable donor values, raw objective observations, label origin,
  eligibility, warnings and exact lexical evidence offsets for every development activity.
- `uncertainty_queue.jsonl`: all flagged records, sorted by a documented triage score and ID.
  This score is not a calibrated probability of a bad label. Related family records are
  flagged for weighting/grouping; they are not automatically declared duplicates.
- `verification_<commit>.json`: git state and hashes of the three deterministic outputs.
  Rerunning from a commit compares existing reports and refuses differences.

Input is exclusively the guarded development loader, checked against the saved build hashes
and membership. The audit checks family/partition isolation and consumed-v1-test exclusion.
It scans the **pinned** FCDO and EC raw XML through the safe XML reader, but inspects Rio
markers only for IDs in development. It never reads sealed candidates, pilot texts, human
worksheets, final labels, backend snapshots or a release model.

The audit includes the existing EC donor source as a separate comparison population, not as
a substitute for the requested FCDO evidence. Raw duplicate objective values are retained
instead of trusting the parser's last-value choice. Absent/partial markers remain unknown.
Invalid or contradictory raw values, inconsistent overall values, raw/parsed discrepancies,
and unusable text prevent inclusion in the suggested experiment set. The original dataset
and donor annotations are never edited. Family variation, identical-text label conflicts,
lexical warnings and retrospective phrases remain warnings, not automatic relabeling rules.

Fixed English regexes check climate/mitigation/adaptation references and retrospective wording.
Evidence has a field, exact start/end offsets and a quote. Negation, implicit objectives,
French/other-language text and objectives documented elsewhere can defeat these checks.
**Neither presence nor absence of a keyword establishes a Rio label.** Flag counts cover all
development records, including unusable and unlabelled ones; they are not label-error rates.
Vocabulary associations use training documents only (minimum document frequency 10,
smoothed publisher-rate ratio at least 4). They identify source/language shortcuts, not
causal evidence of leakage. No classifier or vocabulary is fitted on validation.

Experiments should obtain eligible original donor records through:

```python
from compassio_ml.external.partition import TRAIN, VALID
from compassio_ml.external.paths import V2Paths
from compassio_ml.quality_v2.audit import load_eligible_donor_records

paths = V2Paths.from_env()
train = load_eligible_donor_records(paths, "quality_<hash>", TRAIN)
validation = load_eligible_donor_records(paths, "quality_<hash>", VALID)
```

This reruns the audit for integrity, uses the original partition membership and donor values,
and returns `label_origin = B_donor_reported_rio`. It refuses any non-development partition.
It never consumes an AI-assessment result. Use group-aware folds, train-only fitting and
calibration, predeclared model selection, per-publisher/sector reporting and family-weighted
sensitivity analyses. Include an FCDO-only baseline before mixing EC; report language effects.
Do not inspect validation uncertainty items to select transformations or rewrite labels.

## Optional two-run AI assessment

The committed `configs/ai_assessment_permissions_v2.json` has no approved runs. Real assessment
preparation fails closed. No recognized provider credential variable was present during this
task. A request export is not authorization to transfer source text to an external service.

Two prompts are defined literally in `quality_v2/assessments.py`: a shared Rio rubric with
separate objective-first and intent-checking instructions. Both require abstention if either
objective is undecidable and exact evidence for every scored objective, including zero.
The interface requires separately identified provider/model/version/settings for A and B,
source-specific processing/transfer permission, source/provider terms evidence, attribution,
retention policy, a reviewer of usage rights, and confirmation covering personal/third-party
rights. These usage-rights records are not project-label reviews and do not clear all data.

A private JSON approval file must have `runs.A` and `runs.B`, each containing:

- `identity`: `provider`, `model_id`, `model_version`, `inference_settings`.
- `permission`: `permission_id`, `source_ids`, `allow_processing: true`, `provider_is_local`,
  `allow_external_transfer`, `provider_terms_url`, `source_terms_evidence`,
  `data_retention_policy`, `reviewed_by`, `reviewed_at`,
  `personal_and_third_party_rights_reviewed: true`, `attribution`, `fixture_only: false`.

Do not put API keys in the file. An external provider requires explicit transfer permission;
a fixture-only grant cannot authorize real records. Existing source training/evaluation
permissions are also rechecked. This task adds **no provider SDK or API transport**: a future
approved local runner or provider integration consumes the blinded files and returns envelopes.

```powershell
uv run compassio-v2-quality prepare-assessments --audit-id quality_<hash> --permissions <private-approval.json> --limit 100
uv run compassio-v2-quality import-assessments --pool-id assessment_<hash> --responses-a <A.json> --responses-b <B.json>
```

The pool is separate under `automated_assessments/`. It contains only structurally eligible
**training** activities, one per partition group, selected by a seeded hash. Validation and
the original human pilot cannot enter. `A/requests.jsonl` and `B/requests.jsonl` contain only
opaque item ID, title, description and input hash. Do not send the parent folder:
`internal_mapping_DO_NOT_SEND.json` contains donor values for the later comparison step.
Pass each runner only its own prompt and request file; use separate sessions without shared
response history, donor labels, source metadata, browsing, tools or the internal mapping.

Each response envelope contains `run_id`, the exact issued `identity`, `completed_at`,
`independence_attestation`, and `responses`. Each response row contains `item_id`, `input_hash`,
`status` (`scored`/`abstain`), `mitigation`, `adaptation`, `rationale`, and `evidence` entries
(`objective`, `field`, `start`, `end`, `quote`). Scores must be integers 0–2; abstentions must
leave both null. Missing/duplicate items, invented quotes, changed requests/manifests, wrong
model/run identity or insufficient objective references are rejected.

Distinct runs/prompts do not establish statistically independent errors. Offline identity and
independence statements are supplied attestations, not independently authenticated provider
telemetry. The importer retains exact raw envelopes/hashes, run identities, versions, settings,
prompt hashes and permissions. Comparisons report agreement/disagreement and abstention with
explicit denominators; donor comparisons occur only **after** inference. Outputs are always
`AI_unverified`, never category E/human labels, and never authoritative experiment targets.

`assessment-demo` is **ARTIFICIAL**: manually specified test responses, different fixture
run IDs, one scored response and one abstention. Its displayed agreement is not model evidence.
Unit tests also exercise disagreement and a complete two-run file exchange on artificial XML.

## Rights and claims

FCDO's registered OGL licence supports reuse subject to attribution and exclusions. The
[official OGL v3](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
excludes personal data and third-party rights the publisher cannot license. The
[National Archives guidance](https://cdn.nationalarchives.gov.uk/documents/information-management/ogl-user-guidance.pdf)
describes commercial and non-commercial reuse. This supports an internal-research operational
decision, not a blanket legal clearance or authorization to disclose every narrative.
The source registry and `rights_status: not_reviewed` remain unchanged. EC's separate terms
and third-party caveats still apply; World Bank remains sealed; all GCF restrictions persist.

Automated donor-quality diagnostics and agreement are not estimates of independent accuracy.
Human labels remain zero. Without an independently labeled test, report development results
only as agreement with source-reported labels; make no external-generalization, deployment,
funding-outcome, environmental-impact or model-improvement claim.
