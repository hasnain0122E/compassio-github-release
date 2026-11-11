# packages/shared — generated TypeScript API types

TypeScript types are **generated** from the API's OpenAPI schema, never hand-written:

```
uv run python scripts/generate_api_types.py          # writes apps/web/src/lib/api-types.ts
uv run python scripts/generate_api_types.py --check  # exit 1 if stale
```

The generator is a small, dependency-free script (no third-party OpenAPI generator yet). The
output currently lives in `apps/web/src/lib/api-types.ts` because the web app is a standalone pnpm
project, not a pnpm workspace; `tests/api/test_api_types.py` fails if it drifts from the live schema.
Moving it into this package (as a pnpm workspace member) is deferred.

`apps/web/src/lib/brand.ts` still duplicates the three product strings from `/api/v1/meta`.
