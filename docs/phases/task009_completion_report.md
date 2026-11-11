# Task 009 completion report: backend completion and hardening

Branch `feature/task009-backend-finalization` (from `main` `62a1a17`). Not merged, not pushed,
not deployed. Date 2026-11-10. Machine: Windows 11 Pro (10.0.26300), Intel Core i7-10750H
(6 cores / 12 threads), 15.8 GB RAM, Python 3.12.15 (uv-managed), uv 0.13.0, Node 24.19.0,
pnpm 11.21.0.

## 1. Task 008 integration (Part A)

See `docs/phases/task008_final_integration_report.md`. Summary:

- One confirmed defect fixed: a comparison returned `selection_total` 1,024,000,000 USD for
  AidData 35266 + 54087 while warning they share parent package `aiddata_parent:1648`. Since
  `compassio-comparison-1.1.0` such totals are withheld (regression tests on artificial and
  real data).
- All gates passed on the stable tree (749 passed, 2 skipped); the 15 documented Task 008
  examples reproduced live (11 identical, 4 differing only by the intended 1.1.0 change).
- Safety branch `safety/task008-pre-promotion-main-12f536a`; `main` fast-forwarded
  `12f536a` → `62a1a17`.
- **Retrieval erratum:** an interim message said `verify-retrievals` "3 OK"; that came from
  `tail -3`. The full output lists **5 OK** snapshots (unchanged from Task 008).

## 2. What Task 009 added

| Area | Change | Files |
| --- | --- | --- |
| Event access policy | `hackathon_event` mode: named authorization from `configs/event_data_authorizations.yaml`, source-scoped, loopback-only, optional date window, honest notice; production forces `public` | `core/config.py`, `services/event_access.py`, `services/access.py`, `api/deps.py`, `core/middleware.py` |
| Request hardening | 413 body limit (declared and chunked), 429 per-client screening limit, security headers, JSON 500 without details, `{code, message}` 422 envelope without echoed input | `core/middleware.py`, `main.py`, `api/errors.py` |
| Lifecycle | FastAPI lifespan: optional model preload with hash/fingerprint verification; disposes DB and review-store engines on shutdown | `main.py`, `api/v1/screening.py` (`build_model_manager`) |
| Startup and checks | Read-only preflight, PowerShell start scripts, live smoke test, latency bench | `scripts/demo_preflight.py`, `start_api.ps1`, `start_web.ps1`, `smoke_api.py`, `bench_api.py` |
| Contracts | Committed OpenAPI document with freshness test; TS types regenerated | `scripts/generate_api_types.py`, `docs/api/openapi.json`, `apps/web/src/lib/api-types.ts` |
| PostgreSQL | Compile-only checks for every Task 008 metric query and the candidate query | `tests/api/test_postgres_portability.py` |
| Docs | Handoff, runbook, blueprint, examples, permission scope; PG, rights-policy, env, phase-plan updates | `docs/hackathon/*`, `docs/architecture/postgresql_verification.md`, `docs/security/source_rights_access_policy.md`, `.env.example`, `CLAUDE.md`, `apps/api/CLAUDE.md` |

New settings (all documented in `.env.example`): `COMPASSIO_EVENT_AUTHORIZATION`,
`COMPASSIO_EVENT_AUTHORIZATIONS_PATH`, `COMPASSIO_MAX_REQUEST_BODY_BYTES` (default 262,144),
`COMPASSIO_SCREENING_RATE_LIMIT_PER_MINUTE` (default 60), `COMPASSIO_PRELOAD_MODELS`
(default false; `start_api.ps1` turns it on).

New tests: `tests/api/test_event_access.py` (17), `tests/api/test_hardening.py` (14),
`tests/api/test_api_types.py::test_committed_openapi_document_is_fresh`, 12 PostgreSQL
compile-only cases.

## 3. Startup entry point (verified)

`compassio_api.main:app`. `apps/api/pyproject.toml` builds package `compassio_api` from
`apps/api/src`; `apps.api.main:app` cannot import because `apps/` and `apps/api/` are not
packages. Proven by live servers on ports 8018, 8020–8023, 8030–8032 started with
`uv run uvicorn compassio_api.main:app --host 127.0.0.1 --port <p>` (directly and via
`scripts/start_api.ps1`), all serving real requests.

## 4. Venue readiness experiment

A fresh `git worktree` (clean checkout of the branch) plus **only** five git-ignored files
(the SQLite DB, ML v1 `model.joblib` + `release_manifest.json`, ML v2 `model.joblib` +
`candidate_manifest.json`) was set up in the scratchpad:

- `uv sync --locked --offline` succeeded (6 s, from cache);
- no `COMPASSIO_*` variables in the shell (`env | grep -c COMPASSIO` → 0); `data/ml_v2/`
  contained only `models_v2_dev/`; `data/raw/` only its README;
- `scripts/start_api.ps1` → preflight OK → server up in event mode with ML v2 demo and preload;
- `scripts/smoke_api.py` → **27 requests, 25/25 checks passed**, including ML v2 and ML v1
  inference.

Conclusion: the ML v2 raw training inputs (`external_raw`, the `compassio-ml-v2` worktree)
are **not needed** to run predictions. They are needed only for ML re-verification and the
ML v2 `local_data` tests.

## 5. Live end-to-end results (final commit `96d7b8a`, clean checkout, port 8031)

`scripts/smoke_api.py --base http://127.0.0.1:8031`: 27 requests, 25 checks, 0 failed.

| Step | Result |
| --- | --- |
| Models | `authorized_local_demo`, default `ml_v2`, fallback `ml_v1`; header `hackathon_event` |
| Search `q=hydropower&country=PAK` | 26 records, 6 pages |
| ML v2 text screening | 0.7885 `clearly_flagged`; ML v1 on the same text 0.9660 |
| ML v2 DB record `aiddata:35266` | 0.5945 (same as Task 007), source evidence kept |
| Non-permitted source `gcf_projects:FP085` | 403 `source_not_permitted_for_model_input` |
| Finance contract | PAK ADB disbursements 21,549,925,012.94 USD = sum of `/analytics/trends` points |
| Same-package AidData pair | shown, flagged, `selection_total` null |
| Cross-source pair (CFU r10 / GCF FP005) | flagged, never summed |
| Ranking (CFU, PAK, energy) | 31 candidates, top 0.8667, fingerprint `149e0721bece…` identical on repeat (same as Task 008) |
| Scenario 1,000,000 USD equal ×3 | 333,333.34 + 333,333.33 + 333,333.33, unallocated 0.00 |
| Negative cases | 422 (one id, unknown field, unsupported objective `objective_not_supported`, unfiltered ranking `candidate_set_too_large`), 404 (unknown, restricted `gcf_historical`), 403 review write, 413 oversized |

Live unauthorized configuration (`COMPASSIO_ENVIRONMENT=production` +
`hackathon_event`, port 8032): `/projects`, evidence and country profile → 403
`source_rights_not_cleared`; screening → 403 `inference_not_authorized`; `/models` →
`inference_disabled`; header `X-Compassio-Data-Access: public`.

## 6. Performance (measured, not estimated)

`scripts/bench_api.py` against a fresh server (event mode, ML v2 demo, **preload off**), first
call and median of 5 warm calls, client wall-clock in ms:

| Request | First | Warm median |
| --- | ---: | ---: |
| `/projects` page 1 (26,499 records) | 266.7 | 183.2 |
| `/filters` | 559.3 | 5.9 |
| text search `q=solar` (435) | 18.7 | 18.3 |
| PAK + sector filter | 31.1 | 30.5 |
| deep page 500 | 193.3 | 195.7 |
| detail | 33.1 | 11.8 |
| funding by country | 232.8 | 6.8 |
| funding by sector | 171.2 | 7.5 |
| approved vs disbursed PAK | 377.5 | 6.4 |
| country profile PAK | 945.1 | 7.3 |
| coverage | 393.8 | 6.3 |
| compare 3 / 10 records | 22.8 / 33.0 | 18.8 / 43.0 |
| prioritize CFU PAK (31) | 77.2 | 9.7 |
| prioritize all PAK (740) | 2,242.0 | 11.0 |
| prioritize GCF (379) | 878.8 | 10.5 |
| scenario, 10 projects | 49.2 | 46.8 |
| ML v1 text (cold load) | 5,161.7 | 7.9 |
| ML v2 text (cold load) | 1,230.6 | 22.5 |
| ML v2 DB record | 159.7 | 180.7 |

With **preload on** (separate fresh server): process start to `/health` 8.01 s, then first
ML v1 request 54.8 ms and first ML v2 request 6.4 ms.

**Bottlenecks and decisions:**

- Cold model loading (5.2 s v1, 1.2 s v2) was the largest demo risk. Fixed with
  `COMPASSIO_PRELOAD_MODELS` (on in `start_api.ps1`). Scores unchanged (smoke values identical).
- First-call analytics and 740-candidate ranking (up to 2.2 s) are cached afterwards (~10 ms).
  Running `smoke_api.py` once before judging warms them. Not changed (no semantic risk taken).
- DB-record screening (~150–350 ms) is dominated by the word-attribution explanation, which
  scales with description length (cProfile: `explain._word_attributions`). Left unchanged so
  explanations stay identical.
- Unfiltered listing (~185 ms) is the window-count scan over 26,499 rows, already a deferred
  join. Acceptable; unchanged.

## 7. Integrity after Task 009 (re-run after the final gate)

| Check | Command | Result |
| --- | --- | --- |
| SQLite DB | `uv run compassio-hash data/db/compassio_dev.sqlite` | `d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385` (unchanged) |
| Financial observations | `scripts/demo_preflight.py` | 93,881 (unchanged); schema revision 0003 |
| DB integrity | `uv run compassio-db verify` | 27/27 audited comparisons match; structural checks ok |
| ML v1 artifact | `compassio-hash models/compassio_ccrc_v1/model.joblib` | `53b226f6…3656` (unchanged) |
| ML v2 artifact | `compassio-hash data/ml_v2/models_v2_dev/…/model.joblib` | `654336052b…8574` (unchanged; still `development_candidate`, not in the trusted registry) |
| Frozen split | `uv run compassio-ml verify-frozen` | "Frozen inputs match lock" |
| Sealed evaluations | `uv run compassio-v2 verify-baseline` | "v1 baseline intact" (not re-run) |
| Retrievals | `uv run compassio-v2 verify-retrievals` | 5 OK |
| Protected code/config | `git diff main --stat -- services/finance.py db/ packages/ configs/{inference_models.yaml,trusted_model_releases.json,ml_rights_eligibility_v2.yaml} data/manifests` | no changes |
| Contracts | `uv run python scripts/generate_api_types.py --check` | up to date (TS types + OpenAPI) |

No data was acquired, no model trained or re-evaluated, no financial observation changed.

## 8. Gates (`bash scripts/check.sh` with the ML v2 test environment, commit `96d7b8a`)

| Gate | Result |
| --- | --- |
| `uv sync --locked`, ruff check, ruff format --check | pass |
| mypy (strict) | Success: no issues found in 220 source files |
| pytest | **792 passed, 2 skipped** in 505 s |
| web: pnpm install --frozen-lockfile, lint, typecheck, build | pass |

Expected skips: PostgreSQL execution test (`COMPASSIO_TEST_POSTGRES_URL` unset; no server
available) and `test_local_ml_v2.py:116` (no human worksheets issued). Real local-server smoke:
section 5. PostgreSQL: compile-only checks pass; execution not verified.

## 9. Remaining blockers and limitations

- **Runtime artifacts are git-ignored.** A clone needs the five files in section 4 copied in
  by hand (or demo on this machine). They must not be uploaded publicly.
- **Organizer authorization** is user-reported, verbal, not independently verified, and not a
  licence clearance; event dates are unknown (`valid_from`/`valid_until` null). Public
  deployment, redistribution and commercial use remain out of scope.
- **PostgreSQL** execution is not verified (no server, Docker or WSL; compile-only checks pass).
- **Single worker only** (rate limiter and review write lock are in-process).
- The screening refusal message still says "local development mode" although event mode also
  allows screening (wording only).
- Model preload logs go to the `compassio_api` logger, which uvicorn's default config does not
  print at INFO; failures appear as ERROR via Python's last-resort handler.
- CFU ids are row positions in the CFU export (stable for the pinned DB only).

## 10. Promotion audit fix (2026-11-11)

The final promotion audit found one defect in the Task 009 middleware order, confirmed by a
reproduction before any change:

- `CORSMiddleware` was registered *inside* the new hardening middleware, so early 413
  (`request_too_large`), 429 (`rate_limited`) and event-mode 403 (`event_access_local_only`)
  responses had no `Access-Control-Allow-Origin` header. A browser frontend on
  `localhost:3000` would see an opaque CORS failure instead of the JSON error.
- CORS preflight `OPTIONS` requests to `/api/v1/screening/*` counted against the screening rate
  limit (reproduced: the third preflight returned 429 with a limit of 2), halving the effective
  limit for browsers and making a rate-limited preflight fail.

**Fix:** `main.py` adds `CORSMiddleware` last (outermost layer); `ScreeningRateLimit` ignores
`OPTIONS`. No business logic, schema or response body changed. Regression tests:
`test_early_rejections_carry_cors_headers_and_preflights_are_not_rate_limited` and
`test_event_guard_rejection_carries_cors_headers` (`tests/api/test_hardening.py`).
