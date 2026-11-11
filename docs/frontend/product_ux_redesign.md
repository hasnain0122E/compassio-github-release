# Compassio product UX redesign

Product promise: **Find climate-related projects. Understand their funding.
Know what to review next.**

The product now serves one journey: **Discover → Understand → Shortlist**.
The approved marketing landing page is preserved. The redesign refactors the
working frontend, its generated contracts and shared components rather than
substituting mock data or rebuilding the backend.

## Information architecture

Primary navigation, in order:

1. Discover (`/projects`).
2. My Shortlist (`/workspace`).
3. Analyze a Project (`/screening`).
4. Challenges (`/challenges`).

`/dashboard` redirects to Discover, preserving existing landing links and deep
links. Advanced insights (`/analytics`) and hypothetical scenarios (`/scenarios`)
remain functional under More tools. The scenario action is also contextual to
the shortlist. Neither is promoted in the selection tray.

## Discover

A prominent keyword search leads the page. Suggestions map to real literal
keywords: Flood protection → `flood`, Clean energy → `solar`, Water management
→ `water`, Climate-resilient farming → `irrigation`. The UI explicitly describes
keyword search, not semantic search. Only country and available topic/sector are
visible initially. Source, year, research label and sorting use a native modal
drawer with focus containment, Escape dismissal and focus return.

URL-backed filters use Next.js-supported native history updates. Rapid successive
changes preserve the complete query. Search debouncing is cancelled on explicit
search, topic choice and reset. Cards show exact source excerpts, country, year,
available topic/annotation, View project and Add to shortlist. No inferred AI
score is invented. Result count and pagination are secondary; 12 records are
loaded per page. Sources retain separate records, even when titles look alike.

## Understand

Project detail answers three questions: what the project does, what source
climate evidence exists, and what historical funding is reported. Descriptions
start with an exact excerpt; full descriptions remain expandable. The initial
financial view shows up to three funding-flow facts with their actual currency,
price basis and level. Repayments are not promoted as funding.

View evidence and sources retains all headline/breakdown facts, raw observations
and units, source identifiers, related records, documents, completeness, warnings
and limitations. A source-package warning remains visible in the normal story.
AI analysis is offered for AidData records only; other sources receive an honest
source-evidence explanation, without suggesting a permission bypass.

## Analyze a Project

The title is Compassio Climate Intelligence; Powered by ML v2 is a secondary
detail when the backend selects that engine. Title/description → Analyze project
→ real score, interpretation and concise explanation. The score describes text
screening, never impact, returns or funding eligibility. Borderline and negative
results keep their distinct backend interpretations.

Model details contains thresholds, feature decomposition, source reference,
limitations and optional same-input ML v1 comparison. How it works contains
version, authorization and evaluation information; benchmark tables are another
disclosure and load only when requested. No visible result is a canned example.
Illustrative text is clearly labeled; its model response is calculated live.

## My Shortlist

An empty shortlist leads to Discover; there is no source-ID input. The existing
local selection store and ten-project cap are preserved. Saved cards link back
to evidence. Comparison runs on explicit request. Source/package duplicate
warnings remain prominent, comparable funding groups remain separate, and
other financial/non-funding observations are expandable. Missing-information
matrices are optional.

Prioritize my shortlist sends only saved IDs to the real decision endpoint.
Plain-language presets adjust explicit weights; their selected state is visible.
Fine-tune priorities exposes the mathematical weights. Scores and evidence remain
reviewable. No ranking is described as approval or a forecast of returns.

## Progressive disclosure and visual language

The workspace extends Bearing through `.product-app`: warm neutral backgrounds,
forest navigation, emerald actions, a restrained lime active state, soft rounded
cards and stronger editorial headings. Dark surfaces are charcoal forest.
These overrides do not apply to the landing page. Local fonts, tokens, theme
behavior, focus outlines and reduced-motion support are retained.

One compact notice states the local access mode and that sources are not
licence-cleared. The complete backend notice, source attribution/citations and
source metadata remain accessible on the same page. Financial warnings are not
suppressed. This is progressive disclosure, not a change to rights or semantics.

## Operational constraint

During live browser QA, concurrent local API requests produced SQLite closed-
connection errors. Backend business logic is frozen, so the frontend now
serializes its requests (`MAX_CONCURRENT = 1`), retaining caching, deduplication,
independent cancellation and fresh retries. This trades some advanced-screen
load speed for a reliable local demo. It does not repair the backend pool or
guarantee safety across several independent browser clients. A backend pooling
fix belongs in a separately authorized workstream.

No backend, data/model artifact, registry, permission configuration or generated
contract was changed. C05/C09 are separate showcase entries without fabricated
results. Remaining verification limits are in the redesign QA/report documents.
