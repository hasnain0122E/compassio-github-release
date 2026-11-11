# Compassio — Claude Code project instructions

**Compassio** — *Give Funding a Better Direction.* AI-powered climate funding
intelligence and decision support, Pakistan-first, built for BATTLEVERSE 2026
(Battle of Intelligence).

## Current stage

**Task 006-DB complete (on `main`, concurrently with ML v2 on `feature/ml-v2`).**

- **Backend:** SQLAlchemy and Alembic (migrations `0001`-`0003`). The local SQLite database is
  `data/db/compassio_dev.sqlite` (git-ignored). `compassio-db` ingests:
  - the 4 core sources: AidData + Rio annotations, GCF projects, CFU, ADB;
  - GCF readiness (876 grants);
  - GCF country summaries (aggregates);
  - Climate Project Explorer (818 documents);
  - GCF historical (**restricted staging, never served**);
  - the GCF API enrichment (379/379 export projects dated, with stated-currency lines).

  `compassio-db verify` matches all 27 audited figures.
- **Backend-only downloads:** they go in `data/raw_db/` with their own registry
  (`data/manifests/backend_source_registry.json`, metadata only; `compassio-db registry`). **Never
  put them in `data/raw/` and never edit `data/manifests/source_manifest.json`.** Both belong to
  the ML track.
- **API:** `/sources`, `/projects`, `/projects/{id}` (with enrichments and documents),
  `/documents`, `/filters`, and `/analytics/{overview,metrics,trends,data-quality,
  financing-completeness,gcf-timeline,country-aggregates,relationships}`. Contracts are in
  `docs/architecture/api_contracts.md`.
- **Money:** exact `Decimal`. Totals are single-source and built only via
  `compassio_ml.finance.aggregate`.
- **Rights:** all sources are `not_reviewed`. Data is served only with
  `COMPASSIO_SOURCE_DATA_ACCESS=local_development` outside production.
- **PostgreSQL:** verification **pending** (no server available;
  `docs/architecture/postgresql_verification.md`).
- **Task 005 model:** the frozen tests are CONSUMED. The release is internal only. There is no
  prediction endpoint yet (Task 007).

Before using any source, read `docs/data/data_quality_audit.md` and the
`compassio-data-auditor` skill; before trusting or reporting any model result, use the
`compassio-ml-experiment-reviewer` skill (`.claude/skills/`).

**ML v2 (branch `feature/ml-v2`, Task 006-ML + review gate):** external data (World Bank, FCDO and
EC INTPA IATI; GCF pages kept restricted: robots `ai-train=no`) under git-ignored `data/ml_v2/`.
ML-use rights are enforced from `configs/ml_rights_eligibility_v2.yaml`; consumed v1 test records
are excluded from every v2 pool; development code must load data only via
`compassio_ml.external.development`; never read the backend's `data/raw_db/`. Worksheets issued;
no human labels yet; no v2 model exists. Docs: `docs/research/model_v2/`, `docs/data/external_sources/`.

**Task 006-ML-AUTO:** development experiments may use original donor-reported labels without
human review under existing internal-research rights. Run `compassio-v2-quality audit` first;
use `quality_v2.audit.load_eligible_donor_records` for structurally eligible development data.
Semantic flags and AI disagreement never replace labels. No independent evaluation or
production claim is permitted. The human external test stays sealed; real AI assessment is
disabled without source/provider usage permission. See `automated_quality_workflow.md` in the
model-v2 docs and `docs/phases/task006_ml_auto_completion_report.md`.

**Task 006-ML2 (branch `feature/ml-v2-training`):** frozen plan `configs/ml_v2_fast_experiment.yaml`
(+ escalation addendum) run via `uv run compassio-v2-train benchmark|reproduce|escalate|predict`
(package `compassio_ml.model_v2`). Development champion `ml2fast_49317056_c76204127550` (char TF-IDF
+ LR) in git-ignored `data/ml_v2/models_v2_dev/` is a **development candidate only** — never add it
to the trusted release registry or the API; v1 remains the served model. Its VALID scores are
optimistic (used once for selection) and measure agreement with donor markers, not independent
accuracy. Results: `docs/research/model_v2/fast_benchmark_results.md`, champion card, and
`docs/phases/task006_ml2_completion_report.md`. Optional extra `embeddings` (torch) is only for
the escalation run: `uv run --all-extras ...`.

Always check `docs/phases/phase_plan.md` for what is in scope *now*.

## Architecture

Modular monorepo, not microservices. Python is a uv workspace (single `uv.lock`);
the web app is a standalone pnpm project.

```
apps/api/                FastAPI app — package `compassio_api` (src layout)
  src/compassio_api/
    main.py              create_app() factory + module-level `app`
    core/config.py       typed Settings (COMPASSIO_* env vars), product constants
    api/health.py        GET /health (unversioned)
    api/v1/              versioned routers, mounted at /api/v1 (meta, catalog, projects)
    api/deps.py errors.py  session + access-policy dependencies; {code,message} error handlers
    schemas/             Pydantic response models
    db/                  ORM models, DecimalText, sessions (read-only API engine), Alembic migrations
    ingest/              offline per-source builders + idempotent loaders (`compassio-db`)
    staging/             backend-only source registry, bounded fetcher, validator (data/raw_db)
    services/            typed business logic: projects, catalog, finance, access, cache, integrity
    cli/db_cli.py        `compassio-db` migrate | ingest | status | verify
apps/web/                Next.js 16 (App Router, TypeScript, Tailwind v4) — see apps/web/CLAUDE.md
packages/compassio_ml/   data/ML package `compassio_ml` (src layout)
  src/compassio_ml/
    integrity/           sha256_file(), `compassio-hash` CLI
    safety/              safe ZIP / XML / spreadsheet readers (no extraction, no entities, no macros)
    data/                layout, formats, parsing, source registry, inventory, manifest model + I/O
    research/            labels, text cleaning, leakage groups, eligibility, splits, input allowlist
    modeling/            frozen lock, features, estimators, metrics, benchmark, tracking, inference
    audit/               loaders, per-source inspectors, label audit, overlap, report writers
    cli/                 `compassio-data`, `compassio-manifest` entry points
packages/shared/         README only — future generated TS API types
tests/                   pytest suite (api/, ml/); `local_data` marker = real-file checks
artifacts/               git-ignored generated audit reports
data/{raw,interim,processed,db,raw_db}/  git-ignored except README; data/manifests/ is tracked
models/ experiments/     git-ignored except README
configs/ infra/ scripts/ docs/
```

Dependency direction: `compassio_api` may import `compassio_ml`; **never the reverse**.
ML pipelines run as offline jobs, never inside HTTP request handlers.

## Commands (run from the repository root unless noted; work in PowerShell and Git Bash)

| Purpose | Command |
| --- | --- |
| Sync Python env (exact lockfile) | `uv sync --locked` |
| Run API (dev) | `uv run uvicorn compassio_api.main:app --reload --port 8000` |
| Python lint | `uv run ruff check .` |
| Python format check / apply | `uv run ruff format --check .` / `uv run ruff format .` |
| Python type check | `uv run mypy` |
| Python tests | `uv run pytest` |
| Hash a file (read-only) | `uv run compassio-hash <path>` |
| Inventory raw files | `uv run compassio-data inventory` |
| Full data audit (+ reproducibility) | `uv run compassio-data audit [--check-reproducible]` |
| Write / validate source manifest | `uv run compassio-manifest write` / `uv run compassio-manifest validate` |
| Build research dataset + splits (+ reproducibility) | `uv run compassio-research build [--check-reproducible]` |
| Verify frozen dataset/split lock | `uv run compassio-ml verify-frozen` |
| DB schema / ingest / status / verify | `uv run compassio-db migrate` / `uv run compassio-db ingest --source all` (or `core`, or one source) / `uv run compassio-db status` / `uv run compassio-db verify` |
| Backend source snapshot / registry / reports | `uv run compassio-db fetch --source gcf_api_projects` / `uv run compassio-db registry` / `uv run compassio-db report gcf-enrichment` (also `reconciliation`, `historical-comparison`) |
| Run API with local data inspection | `$env:COMPASSIO_SOURCE_DATA_ACCESS="local_development"; uv run uvicorn compassio_api.main:app --host 127.0.0.1 --port 8000` |
| Validation-stage benchmark (+ reproducibility) | `uv run compassio-ml benchmark --protocol primary --suite full` (`--suite fast --check-reproducible`) |
| Only real-data integration tests | `uv run pytest -m local_data` |
| ML v2 (read-only `$COMPASSIO_DATA_ROOT`, writes only `data/ml_v2/`) | `uv run compassio-v2 verify-baseline` / `acquire <source>` / `verify-retrievals` / `build` / `worksheets` / `validate-reviews` |
| Web install (in `apps/web`) | `pnpm install --frozen-lockfile` |
| Web dev / lint / types / build (in `apps/web`) | `pnpm dev` / `pnpm lint` / `pnpm typecheck` / `pnpm build` |
| All gates | `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` or `bash scripts/check.sh` |

Add Python deps with `uv add --package compassio-api <pkg>` (or `compassio-ml`, or `--dev`);
never `pip install`. Never install packages globally.

## Scientific integrity rules (non-negotiable)

1. **Never generate synthetic project observations and present them as real.** No invented
   projects, amounts, countries, dates, classifications or counts — not in code, fixtures,
   seed data, UI copy or docs. Test fixtures must be obviously artificial (`example_*`,
   `example.invalid`) and exercise logic only.
2. **Never fabricate metrics.** Every reported number must come from a command you ran, on data
   registered in `data/manifests/`, and the report must state the command and data hashes.
3. Climate-relevance classification ≠ proof of real-world environmental benefit.
4. Historical financing commitments ≠ investment profit or return.
5. Approved/funded projects are not necessarily open to new funding.
6. Rankings must never be described as objectively highest financial or environmental return.
7. Records from different sources that look alike must **not** be silently merged or
   double-counted. Linkage must be explicit, recorded, and reviewable.
8. The product is **decision support**, not autonomous funding approval.

## Data provenance requirements

- Raw files live in `data/raw/`, unmodified, never committed. Claude must not edit them
  (enforced in `.claude/settings.json`).
- Each raw file gets a manifest entry (`docs/data/data_contracts.md`) with its SHA-256 before use.
- `rights_status` stays `not_reviewed` unless written evidence of the licence review exists.
- Do not download replacement datasets, scrape sources, or redistribute raw data without explicit approval.
- Code that needs a source file must call `compassio_ml.data.require_source_file()` and fail loudly.

## Model evaluation rules

- The earlier audit's record counts (20,985 / 1,383 / 496 / 76) are reproduced in Task 002; its
  **classification baseline is not** and must not be quoted (treat it as possibly leaky).
- Splits must prevent leakage: deduplicate near-identical descriptions across splits, consider
  grouping by project/financier/source, and keep a held-out Pakistan-related evaluation set.
- Report per-class metrics, calibration, and uncertainty — not accuracy alone — plus the exact
  data hashes, split definition and command.
- Distinguish in-distribution performance from generalization to unseen sources/countries.

## Task-scope discipline

- Do only the current task. Do not start future-phase work "while you're there".
- Do not add dependencies that are only *planned* (PyTorch, transformers, XGBoost, LightGBM,
  MLflow, database drivers…) until the task that needs them.
- No placeholder tests that always pass; no silent catch-all `except`; no hard-coded production
  URLs or credentials; no fake API endpoints.
- **If necessary source data is unavailable, stop and explain** what is missing and where it
  should be placed. Do not substitute synthetic or alternative data.

## Reporting requirements

At the end of every task, report: files changed, exact commands run and their real output
(pass/fail counts), blockers, and assumptions. Never claim a check passed without running it.
If a check could not run, say exactly which and why.

Task 006-INT combines the backend and ML research on integration/task006-combined. See docs/architecture/combined_data_paths.md for the guarded same-checkout layout and optional read-only external input root; docs/phases/task006_integration_report.md records actual verification. Main is unchanged until an explicitly authorized merge.

**Task 007 (branch `integration/task007-ml2`, local only, not merged):** versioned screening API
(`/api/v1/models`, `/models/comparison`, `/screening/text`, `/screening/projects/{id}`, `/reviews`).
Models are pinned in `configs/inference_models.yaml` and lazily loaded via the guarded loaders.
v1 stays `trusted_research_release` (default); ML v2 stays `development_candidate` and is the default
engine only in the opt-in `authorized_local_demo` (`COMPASSIO_ML_V2_LOCAL_DEMO=true`, development,
local_development). Inference is refused in production. DB records are model input only if the v2
rights config permits `automated_evaluation`. Text is stored only with `save=true` + review token, in
the separate hash-chained review store. Report: `docs/phases/task007_completion_report.md`.

**Task 008 (branch `feature/task008-decision-engine`, not merged):** read-only decision engine on
the verified DB: `/api/v1/decision/{methodology,evidence/{id},compare,prioritize,scenarios}` and
`/api/v1/analytics/{funding-by-country,funding-by-sector,institutions,approved-vs-disbursed,
climate-distribution,coverage,country-profile/{iso3}}`. Sums only via `services.finance_rows.safe_total`
(→ `aggregate`); `services/finance.py` stays byte-identical. Contract:
`docs/architecture/decision_engine_contract.md`; report `docs/phases/task008_completion_report.md`.

**Task 008 is on `main` (`62a1a17`).** Integration audit: comparisons never total records of one
source group (`compassio-comparison-1.1.0`); `docs/phases/task008_final_integration_report.md`.

**Task 009 (on `main`, frozen as local tag `backend-ready-for-battleverse`; `docs/hackathon/backend_freeze_report.md`):** backend finalization for
the BATTLEVERSE demo. API entry point is `compassio_api.main:app` (never `apps.api.main:app`).
`COMPASSIO_SOURCE_DATA_ACCESS=hackathon_event` + `COMPASSIO_EVENT_AUTHORIZATION=battleverse_2026`
serves the sources of `configs/event_data_authorizations.yaml` to loopback clients only (a
user-reported organizer authorization, NOT a licence clearance; never in production; dates unset
until known). Hardening: 413 body limit, 429 screening rate limit (single worker), JSON 500, common
`{code, message}` 422 envelope, optional model preload. Scripts: `scripts/demo_preflight.py`,
`start_api.ps1`, `start_web.ps1`, `smoke_api.py`, `bench_api.py`. Handoff: `docs/hackathon/`;
report `docs/phases/task009_completion_report.md`.

**BATTLEVERSE challenge C05 (branch `challenge/c05-poison-quarantine`, not merged):** label-flip
poisoning defence in `compassio_ml.challenges.c05` (attack, OOF group-aware detector, quarantine
gate, disposable training comparison) with config `configs/c05_poison_quarantine.yaml`. Outputs
only under git-ignored `data/ml_v2/challenges/c05/`; never touches canonical labels, models,
registries, the DB or sealed evaluations. The detector/gate must never import the attack oracle.
Docs: `docs/challenges/c05_*.md`.
