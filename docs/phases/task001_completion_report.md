# Task 001 — Completion report (Phase 0 foundation)

Date: 2026-11-08 · Machine: developer workstation (Windows 11) · Result: **all local gates pass**

## 1. Operating system and tool versions

Windows 11 Pro 10.0.26300, Windows PowerShell 5.1, Python 3.12.15 (uv-managed), uv 0.13.0,
Node.js 24.19.0, pnpm 11.21.0, Git 2.55.0, Claude Code 2.1.319. Details are in
`task001_environment.md`.

## 2. Repository tree (tracked-candidate files; generated/ignored content excluded)

```
.
├── .claude/settings.json            # deny: read .env*, edit/write data/raw/**
├── .editorconfig  .env.example  .gitattributes  .gitignore  .python-version
├── .github/workflows/ci.yml
├── CLAUDE.md  README.md  pyproject.toml  uv.lock
├── apps/
│   ├── api/  CLAUDE.md  pyproject.toml
│   │   └── src/compassio_api/  __init__.py  main.py  py.typed
│   │       ├── api/  __init__.py  health.py  v1/{__init__.py, meta.py}
│   │       ├── core/ __init__.py  config.py
│   │       └── schemas/ __init__.py  system.py
│   └── web/  AGENTS.md  CLAUDE.md  package.json  pnpm-lock.yaml  pnpm-workspace.yaml
│       │     eslint.config.mjs  next.config.ts  tsconfig.json  .gitignore
│       └── src/app/{layout.tsx, page.tsx, globals.css, favicon.ico}  src/lib/brand.ts
├── packages/
│   ├── compassio_ml/  CLAUDE.md  pyproject.toml
│   │   └── src/compassio_ml/  __init__.py  py.typed
│   │       ├── integrity/ __init__.py  hashing.py  cli.py
│   │       └── data/      __init__.py  layout.py  manifest.py
│   └── shared/README.md
├── data/{raw,interim,processed}/README.md   data/manifests/README.md
├── models/README.md  experiments/README.md  configs/README.md  infra/README.md
├── scripts/  README.md  check.ps1  check.sh
├── tests/  conftest.py  test_imports.py
│   ├── api/  test_config.py  test_system_endpoints.py
│   └── ml/   test_data_layout.py  test_hashing.py  test_manifest.py
└── docs/
    ├── architecture/ system_overview.md  tech_stack.md  development_workflow.md
    ├── data/         source_register.md  data_contracts.md  data_integrity_policy.md
    ├── decisions/    0001-architecture.md
    ├── phases/       phase_plan.md  task001_environment.md  task001_completion_report.md
    └── research/     problem_definition.md  model_target_and_limitations.md
```

## 3. Dependencies (resolved versions, taken from lockfiles)

**Python runtime** (`compassio-api`): fastapi 0.162.2, starlette 1.10.0, pydantic 2.14.3,
pydantic-core 2.50.4, pydantic-settings 2.16.2, python-dotenv 1.2.4, uvicorn 0.54.0, plus
transitive packages (anyio, click, h11, idna, typing-extensions 4.16.0, typing-inspection 0.4.5, …).
**Python runtime** (`compassio-ml`): pydantic 2.14.3 only.
**Python dev**: ruff 0.17.4, mypy 2.4.1, pytest 9.2.0, httpx2 2.16.0 (+ httpcore2 2.16.0, truststore 0.10.5).
**Web**: next 16.4.5, react 19.3.0, react-dom 19.3.0; dev: typescript 5.9.3, eslint 9.39.5,
eslint-config-next 16.4.5, tailwindcss 4.3.5, @tailwindcss/turbopack 4.3.5, @types/node 20.19.43,
@types/react 19.3.0, @types/react-dom 19.3.0.

Not installed, by design: PyTorch, transformers, XGBoost, LightGBM, MLflow, database drivers,
pandas, scikit-learn.

## 4. Python commands

```powershell
uv sync --locked
uv run uvicorn compassio_api.main:app --reload --port 8000
uv run ruff check . ; uv run ruff format --check . ; uv run mypy ; uv run pytest
uv run compassio-hash <file>
```

## 5. Frontend commands (in `apps/web`)

```powershell
pnpm install --frozen-lockfile ; pnpm dev ; pnpm lint ; pnpm typecheck ; pnpm build
```

## 6. API endpoints

| Method | Path | Response |
| --- | --- | --- |
| GET | `/health` | `{"status":"ok","service":"compassio-api","version":"0.1.0"}` |
| GET | `/api/v1/meta` | `{"product_name":"Compassio","tagline":"Give Green Funding a Better Direction.","category":"Climate Funding Intelligence","api_version":"0.1.0","environment":"development"}` |
| GET | `/openapi.json`, `/docs` | FastAPI-generated schema and UI |

CORS defaults to `http://localhost:3000` and `http://127.0.0.1:3000`, GET only, no credentials.
A wildcard `*` is rejected at configuration validation.

## 7. Tests executed

`uv run pytest`: **67 passed in 0.30 s** (pytest 9.2.0, Python 3.12.15, warnings treated as errors).

| File | Tests | Covers |
| --- | --- | --- |
| `tests/api/test_system_endpoints.py` | 7 | health, meta, 404 for unbuilt routes, OpenAPI path set, CORS allow/deny/preflight |
| `tests/api/test_config.py` | 10 | defaults, env parsing, `.env` file, wildcard/malformed origin rejection, immutability |
| `tests/ml/test_hashing.py` | 13 | NIST vectors, chunk independence, no newline translation, file unchanged, missing file, directory, CLI |
| `tests/ml/test_data_layout.py` | 8 | layout paths, env override, missing-source error and message, directory rejection |
| `tests/ml/test_manifest.py` | 21 | rights-evidence rule, hash/id format, unknown fields, duplicates, JSON round trip |
| `tests/test_imports.py` | 8 | module imports, version metadata, ML package does not depend on the HTTP stack |

Live server smoke test: `uv run uvicorn compassio_api.main:app --port 8765`. `/health` and
`/api/v1/meta` both returned 200, `/openapi.json` returned 200, and the CORS header was present for
`http://localhost:3000`. The server was stopped afterwards.

## 8. Build and type-check results

| Check | Command | Result |
| --- | --- | --- |
| Python lint | `uv run ruff check .` | All checks passed |
| Python format | `uv run ruff format --check .` | 36 files already formatted |
| Python types | `uv run mypy` (strict) | Success: no issues found in 24 source files |
| Web lint | `pnpm lint` | 0 problems |
| Web types | `pnpm typecheck` | passed |
| Web build | `pnpm build` (Next 16.4.5, Turbopack) | Compiled successfully; `/` prerendered static |
| All gates (bash) | `bash scripts/check.sh` | All checks passed |
| Python gates (PowerShell) | `scripts\check.ps1 -SkipWeb` | All checks passed |

The built `index.html` contains "Compassio", "Give Green Funding a Better Direction.",
"Climate Funding Intelligence", a `<main>` landmark and a single `<h1>`.

## 9. Data safety checks

- No datasets were copied, downloaded or generated. `data/raw`, `interim` and `processed` contain
  only their README files. `data/manifests` has no entries.
- `git check-ignore` confirmed these paths are **ignored**: `data/raw/*.csv`, `data/interim/*.parquet`,
  `data/processed/*.csv`, `models/*.pkl`, `experiments/mlruns/`, `.env`, `.env.local`,
  `.claude/settings.local.json`, `.venv/`, `apps/web/.next/`, `apps/web/node_modules/`.
- These paths stay **trackable**: the stage READMEs, `data/manifests/*.json`, `.env.example`,
  `.claude/settings.json`, `uv.lock` and `pnpm-lock.yaml`.
- The largest untracked candidate file is `apps/web/pnpm-lock.yaml` at 136 KB. Nothing large would be committed.
- `rights_status` defaults to `not_reviewed`. Any concluded rights status requires written evidence,
  and validation enforces this.
- No commit has been made. The Git repository is initialized with every file untracked, ready for review.

## 10. Incomplete work, deviations and blockers

- **CI was not executed.** The repository has no remote, so `.github/workflows/ci.yml` has not run on
  GitHub. Its steps match the local gates that passed. The action major versions
  (`checkout@v5`, `setup-uv@v7`, `pnpm/action-setup@v4`, `setup-node@v5`) should be confirmed on the
  first push.
- **httpx → httpx2.** Starlette 1.10 deprecates `httpx` for `TestClient`, and with warnings treated as
  errors the suite failed to load. The fix was to switch to the recommended `httpx2`.
- **Tagline wording.** Section 6 of the brief asked the page to show "Give Funding a Better Direction.",
  but the official tagline is "Give Green Funding a Better Direction." The page and API use the official
  tagline. Change `apps/web/src/lib/brand.ts` and `core/config.py` together if the shorter form is wanted.
  **Correction (Task 002):** the product owner confirmed the official tagline is exactly
  "Give Funding a Better Direction."; API, web, tests and docs were updated in Task 002.
- **Next.js 16 scaffold choices kept.** `cacheComponents` and `partialPrefetching` were left enabled as
  scaffolded. Google-hosted fonts were removed so builds work offline.
- **The web app is a standalone pnpm project** with its lockfile in `apps/web`, not a root pnpm workspace.
  ADR 0001 explains why.
- **Blocker for the next phase:** the source datasets are not in the repository. Task 002 needs the
  developer to copy the original files into `data/raw/<source_id>/`.

## 11. Proposed scope for Task 002 — source registration and read-only inspection

1. The developer copies the original downloaded files into `data/raw/<source_id>/`.
2. Add a `compassio-manifest validate` command and a test that validates every committed manifest.
3. Hash each file and write a manifest entry with rights left as `not_reviewed`.
4. Add the minimal readers needed (for example pandas, lxml, openpyxl) and write read-only inspection
   reports per source: schema, record counts, year and country coverage, Pakistan subset size,
   description completeness, and identifier fields.
5. Produce an evidence-based overlap analysis that tests the hypotheses in `source_register.md`
   (paper ↔ AidData, GCF ↔ CFU ↔ CPE). No merging yet.
6. Try to reproduce the 20,985-record count and explain any difference.

Out of scope for Task 002: cleaning transforms, splits, training.
