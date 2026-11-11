# Task 010 product UX redesign

Date: 2026-11-12. Branch: `feature/task010-complete-frontend`.
Starting checkpoint: `b03a3af`. Worktree: `D:/AI LEARNING/compassio-frontend`.

## Outcome

Refactored the existing working platform around **Discover → Understand →
Shortlist**. The approved landing page and its component files are unchanged.
Four primary navigation destinations replace seven equal tools. Dashboard links
redirect to Discover; advanced analytics and scenarios remain available through
secondary/contextual links. This is a functional implementation, not a mockup.

## Implemented

- Discover: prominent literal keyword search, four working topic suggestions,
  country/topic controls, native advanced-filter drawer, URL state, chips/reset,
  twelve readable result cards per page and normal shortlist actions.
- Project detail: purpose/location, source climate evidence and selected funding
  facts first. Full descriptions, all financial facts/raw units, source metadata,
  documents, relationships and limitations remain expandable. No unsupported
  source is automatically screened or suggested for a restriction bypass.
- Analysis: Compassio Climate Intelligence, actual model result, concise signal
  explanation and secondary Powered by ML v2 label. Thresholds, feature evidence,
  v1 comparison, benchmark tables and evaluation caveats are on demand.
- My Shortlist: discovery-led empty state, locally saved cards, explicit
  comparison, duplicate/incomparability warnings and review priorities scoped
  only to saved IDs. Mathematical weights and missing-information matrices are
  optional. No manual database ID is needed for the normal journey.
- Advanced tools: the tested hypothetical scenario planner is preserved, with
  source-reference entry, objectives and extra limits progressively disclosed.
  Analytics retains its working tabs away from the main product journey.
- Visual polish: app-scoped warm neutral/forest surfaces, restrained lime active
  navigation, softer cards, stronger typography, wider whitespace, visible search
  focus, dark appearance, reduced motion and mobile layouts.
- Challenges: separate C05/C09 showcase status with no fabricated outcomes or
  merged demonstrations. Future entries remain data-driven.
- Source notice: compact local-mode qualification and attribution, with the full
  backend notice, citations, licence notes and source references available.

Details: [product UX](../frontend/product_ux_redesign.md),
[before/after](../frontend/redesign_before_after.md),
[visual QA](../frontend/redesign_visual_qa.md). Existing architecture, design,
route inventory, user journeys and reference documentation were updated.

## Financial and model integrity

The frontend continues to use generated types and real versioned API endpoints.
No financial values, projects, labels, scores or successful API responses were
invented. Browser tests exercise live requests. The sole transport simulation
aborts requests to verify error/retry behavior; it never returns fake data.

Commitments, approvals, disbursements, co-financing and repayments retain their
backend meanings. The initial detail view favors funding flows; other facts
remain available in evidence. Comparison groups preserve currency, basis, level
and source. Totals remain server-owned, nullable and subject to duplicate rules.
Whole multi-country values are qualified. Missing amounts never become zero.
Scenarios remain hypothetical with exact server-side conservation.

ML thresholds, artifacts, registry and rights rules are unchanged. The model
screens text relevance; the UI does not promise impact, funding approval or
returns. ML v1 comparison uses the originally submitted text/source record even
after editing inputs. Denied access remains a visible backend error.

## Verification and evidence

Frontend gates: `pnpm lint`, `pnpm typecheck`, `pnpm test` and `pnpm build`.
Unit suite: **16 passed**, two files. Production compilation/type generation and
all retained routes succeeded.

Contract freshness: `uv run python scripts/generate_api_types.py --check` →
**up to date**.

Focused backend regression command:

```powershell
uv run pytest tests/api/test_decision_engine.py tests/api/test_screening.py tests/api/test_event_access.py tests/api/test_api_types.py -q
```

**105 passed in 91.25 seconds**. Financial contract regression:
`uv run pytest tests/ml/test_finance_contract.py -q` → **19 passed**.
The complete 742-test repository suite was not rerun for this frontend-only
redesign; its earlier results remain historical in Task 011, not new evidence.

Runtime verification: preflight passed; all five pinned runtime artifacts passed
`uv run python scripts/runtime_artifacts.py verify`. Database SHA-256 remains
`d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385`.

The redesigned Playwright suite covers all six founder journeys: flood/Pakistan
discovery, detail/source evidence, shortlist comparison, actual ML v2 and v1,
denied source inference, saved-ID prioritization, optional scenario conservation,
advanced analytics, empty/error/retry states, 390/768/1440px, dark appearance,
keyboard menus and reduced motion. The final production run passed **11/11
tests in 50.0 seconds**, one worker, against real API responses. Both the
same-package and cross-source duplicate cases were exercised, along with
mobile result-state screenshots and filter-drawer focus return.

Screenshots, traces, API captures and JSON results stay under ignored
`artifacts/frontend/`. They contain source-derived records and were not committed
or published. Tests use the installed Chromium executable through
`COMPASSIO_BROWSER_PATH`; launch commands and scripts remain local-only.

The official API smoke script was also run twice against the local server.
All preceding workflow checks passed, including real inference, permissions,
protected totals, duplicate safeguards, deterministic ranking and conservation.
Both runs stopped at the oversized-body check: HTTP 413 was returned, but reading
its body raised Windows `ConnectionResetError` / WinError 10054. Therefore the
full smoke script is **not reported as passing**, and its requested final JSON
capture was not written. The script/backend were not modified to hide the issue.
This lies beyond normal frontend form sizes and requires a separate authorized
backend/runtime investigation.

## QA fixes and limitations

Browser QA caught and corrected encoded project-ID handling, rapid filter-update
races and incomplete combined retry behavior. Preset selection now has visible
feedback; mobile filters remain compact. Repayment/non-funding comparison groups
are expandable. A test fixture initially retained selections between two warning
checks; the test now removes the first pair before exercising the second pair.

Concurrent local requests exposed SQLite closed-connection errors in the frozen
backend. The client now serializes requests, retaining caching and shared GET
deduplication. This improves local demo stability; it does not claim to fix
multi-client backend pooling. No protected code was changed to suppress a test.

Remaining limits: literal keyword search, source-specific sector vocabulary,
separate source records that may have matching titles, a ten-project local
shortlist and detailed tables when explicitly opened. No new persistence service,
semantic search, wallet, real allocation or prediction of impact was added.
Cross-browser, physical-device, screen-reader, exhaustive contrast and physical
network-disconnect testing remain unperformed. Optional persistent human reviews
remain outside the implementation; no decorative save-review action is exposed.

## Isolation

`main` and the dereferenced `backend-ready-for-battleverse` tag still point to
`8c083509e324d76aafc7ee097dc4345a94314afd`. No diff exists in backend packages,
configs, data/model artifacts, OpenAPI or generated TypeScript contracts. No
challenge branch was checked out, edited, merged or deleted. No push, deployment,
retraining, hard reset or cleanup of valid work was performed.
