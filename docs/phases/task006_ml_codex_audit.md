# Task 006-ML review-gate audit of 928cf00

Audit date: 2026-11-09. Branch: `feature/ml-v2`. This document supplements the historical
completion reports; their earlier training-only and GCF-pilot decisions are superseded.
No classifier was trained, no consumed test was evaluated, and no sealed label was opened.

## Finding and repairs

`928cf00` was substantially implemented but was not technically complete:

1. `load_aiddata_development_ids` did not recheck current training rights, unlike the external
   loader. It now fails closed when AidData training permission is withdrawn.
2. Development build paths rejected known forbidden folders but could escape to another
   directory containing a manifest. Both loaders now require a direct child of `datasets/`.
3. `_human_verified_count` would open sealed labels without the evaluation-plan guard and
   count unresolved items as verified. It now reads only `verified_items` from freeze metadata.
4. Final adjudicated Rio values lacked 0–2 bounds and could contain only one objective.
   Both objectives are now mandatory for verified labels and bounded. The third-person rule
   also covers adjudications ending in `needs_review`.
5. Worksheet issuance/checking did not consult the human-reference permission for every
   source. Both now apply the current rights configuration, including unknown-source denial.
6. Generated coverage wording still described GCF research use as permitted without its AI
   restriction. This is corrected, and EC attribution/third-party caveats are recorded.
7. The experiment plan and label-mapping YAML still allowed consumed-test training; the
   evaluation proposal and mapping rule still contemplated GCF evaluation. These active
   instructions now agree with the enforced exclusions. Historical reports remain intact.

Nine regression cases use explicitly artificial fixtures. No reviewer identity, project
observation or human label was invented for real datasets.

## Integrity evidence

`uv run compassio-v2 verify-baseline`: **11/11 PASS**, repeated during the audit. It verifies
all nine registered raw files, the manifest copy, frozen table/membership/config, final plan,
trusted release artifact and fingerprint, and all three completed test-access/output records.
It performs integrity verification only, with no prediction on consumed tests.

| Artifact | SHA-256 |
| --- | --- |
| v1 research table | `71fc5a10285d25ed22d7e804f6cd5ec66783b6c6163168b5f8ab7cb46ae9d394` |
| v1 split membership | `aba478d973f50c7dfd98d8872ccd81fc541e6eded7698aaf7f1fc58adde4be2a` |
| final evaluation plan | `c4760503f4b8798706e24cccfe7b87a4203751b8722d946984ebf76a47b8b3cb` |
| released model | `53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656` |
| model fingerprint | `3023fe3d148b605c3ed9079c93f07296193fd2d8d5f77b8a82a163e58ccdc495` |

`git diff 7f70654..HEAD` shows no changes to the canonical v1 manifests, frozen lock, final
plan, trusted-release registry or `uv.lock`. No datasets or frozen artifacts are staged.

`uv run compassio-v2 verify-retrievals`: **all five retrievals OK**, including both EC
retrievals. The 32 external rights-evidence files match their `SHA256SUMS` entries. That
historical file also lists itself; this self-entry cannot attest its final contents and was
excluded from verification. The evidence files were preserved.

The saved GCF robots body contains `Content-Signal: ai-train=no, search=yes, ai-input=yes`;
its hash is `b99410eda72205dec835258fe95cd2b8e79b40d045a02965c50dc4741a034770`.
The backend registry viewed through `git show main:data/manifests/backend_source_registry.json`
also explicitly prohibits training. ML never loads that backend payload: `raw_db/` and `db/`
are forbidden input paths, the snapshot has no ML parser, and its rights entry is restricted
for every use. Unknown sources are denied. All sources remain `not_reviewed`; operational
internal-research eligibility is not legal clearance.

## Dataset and review evidence

The handoff build is `v2build_9911d9b6caca`. It first materialized while fixes were being
reviewed, so its original manifest records `928cf00` and `dirty: true`; that historical
manifest is preserved. A second build with the final source content reproduced its seven
dataset outputs byte-identically. Their hashes and all integrity counts also match
`v2build_274957046f51` exactly. The content hash, rather than the historical manifest's git
field, identifies the final source. After committing the fixes as `f5d77b1`, baseline
verification again passed 11/11 and all five retrievals verified. A further build is required
after this documentation checkpoint; the final response records its actual result. This is
an explicit provenance limitation, not a claim that the original manifest was clean.

Fresh, empty worksheets were issued for `v2build_9911d9b6caca` after the source commit. They
contain the same deterministic 300 pilot items (90 Pakistan) and 100 audit items (EC 71,
FCDO 29), pass `check-worksheets` with zero errors, and `validate-reviews` still reports zero
completed submissions and zero verified labels. Use these worksheets for the handoff;
previous build directories and worksheets remain preserved. All **14 local v2 integrity
tests passed** after issue. No second pilot was labeled.

Observed membership: **58,174 records**, **26,433 project families**, **26,118 partition groups**.
No family/group spans partitions. All **8,592** consumed v1 test records are excluded from
every development/evaluation pool. GCF's **348** records are restricted reference only.
World Bank is held out as an unseen publisher. The nine linked FCDO records also remain
outside development (eight have usable text). Suspected links isolate records conservatively;
they do not assert project identity. The current suspected-match queue is **8,533 pairs**,
superseding the earlier 2,360-pair queue before EC expansion.

Usable training data: **26,861 external records + 10,203 AidData IDs**; validation:
**5,770 + 2,160 IDs**. These are candidates, not evidence of training readiness. There are
**15,925 donor-labelled usable records**, with **5,055 positives**, **4,170 adaptation
positives**, and **1,379 adaptation-only positives**. Donor labels remain unaudited.

`check-worksheets --build-id v2build_274957046f51`: ready, zero errors. Both 300-item
World Bank pilot sheets and the 100-item donor audit sheet are hash-intact, blind and empty
(EC 71 / FCDO 29 in the audit). `validate-reviews` reports no registry, no completed files
and **zero verified labels**. `adjudication-sheet` and `freeze-labels` both refuse with exit 1
because the genuine reviewer registry is absent. No adjudication or final label was created.

Coverage reproduced in `weak_sector_requirements.json` (source labels, not human verification):

| Sector | Validation positives A+B | Shortfall to 30 | Usable external candidates | Verified positives |
| --- | ---: | ---: | ---: | ---: |
| Transport | 28 | 2 | 177 | 0 |
| Urban resilience | 12 | 18 | 0 | 0 |
| Flood/disaster | 35 | 0 | 0 | 0 |
| Agriculture | 155 | 0 | 294 | 0 |
| Water | 64 | 0 | 139 | 0 |
| Ecosystems | 123 | 0 | 0 | 0 |

Adaptation-only donor labels: **1,121 training / 258 validation**; the external-test policy
requires **78 verified adaptation-only positives**, currently zero. No model performance is
inferred from these counts. World Bank urban/disaster/ecosystem themes need a separately
scoped parser/stratification expansion or another eligible evaluation publisher. No source
was acquired during this audit.

## Commands and actual results before the local commit

| Command | Actual result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 198 files already formatted |
| `uv run mypy` | No issues in 151 source files |
| `uv run pytest` at the original checkpoint | 457 passed, 31 skipped |
| `uv run pytest tests/ml/test_external_v2_review_gate.py` after fixes | 37 passed |
| `uv run pytest` after fixes | 469 passed, 32 skipped |
| `pnpm.cmd lint` in `apps/web` | Exit 0 |
| `pnpm.cmd typecheck` in `apps/web` | Exit 0 |
| `pnpm.cmd build` in `apps/web` | Exit 0; production compilation and static pages generated |
| `git diff --check` | Exit 0 |

The 31 original skips include seven local DB tests, not exclusively v1 ML tests as the prior
report suggests. Those DB tests are not covered by `verify-baseline`; their local source data
is absent in this worktree. The remaining skips concern local v1 source/research/model/final
artifacts. The additional skip was the audit build's worksheet before issue. It was
subsequently issued and all 14 local v2 checks passed. Unit/API tests and the available
real v2 integrity checks ran successfully.

Environment notes: bare `pnpm` failed because PowerShell blocks its `.ps1` launcher;
`pnpm.cmd` worked. `uv` required access to its existing cache outside the sandbox and ignored
an inherited `VIRTUAL_ENV` pointing at the main checkout, correctly using this worktree's
environment. A Python one-liner failed due to Windows argument quoting and was replaced by
PowerShell metadata comparison. The write-tree merge probe was denied repository-object
write access; the three-argument read-only `git merge-tree 7f70654 HEAD main` succeeded.
No actual merge or branch movement occurred.

## Remaining human work and integration

Register genuine A/B reviewers, a third adjudicator and an auditor; complete the double-blind
300-item pilot and 100-item donor audit; adjudicate; review suspected links; then size the
expanded external test from observed prevalence/agreement. Meet weak-sector minima and
complete human rights review before the applicable release/use. These are real outstanding
requirements, not templates counted as completed reviews.

The technical preparation is ready for genuine human labeling after the post-commit integrity
and reproduction checks pass. **The human-reviewed gate is not complete; v2 training is not
approved or ready.** No v2 model exists.

Integration with `main` at `bd2fe30` is ready for a coordinated conflict-resolution and
combined-validation step, not an unattended merge: `docs/phases/phase_plan.md` conflicts;
`.gitignore` and `CLAUDE.md` auto-merge but need review. Preserve the distinction between
backend display permission and ML permission, and rerun both branches' combined checks after
integration. No merge, push or deployment was performed.
