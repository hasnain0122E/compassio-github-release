# API (apps/api) — scoped instructions

Root rules in `/CLAUDE.md` apply. Additions for the API:

- Handlers are thin: validate input, call a service/`compassio_ml` function, return a Pydantic
  schema from `schemas/`. No training, file parsing or heavy computation in request handlers.
- Every endpoint declares `response_model` with a schema in `compassio_api/schemas/`.
- Domain routes go under `api/v1/<resource>.py` and are included in `api/v1/__init__.py`.
  Do not add an endpoint until it is backed by real, registered data — no stub data endpoints.
- Configuration only via `core/config.py` `Settings` (env prefix `COMPASSIO_`). Document every
  new setting in `/.env.example`. Never hard-code URLs or secrets.
- CORS origins are explicit; `*` is rejected by validation and must stay that way.
- Tests live in `/tests/api/`; build apps with `create_app(Settings(_env_file=None, ...))` so a
  developer's `.env` cannot leak into tests.
- Database: schema changes only via a new Alembic revision (`compassio_api/db/migrations`);
  never edit an applied revision. Money columns use `DecimalText` and Python `Decimal` — never
  floats. Keep queries portable (SQLite now, PostgreSQL later).
- The API process is read-only and must not import `compassio_api.ingest`, pandas or the ML
  stack **at app creation** (`tests/api/test_runtime_boundary.py`). Ingestion runs only via
  `compassio-db`.
- Task 007 exception: `compassio_api.inference.engine.ModelManager` lazily imports the guarded
  loaders (`ReleasedClassifier`, `ExperimentalClassifier`) and scikit-learn on the FIRST
  screening request only. Models are pinned (SHA-256, fingerprint, threshold) in
  `configs/inference_models.yaml`; never load a model any other way, never promote ML v2's
  `development_candidate` status, and never add it to `configs/trusted_model_releases.json`.
- Screening requires `effective_source_access == local_development`; ML v2 additionally requires
  `COMPASSIO_ML_V2_LOCAL_DEMO=true` with `environment=development`. DB records are model input only
  if `configs/ml_rights_eligibility_v2.yaml` permits `automated_evaluation` (aiddata only).
- Submitted text is never stored unless `save=true` AND a valid review token is sent. Saved
  screenings and review decisions go to the separate append-only, hash-chained review store
  (`COMPASSIO_REVIEW_DATABASE_URL`), never the read-only project database.
- Every source-derived route depends on `DataPolicyDep` (rights guard). Never bypass it, never
  derive rights from anything but the `sources` table (copied from the committed manifest).
- Financial totals only through `services.finance` → `compassio_ml.finance.aggregate`; when a
  total is unsafe return `unavailable` + reason, never 0.
  `services/finance.py` is hash-pinned (`configs/task006_integration_reference.json`): never edit
  it. Task 008 decision code sums only via `services.finance_rows.safe_total` (→ `aggregate`) and
  selects metric rows via `finance_rows.metric_statement` + the protected `_exclusion_reason`.
- Task 008 decision engine (`services/decision/`, routes `api/v1/decision.py`): read-only, never
  runs a model, never writes; every route except `/decision/methodology` uses `DataPolicyDep`.
  Bump the methodology versions in `services/decision/methodology.py` when behaviour changes.
- Task 009: the event mode (`hackathon_event`) is resolved only from
  `configs/event_data_authorizations.yaml` via `services/event_access.py`; it never changes a
  `rights_status`, never serves `restricted_internal` sources, is loopback-only
  (`core/middleware.EventLoopbackGuard`) and production forces `public`. Request hardening lives in
  `core/middleware.py` (pure ASGI). Rate limiting and the review write lock are in-process: run ONE
  worker. Regenerate `apps/web/src/lib/api-types.ts` and `docs/api/openapi.json` together with
  `scripts/generate_api_types.py` after any schema change.
- Backend-only downloads go through `compassio_api.staging` into `data/raw_db/` with a registry
  entry (SHA-256, retrieval URL/time, HTTP metadata, `not_reviewed`). Never write into
  `data/raw/`, never edit the canonical manifest or `packages/compassio_ml/**` from backend work.
- Enrichment never overwrites a source's value: keep both, record conflicts and precedence.
  Links use stable identifiers/codes only, with method, evidence and a categorical verification
  state (never a probability); title similarity never creates a link.

