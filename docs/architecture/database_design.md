# Database design (Task 006)

| Item | Value |
| --- | --- |
| Engine | **SQLAlchemy 2.1.8** (typed ORM) + **Alembic 1.20.1**; migration `0001` |
| Code | `compassio_api.db` |
| Local engine | **SQLite**, file `data/db/compassio_dev.sqlite` (git-ignored; 124.6 MB after full ingestion) |
| Production target | **PostgreSQL**. The schema, types and queries are written to be portable, but **PostgreSQL has not been run or tested**: no Docker or PostgreSQL install was available, and no driver is installed yet (see §6). |
| Configuration | `COMPASSIO_DATABASE_URL` (`core/config.py`); only `sqlite:///` and `postgresql` URLs are accepted |

## 1. Units of observation are never merged

A `projects` row is one record **as its source publishes it**. The `record_level` column says
which kind:

| Source (`source_id`) | `record_level` | Identity (`id` = `<source_id>:<source_project_id>`) |
| --- | --- | --- |
| `aiddata`, with research annotations from `research_paper` | `aiddata_record` | AidData Record ID, e.g. `aiddata:54013` |
| `gcf_projects` | `gcf_funded_project` | GCF reference code, e.g. `gcf_projects:FP085` |
| `climate_funds_update` | `cfu_project_row` | Sheet row (`projects-r79`). **CFU publishes no ID**, so this identity is valid only for the registered file's SHA-256. |
| `adb_pakistan` | `adb_financing_instrument` | IATI identifier, e.g. `adb_pakistan:XM-DAC-46004-38928-014-LN2198` |

**Within-source grouping** uses `group_key` and `group_meaning`, never merging:

- AidData Parent ID packages: `aiddata_parent:<id>`, "related, not the same";
- ADB project numbers: `adb_project:<nnnnn-nnn>`, the instruments of one ADB project.

**Cross-source identity** exists **only** as rows in `project_relationships`. Each row records
`method`, `evidence`, `status` (the overlap-audit vocabulary) and `human_reviewed` (false today).
There is no universal project ID.

## 2. Tables

| Table | Purpose | Key constraints |
| --- | --- | --- |
| `sources` | Registered source metadata copied from the committed manifest: publisher, version, file SHA-256, reference URL, **rights status and evidence**, observation type, audited count | PK `source_id`; SHA-256 length 64 |
| `import_runs` | One row per ingestion: input hashes, timestamps, status, inserted/updated/unchanged/rejected/removed | status ∈ running/completed/failed |
| `projects` | One source record (§1): title, description, recipient, region, `multi_country`, sector + vocabulary, `year` + `year_type`, date + precision + estimated flag, status, group, `source_reference`, source-specific `attributes` (JSON), `content_sha256` | **UNIQUE(source_id, source_project_id)**; title non-empty; year 1900–2100; date_precision ∈ {day, year} |
| `project_countries` | Countries as published (ordered), with ISO3 **only from a registered mapping** and the `mapping_method` | UNIQUE(project_id, position); ISO3 length 3 or NULL |
| `climate_annotations` | Classifications **published by a source**: research Rio markers, GCF theme, CFU theme | **CHECK is_model_prediction = false**; kind ∈ {research_annotation, source_classification}; UNIQUE(project_id, scheme) |
| `financial_observations` | One published amount with flow kind, level, financing type, `is_component`, `amount` (exact decimal), `raw_value`, `value_status`, unit, currency, `unit_status`, price basis, effective date and year, `date_meaning`, `multi_country`, `estimated`, `recommended_for_aggregates` | UNIQUE(source_id, observation_key). CHECKs: flow kind, level, unit and price-basis vocabularies; **amount IS NOT NULL ⇔ value_status = 'reported'**; ISO currency length; constant-2021 basis ⇒ USD |
| `project_relationships` | Explicit cross-source links | UNIQUE(from, to, type); no self-links; status vocabulary |
| `data_quality_warnings` | Per-record warnings (code, field, message) | UNIQUE(project_id, code) |

All child tables cascade on project deletion. SQLite enforces this through `PRAGMA
foreign_keys=ON` on every connection.

## 3. Money

`DecimalText` (`db/types.py`) stores money exactly:

| Database | Storage | Notes |
| --- | --- | --- |
| PostgreSQL | `NUMERIC(38,10)` | |
| SQLite | Canonical decimal **text** | SQLite's NUMERIC affinity would silently convert to binary floating point |

- **Binary floats are refused:** binding a `float` raises an error, which is tested.
- **Arithmetic** happens in Python `Decimal` through `compassio_ml.finance`.
- **Source floats:** the research table stores AidData's constant-USD values as float64, as the
  source workbook does. They are converted with Python's shortest round-trip `repr`, which
  reproduces the stored double's decimal text exactly.

## 4. Indexes (measured need, not speculation)

| Index | Serves |
| --- | --- |
| `ix_projects_source_year` (source_id, year), `ix_projects_year`, `ix_projects_sector_name`, `ix_projects_group_key` | List filters, group lookup |
| `ix_project_countries_iso3_project` (iso3, project_id) | Country filter as an `IN (subquery)` (covering) |
| `ix_climate_annotations_scheme_flag_project` (scheme, is_climate_related, project_id) | Climate filter (covering) |
| `ix_financial_observations_metric` (source_id, flow_kind, effective_year) | Trends |
| `ix_financial_observations_project`, `ix_project_countries_project`, `ix_climate_annotations_project`, `ix_data_quality_warnings_code` | Detail page, overview |

Measured gain on the real database: Pakistan + climate filter went from **8.7 s to 70 ms** after
replacing correlated `EXISTS` with `IN (subquery)` and these covering indexes.

## 5. Read-only API engine

The API opens SQLite with `mode=ro`:

- a request can never write;
- the API never creates an empty database file;
- a missing database returns `503 database_not_ready`.

Migrations and ingestion use a separate write engine (`compassio-db`).

## 6. Path to PostgreSQL (not yet executed)

1. Add a driver to the API package: `uv add --package compassio-api "psycopg[binary]"`. It is not
   installed now because it is unused and untested.
2. Provision a local PostgreSQL with a local-only password supplied by environment, never
   committed. Bind it to `127.0.0.1` and keep its volume outside the repository.
3. Set `COMPASSIO_DATABASE_URL=postgresql+psycopg://compassio@127.0.0.1:5432/compassio`, with
   the password from the environment or `.pgpass`.
4. Run `uv run compassio-db migrate`, then `uv run compassio-db ingest --source all`, then
   `uv run compassio-db verify`.
5. Run `uv run pytest` with a PostgreSQL URL fixture. **This must happen before PostgreSQL is
   claimed to work.**

**Portability notes:**

- Text search uses `ILIKE` on PostgreSQL and `LIKE` on SQLite (ASCII case-insensitive).
- `NULLS LAST` and `COUNT() OVER ()` are supported by both.
- JSON columns use the generic `JSON` type.
- Check constraints use only portable SQL.

## 7. Task 006-DB additions (migrations `0002`, `0003`)

| Change | Purpose |
| --- | --- |
| `sources.source_registry` (`canonical` / `backend_staging`), `sources.access_tier` (`standard` / `restricted_internal`) with CHECKs | Backend-registry sources sit beside canonical ones. Restricted sources (`gcf_historical`) are never served. |
| `financial_observations.country_iso3` | Set only for **source-published** per-country breakdown lines (GCF API) |
| `project_relationships.asserted_by_source_id`, `verification_state`, `last_verified_on` | Link provenance |
| `project_enrichments` | One row per (project, enrichment source): approval date and type, status and as-of, official URL, published values, conflicts. UNIQUE(project_id, source_id). |
| `documents`, `document_links` | Catalogue documents (never projects) and evidence-based links to projects |
| `record_groups` | Explicit parent groupings with method and verification (ADB project numbers, AidData parent packages) |
| `country_aggregates` | Source-published country figures. UNIQUE(source, iso3, measure). Amount iff reported. |
| `historical_staging` | Restricted staging for the unverified GCF historical archive |
| `0003` | SQLite FTS5 trigram index plus triggers; PostgreSQL `pg_trgm` GIN indexes (not executed) |

**SQLite migration fix:** batch migrations rebuild tables to change constraints. With
`PRAGMA foreign_keys=ON`, dropping a referenced table fails on a populated database, which was
found when rehearsing on a copy of the real database. `env.py` now turns foreign-key enforcement
off for the migration only, then requires `PRAGMA foreign_key_check` to be empty.

**Rehearsed upgrade:**

- the real database went `0001` → `0003` with 25,623 projects and 85,765 observations preserved;
- the foreign-key check came back empty;
- downgrade and upgrade cycles were tested on an empty database.

Raw-SQL objects (`projects_fts*`) are excluded from autogenerate by `migrate.include_object`.

