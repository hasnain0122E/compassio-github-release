@AGENTS.md

# Web (apps/web) — scoped instructions

Root rules in `/CLAUDE.md` apply. Additions for the frontend:

- Next.js 16.4 App Router + TypeScript + Tailwind CSS v4, managed with pnpm (run commands in
  this directory). Read `node_modules/next/dist/docs/` before using unfamiliar Next APIs.
- Type check is `pnpm typecheck` (`next typegen && tsc --noEmit`); `LayoutProps`/`PageProps`
  are generated globals.
- No UI may display invented projects, amounts, scores or charts. Until a real API endpoint
  exists, show an honest empty/unavailable state instead of sample data.
- API types are GENERATED into `src/lib/api-types.ts` by `scripts/generate_api_types.py` (see
  `packages/shared/README.md`); regenerate after API schema changes. Do not hand-write
  duplicate API types beyond `src/lib/brand.ts`.
- Keep dependencies minimal; justify each new one. No web fonts fetched at build time.
- Accessibility: semantic landmarks, one `h1` per page, sufficient colour contrast in both themes.
