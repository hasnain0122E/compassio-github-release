# Local demo runbook (Windows PowerShell)

Verified on 2026-11-10 (Task 009) on Windows 11 Pro, Intel Core i7-10750H, 15.8 GB RAM,
Python 3.12.15 (uv-managed), uv 0.13.0, Node 24.19.0, pnpm 11.21.0. Every command below was run;
results are in `docs/phases/task009_completion_report.md`.

## 1. The API entry point

The ASGI application is **`compassio_api.main:app`**:

- `apps/api/pyproject.toml` builds the package `compassio_api` from `apps/api/src/compassio_api`;
  the uv workspace installs it into `.venv`.
- `apps/api/src/compassio_api/main.py` defines `create_app()` and the module-level `app`.
- `apps.api.main:app` **does not work**: `apps/` and `apps/api/` are not Python packages and
  there is no `apps/api/main.py`, so uvicorn raises an import error.

Proven by live runs: `uv run uvicorn compassio_api.main:app --host 127.0.0.1 --port 8020`
from a clean checkout served all 27 smoke requests (section 5).

## 2. What must be on the demo machine

A `git clone` contains all code, configs and docs, but **not** the git-ignored runtime
artifacts. These five files are the complete runtime data set (verified experimentally:
a fresh `git worktree` plus only these files ran the whole journey, ML v1 and ML v2 included,
with no `COMPASSIO_V2_*` / `COMPASSIO_DATA_ROOT` variables and dependencies installed with
`uv sync --locked --offline`):

| File (relative to the repo root) | Size | SHA-256 (pinned) |
| --- | --- | --- |
| `data/db/compassio_dev.sqlite` | 220 MB | `d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385` |
| `models/compassio_ccrc_v1/model.joblib` | 3.5 MB (dir) | `53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656` |
| `models/compassio_ccrc_v1/release_manifest.json` | small | checked by the loader |
| `data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/model.joblib` | 1.6 MB (dir) | `654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574` |
| `data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/candidate_manifest.json` | small | checked by the loader |

**Not needed to run the API:** `data/raw/`, `data/ml_v2/external_raw/` (the ML v2 raw training
inputs, including the `compassio-ml-v2` worktree), `data/processed/`, `experiments/`,
`artifacts/`. They are needed only to rebuild or re-verify datasets and models
(`verify-frozen`, `verify-baseline`, `verify-retrievals`, the `local_data` tests).

**Moving the files (local only, checksum-verified):** the best option is to demo on the machine
that already has them. Otherwise use `scripts/runtime_artifacts.py` with a local drive (USB):

```powershell
# On the source laptop (repo root): verify, copy to the drive, re-verify, write SHA256SUMS.txt
uv run python scripts/runtime_artifacts.py export --dest E:\compassio_runtime
# On the target laptop (repo root of a clone at the frozen tag): verify the drive, copy, re-verify
uv run python scripts/runtime_artifacts.py import --src E:\compassio_runtime
uv run python scripts/runtime_artifacts.py verify
uv run python scripts/demo_preflight.py
```

`import` never overwrites an existing file with a different checksum (it stops with
`REFUSED`). Never commit the files, put them in a public repository or cloud service, or send
them to an external service (`docs/hackathon/data_permission_scope.md`). Do not copy the raw
ML v2 training data; it is not needed for prediction.

**Offline:**
- *Installation:* after one online `uv sync --locked` and `pnpm install --frozen-lockfile` on
  the demo machine, `uv sync --locked --offline` and `pnpm install --frozen-lockfile --offline`
  succeed from the local caches (both verified on 2026-11-11). This is an offline-*install*
  test from cache, not a disconnected machine.
- *Runtime:* the API ran the full smoke journey with `UV_OFFLINE=1`, and sampling the server
  process's TCP connections during the run (149 samples) showed **no non-loopback
  connection**. The web app uses no remote fonts or URLs. A run with the network adapter
  physically disabled was **not** performed (it needs the operator to switch Wi-Fi off): do that
  once on the demo laptop before the event.

## 3. Commands

Run from the repository root in PowerShell.

```powershell
# 3.1 Install (once, online)
uv sync --locked
cd apps\web; pnpm install --frozen-lockfile; cd ..\..

# 3.2 Check the runtime artifacts (read-only; exit 1 on any problem)
uv run python scripts/demo_preflight.py

# 3.3 Start the API: event mode + ML v2 authorized local demo + model preload, 127.0.0.1:8000
powershell -ExecutionPolicy Bypass -File scripts\start_api.ps1
#   variants: -Mode local (local_development) | -NoMlV2 (ML v1 only) | -NoPreload | -Port 8001

# 3.4 Start the existing frontend (second terminal) at http://127.0.0.1:3000
powershell -ExecutionPolicy Bypass -File scripts\start_web.ps1

# 3.5 Smoke test the running API (third terminal); also warms the analytics caches
uv run python scripts/smoke_api.py --base http://127.0.0.1:8000
```

`start_api.ps1` is equivalent to:

```powershell
$env:COMPASSIO_ENVIRONMENT = "development"
$env:COMPASSIO_SOURCE_DATA_ACCESS = "hackathon_event"      # or local_development
$env:COMPASSIO_EVENT_AUTHORIZATION = "battleverse_2026"
$env:COMPASSIO_ML_V2_LOCAL_DEMO = "true"
$env:COMPASSIO_PRELOAD_MODELS = "true"
uv run uvicorn compassio_api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

The SQLite database needs no configuration: the default `COMPASSIO_DATABASE_URL` is
`sqlite:///data/db/compassio_dev.sqlite` relative to the repository root (so start the API
from the root). The API opens it **read-only** (`mode=ro`).

Interactive API docs: http://127.0.0.1:8000/docs (OpenAPI JSON at `/openapi.json`; a committed
copy is `docs/api/openapi.json`).

## 4. Rules while demoing

- **One worker only.** The screening rate limiter and the review store's write lock are
  in-process; multiple workers are not supported or tested.
- **Bind 127.0.0.1 only.** Event mode refuses non-loopback clients anyway
  (403 `event_access_local_only`). Never use `--host 0.0.0.0`.
- **Never set `COMPASSIO_ENVIRONMENT=production`** for the demo: production always fails
  closed (403 on source data, no screening).
- **Review writes** (saving screenings) stay disabled unless `COMPASSIO_REVIEW_API_TOKEN` is set;
  the demo does not need them.
- Show the access notice and the source attributions on screen (data permission scope §4).

## 5. Tests and checks

```powershell
uv run pytest -m "not local_data"            # artificial-data suite (no real files needed)
uv run pytest                                # full suite (needs the real data; see below)
bash scripts/check.sh                        # every gate (Git Bash), or:
powershell -ExecutionPolicy Bypass -File scripts\check.ps1
uv run python scripts/generate_api_types.py --check   # TS types + OpenAPI fresh
uv run compassio-db verify                   # 27 audited figures (read-only)
uv run python scripts/bench_api.py --base http://127.0.0.1:8000   # latency profile
```

The full suite's ML v2 tests read the external training inputs and need, in the shell:
`COMPASSIO_DATA_ROOT=<repo>\data`, `COMPASSIO_V1_PROJECT_ROOT=<repo>`,
`COMPASSIO_V2_OUTPUT_ROOT=<repo>\data\ml_v2` and
`COMPASSIO_V2_EXTERNAL_INPUT_ROOT=<ml worktree>\data\ml_v2\external_raw`. Without them those
tests skip. The API itself never needs them.

## 6. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `ModuleNotFoundError: apps` | Wrong entry point: use `compassio_api.main:app` |
| Preflight `FAIL database present` | Copy `data/db/compassio_dev.sqlite` (section 2) |
| 503 `database_not_ready` | API not started from the repo root, or DB missing |
| 503 `model_unavailable` | Model file missing or hash mismatch; run the preflight |
| Startup error `COMPASSIO_EVENT_AUTHORIZATION` / `EventConfigError` | Event mode needs a valid entry in `configs/event_data_authorizations.yaml` |
| 403 `source_rights_not_cleared` | Running in `public`/production mode, or the event window (if set) is not active |
| 403 `ml_v2_demo_not_authorized` | Set `COMPASSIO_ML_V2_LOCAL_DEMO=true` with `COMPASSIO_ENVIRONMENT=development` |
| 429 `rate_limited` | More than 60 screening requests per minute from one client; wait `Retry-After` seconds |
| Browser CORS error | Frontend must run on `http://localhost:3000` or `http://127.0.0.1:3000` (or set `COMPASSIO_CORS_ORIGINS`) |
| Server keeps running after closing a script window | Stop it with Ctrl+C in its window; on Windows, killing only the listening process can leave `uv`/shim parents alive. `taskkill /F /T /PID <uv.exe pid>` stops the whole tree |
| First ML v1 request ~5 s | Preload disabled; start with preload (default in `start_api.ps1`) |
