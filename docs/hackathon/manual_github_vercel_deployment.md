# Manual GitHub and Vercel handoff — no deployment performed

These are operator instructions for later review. This task did not push, merge
into main, connect hosting, upload artifacts or deploy anything.

## Publication boundary

The full canonical-data product is currently authorized only for local inspection
or the scoped event demonstration. All source rights remain `not_reviewed`.
User-reported organizer authorization is not a public redistribution or model
hosting licence. Do not upload the database, models, raw/training batches, private
review data, experiment records or environment secrets to GitHub, Vercel or a
backend provider under that permission.

A public frontend may show code/static challenge summaries and honest unavailable
states. It cannot become the full public canonical-data product under current
permissions. Production forces public access and disables inference. Keep that
behavior. Do not deploy in development/event mode to bypass these gates. A later
rights review and separately authorized serving design are prerequisites for
public source data or model inference.

## GitHub — operator performs these steps

1. Review the final integration report, readiness report, diff and local evidence.
   Verify the preserved backend tag and each challenge tip. Choose a private
   repository until code and data publication rights have been reviewed.
2. Inspect staged/tracked paths before upload:

   ```powershell
   git status --short --branch
   git log --graph --oneline integration/battleverse-final-product
   git diff --stat backend-ready-for-battleverse integration/battleverse-final-product
   git ls-files data models artifacts
   git remote -v
   ```

   Tracked data manifests/README files are intentional metadata. Runtime files
   should not appear. Do not force-add ignored files. Check the repository history
   for credentials and unintended source records, not only the tip.
3. If needed, create the repository manually in GitHub and add its URL as origin.
   Do not replace an existing remote without reviewing it. When approved, the
   operator can run:

   ```powershell
   git push -u origin integration/battleverse-final-product
   ```

4. Open a pull request targeting main. Include the local-only release scope,
   verification counts, remaining skips, preserved artifact hashes and limits.
   Review and merge only after manual approval. No force push, reset or deletion
   of challenge branches/worktrees is needed. Keep the frozen backend tag as a
   reference; any later release tag should have a new name.

## Vercel frontend

Vercel supports importing a Git repository as a project and detects Next.js.
Use its [project setup documentation](https://vercel.com/docs/projects) and
[Next.js framework guide](https://vercel.com/docs/frameworks/full-stack/nextjs).

After GitHub review and manual upload:

1. Import the repository manually. Choose Next.js and Root Directory `apps/web`.
2. Use the committed pnpm lockfile, install command
   `pnpm install --frozen-lockfile`, build command `pnpm build`, and the framework's
   default output. This app uses Next server features; it is not a static `out/`
   export. Node 24 was tested locally; choose a supported compatible runtime.
3. Set `NEXT_PUBLIC_COMPASSIO_API_URL` to the separately reviewed HTTPS backend
   origin before building. It is a public browser setting, never a place for tokens.
   This value is baked into the frontend build: rebuild when it changes. Without
   it, browsers try loopback port 8000 on the visitor's own computer.
4. Configure preview and production values separately. Add only their exact
   approved origins to backend CORS; never use wildcard origins to work around
   failing access checks. HTTPS frontend/API avoid mixed-content failures.
5. Keep the production app's data-unavailable and inference-disabled messages
   honest. Vercel preview protection does not itself clear source rights.
6. Manually check landing, all navigation, deep links, themes, mobile layouts,
   static scorecard URLs, API health/CORS, 403/413/429 and empty/unavailable states.
   Do not advertise a full online canonical-data demo before its rights gates pass.
7. Record the reviewed Git SHA and hosting configuration. If validation fails,
   use the provider's previous deployment rollback and retain backend access gates.

## Separate backend hosting requirement

The Vercel frontend does not launch this repository's uv-managed FastAPI process,
install scikit-learn for it, or provide its local read-only SQLite/models. Plan a
separate Python host/container/VM with a persistent, controlled local artifact
mount if a later authorized backend deployment is approved. FastAPI's
[deployment concepts](https://fastapi.tiangolo.com/deployment/concepts/) describe
the separate process, HTTPS, startup and worker considerations.

For a code-only production backend with current fail-closed access:

```text
Working directory: repository root
Install: uv sync --locked
Command: uv run uvicorn compassio_api.main:app --host 0.0.0.0 --port <provider-port> --workers 1 --no-proxy-headers
COMPASSIO_ENVIRONMENT=production
COMPASSIO_SOURCE_DATA_ACCESS=public
COMPASSIO_ML_V2_LOCAL_DEMO=false
COMPASSIO_C09_ENABLED=false
COMPASSIO_C11_ENABLED=true
COMPASSIO_CORS_ORIGINS=<exact-reviewed-frontend-origins>
```

Set provider environment variables through its secrets/config interface. Use TLS
termination and an explicitly reviewed proxy/IP configuration: `--no-proxy-headers`
means an unreviewed reverse proxy can collapse all users into one rate-limit peer.
Do not trust arbitrary forwarded headers. Keep one worker until limiter/review
state is moved to a separately designed shared service. PostgreSQL is not a
verified replacement for this build; do not silently switch databases.

Do not attach canonical artifacts under present local-only permissions. `/health`
can work without them; production source routes and inference should refuse access.
A fully functioning online product requires documented source/model serving rights,
an approved dataset/artifact transfer, appropriate authorization, verified storage,
proxy design and fresh production regression/security/capacity testing. Those are
explicit future blockers, not deployment steps already completed here.
