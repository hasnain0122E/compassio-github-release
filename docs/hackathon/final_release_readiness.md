# Final release readiness

**READY FOR FINAL MAIN PROMOTION — for the authorized single-machine local hackathon build.**

Public canonical-data/model deployment remains **BLOCKED** by source/model serving
rights and the existing production access policy. The user retains the final
review, merge, push and deployment steps. Nothing was merged into main, pushed,
published or deployed during Task 012.

## Evidence supporting local promotion

Completed release snapshot: `c0f8d9e2c7853aee32dde5bb74bd606bf701acb3` (integration branch).

- All four input branches merged with history on
  `integration/battleverse-final-product`; implementation commit
  `c5900acb860c91df4b0266cd3c1be3a79586c1f5`. Later commits contain the final browser test, probe pagination correction and reports.
- Main and `backend-ready-for-battleverse` remain at
  `8c083509e324d76aafc7ee097dc4345a94314afd`. All original branch tips and six
  worktrees are preserved. No merge conflicts or discarded challenge changes.
- Approved landing is unchanged. All original 11 product browser journeys pass.
  Four additional challenge journeys pass, including real canonical-model calls
  at three widths, light/dark layouts, evidence URLs and a real typed 429 with
  browser-readable Retry-After. **15/15 browser tests pass, 54.0 seconds.**
- **862 pytest tests pass, 49 skip**, on the final implementation. Fresh repository
  Ruff, formatting, strict mypy, frontend lint/typecheck, 16 unit tests, production
  build and generated contracts pass. Dedicated adapter/hardening/C11 run: 38 pass; C05/C09/C11 dedicated run: 113 pass.
- Five runtime artifacts match their full frozen hashes. All 27 canonical DB
  figures match; SQLite integrity is ok and FK checks are empty. Finance safeguards,
  registries, labels, thresholds and source manifests remain unchanged.
- Official real API smoke: 27 requests, zero failed checks. C09/C11 enabled and
  disabled behavior is verified. Production/public access still fails closed.
- The Windows 413 JSON-body reset is resolved for both measured upload forms.
  SQLite uses safe read-only pooling regardless of C11. Controlled concurrent
  canonical reads pass. One-worker and bounded-state assumptions remain explicit.
- C05 base/addendum hashes verify and three fresh live sample demonstrations run.
  C09 fresh full reproduction matches all nine deterministic outputs on repeat and
  all nine original challenge judge outputs. C11 recorded capacity is correctly
  labeled fixture-backed; fresh canonical tests make no equivalent capacity claim.

See [verification ledger](task012_verification.md),
[integration report](final_integration_report.md),
[combined scorecard](combined_challenge_scorecard.md),
[judge runbook](final_judge_runbook.md) and
[safe machine-readable evidence](task012_evidence.json).

## Remaining limits and operator actions

| Item | Status / consequence |
|---|---|
| Blockers to reviewed local promotion | No known failing integration gate remains within the local scope |
| 49 skipped cases | Missing raw/rebuild/research/final-evaluation outputs and disposable PostgreSQL; enumerated individually, never counted as passes |
| Offline runtime | Installed from caches; local servers and artifacts work. Physically disconnect and rehearse on the actual demo laptop before the event |
| C05 portability | Requires ignored, hash-verified cached base/addendum batches; not included in a Git clone |
| C09 full evaluation portability | Requires pinned authorized development build/audit; live adapter needs only frozen runtime files |
| Scientific scope | Development donor-marker agreement, residual adaptive/targeted failures, no new independent or sealed final evaluation |
| Capacity | Canonical functional concurrency verified; canonical 200-rps capacity and multiple workers unmeasured |
| SQLite | Supported local read concurrency fixed; not proof of unlimited concurrency or production storage suitability |
| HTTP 413 | Finite drain budget; no guarantee for arbitrarily slow/large hostile TCP senders |
| Hosting | Linux/provider runtime not tested; Next frontend needs a separate reviewed Python backend |
| Source/model rights | Not cleared for public serving; production fails closed; organizer permission is user-reported and dates unset |
| Review persistence | Token gate preserved; demo shortlist is local and screening text is not saved |

The product is reviewable at `http://127.0.0.1:3032` while its local servers run.
The runbook reproduces that configuration. Temporary probe and default smoke
processes stop after use; other worktrees' servers are untouched.

## Manual release path

Review the local diff and evidence, then promote through the user's chosen GitHub
review process. Keep the backend freeze tag immutable. Follow
[manual GitHub/Vercel instructions](manual_github_vercel_deployment.md) for later
code upload and hosting configuration. Do not upload canonical artifacts or deploy
in development mode to bypass production refusal. A publicly functioning
canonical-data/model product requires separate rights and serving approval.
