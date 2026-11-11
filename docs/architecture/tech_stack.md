# Tech stack

Exact resolved versions are in `uv.lock` and `apps/web/pnpm-lock.yaml`; this table records the
versions resolved in Task 001 and Task 002.

## Installed (Phase 0)

| Area | Tool | Resolved version | Why |
| --- | --- | --- | --- |
| Python runtime | CPython (uv-managed) | 3.12.15 | Brief prefers 3.12; broad ML ecosystem support |
| Python env/deps | uv | 0.13.0 | Fast, lockfile-based, workspace support, Windows-friendly |
| Build backend | hatchling | resolved at build time (`>=1.27`) | Simple src-layout packaging |
| API | FastAPI | 0.162.2 | Typed, OpenAPI out of the box |
| | Starlette | 1.10.0 | (FastAPI dependency) |
| | Pydantic | 2.14.3 | Schemas and validation |
| | pydantic-settings | 2.16.2 | Typed env configuration |
| | Uvicorn | 0.54.0 | ASGI server |
| Python dev | Ruff | 0.17.4 | Lint + format |
| | mypy (strict, pydantic plugin) | 2.4.1 | Type checking |
| | pytest | 9.2.0 | Tests |
| | httpx2 | 2.16.0 | HTTP client for `TestClient` (see note) |
| Data inspection (Task 002) | pandas | 3.1.1 | Tabular profiling (string-typed; no coercion) |
| | numpy | 2.5.4 | (pandas dependency) |
| | openpyxl | 3.1.5 | Read-only `.xlsx` access (`keep_links=False`, no VBA) |
| | defusedxml | 0.7.1 | XML parsing with DTD/entity/external-reference protection |
| Python dev (Task 002) | pandas-stubs, types-openpyxl, types-defusedxml | 3.1.0.261029 / 3.1.5.20261017 / 0.7.0.20260504 | Strict typing |
| JS runtime | Node.js | 24.19.0 (local) | LTS-line; Next 16 needs ≥ 20.9 |
| JS package manager | pnpm | 11.21.0 (pinned via `packageManager`) | Strict, fast, lockfile |
| Frontend | Next.js | 16.4.5 | App Router, React Server Components |
| | React / React DOM | 19.3.0 | |
| | Tailwind CSS | 4.3.5 | Utility CSS, no component library |
| | TypeScript | 5.9.3 | |
| | ESLint + eslint-config-next | 9.39.5 / 16.4.5 | |

**Note on httpx vs httpx2.** The brief named `httpx`. Starlette 1.10 emits a
`StarletteDeprecationWarning` when its `TestClient` uses `httpx` and recommends `httpx2`
(the pydantic-maintained successor). Because the test suite treats warnings as errors, Task 001
uses `httpx2`.

## Planned (not installed — added only by the task that needs them)

| Need | Candidates | Phase |
| --- | --- | --- |
| Columnar storage for processed tables | pyarrow / Parquet (only when processed datasets are written) | Data engineering |
| Baseline models | scikit-learn (TF-IDF + linear models), calibrated | Modelling |
| Gradient boosting | XGBoost / LightGBM, only if baselines justify | Modelling |
| Transformer text models | PyTorch + Hugging Face transformers (multilingual, given Chinese/English sources) | Modelling, if justified by baseline error analysis |
| Experiment tracking | MLflow (local file store under `experiments/`) | Modelling |
| Serving store | PostgreSQL (+ driver), or DuckDB/Parquet for MVP read-only serving | API data phase |
| Allocation scenarios | SciPy / OR-Tools linear programming with explicit constraints | Allocation phase |
| API types for web | OpenAPI → TypeScript generator into `packages/shared` | API integration |
| Charts | A single charting library, chosen with the trends UI | Frontend phase |
