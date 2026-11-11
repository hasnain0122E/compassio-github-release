# C09 experiment protocol v1

Use the frozen backend `8c083509e324d76aafc7ee097dc4345a94314afd` and ML v2 candidate
`ml2fast_49317056_c76204127550`. Artifact SHA-256:
`654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574`.
Fingerprint: `c76204127550fb299c11704de61bd07cce3eae6635193e608a42897c5f995ad2`.
Threshold: `0.44474326842740053`. Check committed pins before unpickling, then use the existing
candidate loader's checksum/schema/status/fingerprint checks. Never fit or rethreshold.

Read only the registered FCDO/EC development build `v2build_a37deb181332`. Verify the frozen
experiment's provenance and audit pins with `check_pins`, obtain records through
`load_verified_development` (which uses the sanctioned development loader), and apply the
checksum-pinned completed donor audit's structural eligibility list. This deliberately avoids
rerunning the audit writer in another worktree. Recheck the eligible VALID membership hash
`3b001fc0a693b004e3e5acbe95f05fd9b5c69c32157ebec651ad01a11269049d` and 2,550 records.
Rights remain internal research, permitted pending review; source labels remain donor-reported.

Before implementing the guard, freeze C09 membership: connect records sharing any partition
group, project family or exact text hash. Hash the component's minimum ID with prefix
`c09-v1|`. Hash modulo four equal to zero selects tuning; other values select assessment.
Sort by component hash then ID; cap at 64 tuning and 256 assessment records. Caps are unrelated
to scores or labels. Record text and membership hashes locally. A prepared split cannot be
overwritten. Related records cannot span the two C09 subsets.

The parent VALID pool was already used for ML v2 model selection. C09 membership was frozen
before guard implementation. This is **challenge benchmark evidence, not an independent
external test**. No guard parameter was selected by optimizing assessment results. Guard
constants were specified before inspecting assessment metrics and were retained despite
failures. The initial exploratory runs occurred on a dirty implementation tree; final judge
evidence must be regenerated from a clean committed tree, with an exact repeat.
After the first assessment, source review added a negation-boundary safety rule and complete
discarded-query logging. Neither change was chosen to optimize assessment metrics. Final
results are rerun with those changes; the assessment is not described as a pristine external test.

Execution order:

1. Verify artifacts and read-only resources; freeze development membership.
2. Validate edit ceilings, receipt replay and independent edit distance.
3. Run the unprotected frozen model on clean, five fixed and raw-score-seeking attacks.
4. Freeze the normalization/validation adapter and check Unicode safety/idempotence.
5. Replay the identical fixed and raw-selected attacks through the guard.
6. Select fresh attacks against the guarded score with the same 12-request budget.
7. Validate receipts, measure aggregates, generate escaped HTML, and repeat from the commit.

Metrics are paired with the same original record. Report clean/attacked scores, threshold
crossings, absolute shift mean/median/P95/max, score increases/decreases (epsilon 1e-12 and
>=0.01), climate-positive new false negatives, non-energy/adaptation slices, review burden,
clean disagreement, and request/internal-model query counts. Aggregates count record/attack
pairs; disclose no-ops and unique records. Slice counts under 15 unique positives are flagged.
Repeated attacks on a record are dependent; no statistical significance claim is made.

Latency uses 64 assessment texts, three warmed passes, 192 calls per pipeline. Python traced
peak incremental allocation is measured separately, with native/RSS/model loading excluded.
Timing and memory are machine-dependent, separate from deterministic evidence. Model inputs,
receipts, scores, metrics and query receipts must reproduce byte-for-byte. Full source text
and HTML stay under Git-ignored `artifacts/c09/`; only aggregates and safe code are committed.

Read no sealed evaluation payloads or restricted/backend source texts. Hash the original
SQLite as opaque bytes; never query or alter it. Verify v1/v2 resources and tracked finance/
evaluation-ledger files before/after, plus frozen/C05/frontend references. Concurrent frontend
commits are external activity and must be distinguished from C09 writes.
External frontend reference observations stay in `integrity_comparison.json` and the HTML,
outside deterministic metrics, because that branch may advance during either repeat.
