# C11 measured results

Real local TCP/HTTP; artificial tiny models and invented database through the real guarded loaders and endpoints. No canonical-model capacity claim. Up to two repetitions per scenario; fresh one-worker server each time. Target: 800 abusive + 16 legitimate requests over four seconds; 200 bot rps plus four legitimate rps. Unsafe baseline scenarios stop early and omit their repeat. Actual dispatch rates are shown below; server ingress timing (including legitimate load) is also recorded independently.

Final shield dispatch rate: **199.79–200.77 bot rps**. Independent legitimate requests: **96/96 HTTP 200**. Abusive HTTP 429 responses: **5953**. Shared-IP results are separate below. Near-target rates reflect measured scheduler variation; exact per-run values are shown.

| Mode | Scenario | Run | Sent bot rps | Bot 200 | Bot 429 | Bot other/fail | Legit 2xx | Legit p95 | Recovery | Safety |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | single | 1 | 199.86 | 60 | 740 | 0 | 100.0% | 367.1ms | >3s (censored) | complete |
| baseline | distributed | 1 | 199.94 | 240 | 560 | 0 | 100.0% | 486.2ms | >3s (censored) | complete |
| baseline | mixed | 1 | 169.13 | 69 | 0 | 27 | 0.0% | 243.0ms | 0.008s | STOPPED |
| baseline | shared_ip | 1 | 200.56 | 60 | 740 | 0 | 50.0% | 306.0ms | >3s (censored) | complete |
| baseline | single | 2 | 200.38 | 60 | 740 | 0 | 100.0% | 235.0ms | >3s (censored) | complete |
| baseline | distributed | 2 | 176.19 | 240 | 64 | 0 | 100.0% | 544.1ms | >3s (censored) | STOPPED |
| baseline | shared_ip | 2 | 199.44 | 59 | 741 | 0 | 56.2% | 202.9ms | >3s (censored) | complete |
| shield | single | 1 | 200.77 | 13 | 787 | 0 | 100.0% | 130.4ms | 0.122s | complete |
| shield | distributed | 1 | 200.18 | 52 | 748 | 0 | 100.0% | 273.8ms | 0.006s | complete |
| shield | mixed | 1 | 200.46 | 144 | 656 | 0 | 100.0% | 862.3ms | 0.008s | complete |
| shield | shared_ip | 1 | 200.57 | 13 | 787 | 0 | 50.0% | 178.8ms | 0.120s | complete |
| shield | single | 2 | 199.84 | 14 | 786 | 0 | 100.0% | 199.2ms | 0.544s | complete |
| shield | distributed | 2 | 199.79 | 54 | 746 | 0 | 100.0% | 323.0ms | 0.005s | complete |
| shield | mixed | 2 | 200.31 | 144 | 656 | 0 | 100.0% | 619.8ms | 0.006s | complete |
| shield | shared_ip | 2 | 200.49 | 13 | 787 | 0 | 50.0% | 169.0ms | 0.120s | complete |

All status counts, latency p50/p95/p99, process CPU seconds (including startup), RSS, scheduling lag, state counters and example 429 headers are in [c11_metrics.json](c11_metrics.json). Raw per-request records stay in artifacts/c11. Recovery polls the exhausted attacking peer for up to three seconds after draining the burst; null is censored, not a timeout or successful recovery.

The baseline already rejects abuse and preserves independent-peer request success. C11 adds bounded state, a cross-peer safety ceiling, separate read budgets and faster continuous recovery. Shared-IP screening callers cannot be distinguished; mixed-route read access can survive while shared-IP screening is throttled. Small legitimate sample sizes and fixture inference limit generalization. Earlier shield validation, when available, is retained separately in the receipt (including below-target runs). Final protocol bounds pending dispatches to 128 (64 active HTTP + 64 queued) and clears stale process receipts before launching.
