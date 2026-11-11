# Frontend component architecture

Next.js App Router pages supply metadata and Suspense boundaries. Interactive
views are client components under `src/app/(app)`. Next.js 16 bundled guidance
was read before continuing implementation. The `(app)` layout composes Providers
and AppShell; the landing page keeps its distinct editorial layout.

| Layer | Responsibility |
| --- | --- |
| `lib/api-types.ts` | Generated backend contract; never manually edited |
| `lib/api.ts` | Versioned typed requests, errors, GET cache, deduplication, serialized local-demo request queue |
| `lib/use-api.ts` | Loading/error/retry state and on-demand actions |
| `lib/selection.tsx` | Up to ten selected projects persisted locally, shared by compare and scenarios |
| `lib/format.ts` | Display-only decimal formatting; no financial aggregation |
| `components/styles.ts`, `ui.tsx` | Buttons, panels, forms, states, disclosures, keyboard tabs |
| `components/shell.tsx` | Desktop rail, mobile modal, command menu, theme and selection tray |
| `components/finance.tsx` | Meaning badges, facts, declarations, access and exclusions |
| `components/charts.tsx` | Accessible SVG/year charts, ranked bars, score dial and allocations |
| `components/analytics-panels.tsx` | Shared live financial and coverage views |
| `components/source-notice.tsx` | One compact access/attribution notice, expandable backend notice and source metadata |

GET subscribers may cancel independently without aborting another component's
shared request. Queue slots transfer directly to queued callers. Retrying
invalidates the GET cache before reloading. Components ignore aborted results.
Screening comparison uses the submitted text or returned source evidence ID;
editing inputs cannot silently switch the comparison project. Prioritization is
restricted to saved shortlist IDs and runs only when requested. Comparison is
also explicitly requested, rather than automatically run while selecting projects.

Discover uses native history replacement (supported by the bundled Next.js
guide) to keep filters URL-backed without losing rapid successive changes.
The full evidence and financial components are reused inside progressive
disclosures. Navigation has four primary destinations; legacy dashboard links
redirect to Discover. Analytics and scenarios remain secondary deep links.

No source data is posted to external AI services. Model inference stays in the
local API. Review tokens are never added to browser bundles. Challenge navigation
is an extensible registry only; no C05/C09 implementation is integrated here.

Unit tests cover financial formatting, backend error conversion, cache freshness,
independent cancellation and queue concurrency. Playwright tests exercise real
API-backed actions; network-abort tests simulate transport failure without
fabricating successful data responses. Reports/screenshots stay in ignored
`artifacts/frontend/` to avoid committing source records.
