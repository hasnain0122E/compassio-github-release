# C11 judge scorecard

Read this with [measured results](c11_results.md), the [offline judge page](c11_judge_results.html)
and the [reproducibility receipt](c11_metrics.json). Only actual measurements in
those receipts support the traffic result; scheduled traffic alone is not proof.

| Gate | Result / scope |
|---|---|
| Branch/base isolation | Requested C11 branch, clean frozen starting commit; no merges, pushes or deployment |
| Existing-defense audit | Task 009 sliding window, size, event, CORS, error, inference and read-only DB behavior documented |
| Opt-in admission | Atomic monotonic token buckets; old limiter selected only when C11 disabled |
| Identity | Socket-bound loopback source IPs verified over HTTP; no identity headers trusted |
| 200 rps local gate | Eight final shield runs: 199.79–200.77 bot rps; baseline failures stopped safely |
| Legitimate survival | 96/96 independent requests succeeded; shared-IP calls reported separately |
| 429 | Real HTTP envelope, Retry-After and CORS evidence retained |
| Recovery | Final shield first-success recovery 5–544 ms; baseline screening windows censored at 3s |
| State/memory | 1,024-key bound; 50,000-key churn added 144 traced bytes; expiry cleared all 1,024 keys |
| Repeated load | Two runs per safe scenario; unsafe baseline scenario is not repeated |
| Ruff lint | Passed across repository |
| Ruff format | Passed across repository |
| Strict mypy | Passed: 222 workspace source files and two challenge scripts |
| C11 tests | 15 passed: fake clocks, concurrency, bounds, guards, CORS, artifacts and DB fixtures |
| Full pytest | 742 passed, 65 skipped; includes authorization/CORS/413 regressions |
| Canonical artifacts/data | Unavailable in this worktree; canonical integrity/capacity gate skipped |
| Fixture integrity | v1/v2 and SQLite SHA-256 unchanged; SQLite integrity and FK checks pass |
| Frontend compatibility | Standard typed error note supplied; no frontend edits/integration claim |

## Validation commands

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run mypy scripts/c11_benchmark.py scripts/c11_report.py
uv run pytest tests/api/test_c11_availability.py -q -p no:cacheprovider --basetemp=artifacts/c11/c11-test-tmp
uv run pytest -q -p no:cacheprovider --basetemp=artifacts/c11/full-test-tmp
```

The first full pytest attempt failed on sandbox-denied Windows cache/temp access
and was invalid. The full suite was rerun with authorized filesystem access and
an isolated temporary directory; the passing result above comes from that rerun.
No timing-sensitive benchmark assertion is mandatory in ordinary CI.

## Every skipped gate

One PostgreSQL portability test needs an explicitly disposable PostgreSQL URL.
The other 64 skips need absent local source files, processed/research datasets,
verified canonical database/snapshots, final-evaluation outputs, model releases,
v2 retrieval/review builds or local ML runs. The receipt includes every pytest
skip location and reason. These skips do not establish full-system regression
success. No canonical model hashes were recomputed from unavailable binaries;
the pinned inference and trusted-release registry files remain unchanged.

Multi-worker/distributed-state deployment, real distributed botnet defense,
production capacity, unlimited identity churn fairness, canonical-model load
capacity, and frontend integration are outside this local challenge gate.
No C05, C09, frontend, finance, ML evaluation, registry or canonical data files
were modified. The SQLite code change only selects a safe read-only pool when
C11 is enabled; it never migrates/writes the canonical DB.

Ready for judges as a bounded, explicitly fixture-backed local challenge demo,
subject to the actual achieved traffic and latency measurements shown in results.
It is not a public-production deployment approval.

Final shield: 5,953 abusive HTTP 429 responses among 6,400 bot requests, with zero
HTTP capacity errors, timeouts or transport failures. Per-run legitimate p95 was
130–862 ms for independent peers; the highest value came from the mixed workload.
Peak process RSS was 234,987,520 bytes (224.1 MiB); measured state high-water was
seven keys including recovery. Traced limiter stress peaked at 269,028 bytes,
with 267,526 bytes filled and 267,670 after 50,000 rejected new identities.
After expiry there were zero keys and 107,300 traced bytes retained by Python's
containers/allocator; cleanup is not a promise to return RSS to zero. Shared-IP
legitimate success was 50%: reads succeeded and screening was throttled.

The receipt also preserves eight earlier shield runs, including below-target
147.37 and 175.65 rps results. Those runs do not establish the 200 rps gate.
