# Backend freeze report: BATTLEVERSE 2026

Compassio's backend is frozen for Task 010 (frontend at the venue). Date: 2026-11-11. Local
only: nothing was pushed, released or deployed (the repository has no remote configured).

## 1. Final commit and tag

| Item | Value |
| --- | --- |
| Final `main` | the commit that adds this report (message "Backend freeze report"); its parent is `be25d41` |
| Tag | `backend-ready-for-battleverse` (annotated, local), pointing at that commit: `git rev-parse backend-ready-for-battleverse^{commit}` |
| Gated code tree | `be25d41`; the tagged commit differs from it only by this report and the matching `CLAUDE.md` / phase-plan lines (documentation) |
| History since Task 008 `main` (`62a1a17`) | `bd08037`, `96d7b8a`, `89c1252` (Task 009), `5a7a08d` (promotion audit fix), `be25d41` (freeze prep), freeze report |
| Safety branches | `safety/task009-pre-promotion-main-62a1a17`, `safety/task008-pre-promotion-main-12f536a`, `safety/task007-pre-promotion-main-7e8422b`, `safety/task006-int-final-main-bd2fe308` |
| Merge method | fast-forward only (`git merge --ff-only`); no force, squash or rebase |

## 2. Promotion audit findings

- **One defect found and fixed before the merge** (`5a7a08d`): `CORSMiddleware` sat inside the
  Task 009 hardening middleware. Early 413/429/event-403 responses therefore had no
  `Access-Control-Allow-Origin` header (the browser frontend would get an opaque CORS error),
  and CORS preflights consumed screening rate-limit slots (third preflight → 429 with a limit
  of 2). Both were reproduced first. Fix: CORS is the outermost layer; `OPTIONS` is never rate
  limited. Two regression tests. Live: a 300,000-byte POST with `Origin: http://localhost:3000`
  returned 413 **with** `access-control-allow-origin`.
- **Stale contract example fixed:** `docs/hackathon/demo_api_examples.md` showed pre-envelope
  422 bodies; it was regenerated from the promoted `main`.
- **No other material issue.** Protected finance code (`services/finance.py`,
  `finance_rows.py`, `services/decision/`), DB code and migrations, inference code, model
  registries, ML configs, frozen evaluation configs, `packages/` and `data/manifests/` have
  **no diff** since Task 008's `main`. No credentials (pattern scan), no database, model,
  pickle, parquet or spreadsheet files are tracked (`git ls-files`). The only
  `gcf_historical` text in the new docs is the refused-request example (404).
- **Noted, not changed:** `demo_api_examples.md` and the earlier Task 008 docs contain trimmed
  excerpts (titles, amounts) of `not_reviewed` source records. That is acceptable in this local
  repository but must be reviewed before the repository is ever published.

## 3. Test results

`bash scripts/check.sh` with the ML v2 test environment, on the gated trees:

| Tree | ruff / format | mypy (strict) | pytest | web lint / typecheck / build |
| --- | --- | --- | --- | --- |
| `5a7a08d` (Task 009 final, before the merge) | pass | 220 files, no issues | **794 passed, 2 skipped** (597 s) | pass |
| `be25d41` (freeze tree) | pass | 220 files, no issues | **794 passed, 2 skipped** (646 s) | pass |

**Expected skips (2):** `tests/api/test_postgres_portability.py:45` (PostgreSQL execution:
`COMPASSIO_TEST_POSTGRES_URL` unset, no server available) and `tests/test_local_ml_v2.py:116`
(no human review worksheets issued). Without the ML v2 test environment variables, 6 more ML v2
tests skip; the API never needs those variables.

**Integrity (re-run on the freeze tree):**

| Check | Result |
| --- | --- |
| `uv run compassio-db verify` | ok; 27/27 audited comparisons; structural ok; restricted `[gcf_historical]`; cleared for public display `[]` |
| `uv run compassio-ml verify-frozen` | Frozen inputs match lock |
| `uv run compassio-v2 verify-baseline` | 11 PASS (incl. 3 consumed tests, hashes ok, not re-run); "v1 baseline intact" |
| `uv run compassio-v2 verify-retrievals` | 5 OK |
| `uv run python scripts/runtime_artifacts.py verify` | All 5 runtime artifacts verified |
| `uv run python scripts/demo_preflight.py` | Preflight OK; 93,881 financial observations; schema 0003 |
| `uv run python scripts/generate_api_types.py --check` | up to date (TS types + OpenAPI) |

## 4. Verified startup commands (PowerShell, repository root)

```powershell
uv sync --locked                                                     # once, online
cd apps\web; pnpm install --frozen-lockfile; cd ..\..                # once, online
uv run python scripts/runtime_artifacts.py verify                    # 5 artifacts, SHA-256
powershell -ExecutionPolicy Bypass -File scripts\start_api.ps1       # API  http://127.0.0.1:8000
powershell -ExecutionPolicy Bypass -File scripts\start_web.ps1       # web  http://127.0.0.1:3000
uv run python scripts/smoke_api.py --base http://127.0.0.1:8000      # 25 checks; warms caches
```

`start_api.ps1` runs the preflight, then
`uv run uvicorn compassio_api.main:app --host 127.0.0.1 --port 8000 --workers 1` with
`hackathon_event` + `battleverse_2026`, `COMPASSIO_ML_V2_LOCAL_DEMO=true`,
`COMPASSIO_PRELOAD_MODELS=true`, `COMPASSIO_ENVIRONMENT=development`. Entry point
`compassio_api.main:app` (never `apps.api.main:app`). Verified on promoted `main` on
2026-11-11: one server process (no worker children), startup complete, smoke 25/25; the web
app served `/` and `/screening` with HTTP 200.

## 5. Runtime artifact checklist (git-ignored; never commit)

| # | Relative destination | Purpose | SHA-256 | Needed at runtime |
| --- | --- | --- | --- | --- |
| 1 | `data/db/compassio_dev.sqlite` (230,395,904 bytes) | Canonical project database, opened read-only | `d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385` | **Yes** (all data routes) |
| 2 | `models/compassio_ccrc_v1/model.joblib` (3,615,411 bytes) | ML v1 trusted research release (fallback engine) | `53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656` | **Yes** for screening (data routes work without it) |
| 3 | `models/compassio_ccrc_v1/release_manifest.json` (4,111 bytes) | ML v1 manifest; the loader checks artifact hash, version and fingerprint | `bc3c8f78c5a42aa434da8c72459cf49e80d8f41300aaa478468802facd595282` | **Yes** with #2 |
| 4 | `data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/model.joblib` (1,650,643 bytes) | ML v2 development candidate (local-demo default engine) | `654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574` | **Yes** for the ML v2 demo |
| 5 | `data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/candidate_manifest.json` (2,477 bytes) | ML v2 manifest; loader checks hash, status and fingerprint | `72b78bbb6eb02679acbbcfc1f90c2feeb13b0b42dbf597d65e4db86701e36ca5` | **Yes** with #4 |

- **Verify locally:** `uv run python scripts/runtime_artifacts.py verify` (all five, pinned) or
  `uv run python scripts/demo_preflight.py` (DB + model artifacts against
  `configs/inference_models.yaml`), or `uv run compassio-hash <path>`.
- **Transfer (local only):** `runtime_artifacts.py export --dest <USB folder>` then, on the
  other laptop, `runtime_artifacts.py import --src <USB folder>` and `verify`. Tested on
  2026-11-11: export (re-hash + `SHA256SUMS.txt`), import into an empty checkout, idempotent
  re-import, and refusal (`REFUSED`) when a destination file differs.
- **Not needed and not to be copied:** `data/raw/`, `data/ml_v2/external_raw/` (ML v2 raw
  training inputs), `data/processed/`, `experiments/`, `artifacts/`. Proven unnecessary for
  prediction by the clean-checkout run (Task 009 report §4).
- Never upload these files to a public repository or cloud service.

## 6. Local demo smoke results (promoted `main`, official script)

`scripts/start_api.ps1` (event mode, ML v2 demo, preload, one worker, `UV_OFFLINE=1`) then
`scripts/smoke_api.py --base http://127.0.0.1:8000`: **27 requests, 25/25 checks passed.**

| Check | Result |
| --- | --- |
| SQLite loads | preflight OK; search `hydropower` PAK → 26 records |
| ML v2 default / ML v1 available | `authorized_local_demo`, default `ml_v2`, fallback `ml_v1`; text scores v2 0.7885, v1 0.9660 |
| Project screening | `aiddata:35266` (ML v2) with source evidence; `gcf_projects:FP085` refused (403) |
| Funding analytics | PAK ADB disbursements 21,549,925,012.94 USD = sum of protected trend points |
| Unsafe duplicate totals | same-package AidData pair and cross-source pair: shown, flagged, `selection_total` null |
| Stable ranking | 31 candidates, fingerprint `149e0721bece…` identical on repeat |
| Budget conservation | 333,333.34 + 333,333.33 + 333,333.33 + 0.00 unallocated = 1,000,000 |
| Rejections | 422 ×4 (incl. `objective_not_supported`, `candidate_set_too_large`), 404 ×2, 403 review write, 413 |
| Production / public | separate server with `COMPASSIO_ENVIRONMENT=production` + `hackathon_event`: data routes 403 `source_rights_not_cleared`, screening 403 `inference_not_authorized`, header `public` |
| One worker | process tree: `uv` → uvicorn shim → one Python server process |

**Offline:** offline *installation* from cache verified (`uv sync --locked --offline`,
`pnpm install --frozen-lockfile --offline`). Offline *runtime* evidenced, not proven by
disconnection: with `UV_OFFLINE=1`, 149 TCP samples of the server process during the smoke run
showed no non-loopback connection; the web app has no remote fonts or URLs. A run with the
network adapter disabled was not performed. Do it once on the demo laptop.

## 7. Security and event-access boundaries

- `hackathon_event` serves only the sources in `configs/event_data_authorizations.yaml`
  (`battleverse_2026`: organizer authorization **verbally confirmed, reported by the team**,
  not independently verified, **not** a licence clearance; event dates unknown → `null`).
- Loopback clients only (403 `event_access_local_only`); `gcf_historical` never served;
  `environment=production` always forces `public` (fail-closed, verified live).
- Not permitted: public deployment, redistribution, commercial use, sending source data to
  external AI services, model training on GCF API/page data.
- Hardening: 413 body limit (262,144 bytes), 429 per-client screening limit (60/min,
  in-process), JSON 500 without details, `{code, message}` 422 envelope without echoed input,
  `nosniff` / `no-referrer` / `no-store` headers, CORS limited to localhost:3000 and
  127.0.0.1:3000 and applied to every response including early rejections.
- Review writes stay disabled without `COMPASSIO_REVIEW_API_TOKEN`; the review store is
  append-only, hash-chained, single-process.
- Every `rights_status` remains `not_reviewed`; no manifest or rights config changed.

## 8. Frontend API contract locations (Task 010 starting point)

| File | Status |
| --- | --- |
| `docs/hackathon/backend_handoff.md` | current (endpoints, ids, pagination, errors, finance and ML fields, demo ids) |
| `docs/hackathon/local_demo_runbook.md` | current (updated for transfer and offline findings) |
| `docs/hackathon/frontend_blueprint.md` | current (eight screens, build order) |
| `docs/hackathon/demo_api_examples.md` | regenerated from promoted `main` |
| `docs/hackathon/data_permission_scope.md` | current |
| `docs/api/openapi.json` | fresh (test `test_committed_openapi_document_is_fresh`) |
| `apps/web/src/lib/api-types.ts` | fresh (test `test_generated_types_match_the_current_openapi_schema`) |

## 9. Known limitations

- Runtime artifacts are git-ignored: a clone needs the five files (section 5).
- PostgreSQL execution is **not verified** (no server, Docker or WSL); compile-only checks pass.
- One API worker only (rate limiter and review write lock are in-process).
- First calls: up to ~2.2 s for 740-candidate ranking and ~0.9 s for the country profile
  (cached afterwards); startup with preload ~8 s.
- Organizer authorization is verbal and user-reported; event dates unset.
- The screening refusal message still says "local development mode" although event mode also
  allows screening (wording).
- Preload success is logged at INFO on the `compassio_api` logger, which uvicorn's default
  logging does not print.
- CFU ids are row positions in the CFU export (stable for the pinned database).
- A physically disconnected run has not been performed.

## 10. May Task 010 begin without backend work?

**Yes.** The frozen `main` contains the complete backend: 33 documented endpoints, generated
types and OpenAPI, startup, preflight, transfer and smoke scripts, all verified. The frontend can
be built against `http://127.0.0.1:8000` immediately. Backend changes during Task 010 should be
limited to defects found while integrating, each with a regression test.
