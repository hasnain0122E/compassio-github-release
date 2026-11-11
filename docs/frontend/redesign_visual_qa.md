# Product redesign visual QA

Date: 2026-11-12. Real loopback FastAPI with pinned data/models; Next.js
production frontend; Playwright 1.65 and the installed Chromium 1248 executable.
No successful response is mocked. Screenshots remain local and git-ignored.

## Reviewed states

All core routes, the dashboard redirect and the Challenges shell were rendered
at **390px, 768px and 1440px**. Discover was checked in light and dark at each
width, with no document-wide horizontal overflow or browser page errors in the
passing responsive run. Reduced motion was enabled. Advanced table content
retains local horizontal scrolling.

Actual screenshot review covered:

- Desktop Discover: search-first hierarchy, two-column readable cards, subdued
  count, active filter chips and four primary navigation destinations.
- Mobile Discover: keyword search, compact country/topic controls, separate
  More filters action, one card column and normal shortlist actions.
- Project detail: concise source description, climate evidence and funding facts;
  optional full description, raw evidence and source details.
- Analysis: description/result hierarchy, actual text score, concise explanation,
  hidden model/benchmark detail and correct disabled empty-input action.
- My Shortlist: empty state, saved cards, explicit comparison, prominent duplicate
  warnings and optional priorities/scenario tools.
- Expanded priority evidence, filter drawer and mobile analysis/comparison results.
- Dark Discover: charcoal forest surfaces, lime active navigation, readable text,
  emerald actions and visible keyboard focus.

## Defects corrected through QA

Encoded IDs initially failed when navigating from a result card. The original
decoding behavior was restored. Rapid consecutive filters initially lost an
earlier change because router replacements shared stale query state. Native
history updates now merge the current URL immediately. A combined retry reloads
both filter metadata and results and avoids duplicate primary error panels.

SQLite concurrency errors were observed in the frozen local backend. The
frontend request queue was reduced to one, without changing backend code. The
main result state and both source/package warning types were subsequently
tested live. The remaining multi-client pooling limitation is documented.

Visual refinement moved repayment groups out of the initial funding comparison,
made priority preset selection visible, reduced the mobile filter height, added
search focus treatment and retained the full financial evidence in disclosures.

## Test interpretation and artifacts

The responsive suite waits for *visible* loading placeholders to finish.
Deferred benchmark content may legitimately contain an unrequested loading
placeholder inside a closed disclosure. It is not forced to load just to
satisfy a DOM count. Successful API results are always real.

Artifacts use `artifacts/frontend/redesign-*`, including light/dark Discover,
project detail, empty shortlist, analysis, comparison, priority evidence and the
filter drawer. `browser-results.json` stores the latest suite result. These
contain source-derived content and are not committed, uploaded or published.
Final test counts and commands are in the product redesign phase report.

Final production browser suite: **11 passed in 50.0 seconds**. All successful
responses were served by the real backend. The separate API smoke script remains
incomplete at its oversized-request 413/body-reset case; it is not counted as a
passing full smoke run. See the phase report for the observed failure.

## Limits

This is representative Chromium QA, not formal accessibility certification.
No Firefox/Safari, physical-device, screen-reader, exhaustive contrast-scanner
or physical network-disconnect test was performed. Advanced analytics and long
evidence remain detailed when explicitly opened. Literal keyword matching,
source-specific sector labels and separate source records remain backend limits.
