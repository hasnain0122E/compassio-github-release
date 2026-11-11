# Task 006-INT integration report

Integration branch: `integration/task006-combined` in the application worktree. The merge
commit and final verification evidence are recorded in the final update below.

## Verified source checkpoints

- Backend `main`: `bd2fe3085fcc30d89f9ace9d4cc3326598cf31b0`.
- ML `feature/ml-v2`: `22f44628155572b2a46c7b25a40f4ff02e85ab49`.
- Both worktrees were clean; the complete ML-AUTO implementation was committed.
- V1 baseline passed 11/11 before the merge. All required v1 inputs, released artifact,
  test-access ledgers, backend snapshot and real SQLite DB were present.
- V2 source snapshots existed only in the ML worktree; Git did not copy them. The combined
  checkout reuses its `external_raw/` directory read-only and owns new outputs locally.

## Conflicts and implementation

Actual merge conflict: only `docs/phases/phase_plan.md`. Resolution preserves the backend,
ML review-gate and ML-AUTO rows, with no blanket ours/theirs strategy. `.gitignore` and
`CLAUDE.md` auto-merged and were reviewed to retain both tracks. Root `pyproject.toml`,
`uv.lock`, test configuration and source registries had no conflicting changes. Both
`compassio-v2` and `compassio-v2-quality` console scripts are retained.

Integration-specific source changes:

1. `external/paths.py`: narrowly bounded same-checkout layout plus optional read-only
   `COMPASSIO_V2_EXTERNAL_INPUT_ROOT`; every write rechecks separation. Separate-worktree
   protection remains. ML cannot read current-checkout or input-root backend snapshots/DB.
2. `cli/v2_cli.py`: path display includes the resolved external-source input directory.
3. Backend `db_cli.py`: status/verify/report and migration-status inspection use the read
   engine, preserving explicit write engines only for migration/ingestion.
4. `.env.example` and [combined path architecture](../architecture/combined_data_paths.md)
   document independent data/DB/model/evaluation namespaces and distinct permissions.
5. `tests/test_integration_boundaries.py`: regression checks for registries, source rights,
   same/separate-checkout roots, denied outputs, denied backend source inputs, sealed-pool
   exclusion, readonly verification commands, public denial, and source-checkpoint integrity.
6. `configs/task006_integration_reference.json`: metadata-only portable hashes of 22 unchanged
   canonical/backend/ML policy, v1 lock/release/finance/model/migration source files.

No migration, source manifest, existing registry, frozen dataset or released model is edited.

## Pre-merge real backend evidence

Read-only probe: `artifacts/reports/task006_int_backend_probe.py`, run from the application
worktree via its own uv environment. It uses `create_read_engine`, SQLAlchemy sessions and
actual FastAPI ASGI requests against the real database, never mocks, migrations or ingestion.
Report: ML worktree `artifacts/reports/task006_int_backend_before.json`.

- SQLite revision `0003`; database SHA-256:
  `d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385`.
- 27/27 audited comparisons and structural checks passed.
- 26,499 projects, 93,881 financial observations, 26,020 annotations, 818 documents,
  620 country aggregates, 128 restricted historical rows, 379 enrichments.
- 379/379 GCF export projects enriched; 876 readiness rows remain distinct from funded projects.
- 16 real-data API requests passed, including search, GCF detail, linked documents, Pakistan
  GCF timeline, country aggregates, overview and every one of the 10 financial metrics.
- Eight default-public/production checks returned 403. Database hash unchanged by requests.
- Financial-observation and annotation-table hashes and complete API responses are retained
  for exact comparison after integration. No new financial observation or project is ingested.

## Validation before first integration commit

- Canonical manifest: nine entries, hashes/sizes match.
- Backend registry: one existing snapshot verified; tracked/local registries agree.
- Database verification on existing DB: 27/27, no missing extended sources.
- Focused regression/ML workflow suite: **117 passed**.
- Ruff: passed. Strict mypy: passed, 178 source files.
- Next.js lint/typecheck/production build: passed.
- V1/ML protected artifacts remain unchanged; original 24 sealed/pilot/worksheet artifacts
  are snapshotted by hash without opening labels.

Full combined pytest and clean-commit v2 build/donor-audit reproducibility are deliberately
recorded after execution in the final update, not assumed from either source report.

## Boundaries and pending work

Source registries are independent. Public display, internal research, ML use, third-party AI
processing, external transfer, attribution and redistribution have separate authorities, as
documented in the architecture table. All source rights stay `not_reviewed`; no clearance is
invented. GCF API/page restrictions, consumed-test exclusions and AI-provider denial persist.

PostgreSQL execution remains pending: no configured disposable test URL or detected local
PostgreSQL tooling. Compile-only dialect checks are not execution proof. No server/driver is
installed for this task. Human external labels remain absent; donor-only experiments may
proceed within the earlier internal-research scope, but no model or independent accuracy
claim is produced. Transport/urban coverage, source shortcuts and label noise remain risks.

No push, deployment, merge into main, reset, clean, discard, stash or source-data overwrite
is performed. The main branch pointer remains at the verified backend checkpoint.

## Final verified integration checkpoint

Actual merge commit: **`cfd98bb0c14c43c501fafc2c69b24c96dc7d2f49`**, with parents
`bd2fe3085fcc30d89f9ace9d4cc3326598cf31b0` and
`22f44628155572b2a46c7b25a40f4ff02e85ab49`.
Follow-up source fix: **`7034596d46b78f5a08f86c1d0347fc6d4d12d499`**.
The final branch tip also includes this evidence report; its hash is provided in the final
handoff (`git rev-parse integration/task006-combined`). No source branch pointer was moved.

The only discovered integration failure was `verify-retrievals` formatting a source path
relative to the output root. With a read-only external root, that relative path did not
exist. The verifier now formats paths relative to `external_raw`; a regression test covers
the case. No source-file checksum failed. The original 117-case focused suite passed;
the added verifier regression also passed and is included in the final full suite.

There are **60 changed files versus the backend checkpoint**, comprising imported ML work
and the integration-specific changes listed above. `CLAUDE.md`, `.gitignore`, console scripts,
test configuration and shared dependency configuration were reviewed. `uv.lock` is unchanged;
no new dependency was added. The metadata-only reference pins 22 unchanged source/registry/
lock/finance/release/migration files to their respective source commits. Migrations `0001`,
`0002`, `0003`, SQLAlchemy models, financial aggregation code and released-model loader are
byte-equivalent after repository text normalization to the backend checkpoint.

### Actual combined checks

Commands ran in the application worktree, with
`COMPASSIO_V2_EXTERNAL_INPUT_ROOT=D:/AI LEARNING/compassio-ml-v2/data/ml_v2/external_raw` for
ML commands. `COMPASSIO_DATA_ROOT` selects the application `data/` input root. V2 outputs
are owned by the combined checkout at `data/ml_v2/`.

| Command / check | Actual result |
| --- | --- |
| `uv run compassio-manifest validate` | Nine entries; hashes and sizes match |
| `uv run compassio-v2 verify-baseline` | **11/11 PASS** before merge and after integrated build/audit |
| `uv run compassio-v2 verify-retrievals` | All five existing retrievals verified after the display-path fix |
| `uv run compassio-db registry` | One snapshot verified, tracked/local metadata identical |
| `uv run compassio-db --database-url sqlite:///data/db/compassio_dev.sqlite verify` | **27/27 comparisons**, structural checks pass, all extended sources present |
| `uv run compassio-v2 build` (twice) | `v2build_a37deb181332`; second run **byte-identical** |
| Eight generated build reports, hashes before/after rebuild | **8/8 identical** |
| `uv run compassio-v2-quality audit --build-id v2build_a37deb181332` (twice) | `quality_7e70e77d22bba416`; all three deterministic outputs reproduced |
| `uv run pytest` | **621 passed, 2 skipped**, 623 collected, 471.39 seconds |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 233 files already formatted |
| `uv run mypy` | No issues in 178 source files |
| `pnpm.cmd lint` in `apps/web` | Exit 0 |
| `pnpm.cmd typecheck` in `apps/web` | Exit 0 |
| `pnpm.cmd build` in `apps/web` | Exit 0; production static build succeeded, no deployment |
| Real FastAPI requests against existing DB | **16/16 HTTP 200**, all response hashes identical before/after merge |
| Default-public/production restrictions | **8/8 HTTP 403** |
| Original ML sealed/pilot/worksheet files | **24/24 unchanged** |
| `git diff --check` | Exit 0 |

Every skipped test:

1. `tests/api/test_postgres_portability.py::test_postgresql_migration_and_decimal_round_trip`:
   no `COMPASSIO_TEST_POSTGRES_URL` or local PostgreSQL tooling/server available. Table/dialect
   and search SQL compilation tests **ran**, but are not PostgreSQL execution verification.
2. `tests/test_local_ml_v2.py::test_issued_worksheets_ready_and_unfilled[v2build_a37deb181332]`:
   new combined build deliberately has no issued pilot worksheets. The original 300-item
   double-review pilot and 100-item audit remain unchanged in the ML worktree. No duplicate
   pilot, human identity, review or label was created to make the test pass.

All available real v1 source/research/model/final-ledger integrity tests, both real-data backend
ingestion suites, FTS checks and integrated v2 partition checks ran. Backend ingestion tests
use disposable SQLite databases; the application database was never ingested or migrated.
The existing backend registry was already marked ingested, so test ingestion's metadata
marker is a no-op; tracked/local source registration remains unchanged.

### Database, financial and API preservation

Database SHA-256 before and after integration and the full tests:
`d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385`.

Canonical hashes over sorted typed rows are unchanged:

- Financial observations: `1a9b58823f4d921f57c1aa3cd46653a2d02797951bb85a37315221f78eae606c`.
- Annotations: `fd7ad5debbe02d8bb713aed3e1c885a04f71b707dce81094e5aa3ea10c9d04eb`.

No pre-existing financial total changed. All 10 existing financial trend metrics were
requested, not just one sample; response hashes match the backend checkpoint exactly.
The 379 existing GCF projects remain enriched. The 14 API-only codes are not silently added.
Readiness grants, document rows, country aggregates and restricted historical rows retain
their separate tables/record levels and exclusion rules. Reconciliation checks remain zero.

The real-data probe makes FastAPI ASGI HTTP requests through `TestClient` against the real
read-only SQLite file; it does not mock responses or expose a public service. Search/detail,
linked documents, country aggregates, overview, GCF timeline and every financial metric were
exercised. FTS-on-real-data tests also matched ordinary literal search.

Pakistan GCF approval-year funding remains exactly as the backend checkpoint published it
(GCF's own country breakdown, USD; approvals, not disbursements or open opportunities):

| Year | Amount |
| --- | ---: |
| 2016 | 36,960,000 |
| 2018 | 49,000,000 |
| 2019 | 34,990,832 |
| 2022 | 10,000,000 |
| 2023 | 90,000,005 |
| 2024 | 83,276,281 |
| 2025 | 27,500,000 |

Local before/after evidence is in the ML worktree's
`artifacts/reports/task006_int_backend_{before,after}.json`, generated by its
`artifacts/reports/task006_int_backend_probe.py` read-only helper. The files hold exact API
responses and sorted-row hashes for comparison and stay out of Git.

### ML v1 preservation

All nine original sources and the canonical manifest remain unchanged. Frozen table
`71fc5a10285d25ed22d7e804f6cd5ec66783b6c6163168b5f8ab7cb46ae9d394` and membership
`aba478d973f50c7dfd98d8872ccd81fc541e6eded7698aaf7f1fc58adde4be2a` match their lock.
The final plan, three completed test-access ledgers/output hashes, trusted-release registry,
and release loader/artifact are intact. Artifact hash:
`53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656`;
content fingerprint `3023fe3d148b605c3ed9079c93f07296193fd2d8d5f77b8a82a163e58ccdc495`.
No consumed final test was recomputed. Release smoke tests predict on explicitly artificial
input only and are not new evaluations.

### ML v2 preservation and donor-audit integrity

`v2build_a37deb181332` was created from clean merge commit `cfd98bb...` (`dirty: false`).
Its seven dataset hashes (five development/linkage files, sealed candidates, restricted
reference) and pool-integrity counts match the ML checkpoint's `v2build_9911d9b6caca`
**exactly**. The new build ID records the integration path-guard code; it does not represent
a changed split or new observations. A clean-commit rebuild at `7034596...` matched exactly.

Pool integrity: **58,174 records**, **26,118 partition groups**, **26,433 project families**;
no cross-partition group/family spread. All **8,592** consumed v1 test records remain excluded.
GCF pages: 348 restricted records; backend GCF API never enters ML inputs. World Bank remains
external-evaluation-only, including the nine linked FCDO activities outside development.

The integrated donor audit reproduces the original ML record diagnostics and uncertainty
queue byte-for-byte. Its overall report differs only as expected for the newly pinned build
and source provenance. Integrated report SHA-256:
`f080fad45443d78d69c5fa5c37b4c6da314bb02c776ae17f036f32c1badaa401`.
Record diagnostics SHA-256:
`6807e0cc8bb8e543372cd4096d3d01e1d9d82806edd197539ff9065bceaa92da`.
Queue SHA-256: `1b93b56737e24fac768d9cbc5452654d9d2e39acd46c089741327aadfb564e35`.
Clean-code replay receipt:
`data/ml_v2/automated_quality/quality_7e70e77d22bba416/verification_7034596d46b78f5a08f86c1d0347fc6d4d12d499.json`.

Eligible donor examples remain **15,867** (5,021 positive / 10,846 negative; 4,436 non-energy
positive; 1,366 adaptation-only). FCDO remains **4,383** (796 positive / 3,587 negative);
EC remains **11,484**, separately recorded. Fifty-eight usable FCDO activities with
contradictory raw markers remain structurally excluded, without editing donor values.
Human labels and real AI assessments remain zero. Source-label diagnostics are not accuracy.

### Local resources, rights and readiness

No required SQLite/v1/source-retrieval artifact is missing locally. The combined checkout
owns its generated build/audit; its external raw inputs are an explicit **read-only dependency
on the existing ML worktree directory**, not silently assumed to have arrived through Git.
Original protected evaluation assets remain in that directory and were hash-verified unchanged.
The new build's absent worksheet is deliberate, as described in the skip list.

No filesystem ACL/permission was relaxed for protected artifacts. CLI path guards and SQLite
read-only connections constrain the operations; legacy v1 writer commands were not run.
Registries, source-specific rights, AI-provider/transfer permissions, attribution and release
restrictions remain distinct. No source is legally cleared, no actual AI provider is enabled,
and no public data-serving or redistribution permission follows from this merge.

**Ready to merge into main: YES for the tested SQLite/local-research scope**, after user
review; this task does not perform that merge. PostgreSQL execution remains unverified.
Independent human external evaluation, source/third-party rights review, weak transport/urban
coverage and donor/source-language shortcuts remain scientific/release limitations. They do
not imply the code integration failed, nor does successful integration resolve them.
No v2 classifier, prediction endpoint, public release, push or deployment is included.
