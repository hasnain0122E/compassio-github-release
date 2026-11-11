# Source-rights access policy (Task 006)

**All nine sources have `rights_status: not_reviewed`** (`data/manifests/source_manifest.json`).
Publicly downloadable is **not** the same as free to redistribute
(`docs/data/source_rights_matrix.md`). The API therefore serves source-derived records only
where it is safe to do so.

## 1. Modes

Implemented in `compassio_api.services.access` and `core/config.py`:

| `COMPASSIO_SOURCE_DATA_ACCESS` | Environment | Effective mode | Source-derived routes |
| --- | --- | --- | --- |
| *(unset)* = `public` | any | `public` | Only sources whose rights are `permitted` or `permitted_with_conditions`, **which the manifest accepts only with written `rights_evidence`**. Today none qualify, so **403 `source_rights_not_cleared`**. |
| `local_development` | development or test | `local_development` | All registered sources, with the header `X-Compassio-Data-Access: local_development` and `access.notice` "LOCAL DEVELOPMENT ONLY … do not expose or redistribute" |
| `local_development` | **production** | **`public`** (forced) | **Fails closed**: production can never run in local-inspection mode |
| `hackathon_event` + `COMPASSIO_EVENT_AUTHORIZATION` (Task 009) | development or test | `hackathon_event` | Only the sources listed in the named entry of `configs/event_data_authorizations.yaml` (never `restricted_internal`); **loopback clients only** (others: 403 `event_access_local_only`); no data outside a set date window; notice "EVENT DEMONSTRATION ONLY … not a licence clearance". See `docs/hackathon/data_permission_scope.md` |
| `hackathon_event` | **production** | **`public`** (forced) | Fails closed |

- **Default:** public exposure is **disabled by default**; local inspection must be switched on
  explicitly.
- **Where rights come from:** the `sources` table, copied from the committed manifest at
  ingestion. The API cannot modify it; the engine is read-only.

## 2. What is enforced per request

- **List and filters:** restricted to visible sources (`source_id IN visible`).
- **Detail:** a record from a non-visible source returns 404, indistinguishable from missing.
  Annotations, links and group members from non-visible sources are omitted. For example, an
  AidData record whose `research_paper` annotation source is not cleared is shown without the
  Rio marker.
- **Analytics:** metrics from non-visible sources return 403. Overview, filters and metrics list
  only visible sources. Cached entries are keyed by mode and visible sources.
- **Always available:** `/health`, `/api/v1/meta`, and `/api/v1/sources` (metadata and rights
  status, no records).

**Tests:**

- `tests/api/test_rights_access.py`: default mode, production override, 403 on all six data
  routes in both fail-closed configurations, partial clearance, hidden links and annotations;
- `tests/test_local_db.py`: production returns 403 on the real database;
- **live check:** `uvicorn` with `COMPASSIO_ENVIRONMENT=production` and
  `SOURCE_DATA_ACCESS=local_development` returned 403 on `/projects`, the detail route,
  `/analytics/overview` and `/analytics/trends`, and 200 on `/health` and `/sources`.

## 3. Local-development-only APIs

`/api/v1/projects`, `/api/v1/projects/{id}`, `/api/v1/filters`, `/api/v1/analytics/overview`,
`/api/v1/analytics/metrics` and `/api/v1/analytics/trends`.

**Operational guidance:**

- Run with `--host 127.0.0.1`; never bind `0.0.0.0` with local inspection enabled.
- Do not screenshot results for publication or share the database file (`data/db/`, git-ignored).

## 4. Before any public deployment

1. **Complete a human rights review per source**, then record in the manifest:
   - `rights_status`: `permitted` or `permitted_with_conditions`;
   - `rights_evidence`: licence URL, date, reviewer and conditions.

   Then re-run ingestion so `sources` picks the change up. Nothing in code may set a clearance.
2. **Implement the attribution each licence requires** in the UI:
   - AidData ODC-By notice and citation;
   - Qi et al. 2026 citation;
   - "First published by the Green Climate Fund" plus a link;
   - CFU and ADB as their terms require.

   Check whether GCF's terms permit the intended (possibly commercial) use.
3. **Decide whether CFU's row-position IDs are acceptable** for public URLs.
4. **Harden the deployment.** This task intentionally adds no identity platform:
   - authentication for any non-public route;
   - rate limiting;
   - TLS;
   - a production database with its own credentials from a secret store;
   - CORS limited to the production origin.
5. **Do not redistribute full records** (bulk export) without explicit redistribution permission
   for that source.
