# C11 token-bucket policy v1

Opt in with `COMPASSIO_C11_ENABLED=true`; default false retains Task 009 behavior.
All configuration is typed server-side `Settings`. Malformed, nonfinite, zero or
out-of-range values fail application startup, even when disabled; no silent
unlimited fallback. Existing environment/public/event authorization is unchanged.

| Class | Peer refill / burst | Global refill / burst | Cost |
|---|---:|---:|---:|
| `screen` | 2/sec / 6 | 20/sec / 40 | 1 |
| `read` | 10/sec / 20 | 50/sec / 50 | 1 |

Screen includes `/api/v1/screening/*` and POST `/api/v1/decision/*` (comparisons and
prioritization can perform substantial reads). Other `/api/v1/*` requests use the
read policy, including review writes, which retain their separate token guard.
OPTIONS and non-API paths such as health/docs are exempt. Public health is a
liveness endpoint, not an expensive-work admission bypass. Normal search, detail,
evidence and shortlist navigation fit these local-demo defaults; no frontend
integration or production tuning is claimed.

Environment suffixes: `C11_SCREEN_RATE`, `C11_SCREEN_BURST`, `C11_READ_RATE`,
`C11_READ_BURST`, `C11_GLOBAL_SCREEN_RATE`, `C11_GLOBAL_SCREEN_BURST`,
`C11_GLOBAL_READ_RATE`, `C11_GLOBAL_READ_BURST`, `C11_MAX_KEYS`, `C11_IDLE_SECONDS`.
Each has the `COMPASSIO_` prefix. Unit costs are explicit in immutable `Budget`
objects; integration code may supply other positive costs no greater than burst.

At monotonic time t, tokens = min(burst, previous + elapsed × refill). A short
thread lock protects the complete peer/global check and deduction. Both pass or
neither is charged. Requests never await or sleep for tokens. Reject with 429,
the standard `{code: "rate_limited", message: "Too many requests. Please try again
in a moment."}` envelope, and ceiling(max(peer wait, global wait)) seconds in
Retry-After, minimum 1. Concurrent traffic may consume newly refilled tokens:
Retry-After is a useful delay, not a reservation. No misleading remaining/quota
headers are emitted. CORS exposes Retry-After in C11 mode.

The ordered table holds at most 1,024 peer/class keys by default, half reserved for
each class. Global buckets add two constant entries. Unknown identities share one
key per class. Expiry is 120 seconds since the last successful admission. It must
be at least burst/refill, so eviction cannot reset outstanding token debt.
Pruning occurs on admission and instrumentation; idle state is bounded even
without requests. At capacity, new identities get 429 until the oldest same-class
entry expires; active entries are never evicted to grant fresh bursts. Rejected
identities allocate no state and do not prolong expiry. Cleanup scans are bounded
by the configured cap; normal operations are constant-time. `snapshot()` exposes
aggregate counters locally, with no identity strings or public metrics endpoint.

Order: CORS → security headers → body size → event guard → admission → existing
access-header/exception/dependency handling → route. Early C11 responses receive
CORS and security headers. Since the access-mode response header is inside the
limiter, early rejections do not promise that optional header.

One process only. Peer fairness cannot distinguish devices behind NAT. Read and
screen capacity are isolated, but global screening exhaustion can still deny a
legitimate screening caller. A larger distributed botnet can consume both route
classes or exhaust physical capacity. This policy makes no contrary promise.

## Frontend contract (future integration)

```typescript
type RateLimited = { code: "rate_limited"; message: string };
// If response.status === 429, parse the standard error and display:
// "Too many requests. Please try again in a moment."
// Optional delay: Number(response.headers.get("Retry-After")); seconds, not ms.
// Do not retry automatically in a tight loop or retry review writes blindly.
```

The current frontend worktree has not been edited or integrated with C11.
