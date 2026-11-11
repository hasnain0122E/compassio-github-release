# Task 013 deployment report — 2026-11-12

**Outcome: deployment implementation and local verification completed; the public
product is NOT deployed. No public HTTPS URL, cloud upload or paid resource was created.**
The Vercel and Render integrations were discovered but are not connected. The user
will handle outstanding source/model rights review; no approval has been invented.

## Feasibility assessment

The real application is Next.js **16.4.5**, React 19.3.0, App Router, with Cache
Components and partial prerendering. `/projects/[id]` needs the Next server;
this is not an `out/` static export. Existing product UI and financial logic are
unchanged. pnpm **11.21.0**, `apps/web/pnpm-lock.yaml`, and Node 24 are the intended
frontend build environment. Vercel root is `apps/web`, install is
`pnpm install --frozen-lockfile`, build is `pnpm build`, output is Next's default.
`apps/web/vercel.json` records this. Hosted builds reject missing, non-HTTPS,
credential-bearing or loopback API origins.

The backend entrypoint is **`compassio_api.main:app`**, from the repository root.
Python is pinned to **3.12**, tested 3.12.15; `uv.lock` is authoritative. Tested
versions include FastAPI 0.162.2, Uvicorn 0.54.0, SQLAlchemy 2.1.8,
scikit-learn 1.9.1, NumPy 2.5.4 and SciPy 1.18.1. The image installs locked runtime
dependencies once, without dev packages or optional embedding dependencies.
No training/acquisition command runs at startup or inference.

| Frozen file | Exact bytes | MiB |
|---|---:|---:|
| Canonical SQLite | 230395904 | 219.723 |
| ML v1 joblib | 3615411 | 3.448 |
| v1 release manifest | 4111 | 0.004 |
| ML v2 joblib | 1650643 | 1.574 |
| v2 candidate manifest | 2477 | 0.002 |

All five SHA-256 values match `scripts/runtime_artifacts.py`. Both model hashes
also match `configs/inference_models.yaml`. Files were copied **locally only**
from the integration checkout, without modifying it. SQLite remains byte-identical:
**26,499 projects, 93,881 financial observations, schema 0003**, all **27** canonical
comparisons and structural checks pass, SQLite integrity is `ok`, foreign-key
violations are zero. No subset or financial conversion was made. Original text
Decimal amounts, unknowns, currencies and source boundaries are retained.

## Measured resource evidence

Final `scripts/deployment_capacity.py` run used real TCP requests to isolated,
single-worker loopback processes on Windows 11, Python 3.12.15, 12 logical CPUs,
with BLAS/OpenMP threads limited to one. Windows interpreter PID is measured,
not the small venv launcher. RSS is sampled every 20 ms. These are local resource
measurements, not Linux/provider benchmarks or model evaluation results.

| Measurement | Actual local result |
|---|---:|
| Production liveness startup / CPU time | 2.7842 s / 1.796875 CPU s |
| Local authorized API startup / CPU time | 2.1139 s / 1.71875 CPU s |
| Local startup working set | 85.84 MiB |
| Peak sampled working set with both models | **326.715 MiB** |
| Working set after v1 / after v2 | 278.14 / 283.14 MiB |
| First v1 inference, including cold imports/load | 7.0448 s |
| First v2 inference, after v1 was loaded | 1.6886 s |
| Subsequent v1 requests | 0.0117–0.0179 s |
| Subsequent v2 requests | 0.0115–0.0306 s |
| Three v1 / three v2 requests CPU time | 5.75 / 1.640625 CPU s |
| Pakistan discovery / keyword search | 0.1165 / 0.0414 s |

Render Free currently provides **512 MB, 0.1 CPU**. Local process memory is below
that RAM figure, but this is **not a capacity pass**: Linux cgroups include
filesystem cache and dependencies/platform overhead differ. Peak process memory
plus one full SQLite file's cached pages is approximately **546 MiB**; clean
file cache is reclaimable, but a constrained Linux load test is still necessary.
At 0.1 CPU, cold imports and model verification can take substantially longer;
CPU time alone implies tens of seconds under throttling, before downloads.
No Render instance was available to measure OOM behavior or startup deadlines.

Render sleeps after 15 idle minutes, may take about a minute to wake, and loses
runtime filesystem changes on sleep/restart/redeploy. Every cold boot can require
another roughly **236 MB** private download plus hash/DB validation. Free has no
persistent disk and 750 workspace instance-hours/month. Bandwidth/build overages
can be billable when a payment method is present: do not enable paid capacity or
overage billing. Verify account usage/spend controls before deployment.
[Render Free](https://render.com/docs/free),
[compute limits](https://render.com/docs/compute-plans), checked 2026-11-12.

Vercel Hobby permits personal/noncommercial use, with usage caps; select Hobby
and confirm account allowance before deployment.
[Vercel Hobby](https://vercel.com/docs/plans/hobby).
Hugging Face CPU Basic lists 2 CPUs/16 GB but current new Docker/Gradio compute
Spaces require a paid plan; it is **not a verified zero-cost fallback**.
[Current Spaces requirements](https://huggingface.co/docs/huggingface_hub/guides/manage-spaces).
No alternate host was activated; Render has not yet been tested or failed.

## Serving permissions and artifact design

`configs/event_data_authorizations.yaml` records only local judging and explicitly
excludes public deployment and redistribution. All source rights remain
`not_reviewed`; there is no approved public field subset. The user's instruction
to handle remaining approval is not recorded as completed clearance. Production
continues to force `public`, deny uncleared data, and disable ML inference/C09.
No development-mode cloud bypass or new public authorization mode was introduced.
An actual approved cloud-serving policy is therefore still an implementation
prerequisite for the full live product, not merely an environment-variable toggle.

| Option | Assessment |
|---|---|
| A: provider-private files | Render Free has no persistent disk; no connected private artifact service verified. Image delivery needs approved cloud transfer. |
| B: private object storage | Implemented dormant HTTPS per-file provisioning; exact hashes, bounded streamed downloads, no redirects, atomic publication, read-only files, SQLite plus canonical audits. Requires approved private storage and provider secret files. |
| C: derived serving database | Not selected: no approved source/field subset exists; changing canonical records would violate the preservation requirement. |
| D: private image | Technically avoids boot downloads, but transfer is not yet cleared and image registry/account quotas/access were not verified. Default image deliberately excludes binaries. |

Cloudflare R2 Standard lists 10 GB-month storage, 1 million Class A and 10 million
Class B operations/month free, with free egress. The five files fit this allowance,
but R2 is usage-billed beyond it; **no R2 billing account or bucket was activated**.
Use an already approved storage account only after reviewing billing controls;
do not interpret an allowance as authorization to activate billable infrastructure.
[R2 pricing](https://developers.cloudflare.com/r2/pricing/).

`infra/provision_runtime.py` accepts private signed HTTPS URLs from a provider
secret file and a separate cloud-transfer approval receipt. That receipt does
not grant public data/model serving. No URL, token, artifact or invented approval
is tracked. A corrupt download is never published. Existing differing files
are never overwritten. Full remote download and Linux Docker execution remain
untested because no approved connected storage/provider or local Docker exists.

## Verification and remaining blockers

- Python baseline: **829 passed, 1 skipped, 81 deselected** (`not local_data`).
  PostgreSQL skip is expected; SQLite is the deployment target.
- Targeted canonical inference/decision/security run: **99 passed, 16 skipped**;
  C05 experiment inputs are absent. This overlaps baseline tests; counts are not added.
- New cloud boundary/provisioning tests: **10 passed**, including canonical
  no-download verification and rejection/cleanup of corrupt bytes.
- Frontend lint, typecheck, **16 unit tests**, optimized build and generated API
  contract checks pass. Backend changed-file lint/type checks pass.
  The hosted-build guard rejects an unset API origin and accepts a valid HTTPS
  origin in a compile-only rehearsal; no placeholder origin was deployed.
- **15/15 Chrome browser journeys** pass against production Next and the real
  authorized **development-mode loopback backend**. This is not production-authorized
  inference: the production backend correctly returns 403 instead.
- TCP capacity/security probe passes: real v1/v2 hashes/output, concurrent reads,
  repeated calls, 413, CORS allow/deny, spoofed forwarded-IP bursts causing 429,
  and post-limit recovery. No mock API successes.
- First browser attempt lacked Playwright's expected bundled browser; rerun with
  installed Chrome passed. One targeted pytest run encountered Windows sandbox
  temporary/cache permissions; rerun outside sandbox without cache passed.
- Local Docker/Linux build, provider cold restart, external HTTPS, public browser
  journey and private remote transfer: **NOT RUN**. No public URLs exist to test.

Required finish: connect hosting accounts; resolve source/model cloud transfer
and serving scope; implement/test that approved production policy; supply private
storage if approved; run constrained Linux/provider measurements; then deploy
and verify public HTTPS/browser journeys. See the runbook and verification ledger.
The deployment commit is the commit adding this report; it does not rewrite history.
