# Free hosting runbook

## Scope and prerequisites

The checked-in configuration deploys the real code **with production gates**.
Without cleared artifacts/policy, it is a code-only unavailable product, not a
successful live canonical demo. Never use `environment=development` on a cloud
host to bypass the existing gate. No paid service/database is needed or authorized.

Connect Vercel and Render accounts or use their dashboards. Keep the original
integration checkout untouched. Publish only this deployment commit from the
publishing checkout; review `git ls-files data models artifacts` before pushing.

## Vercel

1. Import `Hasnain0122E/compassio-github-release` into a **Hobby** personal project.
2. Select **Next.js**, root **`apps/web`**, **Node 24**, install
   `pnpm install --frozen-lockfile`, build `pnpm build`. The committed
   `packageManager` selects pnpm 11.21.0. Keep framework-default output; no `out/`,
   SPA rewrite, or static export. Keep existing Next routing/configuration.
3. Set public build variable `NEXT_PUBLIC_COMPASSIO_API_URL` to the backend's
   **actual HTTPS origin**, without credentials/path. Do not deploy a placeholder.
   Configure production/preview separately; changing it requires a rebuild.
4. Record the assigned frontend origin, add that exact origin to backend CORS,
   and redeploy. Arbitrary preview domains are deliberately not allowed.
5. Keep judge access consistent with the eventual approved serving audience.
   Verify deep-link refresh at `/projects/aiddata%3A35266`, navigation, assets,
   error pages, mobile and theme after the actual backend is authorized.

## Render

Create a Blueprint from root **`render.yaml`**, or New Web Service with Docker
runtime, repository-root context and `infra/Dockerfile`. Select **Free** instance,
one service, no disk/database/paid add-ons. Auto-deploy is off so changes do not
silently alter the demo. Health check is `/health`; this means liveness only.

Build stages use Python 3.12.15 slim and uv 0.13.0; `uv sync --locked --no-dev`
installs the frozen runtime. Non-root UID 10001 runs:

```sh
python infra/start_api.py
```

The launcher validates production/HTTPS CORS/no review token, binds `0.0.0.0`,
reads `PORT` (default 10000), uses one worker, disables proxy headers/access logs.
The API uses read-only SQLite, lazy verified models and the existing body limiter.
Production interactive docs/OpenAPI routes return 404. Container health script:
`python infra/healthcheck.py`.

| Environment | Value |
|---|---|
| `PORT` | Provider-assigned; do not override in Render |
| `COMPASSIO_ENVIRONMENT` | `production` |
| `COMPASSIO_SOURCE_DATA_ACCESS` | `public` |
| `COMPASSIO_CORS_ORIGINS` | Exact assigned frontend HTTPS origin(s), comma separated |
| `COMPASSIO_ML_V2_LOCAL_DEMO` | `false` |
| `COMPASSIO_PRELOAD_MODELS` | `false` under current disabled-inference scope |
| `COMPASSIO_C09_ENABLED` | `false` under current production scope |
| `COMPASSIO_C11_ENABLED` | `true`, single worker |
| `COMPASSIO_MAX_REQUEST_BODY_BYTES` | `262144` |
| `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS` | `1` in Docker |
| `COMPASSIO_REVIEW_API_TOKEN` | Unset; no public review writes |

`infra/.env.example` contains placeholders only. Do not put secrets in the
Vercel public API URL. Render/Vercel connections do not clear source rights.

## Dormant private runtime provisioning

After genuine **cloud-transfer** review, use an approved private store. Keep raw
files private and out of Git/build context. Record the actual review in provider
secret file `/etc/secrets/cloud-transfer-approval.json` with fields:
`cloud_transfer_approved` (boolean), `evidence_reference`, `reviewed_by`,
`approved_provider`. No fabricated receipt is supplied in the repository.

Provider secret file `/etc/secrets/runtime-downloads.json` must map **exactly**
the five relative paths in `scripts/runtime_artifacts.py:ARTIFACTS` to private
signed HTTPS download URLs. Use single-file responses, no redirects or archives.
Mint URLs whose lifetime covers the event and cold restarts; rotate/redeploy
before expiry. Do not paste them into shell arguments or logs.

Set these provider variables only when transfer is approved:

```text
COMPASSIO_RUNTIME_ROOT=/tmp/compassio-runtime
COMPASSIO_RUNTIME_DOWNLOADS_FILE=/etc/secrets/runtime-downloads.json
COMPASSIO_RUNTIME_APPROVAL_FILE=/etc/secrets/cloud-transfer-approval.json
COMPASSIO_DATABASE_URL=sqlite:////tmp/compassio-runtime/data/db/compassio_dev.sqlite
COMPASSIO_INFERENCE_ROOT=/tmp/compassio-runtime
```

The launcher provisions before binding. Downloads stream to temporary files;
hash mismatch/oversize/redirect/network/DB audit failure aborts startup without
printing signed URLs. Existing matching files are reused; differing files fail.
Read-only canonical audit includes all 27 comparisons and structural checks.
There is no retraining or synthetic fallback. Provisioning **does not enable
production inference or clear public source rights**. Implement the reviewed
production serving policy separately once its actual scope is supplied.

Models deserialize only through existing pinned loaders. The default image
contains no canonical files; `.dockerignore` allowlists code/config plus one
static aggregate report. No model/database download API or static mount exists.

## Local Linux production rehearsal

Docker is not installed in this execution environment, so these steps remain
to be run on Linux/Docker before declaring Render capacity validated:

```sh
docker build -f infra/Dockerfile -t compassio-task013 .
docker run --rm --name compassio-task013 --memory=512m --cpus=0.1 \
  -p 10000:10000 -e PORT=10000 \
  -e COMPASSIO_CORS_ORIGINS=https://YOUR-ACTUAL-FRONTEND \
  -e COMPASSIO_C11_ENABLED=true compassio-task013
docker stats --no-stream compassio-task013
curl --fail http://127.0.0.1:10000/health
```

Without attached artifacts data routes return typed 503; with uncleared canonical
data they return 403. Both are honest denials. A 200 health check is not product
readiness. For approved private transfer, mount the secret files read-only and
pass the five variables above; do not put binaries in the image. Capture startup,
`memory.current`, `memory.peak`, CPU time, inference under load, OOM events and
restarts with the complete runtime. Include warm cache and repeated requests.

Portable local verification from repository root:

```sh
uv sync --locked
uv run python scripts/runtime_artifacts.py verify
uv run python scripts/demo_preflight.py --json
uv run compassio-db verify --report artifacts/task013/integrity.json
uv run python scripts/deployment_capacity.py --out artifacts/task013/capacity.json
uv run python scripts/generate_api_types.py --check
uv run pytest -p no:cacheprovider -m 'not local_data'
cd apps/web
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm start
```

For the authorized local browser demo, retain the existing loopback API launchers
and enable C09/C11 explicitly. Linux equivalent is one Uvicorn worker bound to
`127.0.0.1`, `--no-proxy-headers`, development/local access plus ML v2 demo flag.
Set the frontend API origin before building and `COMPASSIO_WEB_URL` /
`COMPASSIO_API_URL` before `pnpm test:e2e`. Browser executable can be supplied
with `COMPASSIO_BROWSER_PATH`; install Playwright Chromium otherwise.

## External acceptance, recovery and redeploy

After actual URLs and authorized serving exist:

```sh
uv run python scripts/verify_public_demo.py --web https://ACTUAL-FRONTEND \
  --api https://ACTUAL-BACKEND --out artifacts/task013/public.json
```

The HTTPS probe deliberately fails an inference-disabled/data-unavailable
deployment. It verifies model hashes and CORS; it does not replace browser
journeys. Run browser tests on actual URLs, deep refresh, and multiple devices.
Then leave Render idle for **over 15 minutes**, revisit from another device,
record wake/download/model times, and repeat the journey. Do not use keep-alive
traffic to conceal the free-tier cold start. Check usage and avoid overage billing.

C11 intentionally keys by TCP peer with forwarded headers disabled. Render's
proxy may collapse clients into one bucket; test simultaneous devices plus
spoofed headers. Keep that conservative shared limit unless a documented trusted
proxy design is separately implemented. Never set forwarded trust to `*`.

On failure: inspect provider logs without logging secrets, keep denials, check
signed URL expiry/hash/config, redeploy the reviewed commit through Render's
Manual Deploy and Vercel Redeploy (after changing baked API URL). Use provider
rollback to a known reviewed deployment if available. Render Free retains only
two previous rollback targets. Never regenerate the DB or retrain to repair a
deployment. Never upgrade to paid capacity automatically. If Linux/Render OOMs,
retain evidence and evaluate another account-eligible genuinely free host;
Hugging Face new Docker Spaces currently need a paid plan and are not that path.
