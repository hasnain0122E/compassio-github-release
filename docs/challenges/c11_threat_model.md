# C11 threat model

Assets: normal Discover → Understand → Shortlist browsing, inference capacity,
database reads, process memory, predictable errors and existing access boundaries.

| Threat | Experiment / defense | Limitation |
|---|---|---|
| One screening flooder | `single`: 200 offered rps, peer token bucket | IP identifies a network peer, not a person |
| Several flooders | `distributed`: four actual loopback source IPs share 200 rps; global screening ceiling | More real peers can exhaust global screening capacity |
| Concurrent legitimate calls | Independent `.9` peer, two screening and two project-read requests/sec | Small local sample; CPU/network saturation still possible |
| Burst and recovery | Exhaust attacking peer, then poll normal screening after burst | No guaranteed latency under arbitrary competing traffic |
| Mixed endpoints | `mixed`: half screening, half project reads | Read attackers can exhaust the read ceiling too |
| NAT/shared peer | `shared_ip`: attacker and legitimate use `.2` | Screening fairness is impossible within that identity; report it |
| Forged identity headers | Ignore X-Forwarded-For and arbitrary client IDs | Server/proxy must preserve trustworthy ASGI peer provenance |
| Identity churn | Cross-peer buckets plus fixed table cap and per-class reservation | New legitimate keys may be rejected until expiry |
| Oversized input / unauthorized use | Preserve Task 009 413 and existing 403 guards | Allowed-body bandwidth is still spent before admission |

The network experiment binds TCP source addresses `127.0.0.2` through `.5` and `.9`
and verifies each through a harness-only peer-inspection route before generating
load. No header or authenticated identity simulation is used. These are multiple
local socket addresses on one machine, not real distributed hosts or devices.
Controlled ASGI unit tests also inject peer identities; those tests are distinct
from network evidence. Unknown/malformed addresses share one `unknown` bucket.

Bind the disposable server only to `127.0.0.1`, one worker, proxy headers disabled.
The harness-only peer route and stop-file watcher are never added to the product
app. Do not expose this harness or copy its artificial fixture registry into a
production deployment. Multi-worker/host support requires shared atomic state,
plus separately reviewed ingress, identity, resource and capacity controls.
