# Judge journeys and local reproduction

From the frontend worktree root:

```powershell
uv run python scripts/demo_preflight.py
powershell -ExecutionPolicy Bypass -File scripts/start_api.ps1
# Separate terminal
powershell -ExecutionPolicy Bypass -File scripts/start_web.ps1
# Separate terminal
cd apps/web
pnpm test:e2e
```

Install Chromium once with `pnpm exec playwright install chromium`. An existing
compatible local Chromium can be selected with `COMPASSIO_BROWSER_PATH`.
`COMPASSIO_WEB_URL` overrides the test web URL. Keep the API on loopback and
respect its configured CORS origins. Use a freshly started server after a new
production build so it serves matching HTML and JavaScript chunks.

1. Open Discover at `/projects`. Search **flood**, choose **Pakistan**, and
   open a project card. Country and topic are the only initially visible filters;
   source, years, research climate label and sorting live in **More filters**.
2. Read the project purpose, climate evidence and historical funding. Open
   **View evidence and sources** for raw figures, provenance, source references,
   documents, completeness and limitations. **Add to shortlist** saves it locally.
3. Return to Discover and save a second project. Open **My Shortlist** and press
   **Compare selected projects**. Comparable financial facts stay separate by
   meaning and basis. Duplicate/package warnings remain prominent.
4. Use **Prioritize my shortlist** to organize only the saved projects for review.
   Choose a plain-language focus; fine-tune weights only if needed. The result
   explains the recorded evidence, not funding approval or financial returns.
5. Open **Analyze a Project**, enter a title/description and press **Analyze
   project**. Read the actual climate-text screening signal and short explanation.
   **Model details** reveals the frozen threshold, feature contributions and v1
   comparison; **How it works** contains version/evaluation details. A permitted
   project can also be analyzed directly from its evidence page. Unsupported
   sources are never automatically screened or suggested for bypass.
6. From My Shortlist, optionally choose **Explore a hypothetical funding scenario**.
   Supply a budget and method; limits/objectives are advanced. The server reports
   exact budget conservation. This is a simulation, never an offer of funding.
7. **More tools** contains Advanced insights and hypothetical scenarios. Historical
   funding analytics and full source coverage remain accessible away from the
   main Discover / Understand / Shortlist journey.

All steps operate on the pinned local database and real API. They demonstrate
review support, not funding approval, open funding offers, financial returns or
verified climate impact. Record-level screenshots and response captures are
local-only artifacts and must not be published outside the authorization scope.
