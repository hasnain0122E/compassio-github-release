# C11 offline judge demonstration

Open [the self-contained measured results page](c11_judge_results.html) in any
browser. It contains the admission diagram, before/after results and latency chart,
actual 429 JSON/headers, legitimate success, recovery and explicit limitations.
It needs no network, JavaScript library, account or public deployment.

Reproduce from the repository root (loopback port 18761 must be unused):

```powershell
uv sync --locked
uv run python scripts/c11_benchmark.py --mode baseline --seconds 4 --repeat 2
uv run python scripts/c11_benchmark.py --mode shield --seconds 4 --repeat 2
uv run python scripts/c11_report.py
```

The harness creates artificial fixtures and launches/stops its own local servers.
Use Ctrl+C to stop early; see [protocol](c11_experiment_protocol.md) for details.
Read [results](c11_results.md) and [machine-readable receipt](c11_metrics.json).

For a manually managed existing authorized local demo (requires your own local
artifacts and data; these are absent here):

```powershell
$env:COMPASSIO_C11_ENABLED='true'
$env:COMPASSIO_SOURCE_DATA_ACCESS='local_development'
uv run uvicorn compassio_api.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
```

Ctrl+C stops this server. Do not run the flood generator against it: the generator
owns a separate disposable server. Do not change public access settings to make
inference available remotely. Disable the challenge by unsetting
`COMPASSIO_C11_ENABLED`; the frozen Task 009 policy then remains in effect.

Judge wording must follow measured evidence: independent socket peers represent
network-level identity separation. Shared-IP clients cannot be separated. The
baseline already throttles. C11's contribution is bounded state, global ceilings,
route isolation, continuous refill and a safe opt-in SQLite pool under concurrency.
