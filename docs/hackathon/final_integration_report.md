# Task 012 — final product integration

Date: 2026-11-12. Scope: one local, authorized hackathon build. No merge into main,
push, publication or deployment was performed.

## Git isolation and provenance

Completed release snapshot: `c0f8d9e2c7853aee32dde5bb74bd606bf701acb3` on the integration branch.
The final documentation-only commit records this snapshot; application code is unchanged.

Worktree: `D:/AI LEARNING/compassio-final`. Branch:
`integration/battleverse-final-product`. It already existed, clean at the frozen
backend, when this task began. Implementation commit: `c5900acb860c91df4b0266cd3c1be3a79586c1f5` (later test/report
commits are descendants). The final report commit is discoverable with
`git log -1 --format=fuller integration/battleverse-final-product`.

All requested references matched exactly; none had advanced:

| Input | Verified commit |
|---|---|
| main / backend-ready-for-battleverse | `8c083509e324d76aafc7ee097dc4345a94314afd` |
| feature/task010-complete-frontend | `e0c71af6e5afb61968363215f2571c164f8942ac` |
| challenge/c05-poison-quarantine | `7253c15f5133229b2ebef7819b83c323827d5992` |
| challenge/c09-adversarial-robustness | `4cf835c81316611fe114566d48c30838895daac6` |
| challenge/c11-availability-shield | `20e6a35b2fd2ddbbdbf88d462846127033e1b4fa` |

Controlled `--no-ff` merges, in order:

| Merge commit | First parent | Second parent |
|---|---|---|
| `5a85a9cff9d431c7ceeebb437fc380fd970c1625` | frozen backend | frontend `e0c71af` |
| `a47d65190281db5cd257fa358ae6495b6c2a3cf1` | `5a85a9c` | C05 `7253c15` |
| `44ae3e2eb3ab90acfb6668b6e5cd3afcaa7492c2` | `a47d651` | C09 `4cf835c` |
| `e9e7a47f41dade8d7adc150a2306f169b771adeb` | `44ae3e2` | C11 `20e6a35` |

All merges were conflict-free. No branch changes were discarded. Before merging,
complete branch patches were saved under ignored `artifacts/task012/*-before.patch`;
diffs, ancestry, contracts, entry points and artifact requirements were inspected.
Frontend touched web/docs; C05 and C09 primarily added isolated ML modules; C11
modified configuration, startup, the read connection factory and hardening tests.
The behavioral reconciliations below were necessary despite the absence of text conflicts.

Existing worktrees preserved: original C05 checkout, `compassio-c09`, `compassio-c11`,
`compassio-frontend`, `compassio-ml-v2`, plus this integration checkout. Their branch
tips and the immutable backend tag were not changed. The already-running process
on port 3000 was preserved. Integration uses web 3032 / API 8032; default-mode smoke
uses an independent API on 8033. Disposable load probes choose unused loopback ports.

## Product and challenge behavior

The approved landing page is byte-identical to the frontend branch. Discover →
Understand → My Shortlist, all four primary destinations, localStorage persistence,
real Pakistan project evidence, financial provenance, v2 screening, same-input v1
comparison, optional analytics and scenarios remain available. `/dashboard`
retains its compatibility redirect to Discover. Main navigation remains simplified.

`/challenges` is now Compassio Trust & Resilience: three cards with plain-language
problems and solutions, before/after meters, recorded metrics, source scorecards,
demonstration actions and expandable methodology. Only three small scorecards are
served as static evidence; raw experiment datasets are excluded from the web bundle.
The UI distinguishes recorded evaluations from live computation. C05/C11 execute
through terminal commands; C09 also has a real live browser action. No fabricated
live result or synthetic project is presented as evidence.

C05 keeps policy A, candidate B, poisoning simulation, gate, oracle-after-decision
evaluation and all original evidence. The cached base and addendum were copied
locally into ignored paths and verified (12 + 6 manifest entries). Live sample
commands execute detection on verified development data; they do not retrain the
registered model. No donor labels, splits, registry, threshold or sealed final test
data were changed or consumed.

C09 remains off by default. With `-C09` and authorized local ML v2 mode,
`POST /api/v1/challenges/c09/screen` returns `raw`, `guarded`, `standard_api`, guard
version, review flags and reasons. It reuses the already hash-verified registered
pipeline. Normal `/screening/*` behavior is unchanged. The original API sanitizer
strips controls more broadly than the challenge guard: reporting all three paths
prevents mislabeling a sanitized API score as the raw challenge predictor.
Explanations score the exact fields used by their path; guarded offsets refer to
normalized fields. Source project screening permissions and review-write gates
remain unchanged. This text-only adapter never accepts a project id to bypass them.
Both admission policies cover the adapter, and only one is selected at a time.

C11 remains off by default. `-C11` selects its bounded peer/global token buckets
instead of the original screening limiter. CORS remains outermost, OPTIONS bypasses
admission, and `Retry-After` is browser-readable with either limiter. The frontend
shows typed 429 recovery guidance for reads as well as screening. One worker and
`--no-proxy-headers` are explicit; distributed/multiworker protection is not claimed.

## Reliability defects

**SQLite concurrency — fixed for the normal product and C11.** The `sqlite://`
creator previously selected SingletonThreadPool, which can close another thread's
active connection. The default read factory now selects QueuePool (5 retained,
10 overflow, 2-second checkout timeout), independent of C11. Sessions remain
request-local. Connections still open the existing file with SQLite `mode=ro`;
foreign keys remain enabled. No journal mode, schema, canonical rows, ingestion
logic or finance service was modified. A 24-thread/120-read regression and real
canonical concurrent TCP requests exercise this fix. The frontend's conservative
single-request queue is retained; backend correctness no longer depends on it.

**413 response body on Windows — fixed for measured uploads.** Rejecting before
reading a pending upload could reset the TCP connection while the client read JSON.
The rejection path now drains without buffering, up to a fixed byte/time budget
(1 second; max of 1 MiB and four times the configured body limit), then returns
typed JSON and closes. Declared-length and chunked 300,000-byte uploads were tested
over real Windows TCP with C11 both off and on; the full error body and CORS header
were readable. Slow or arbitrarily large malicious uploads can exhaust this
budget; complete-body delivery for every hostile transport is not promised.

**C11 Ruff discrepancy — reproduced and fixed.** Fresh lint found RUF001 and E501
in `scripts/c11_report.py`. Both are corrected without rewriting historical metrics.
The challenge's historical lint statement is superseded by this task's fresh logs.

## Canonical artifacts and finance

The existing `scripts/runtime_artifacts.py import` verified the source before
copying and reverified the destination. None of the artifacts was overwritten.
All remain ignored and uncommitted. Full frozen hashes:

| Artifact | SHA-256 |
|---|---|
| SQLite | `d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385` |
| ML v1 | `53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656` |
| v1 manifest | `bc3c8f78c5a42aa434da8c72459cf49e80d8f41300aaa478468802facd595282` |
| ML v2 | `654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574` |
| v2 manifest | `72b78bbb6eb02679acbbcfc1f90c2feeb13b0b42dbf597d65e4db86701e36ca5` |

`compassio-db verify` checks all 27 audited figures; SQLite integrity is `ok`,
foreign-key violations are empty. Preflight finds schema 0003, 26,499 projects and
93,881 financial observations. Protected finance modules, canonical ORM models,
rights/source manifests, model registries and thresholds are unchanged from the
freeze. Existing real-data decision tests and the official API smoke check Decimal
totals, source/currency/basis boundaries, duplicate-package warnings and budget
conservation. No cross-source total is introduced by the showcase.

## Verification evidence

See `task012_verification.md` for final commands, exact results and every skip.
Ignored full logs, TCP receipts, browser screenshots and traces are under
`artifacts/task012`, `artifacts/frontend`, and `artifacts/c09/task012`.
The official API smoke completed 27 requests with zero failed checks against the
canonical database and both real models. The controlled canonical mixed-load probe
recorded 64/64 HTTP 200 with C11 off. With an explicitly reduced read budget
(rate 1/s, burst 4) it recorded 4 HTTP 200 and 60 typed HTTP 429, and an independent
local peer succeeded. This is functional rejection/concurrency evidence, not the
fixture-backed 200-rps capacity experiment. Production checks returned 403 for
source data, normal screening and the C09 adapter.

Initial environment failures are not counted as passes: sandbox-denied Git metadata,
uv cache and temporary files required authorized reruns; pytest's inaccessible cache
required `-p no:cacheprovider`. Playwright's default revision was absent, so the
installed Chromium executable was explicitly selected. No assertion was weakened
to conceal these failures. Adding the explicit new API route required updating
the implemented-route allowlist and regenerating OpenAPI and TypeScript contracts.

## Release scope

This is a single-machine local build using the existing authorized access modes.
Dependencies installed from local caches. Runtime requires the five frozen files;
C05 live additionally requires its verified cached experiments. C09 full reproduction
requires the pinned development build/audit in the read-only source checkout.
A physically disconnected-machine rehearsal remains an operator step.

PostgreSQL execution, distributed capacity, independent model generalization and
public source/model serving are not established. Source rights remain not reviewed;
organizer authorization is user-reported and event dates remain unset. Public
hosting remains fail-closed. See `manual_github_vercel_deployment.md` for manual
GitHub/Vercel steps and the separate backend requirement.

**READY FOR FINAL MAIN PROMOTION** for the authorized local hackathon scope.
`final_release_readiness.md` records the evidence and remaining public-serving blockers. Only the user may promote, push or deploy.
