# Compassio

**Give Funding a Better Direction.**

Compassio is an AI-powered climate funding intelligence and decision-support tool. It is
Pakistan-first and built for BATTLEVERSE 2026 (Battle of Intelligence). It helps organizations:

- discover real climate-finance projects;
- screen project descriptions for climate relevance with a trained model;
- look at the evidence behind each classification;
- explore transparent allocation scenarios.

Humans make the final decisions.

> **Current stage: Task 006 (Phase 5A), working backend on real records.**
> - **Data:** 25,623 audited project records from four registered sources are ingested into a
>   local database with provenance, exact-decimal finance and explicit cross-source links.
> - **API:** typed FastAPI routes for discovery, sources, filters and analytics.
> - **Model:** the Task 005 research classifier is released internally only. There are no ML
>   prediction endpoints yet (Task 007).
> - **Rights:** all source rights are `not_reviewed`, so source data is served **only in local
>   development mode**. Production fails closed.

## Repository layout

| Path | Contents |
| --- | --- |
| `apps/api` | FastAPI app (`compassio_api`): DB models, migrations, ingestion, services, routes |
| `apps/web` | Next.js 16 + TypeScript + Tailwind app |
| `packages/compassio_ml` | Data/ML package (`compassio_ml`): safe readers, audit, research dataset, model, finance contract |
| `packages/shared` | Planned generated TypeScript API types (README only) |
| `data/` | `raw`, `interim`, `processed`, `db` (git-ignored) and `manifests` (tracked) |
| `models/`, `experiments/` | Git-ignored artifact locations |
| `configs/`, `infra/`, `scripts/` | Configs, infrastructure and the check scripts |
| `tests/` | pytest suite |
| `docs/` | Architecture, data, security, research, phase reports, ADRs |

## Quick start (Windows PowerShell)

```powershell
uv sync --locked

# 1. Database: create the schema, then import the registered sources (idempotent).
#    Needs the raw files in data\raw\ and the Task 003 table (uv run compassio-research build).
uv run compassio-db migrate
uv run compassio-db fetch --source gcf_api_projects   # optional: official GCF API snapshot -> data\raw_db\
uv run compassio-db registry                          # validate backend snapshots
uv run compassio-db ingest --source all               # 9 source keys (~1.5 min); `core` = Task 006 four
uv run compassio-db verify                            # compares the database with the audited counts
uv run compassio-db report gcf-enrichment             # coverage; also: reconciliation
uv run compassio-db status

# 2. API on this machine only. Source rights are not reviewed, so local inspection must be
#    switched on explicitly; the default ("public") serves no source-derived data.
$env:COMPASSIO_SOURCE_DATA_ACCESS = "local_development"
uv run uvicorn compassio_api.main:app --host 127.0.0.1 --port 8000   # http://127.0.0.1:8000/docs

# 3. Web app
cd apps/web
pnpm install --frozen-lockfile
pnpm dev                                                               # http://localhost:3000
```

Example queries:

- `/api/v1/projects?country=PAK&q=hydropower`
- `/api/v1/projects/gcf_projects:FP085`
- `/api/v1/analytics/trends?metric=adb_commitments_usd`

Contracts: [`docs/architecture/api_contracts.md`](docs/architecture/api_contracts.md).

Run all quality gates with `powershell -ExecutionPolicy Bypass -File scripts\check.ps1`, or
`bash scripts/check.sh`.

## Scientific boundaries

- Climate-relevance classification is not evidence of environmental impact.
- Financing commitments are not returns.
- An approved project is not necessarily seeking funding.
- Rankings are prioritization aids, not claims of an objectively best option.

The API never adds commitments, approvals, disbursements and repayments together. It never
converts currencies and never sums the same project across sources. See:

- [`docs/data/financial_aggregation_policy.md`](docs/data/financial_aggregation_policy.md)
- [`docs/data/data_integrity_policy.md`](docs/data/data_integrity_policy.md)
- [`docs/research/model_target_and_limitations.md`](docs/research/model_target_and_limitations.md)

## Data

Source datasets and the database are **never committed**. Place the original files in
`data/raw/<source_id>/` (see [`docs/data/source_register.md`](docs/data/source_register.md)), then
run:

```powershell
uv run compassio-manifest validate                  # hashes match the committed manifest
uv run compassio-data audit --check-reproducible    # regenerate artifacts/data_audit/*
```

Further reading:

- **Audit findings:** [`docs/data/source_inventory.md`](docs/data/source_inventory.md),
  [`data_quality_audit.md`](docs/data/data_quality_audit.md),
  [`research_label_audit.md`](docs/data/research_label_audit.md)
- **Ingestion:** [`docs/data/ingestion_pipeline.md`](docs/data/ingestion_pipeline.md)
- **Rights:**
  [`docs/security/source_rights_access_policy.md`](docs/security/source_rights_access_policy.md)
