# C11 bounded local experiment protocol

Run from this C11 worktree on Windows with Python 3.12 and `uv sync --locked`.
No public address is accepted by the CLI. The parent reserves/checks port 18761,
starts its own disposable loopback-only one-worker child, disables proxy headers,
waits for health, verifies source-IP binding and stops that child after each run.
Do not concurrently run CPU-heavy checks while collecting final timing evidence.

```powershell
uv run python scripts/c11_benchmark.py --mode baseline --seconds 4 --repeat 2
uv run python scripts/c11_benchmark.py --mode shield --seconds 4 --repeat 2
uv run python scripts/c11_report.py
```

The baseline imports API source exported from the exact frozen Git commit into
`artifacts/c11/frozen`, not from another checkout or branch. Shield imports the C11
working source. Both use the same existing tiny artificial v1/v2 model fixtures,
real guarded loaders, preload policy, artificial migrated/seeded SQLite database,
request body and real endpoints. v2 is the local-demo default. No canonical data
or model artifact is available in this worktree. Fixture predictions are not ML
evaluation evidence. Hashes before/after cover fixture models, database and pinned
repository registries; no review write is requested.

Each scenario offers 200 bot rps at monotonic 5ms deadlines for four seconds,
plus four legitimate rps (alternating project reads and text screening). A maximum
64 requests are in flight and at most 128 dispatch tasks are pending; clients use
pooled TCP connections bound to distinct
verified loopback source IPs. Backpressure can reduce actual generation below
target; record actual send timestamps rather than equating scheduled and sent.
No sleeps simulate throttling; only workload pacing/recovery observation waits.

Four scenarios: single screening peer; four screening peers; four peers mixing
50% project GET and 50% screening POST; single shared-IP peer with legitimate
traffic. Each ordinarily repeats twice on a fresh server. If ten 500, timeout or
transport failures are observed, or 128 tasks remain pending, stop scheduling,
drain bounded outstanding work,
record the partial run and omit further repeats of that unsafe scenario. These
outcomes are never counted as limiter rejections. Maximum CLI duration is ten
seconds/scenario and three repeats; defaults total at most 13,056 load requests
across both modes, plus bounded readiness and recovery probes.

Recovery starts after load requests drain: poll the attacking peer every 100ms
for up to three seconds. Null recovery is censored; transport errors are recorded
separately. Baseline's minute-long window need not recover in this short interval.
This measures a first successful post-burst request, not unlimited restored capacity.

Raw receipts include request send times, all response codes/transport categories,
p50/p95/p99 across completed attempts, legitimate success fraction, actual send
rate `(N-1)/(last-first)`, completed rate over workload/drain time, positive final
dispatch delay (`max_scheduling_lag_ms`, not the peak across all ticks), recovery,
process CPU seconds including startup and shutdown RSS
and peak RSS. CPU covers the uvicorn serve interval, including lifespan model
preload; interpreter/import bootstrap before that interval is excluded. It is not
an isolated workload CPU percentage. Per-role
metrics include failed attempts; success-only latency is available from raw rows.
The harness-only `X-C11-Load` header marks requests for independent server-ingress
count/timing; it is diagnostic metadata and is never an admission identity or
authorization input. State high-water/admit/reject counts come from the C11 object at stop.
Separate fake-clock tests verify expiration and 10,000-key pressure without a
120-second live wait. RSS includes models/server, not only limiter memory.

Stop safely with Ctrl+C in the parent terminal: its `finally` creates the child's
stop file and waits up to ten seconds, then kills only its own child if necessary.
If the parent terminal is forcibly closed, create the active process receipt's
`.stop` companion file in `artifacts/c11` (e.g.
`New-Item artifacts/c11/shield-0-single-process.stop -Force`). No shared server is
used. Logs, artificial binaries and raw request rows are Git-ignored under
`artifacts/c11`; compact JSON, HTML and documentation are tracked.

Challenge acceptance is a separate hardware-dependent gate: inspect actual rate
near 200 with measured timing, no unexplained transport/capacity failures in the
shield, successful independent legitimate requests and bounded recovery. Never
make these timing thresholds ordinary CI assertions. Report runs below target
explicitly; no claim that a failed generator verified the offered load.
