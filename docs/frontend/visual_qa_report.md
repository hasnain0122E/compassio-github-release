# Visual QA — 2026-11-11

Historical integration QA. Current product redesign QA is recorded in
[redesign_visual_qa.md](redesign_visual_qa.md).

Local production build, real loopback FastAPI, installed Chromium 1248 selected
through `COMPASSIO_BROWSER_PATH`, Playwright 1.65. Screenshots and failure traces
are local-only under ignored `artifacts/frontend/`.

All nine route views (eight core routes plus Challenges) were rendered at 390,
768 and 1440px with reduced motion. Automated checks cover one h1 per view, no
document-wide horizontal overflow, completed loading states and no browser
page errors. Financial/evidence tables intentionally scroll inside their panels.

Visual inspection covered the landing page, desktop dashboard, mobile analytics,
tablet project detail, mobile screening/ranking/scenario results and dark desktop
projects. Light and dark screenshots were captured at all three widths. This is
representative Chromium QA, not a claim of exhaustive cross-browser or formal
accessibility certification.

Observed defects repaired:

- Mobile ranked financial bars had zero usable width between labels and values.
  Bars now occupy a separate row at narrow widths, with a minimum desktop slot.
  Browser assertions verify their containers remain wider than 20px.
- Expanded priority-component tables could force page overflow. They now have
  a local scroll container and readable minimum width.
- White text on the brighter dark-theme action green had insufficient contrast.
  Primary actions now use theme-specific foreground tokens.
- Arrow keys changed the selected tab without moving focus. Arrows, Home and End
  now move focus and prevent default page scrolling.
- Full source descriptions overwhelmed the screening result. The initial
  highlighted excerpt is limited to 900 characters; full evidence remains in a
  native disclosure, and the submitted model input is unchanged.

Native menu dialogs were tested for opening, Escape dismissal and focus return.
The command menu was exercised with keyboard search/navigation. Real empty
searches, missing projects, source denial and simulated transport failure/retry
are included in the browser suite. A failed transport is simulated by aborting
requests; successful data responses are never mocked.

Limitations: no physical phone, Firefox, Safari, screen-reader session, offline
network-adapter test or exhaustive contrast scanner. Long tables/charts require
local horizontal scrolling on small screens. Final test counts and reproduction
commands are recorded in the Task 011 integration report.
