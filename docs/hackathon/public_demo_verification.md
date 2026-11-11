# Public demo verification ledger

Date: 2026-11-12. **No public deployment exists or has been verified.**

| Acceptance item | Actual result |
|---|---|
| Vercel URL | Not assigned; account unconnected |
| Backend URL | Not assigned; account unconnected |
| External HTTPS status / TLS / CORS | NOT RUN; no URLs |
| Live judge journey on independent devices | NOT RUN |
| Provider idle shutdown / cold restart | NOT RUN |
| Linux Docker/cgroup capacity | NOT RUN; Docker unavailable |
| Private remote artifact download | NOT RUN; no approved connected store |
| Canonical public serving | Blocked by unresolved serving scope; no approved subset |
| Production ML v1 / v2 | Deliberately denied by current production policy |

## Actual local evidence

Production optimized Next ran on `http://127.0.0.1:3137`; the real authorized
development backend ran on `http://127.0.0.1:8137`. These are **local loopback
addresses**, not judge-accessible URLs. Ports 3000/8000 were already occupied,
so the test used separate ports without modifying those existing processes.

All **15 browser journeys passed** with installed Chrome in 1.3 minutes:
Discover/search/filter, details/climate/finance provenance, shortlist/refresh,
comparison/prioritization, scenario conservation, same-input real v1/v2 scoring,
source restrictions, errors and empty results, C09 live normalization, C11 typed
429/Retry-After recovery, C05/C09/C11 recorded evidence links, mobile/tablet/desktop
layouts, keyboard use and dark mode. C05/C11 scorecards remain recorded evidence,
not new live benchmark claims. No mock API route was installed.

Final isolated TCP probe (`artifacts/task013/capacity.json`, intentionally ignored):

| Route/check | Authorized loopback backend | Production backend with canonical files |
|---|---|---|
| `/health` | 200 | 200 |
| Pakistan discovery | 200, actual projects | 403 `source_rights_not_cleared` |
| Keyword search / detail | 200 | 403 |
| ML v1 / ML v2, three calls each | 200, exact frozen model hashes | 403 `inference_not_authorized` |
| Oversized request | 413 with approved CORS header | 413 with approved CORS header |
| Unapproved Origin | No CORS allow-origin | No CORS allow-origin |
| Eight concurrent reads / four threads | 200 | 403 |
| Burst with changing spoofed forwarded IPs | 429, same real peer bucket | 429 |
| Post-limit retry | 200 real model result | 403; policy still enforced |

Cloud tests confirm `/docs`, `/redoc`, `/openapi.json` return 404 in production,
health remains available, unsafe cloud origins are refused, one worker/no proxy
trust/provider PORT are configured, unapproved provisioning does not download,
existing canonical files verify without downloading, and corrupt bytes are not
published. These tests do not constitute a cloud network transfer.

Canonical verification: all five file hashes, SQLite integrity/foreign keys,
27 comparisons and structural checks pass; 26,499 projects and 93,881 finance
observations unchanged. Generated TypeScript/OpenAPI contracts are current.

Python: 829 baseline passed / 1 PostgreSQL skip / 81 local-data deselections;
99 targeted canonical/security passed / 16 C05-artifact skips; 10 cloud tests
passed. These runs overlap; do not add the counts. Frontend lint/typecheck/build
and all 16 unit tests pass. One initial browser run failed before launch due to
a missing bundled browser; Chrome rerun passed. A sandbox pytest filesystem
failure was resolved by an approved rerun without pytest cache.

## Required public completion record

After deployment, append actual UTC time, deployment Git SHA, assigned HTTPS
origins, provider plan/region, observed statuses, CORS headers, real returned
model hash/response correctness, cold/warm latency, cgroup peak, restart behavior,
concurrent-device behavior and browser results. Run `scripts/verify_public_demo.py`
and the browser journeys from the runbook. Never replace missing measurements
with predictions or mark this ledger passed from a local build.
