# Final judge runbook

Use the integration checkout. This demonstration supports human review; it does
not predict approval, investment returns or actual environmental benefit.

## Prepare once

Python 3.12, uv, Node >=20.9 (tested with Node 24), and the project's pinned pnpm.

```powershell
uv sync --locked --offline
Push-Location apps/web
pnpm.cmd install --frozen-lockfile --offline --store-dir D:/.pnpm-store
Pop-Location
uv run python scripts/runtime_artifacts.py verify
uv run python scripts/demo_preflight.py
uv run compassio-db verify
uv run python -m compassio_ml.challenges.c05.cli verify
```

The store path is specific to this laptop; other laptops must populate their own
cache. A clone needs the five ignored runtime files through the existing local
checksum-verified import/export tool. C05 also needs ignored
`data/ml_v2/challenges/c05/{c05_acbd465eef5a,addendum_80ef1619158b}`. Copy only
authorized local cached experiments, verify them, and never commit/upload them.

## Start the verified isolated configuration

Terminal 1, repository root:

```powershell
$env:COMPASSIO_CORS_ORIGINS='http://localhost:3032,http://127.0.0.1:3032'
powershell -ExecutionPolicy Bypass -File scripts/start_api.ps1 -Port 8032 -C09 -C11
```

Terminal 2, `apps/web`:

```powershell
$env:NEXT_PUBLIC_COMPASSIO_API_URL='http://127.0.0.1:8032'
pnpm.cmd build
pnpm.cmd start --hostname 127.0.0.1 --port 3032
```

Open `http://127.0.0.1:3032`. Use one API worker, loopback binding and no trusted
forwarded headers. The launcher supplies authorized event mode, ML v2 local demo,
model preload and `--no-proxy-headers`. Omit `-C09`/`-C11` to reproduce the default
unguarded behavior. On default ports, use the existing `start_api.ps1` and
`start_web.ps1` without port overrides and rebuild the web app for API 8000.
Do not interrupt a server belonging to another worktree.

## Five-minute product journey

1. Open the approved landing page and select Discover.
2. Search `flood`, choose Pakistan, open a real project card.
3. Read “What is this project?” and its climate evidence. Climate relevance is a
   signal for review, not proof of impact.
4. Read the funding facts, then expand evidence and sources. State the currency,
   amount basis and source. Missing amounts are unknown, not zero; historical
   commitments do not imply current open funding or returns.
5. Add to My Shortlist. Return to Discover, choose another project and add it.
6. Open My Shortlist and compare. Read duplication/currency warnings; do not add
   incomparable sources or double-count packages. Reload to show persistence.
7. Open Analyze a Project, submit permitted text and show the real ML v2 result.
   Expand model information and the same-input ML v1 comparison. Explain that v2
   is a development candidate trained on donor markers and needs human review.
8. Open Trust & Resilience through Challenges, keeping the main journey simple.

Analytics and scenarios remain secondary optional tools. Scenario budgets are
hypothetical allocations, not a claim that any project accepts new funding.

## C05 — labels before learning

Show policy A versus candidate B on the recorded card, including the targeted
failure and review trade-off. Then run from the repository root:

```powershell
uv run python -m compassio_ml.challenges.c05.cli verify
uv run python -m compassio_ml.challenges.c05.cli live --sample 3000
uv run python -m compassio_ml.challenges.c05.cli live --sample 3000 --attack targeted_non_energy_positive
uv run python -m compassio_ml.challenges.c05.cli live --sample 3000 --attack targeted_non_energy_positive --policy hardened
```

These execute real challenge code on a deterministic 3,001-record development
sample. They fit disposable detection models and leave the registered ML v2 model
alone. Their sample results differ from the full recorded 13,317-record evaluation.
Labels are not silently corrected. The oracle is consulted only after decisions.

## C09 — demonstrate an actual call

Paste permitted project text into the live C09 box. Run input protection. Show
separate raw and guarded label scores, model version, threshold and review status.
Unchanged input can produce identical results; do not promise a flip or improvement.
The HTTP result additionally retains the standard API score because its existing
sanitizer differs from the raw challenge predictor. The developer evaluation still
contains five adaptive guarded flips; review flags do not mean an attack was stopped.

Full offline reproduction (read-only source development artifacts required):

```powershell
uv run python -m compassio_ml.c09.demo --source-root '<authorized-source-checkout>' --output artifacts/c09/judge-new --check-reproducible
```

Use a fresh output directory and a clean committed integration branch. Do not
overwrite frozen memberships. This may take several minutes; show the recorded
scorecard while it runs. The task's fresh run is under `artifacts/c09/task012`.

## C11 — preserve the browsing server

Explain the recorded fixture-backed capacity test and its shared-IP limitation.
For a real canonical functional demonstration, run:

```powershell
uv run python scripts/task012_probe.py
```

It starts separate one-worker processes, tests default and enabled modes, makes
64 mixed canonical reads with concurrency eight, checks typed 429/Retry-After,
uses an explicitly small 1/s burst-four read budget, checks an independent peer,
tests 413 body delivery, compares inference paths and checks production refusal.
It writes `artifacts/task012/canonical-probe.json` and stops its own processes.
It never sends a 200-rps flood to the judge's demo process.

## Recovery and offline rehearsal

For a 429, wait the displayed Retry-After and retry. Do not disable authorization
or increase budgets during a judge run to hide a rejection. For unavailable data,
run preflight and artifact verification; never ingest over the canonical database.
Review writes are deliberately unavailable without a separate configured token.

Before the event, disconnect networking and repeat this journey on the actual
laptop. Runtime is local and uses bundled fonts, but physical disconnection was
not tested automatically. Preserve the evidence files locally; no raw dataset or
model upload is authorized by the local event permission.
