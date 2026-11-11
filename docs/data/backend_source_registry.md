# Backend source registry (Task 006-DB)

The backend has its **own staging registry** for files it downloads itself. It is independent of
the canonical nine-source manifest (`data/manifests/source_manifest.json`), which belongs to the
ML track and is **only read** by the backend. The staging registry is designed to be reconciled
with the canonical manifest later (§5).

## 1. Layout

| Path | Tracked? | Content |
| --- | --- | --- |
| `data/raw_db/<backend_source_id>/<UTC snapshot id>/<file>` | no (git-ignored) | Immutable payload exactly as downloaded |
| `data/raw_db/<…>/http_headers.json` | no | HTTP status + kept headers (provenance sidecar) |
| `data/raw_db/registry.json` | no | Operational registry |
| `data/manifests/backend_source_registry.json` | **yes** | Byte-identical copy of the registry: provenance metadata only, **no records** |

- **Hidden from ML tools:** `data/raw_db/` sits outside `data/raw/`, so `compassio-manifest
  validate`, `compassio-data inventory` and the audit never see these files. This was verified
  after the download: inventory still reports "9 files, 9 distinct by SHA-256" and the manifest
  validates.
- **Code:** `compassio_api.staging.registry` (model and validator) and
  `compassio_api.staging.fetch` (downloader).

## 2. Entry fields (`SnapshotEntry`, `extra="forbid"`)

| Field | Meaning |
| --- | --- |
| `backend_source_id`, `snapshot_id` | Stable source ID; UTC timestamp `YYYYMMDDThhmmssZ` |
| `publisher`, `description`, `unit_of_observation` | From the backend source definition |
| `landing_url`, `retrieval_url` | Official landing page; the exact URL fetched |
| `retrieved_at`, `http_status`, `http_metadata` | Retrieval time; status; kept headers (content-type, date, last-modified, etag, content-length, expires) |
| `original_filename`, `stored_relpath`, `sha256`, `size_bytes`, `file_format` | File identity |
| `source_update_date`, `source_update_date_note` | **Only** if the publisher states it (HTTP `Last-Modified`); otherwise NULL plus an explanation. Never inferred. |
| `rights_status` | `not_reviewed` or `under_review` only. **The model cannot express a clearance**: that needs the canonical review process. |
| `attribution_notes` | Terms and attribution as known (not a clearance) |
| `ingestion_status`, `ingested_at` | `registered`, `validated` or `ingested`. Per **snapshot**, not per database: it records the first successful ingestion anywhere (for the real snapshot, the rehearsal copy at 14:50 UTC). |

## 3. Commands

```powershell
uv run compassio-db fetch --source gcf_api_projects   # one HTTPS GET, new snapshot folder
uv run compassio-db registry                          # validate (exit 1 on any error)
```

**Fetcher behaviour:**

- One request with a generic client name, a 120 s timeout and a 60 MB cap.
- The payload must parse as JSON before it is registered.
- The snapshot folder is created with `exist_ok=False` and the file opened with exclusive create
  (`"xb"`). **An earlier snapshot can never be overwritten.** A second fetch makes a new snapshot.

**The validator rejects:**

- missing registered files;
- size or SHA-256 changes;
- **unregistered files** anywhere under `data/raw_db/` (except the registry, the README and the
  header sidecars);
- duplicate snapshots;
- unknown backend source IDs;
- **drift** between the local and tracked registry copies.

`compassio-db ingest --source gcf_api_projects` refuses to run if validation fails.

## 4. Registered snapshot (real)

| Field | Value |
| --- | --- |
| Source | `gcf_api_projects`, GCF Open Data Library API |
| Retrieval URL | `https://api.gcfund.org/v1/projects` (landing: `https://data.greenclimate.fund/`) |
| Snapshot | `20261109T144534Z`, HTTP 200, `application/json; charset=utf-8` |
| File | `gcf_api_projects/20261109T144534Z/projects.json`, 2,852,244 bytes |
| SHA-256 | `146242891bac37ce48ee263e1e3bcbb66d32e79d689d91f8cec37a7e9a69f3dc` |
| Publisher update date | **Not stated** (no `Last-Modified` header and no date field) |
| Rights | `not_reviewed`. GCF terms allow research and non-commercial use with attribution; commercial use or redistribution needs consent. robots.txt `Content-Signal: ai-train=no` means **do not use for model training (ML v2 note)**. |
| Access check | `robots.txt` on `www.greenclimate.fund` allows `/`; one request, no page crawling |

## 5. Reconciliation with the canonical manifest (proposal, not done)

The canonical manifest and its `SourceDefinition` registry live in `packages/compassio_ml`. They
are not modified while ML v2 runs. Proposed later steps:

1. Add a `SourceDefinition` for `gcf_api_projects` (JSON, unit "GCF funded project").
2. Either extend `SourceManifestEntry` with optional retrieval fields (retrieval URL, HTTP
   metadata, snapshot ID), or keep backend snapshots in this separate registry and reference them
   from the manifest.
3. Decide whether API snapshots move under `data/raw/` (making them visible to ML tools) or stay
   in `data/raw_db/`.
4. If ML v2 also downloads GCF data, keep both snapshots with their own hashes and reconcile by
   SHA-256. Never overwrite one with the other.
