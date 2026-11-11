# Search performance (Task 006-DB)

## 1. Before: measured need

**Setup:** real database after the Task 006-DB ingestion (26,499 project rows, SQLite), the real
FastAPI app through TestClient, median of 7 warm calls per query.

**Query plan** for `q=solar`:

```
CO-ROUTINE (subquery-2)
SEARCH projects USING INDEX ix_projects_source_year (source_id=?)
SCAN (subquery-2)
USE TEMP B-TREE FOR ORDER BY
```

Every row's title and description was scanned with `LIKE '%…%'`. When a page came back empty,
the count fallback scanned again.

## 2. Change: SQLite FTS5 trigram pre-filter (migration `0003`)

| Component | Detail |
| --- | --- |
| Index | External-content virtual table `projects_fts(title, description)` with `tokenize='trigram'`: case-insensitive substring index, kept in sync by insert, update and delete triggers |
| Query | For `q` of **≥ 3 characters**: `projects.rowid IN (SELECT rowid FROM projects_fts WHERE projects_fts MATCH :phrase)` plus the **original literal `LIKE` condition**. The phrase is a bound parameter, quoted with internal `"` doubled. |
| Short queries | Under 3 characters, the plain scan is used unchanged |
| Semantics | **Unchanged.** The trigram index is only a candidate filter; the literal, escaped `LIKE` still decides every match. Trigram matching is case-insensitive and a superset of SQLite's ASCII-insensitive `LIKE`, so no match can be lost. |
| User input | No user-controlled SQL or FTS syntax: `"`, `OR`, `NEAR()`, `*`, `-` and `column:` are matched literally (tested) |
| Not changed | Filters, sorting, deterministic pagination and financial semantics |

**Equivalence check (real database):** 13 queries were compared, including `100%`, `done_ok`,
`Côte`, `PAK`, `B.21` and a no-match query. FTS + LIKE returned **identical ID sets** to LIKE
alone (0 mismatches). The FTS row count equals the projects row count (26,499).

## 3. After (same database, same method)

| Query | Before | After | Results |
| --- | ---: | ---: | ---: |
| `q=solar` | 432.2 ms | **25.8 ms** | 435 |
| `q=hydropower&country=PAK` | 59.6 ms | 26.5 ms | 26 |
| `q=climate resilience` | 466.8 ms | **29.1 ms** | 332 |
| `q=water supply&source=aiddata&year_from=2010&year_to=2020` | 275.6 ms | 29.1 ms | 213 |
| `q=flood&sort=-year&page=3` | 380.5 ms | 25.8 ms | 543 |
| `q=renewable energy&sector=ENERGY` | 70.3 ms | 24.8 ms | 42 |
| `q=zzzz_no_match` | 591.3 ms | **13.7 ms** | 0 |

**Live uvicorn on the real database** (127.0.0.1, warm):

| Request | Latency |
| --- | ---: |
| `q=solar` | 24 ms |
| `q=hydropower&country=PAK` | 19 ms |
| `q=climate resilience&source=gcf_readiness` | 25 ms |
| GCF detail | 30 ms |
| Documents | 12 ms |
| GCF timeline (PAK) | 20 ms |

**Other new routes:**

- `/analytics/data-quality`: about 3.5 s on a cold cache, then about 5 ms. It is cached until the
  next ingestion, using the same version-keyed cache as the overview.
- `/analytics/financing-completeness`: about 1.4 s cold, then about 29 ms.

**Elasticsearch and vector databases are not needed** at this scale.

## 4. PostgreSQL (not executed)

Migration `0003` creates the `pg_trgm` extension and GIN trigram indexes on `title` and
`description`. PostgreSQL's planner uses these for `ILIKE '%…%'`, which is the query the API
already issues on PostgreSQL. The FTS5 pre-filter is SQLite-only (verified by a compile-only
test). Performance on PostgreSQL is **unmeasured**; see `postgresql_verification.md`.

## 5. Maintenance note

FTS5 external content follows `projects.rowid`. If a future migration rebuilds the `projects`
table (SQLite batch mode), it must end with:

```sql
INSERT INTO projects_fts(projects_fts) VALUES('rebuild');
```
