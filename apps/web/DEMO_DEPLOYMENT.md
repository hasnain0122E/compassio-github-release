Vercel demo settings

- Root Directory: `apps/web`
- Framework Preset: Next.js
- Node.js: 22.x
- Install Command: `pnpm install --ignore-workspace --frozen-lockfile`
- Build Command: `npm run build`
- Output Directory: Next.js default (leave override disabled)
- Environment, Preview and Production: `NEXT_PUBLIC_COMPASSIO_DEMO_MODE=true`
- No API URL, Python service, database, model artifact or secret is required.
- Keep inclusion of files outside the root directory disabled.

The public demo flag is compiled at build time; redeploy after changing it. With
the flag absent or false, the existing API client and HTTPS backend validation
remain active. Demo mode dynamically loads only author-written sample records;
it never contacts a backend. Shortlists persist in this browser under a separate
demo storage key. Screening uses deterministic keyword rules, not ML inference.
Recorded C05/C09/C11 scorecards are public Markdown from prior local evaluations.

Local verification (PowerShell, in apps/web):

```powershell
$env:NEXT_PUBLIC_COMPASSIO_DEMO_MODE='true'
npm run lint
npm run typecheck
npm run test
npm run build
npx playwright test --config playwright.demo.config.ts
```

No push or deployment is performed by this change.
