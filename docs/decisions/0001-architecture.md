# ADR 0001 — Foundation architecture

- **Status:** Accepted (Task 001)
- **Date:** 2026-11-08

## Context

Compassio is a hackathon MVP that must still be maintainable and scientifically credible. It needs
a web UI, an HTTP API, and an ML/data codebase whose results can be reproduced and audited. The
team develops on Windows.

## Decision

1. **Modular monorepo**, three deployable/installable units: `apps/web`, `apps/api`,
   `packages/compassio_ml`. No microservices, message queues or service mesh.
2. **Python uv workspace** with a single `uv.lock`; each Python unit is an installable src-layout
   package built with hatchling. Python 3.12.
3. **FastAPI + Pydantic** for the API; typed settings via pydantic-settings; versioned routes under
   `/api/v1`; explicit CORS origins.
4. **ML separated from HTTP.** `compassio_ml` has no web dependencies; pipelines run offline and
   produce versioned artifacts; the API only reads them.
5. **Next.js (App Router) + TypeScript + Tailwind** for the web app, as a standalone pnpm project.
   It becomes part of a pnpm workspace only when `packages/shared` contains generated API types.
6. **Data stays out of Git.** Raw/derived data and models are git-ignored; small JSON provenance
   manifests are committed and validated by a typed model.
7. **Defer heavy choices.** No database, ML framework, experiment tracker or charting library is
   installed until the task that needs it (candidates in `docs/architecture/tech_stack.md`).
8. **Decision support framing.** Outputs are evidence and prioritization aids; the system never
   approves funding.

## Consequences

- One command each for Python and web gates; CI mirrors them without secrets or datasets.
- Product strings are duplicated between API and web (`brand.ts`) until type generation exists.
- Adding a database or ML stack later requires a new ADR, keeping the choice explicit.
- The standalone web project means two lockfiles (`uv.lock`, `apps/web/pnpm-lock.yaml`).

## Alternatives considered

- *Separate repositories* — rejected: coordination overhead for a small team.
- *Django* — rejected: heavier than needed; FastAPI's OpenAPI output suits generated TS types.
- *Poetry / pip-tools* — rejected in favour of uv's speed, workspaces and Python management.
- *Installing the planned ML stack now* — rejected: large, unused, and premature.
