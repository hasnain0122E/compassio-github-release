# Task 013 deployment security review

**Disposition:** suitable for further deployment rehearsal with production gates;
not approved as a publicly serving canonical-data/ML product. No cloud resources,
secrets, private artifact uploads or billable services were created in this task.

## Preserved and added controls

- Canonical API engine opens SQLite `mode=ro`. Five pinned files are unchanged;
  no migration, ingestion, retraining or financial normalization runs at startup.
- All existing source access, restricted-source exclusion, model-input rights,
  frozen-loader SHA/fingerprint, typed validation/errors, C09 opt-in and C11
  opt-in behavior remain. No wildcard source clearance or cloud development mode.
- Single Uvicorn worker; body cap 262144 bytes; exact configured frontend CORS
  origins; HTTPS validated by cloud launcher; Vercel rejects missing/insecure API
  origins. CORS is browser policy, **not visitor authorization**.
- `--no-proxy-headers` prevents arbitrary `X-Forwarded-For` from becoming limiter
  identity. C11 stays bounded and returns typed 429/Retry-After. Provider proxy
  clients may share a bucket; no unverified trusted proxy rule was added.
- Default Docker context allowlists source/config only. Git/data/model/secret
  trees are excluded. The image runs non-root, with one BLAS/OpenMP thread, no
  acquisition tools invoked, no per-request dependency installation.
- Production `/docs`, `/redoc`, `/openapi.json` disabled; health is liveness only.
  Existing local API docs and Windows launchers remain available.
- Review writes stay disabled without their separate token; cloud launcher
  rejects a configured review token. Visitors retain browser-local shortlists.
- Private provisioning is opt-in and needs an evidenced transfer receipt. Exact
  relative-path allowlist, HTTPS, redirect rejection, streamed size caps, pinned
  hashes, atomic publication, read-only files and full DB audit protect loading.
  Existing different bytes fail; no synthetic fallback. Exception output is
  redacted because signed download URLs are secrets.
- There is no static artifact mount, raw database/model route or public download
  credential. Private download locations belong only in provider secret files.
  UI guidance continues to identify model labels as human-review signals, not
  proven climate impact, finance verification or funding approval.

## Unresolved boundaries and evidence

The recorded organizer permission is local judging only, with no event dates
set, and excludes cloud/public redistribution. All source rights stay
`not_reviewed`. User will handle review; this is not recorded as already
completed. Neither private storage nor nonprofit status grants public serving
rights. No source or field subset has been claimed as cleared. Implement the
event audience/time/source/model policy only after its actual scope is known;
do not flip production to development. Provisioning approval covers transfer
only and never changes application authorization.

Linux cgroup memory may include SQLite page cache; Windows 326.715 MiB peak
working set does not prove a 512 MB Render fit. Render sleep discards downloads,
expired signed URLs fail cold restart, and 0.1 CPU can delay health readiness.
Provider proxy collapse is safe but can reduce multi-judge availability. These
need real provider verification, not relaxed limits or forwarded trust.

No connected provider/store or Docker runtime was available. Full container
build, remote transfer, actual TLS, provider IP behavior, billing controls,
idle restart and external browser verification remain open. R2 has free quotas
but usage billing; no account was enabled. Render bandwidth/build overages can
bill accounts with payment methods; choose free capacity and verify controls.

Tests: 10 deployment boundary/provisioning tests; targeted canonical inference,
source-rights, event, body-size, C11 and integration checks; generated contracts;
27 canonical DB comparisons; 15 real-data production-frontend browser journeys;
TCP CORS/413/429/spoof/recovery/concurrency checks. Actual production requests
correctly deny data and inference. No live deployment success is asserted.
