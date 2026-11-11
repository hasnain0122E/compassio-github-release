# C11: Compassio Availability Shield

The organizer asks for a sliding-window or token-bucket defense against 200 rapid
requests/second while preserving legitimate traffic. This isolated challenge adds
an opt-in, process-local token-bucket admission policy to the existing FastAPI app.
It does not change the default runtime or authorize public inference.

## Frozen audit

The clean starting branch was `challenge/c11-availability-shield`, HEAD
`8c083509e324d76aafc7ee097dc4345a94314afd`. The annotated tag
`backend-ready-for-battleverse` peels to that commit. No other worktree was edited.

Task 009 already supplies pure ASGI body-size validation (declared and chunked),
loopback-only event access, security headers and a screening sliding window:
60 requests/minute/ASGI peer by default, 0 disables. It skips OPTIONS and uses
monotonic time but retains identity keys indefinitely. All screening paths share
that budget, including errors. It has no cross-peer ceiling or read-route budget.
Its single ASGI event-loop execution has no await during mutation, but it does not
provide a lock for shared threaded access. It is documented for one worker.

The app adds CORS last/outermost, preserving browser access to 413/429/403 bodies.
Errors use `{code, message}` (validation can add detail). Event access checks
`scope.client`, not headers; the app has no explicit trusted-proxy configuration.
Uvicorn must therefore run with `--no-proxy-headers` in this demo.

Screening routes are synchronous FastAPI handlers, dispatched to worker threads.
Models are lazy-loaded through pinned registry/checksum verification; optional
preloading is permission-gated. Screening permissions remain in existing services;
review writes additionally require the existing review token. SQLite connections
open lazily with `mode=ro`; the separate review database is untouched by this test.

The mixed baseline exposed `SingletonThreadPool` closing active SQLite connections
as requests used more threads: real 500/transport failures, not throttling. C11
opts into `QueuePool` (5 persistent + 10 overflow, 2s checkout timeout) for the
existing read-only connection creator. Default pool behavior is unchanged.

## Implementation

`core/availability.py` admits before route dependencies, inference and queries.
`create_app()` selects either C11 or the existing limiter, never both. CORS, size,
event and security middleware remain outside admission. Separate screening/read
budgets and reserved identity capacity prevent screening alone exhausting reads.
The limiter uses no sleeps, external services or new runtime dependencies.

See [policy](c11_rate_limit_policy.md), [threat model](c11_threat_model.md),
[protocol](c11_experiment_protocol.md), [results](c11_results.md) and
[scorecard](c11_scorecard.md). This is a bounded fixture experiment, not a claim
about canonical-model throughput or production deployment readiness.
