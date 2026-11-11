# System overview

Status legend: **✅ implemented (Tasks 001–002)** · **🔜 planned**

```
                      ┌───────────────────────────────┐
  Browser ──────────▶ │ apps/web  (Next.js 16)        │  ✅ landing page only
                      └──────────────┬────────────────┘
                                     │ HTTP (CORS: explicit origins)
                      ┌──────────────▼────────────────┐
                      │ apps/api  (FastAPI)           │  ✅ /health, /api/v1/meta
                      │  thin handlers → services     │  🔜 projects, screening,
                      └──────────────┬────────────────┘      allocation, trends
                                     │ imports (one-way)
                      ┌──────────────▼────────────────┐
                      │ packages/compassio_ml         │  ✅ safe readers, inventory,
                      │  offline pipelines + inference│     manifest, read-only audit
                      └──────────────┬────────────────┘  🔜 ingest, clean, train,
                                     │                      evaluate, infer
          ┌──────────────────────────▼──────────────────────────┐
          │ data/raw → data/interim → data/processed  (git-ignored) │
          │ data/manifests (tracked provenance)                     │
          └─────────────────────────────────────────────────────────┘
```

## Components

| Component | Responsibility | Status |
| --- | --- | --- |
| `apps/web` | User interface: project explorer, comparison, review queue, allocation scenarios, trends | ✅ static landing page; 🔜 everything else |
| `apps/api` | Typed HTTP API over processed data and model outputs; no training | ✅ health + meta; 🔜 domain routes |
| `packages/compassio_ml` | Ingestion, cleaning, linkage, features, training, evaluation, batch inference | ✅ integrity utilities, safe readers, inventory/manifest, read-only audit; 🔜 cleaning, linkage, features, training |
| `packages/shared` | TypeScript types generated from OpenAPI | 🔜 README only |
| `data/` | Staged datasets + committed manifests | ✅ 9 raw sources registered (git-ignored); manifest committed; no interim/processed data |
| Database | Serving store for processed records | 🔜 not chosen/installed (see ADR 0001) |

## Key boundaries

1. **ML ↔ HTTP separation.** Training and heavy processing run as offline commands producing
   versioned artifacts. The API reads artifacts/processed data; it never trains or parses raw files
   per request.
2. **One-way dependency.** `compassio_api → compassio_ml`, never reverse (tested).
3. **Provenance end to end.** Every record served by the API will trace back to a manifest entry
   (`source_id`, `sha256`).
4. **Decision support.** Outputs are evidence and prioritization aids for human reviewers.
