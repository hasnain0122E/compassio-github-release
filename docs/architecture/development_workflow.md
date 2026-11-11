# Development workflow

## Prerequisites

- uv ≥ 0.13 (installs Python 3.12 automatically from `.python-version`)
- Node.js ≥ 20.9 (developed on 24.x) and pnpm 11 (`corepack enable` picks the pinned version)
- Git

## First-time setup

```powershell
uv sync --locked                       # creates .venv with Python 3.12 + all locked deps
cd apps/web; pnpm install --frozen-lockfile; cd ../..
Copy-Item .env.example .env            # optional local overrides
```

## Daily commands

```powershell
uv run uvicorn compassio_api.main:app --reload --port 8000   # API  → http://localhost:8000/docs
cd apps/web; pnpm dev                                         # Web  → http://localhost:3000
```

## Quality gates (identical locally and in CI)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check.ps1    # or: bash scripts/check.sh
```

Runs: `uv sync --locked`, `ruff check`, `ruff format --check`, `mypy`, `pytest`, and in
`apps/web`: `pnpm install --frozen-lockfile`, `pnpm lint`, `pnpm typecheck`, `pnpm build`.
CI (`.github/workflows/ci.yml`) runs the same steps with no secrets and no datasets.

## Conventions

- **Dependencies:** `uv add --package compassio-api|compassio-ml <pkg>` or `uv add --dev <pkg>`;
  `pnpm add <pkg>` inside `apps/web`. Commit lockfiles. Never install globally.
- **Python:** src layout, absolute imports, no `sys.path` manipulation, strict typing, line length 100.
- **Line endings:** LF in the repo (`.gitattributes`), CRLF only for `.ps1`.
- **Tests:** in `tests/api` and `tests/ml`; warnings are errors; no tests that cannot fail.
- **Branches/commits:** small, task-scoped changes; one task → one reviewed branch.
- **Data:** see `docs/data/data_integrity_policy.md`. Never `git add -f` anything in `data/`
  except manifests.
