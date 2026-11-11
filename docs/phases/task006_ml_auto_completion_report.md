# Task 006-ML-AUTO completion report

Branch `feature/ml-v2`, starting commit `77cfdbe21ad44c2c6dec919e1f498e37d4a0544e`.
No classifier was trained, no source label was edited, no sealed example was sent to AI,
and no branch was merged, pushed or deployed. This task explicitly permits exploratory
development without manual project-label reviews; the independent-evaluation rules remain.

## DONOR-LABEL EVIDENCE

Observed by `uv run compassio-v2-quality audit --build-id v2build_9911d9b6caca`:
**34,463 development IATI activities** scanned, including unusable/unlabelled records.
The nine FCDO activities linked to the external publisher pool are excluded before marker
inspection. No sealed candidate/pilot file is read by this audit.

FCDO is the primary requested source. Existing EC INTPA data is audited and reported
separately as a comparison population under its own rights. No new source was downloaded.
Donor Rio markers are source annotations, not human-verified Compassio labels.

| Source / partition | Eligible | Positive | Negative | Non-energy positive | Adaptation-only |
| --- | ---: | ---: | ---: | ---: | ---: |
| FCDO training | 3,511 | 649 | 2,862 | 600 | 226 |
| FCDO validation | 872 | 147 | 725 | 137 | 58 |
| EC training | 9,806 | 3,545 | 6,261 | 3,106 | 882 |
| EC validation | 1,678 | 680 | 998 | 593 | 200 |
| **Total** | **15,867** | **5,021** | **10,846** | **4,436** | **1,366** |

FCDO alone: **4,383 eligible**, **796 positive**, **3,587 negative**, **737 non-energy
positive**, **284 adaptation-only**. Of the original 4,441 usable FCDO labelled activities,
58 have contradictory raw marker values and are excluded from the suggested experiment set.
This preserves their original labels and raw evidence instead of choosing a last value.
EC contributes 11,484 eligible donor-labelled activities, with its distinct annotator,
language and project-family distribution retained.

The combined eligible population spans **6,635 project families / 6,411 partition groups**;
row count must not be confused with independent sample count. There are **13,317 training**
and **2,550 validation** activities after structural exclusions.

## AUTOMATED QUALITY CHECKS

Implementation: `compassio_ml.quality_v2` plus the `compassio-v2-quality` CLI. It uses only
the guarded development loader, validates candidate/membership hashes and joins, rechecks
rights/isolation, and scans pinned source XML through the safe XML reader. Existing parsers,
datasets, membership, labels, v1 assets and human worksheets are unchanged.

Counts below cover **all 34,463 development activities**, not just eligible records. Flags
overlap and must not be summed as unique errors or divided by the eligible count as an error rate.

| Check | Flagged activities | Meaning |
| --- | ---: | --- |
| Invalid raw Rio values | 0 | No observed value outside 0/1/2 in this development population |
| Contradictory raw mitigation markers | 33 | Multiple distinct values for one objective |
| Contradictory raw adaptation markers | 51 | Multiple distinct values; overlaps mitigation flags |
| Missing/partial objectives | 17,110 | Unknown labels; never counted as negative |
| Multiple records in a family | 33,775 | Related observations; grouping/weighting warning, not a duplicate identity assertion |
| Within-family label variation | 6,940 | Could reflect different components; no automatic relabeling |
| Identical-description label conflict | 207 | Stronger uncertainty signal; source labels retained |
| Positive without any lexical climate evidence | 3,622 | Limited English lexicon; not proof of a wrong positive |
| Positive mitigation without objective-specific lexical evidence | 3,132 | Objective-specific diagnostic only |
| Positive adaptation without objective-specific lexical evidence | 3,688 | Objective-specific diagnostic only |
| Negative with lexical climate evidence | 454 | Includes incidental/negated mentions; not proof of a false negative |
| Retrospective wording | 103 | Explicit phrases only; undated text is not proven contemporaneous |

FCDO contributes 520 positive-without-any-evidence warnings and 153 negative-with-evidence
warnings; EC contributes 3,102 and 301 respectively. All raw-marker contradiction flags are
from FCDO. Raw marker flags catch information lost by the existing parser's single-value
representation without altering that parser or frozen builds.

The uncertainty queue contains **33,986** activities, mostly because family relationships
and missing markers are common. It is a machine triage artifact, not a requirement that the
user manually review every row. Priority is a deterministic weighted count of flags, not a
calibrated error probability. No heuristic has a measured precision/recall against truth.

Training-only vocabulary diagnostics expose publisher/language associations. Examples:
`fcdo` occurs in 10,470 usable FCDO training descriptions/titles; `les` occurs in 1,294 usable
EC training activities; `unspecified` occurs in 3,037 FCDO training activities. These are
document-frequency observations, not model scores. French/other languages, negation and
implicit climate objectives are limitations of the English evidence lexicon.

Machine-readable outputs (git-ignored, local only):
`data/ml_v2/automated_quality/quality_1f69651663f0e680/`:

| Artifact | SHA-256 |
| --- | --- |
| `quality_report.json` | `832488a7e41dfa485808ff0c068b0332c3555a01ae0126a4b1e0978a299c5f37` |
| `record_quality.jsonl` | `6807e0cc8bb8e543372cd4096d3d01e1d9d82806edd197539ff9065bceaa92da` |
| `uncertainty_queue.jsonl` | `1b93b56737e24fac768d9cbc5452654d9d2e39acd46c089741327aadfb564e35` |

Inputs: development Parquet `9c25b796450d1c13b71f28860280876afbab7b9e373df31a63d741f0fda2b53f`;
membership `4a3f6541cf658f4a3a825d83d40522fe8bd9ec1fa122686c4eaab66825c02a46`.
Quality source hash: `7865bf5b2154382a9a4dc3873acd57ae1958a94e136c4ee31587438025e915e1`.
The JSON report retains all retrieval-manifest pins, build manifest hash, rights configuration,
fixed regexes, original labels, source identity and evidence offsets. Repeated audit commands
compare all deterministic outputs; post-commit verification writes a separate git receipt.

## AI-LABEL EVIDENCE

**Actual AI labels: 0. Actual model calls: 0.** No OpenAI, Anthropic, Azure OpenAI or Google
API credential was present in the checked environment, and no provider-use approval exists.
Credential values were not printed or stored. The default provider-permission file denies
real preparation. There is no newly installed provider SDK or API transport.

Optional infrastructure supports two distinct blinded file-exchange runs with separate literal
prompts, run IDs and model identities/versions/settings; structured objective scores; exact
input references; mandatory abstention; prompt/input/response hashes; source/provider usage
permission records; and agreement/disagreement with explicit denominators. Requests have an
explicit text-only allowlist, no donor labels or other-run responses. The importer compares
against donor values only after responses return. Its input/model integrity checks do not
authenticate a provider's identity or establish statistically independent model errors.

The assessment pool is **training-only**, one record per partition group, in a separate
`automated_assessments/` directory. It never includes validation or the human pilot. The
internal donor mapping is explicitly marked `DO_NOT_SEND`. Restricted sources and unapproved
processing/transfer are refused. AI results remain `AI_unverified`; no code promotes them to
human labels or uses them as authoritative training targets.

`assessment-demo` creates **ARTIFICIAL** observations and manually specified fixture responses
only, labelled as such, to exercise two run IDs, scoring and abstention. Unit tests additionally
exercise agreement/disagreement and the full file-exchange path. None is claimed as model evidence.
See [the workflow](../research/model_v2/automated_quality_workflow.md) for prompts, schemas,
commands, provider approval fields and limitations.

## HUMAN-LABEL EVIDENCE

**Zero human-verified labels.** No reviewer identity was registered, invented or inferred.
The 300-item double-review pilot and 100-item donor audit were neither completed nor changed.
All **24 protected candidate/pilot/worksheet artifacts** hashed before this task's output
generation were unchanged at verification. Hashing protected artifacts is integrity checking,
not using their texts or labels. No label-opening command was invoked.

## RIGHTS STATUS

All source `rights_status` values remain **`not_reviewed`**. Operational permissions in
`ml_rights_eligibility_v2.yaml` allow internal non-commercial research on FCDO/EC, pending
the existing review conditions. This report does not declare legal clearance.

FCDO's registered OGL licence and required attribution are recorded in every quality report.
The [official OGL v3](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
excludes personal data and third-party rights the publisher cannot license; the
[official guidance](https://cdn.nationalarchives.gov.uk/documents/information-management/ogl-user-guidance.pdf)
supports commercial/non-commercial reuse subject to conditions. The direct OGL page returned
403 to browsing; official search results/guidance and existing registered licence evidence
were used. No alternative website was treated as the licensor. EC remains subject to its
separate attribution and third-party caveats. GCF pages/API remain restricted, unknown sources
fail closed, and World Bank stays outside development. No source text left the machine.

Provider permission is separate from source training permission. External transfer requires
an explicit grant with provider/source terms, retention, attribution and personal/third-party
rights evidence. This task neither assumes that an API key implies permission nor requests
that hundreds of project labels be reviewed to establish that permission.

## V2 DEVELOPMENT READINESS

**YES, for exploratory internal development using original donor-reported labels**, under
the user's Task 006-ML-AUTO scope. This is a distinct decision from the earlier requirement
for reviewed independent evaluation. No v2 classifier or improvement result is produced here.

Use `quality_v2.audit.load_eligible_donor_records` to reproduce the audit and obtain structurally
eligible TRAIN or VALID data via the sanctioned development loader. Keep explicit label origin,
original split groups, training-only fitting/calibration/thresholds, source/sector/language
slices and family-weighted sensitivity analyses. Begin with FCDO-only baselines; declare EC
mixing and donor-specific validation separately. Do not filter or rewrite labels because a
keyword rule or AI assessment disagrees, and do not tune preprocessing on validation warnings.

Donor-only validation positives after structural exclusions:

| Sector | Positives | Negative | Adaptation-only | Shortfall to 30 positives |
| --- | ---: | ---: | ---: | ---: |
| Transport | 15 | 44 | 8 | 15 |
| Urban resilience | 12 | 9 | 1 | 18 |
| Water | 52 | 42 | 25 | 0 |
| Agriculture | 146 | 33 | 48 | 0 |
| Flood/disaster | 32 | 85 | 26 | 0 |
| Ecosystems | 110 | 16 | 24 | 0 |

These are donor-only counts, unlike the earlier A+B researcher/donor table. Urban/transport
remain weak and other slices can be highly imbalanced. Suppress unsupported subgroup claims.

## INDEPENDENT TEST READINESS

**NO.** Human-verified external labels remain zero, and no AI-assessed substitute test was
created. AI or donor agreement cannot establish independent accuracy, unseen-publisher
generalization, model improvement, impact, or deployment readiness. All **8,592** consumed v1
test records remain excluded. The original external evaluation pool stays reserved for a
future genuine independent labeling route; it is not needed to run exploratory development.

## REMAINING LIMITATIONS

1. Automated warnings are unvalidated diagnostics, not a measured donor error rate.
2. Broad families, repeated descriptions, inconsistent component labels, language and source
   shortcuts remain risks; rows are not independent samples.
3. Metadata/date uncertainty and retrospective narratives prevent proposal-time claims.
4. There is no approved AI provider, no real AI assessment and no independently labeled test.
5. Source/provider rights and personal/third-party exceptions require care before uses beyond
   the current internal-research scope. No global legal clearance is claimed.
6. A complete model experiment, model-selection protocol and independent evaluation are future
   work. This task implements audit/support and an honest readiness decision only.

## Validation and preservation

Actual commands/results before the local commit:

| Command | Result |
| --- | --- |
| `uv run compassio-v2 verify-baseline` | 11/11 PASS; no consumed test evaluated |
| `uv run compassio-v2 verify-retrievals` | All five retrievals OK |
| `uv run pytest tests/ml/test_quality_v2.py` | 29 passed |
| `uv run pytest` | 499 passed, 31 skipped |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 206 files already formatted |
| `uv run mypy` | No issues in 156 source files |
| `pnpm.cmd lint`, `pnpm.cmd typecheck`, `pnpm.cmd build` in `apps/web` | All exit 0; production static build succeeded |
| `git diff --check` | Exit 0 |

The 31 skips are pre-existing local-v1/backend tests whose artifacts are absent in this
worktree; seven are DB tests and are not covered by `verify-baseline`. All 14 available real
v2 isolation checks ran. Baseline verification reads the configured original data root and
verifies frozen artifacts/release/final-test hashes, without recomputing consumed-test scores.

Initial implementation lint/type issues were corrected; targeted tests passed after the final
assessment-manifest integrity changes. Final commit integrity and audit reproducibility are
rerun after committing, with their actual results reported in the handoff and per-commit
receipt. Generated reports stay local; only source/config/test/documentation changes are committed.
