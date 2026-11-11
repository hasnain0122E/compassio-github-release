# PostgreSQL verification: **PENDING** (not executed)

## 1. What was investigated (2026-11-09, this workstation)

| Option | Finding |
| --- | --- |
| Existing PostgreSQL | None: no `psql`, `pg_ctl` or `postgres` on PATH; no `C:\Program Files\PostgreSQL`; no `postgres*` Windows service |
| Docker or Podman | Not installed |
| WSL | `wsl.exe` exists, but WSL itself is **not installed** ("The Windows Subsystem for Linux is not installed") |
| Official installer | Would need a system-level install and administrator rights. **Not done** without your approval (task rule). |

**No system service, PATH change, firewall rule or administrator action was made.** No PostgreSQL
driver was added, because it could not be exercised.

## 2. What was verified without a server (labelled as such)

`tests/api/test_postgres_portability.py`, **compile-only**:

- **DDL:** every one of the 14 tables compiles for the PostgreSQL dialect, and the money columns
  render as `NUMERIC(38, 10)`.
- **Search SQL:** compiles to `ILIKE` and does **not** reference the SQLite-only `projects_fts`.

This proves the SQL is generated correctly. **It does not prove execution.**

Migrations branch by dialect:

- `0003` creates `pg_trgm` and GIN indexes on PostgreSQL;
- `0002` and `0001` use portable operations;
- the SQLite foreign-keys-off migration recipe in `env.py` applies to SQLite only.

## 3. Execution test, ready but skipped

`test_postgresql_migration_and_decimal_round_trip` runs only when `COMPASSIO_TEST_POSTGRES_URL` is
set. It is **reported as SKIPPED** ("PostgreSQL verification pending"), never as passed.

## 4. Steps once you approve an installation

```powershell
# A) Official installer (needs admin; EDB Windows installer), or B) Docker Desktop. Then:
uv add --package compassio-api "psycopg[binary]"          # updates uv.lock (document for merge)
# Create an isolated database and a role with a local-only password (not committed):
#   createdb -h 127.0.0.1 -U postgres compassio_dev
$env:COMPASSIO_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/compassio_dev"
$env:PGPASSWORD = "<local only>"
uv run compassio-db migrate                               # 0001..0003 (pg_trgm needs privilege)
uv run compassio-db ingest --source all
uv run compassio-db verify
$env:COMPASSIO_TEST_POSTGRES_URL = $env:COMPASSIO_DATABASE_URL
uv run pytest tests/api/test_postgres_portability.py -rs
```

## 5. Comparisons to run against SQLite

- `compassio-db verify`: all 27 audited comparisons, plus `report reconciliation`.
- Decimal round-trip of the largest AidData amounts (`NUMERIC(38,10)`). AidData constant-USD
  values have up to 9–10 decimal places in float `repr`; check for scale truncation.
- `/projects` search counts (`ILIKE` vs SQLite `LIKE`). **Expected difference:** `ILIKE` is
  Unicode case-insensitive, while SQLite `LIKE` is ASCII-only case-insensitive.
- Unique constraints and cascades, by re-running the ingestion idempotency checks.
- `NULLS LAST` ordering and `COUNT() OVER ()` pagination totals.

## 6. Task 009 attempt (2026-11-10)

- **Environment checked:** no `psql`, `pg_ctl` or `postgres` on PATH, no
  `C:\Program Files\PostgreSQL`, no PostgreSQL Windows service, no Docker and no WSL on the
  development machine. No disposable PostgreSQL server could be started without installing new
  system software, which Task 009 does not do (SQLite must stay the stable demo database).
- **Added compile-only coverage:** `tests/api/test_postgres_portability.py` now also compiles
  every Task 008 metric selection (`finance_rows.metric_statement`, 11 metrics, with country
  and year filters) and the prioritization candidate query for the PostgreSQL dialect. This
  proves SQL generation only.
- **Execution gate:** `test_postgresql_migration_and_decimal_round_trip` remains SKIPPED
  (`COMPASSIO_TEST_POSTGRES_URL` unset). No driver (`psycopg`) is installed.

**Status: PostgreSQL verification pending.** Do not describe the backend as PostgreSQL-verified.
