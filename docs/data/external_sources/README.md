# External sources for ML v2 (Task 006-ML)

| Document | Content |
| --- | --- |
| `configs/external_sources_v2.yaml` | Versioned registry: publisher, URL, access status, unit, IDs, dates, text fields, label category/authority, sectors, finance units, relationships, terms evidence, confirmed facts vs assumptions |
| `configs/label_mapping_v2.yaml` | Label categories A–E and compatibility flags |
| `acquisition_and_inspection_report.md` | What was retrieved, hashes, counts, coverage, overlaps (numbers from the build) |
| `rights_and_attribution_matrix.md` | Terms evidence, permitted uses, attribution, privacy notes |
| `../../research/model_v2/` | Labelling, split design, access policy, experiment design, evaluation proposal |

## Paths (read-only inputs vs writable outputs)

v1 tooling still uses `COMPASSIO_DATA_DIR` for one combined root. ML v2 tooling
(`compassio_ml.external.paths.V2Paths`) separates them:

| Variable | Meaning | Access |
| --- | --- | --- |
| `COMPASSIO_DATA_ROOT` | Original project's `data/` (raw, processed, manifests) | Read-only |
| `COMPASSIO_V1_PROJECT_ROOT` | Original project root (`models/`, `experiments/`); default = parent of `COMPASSIO_DATA_ROOT` | Read-only |
| `COMPASSIO_V2_OUTPUT_ROOT` | All v2 outputs; default `<worktree>/data/ml_v2` (git-ignored) | Writable |

Every write goes through `V2Paths.writable()`, which refuses paths outside the output root or
inside an input root; overlapping roots are refused at start-up.

## Commands

```
uv run compassio-v2 paths                 # resolved roots
uv run compassio-v2 verify-baseline       # read-only v1 integrity (manifest, frozen split, plan, release, consumed tests)
uv run compassio-v2 acquire <source_id>   # worldbank_projects | gcf_project_pages | iati_fcdo
uv run compassio-v2 verify-retrievals     # re-hash every retrieved file
uv run compassio-v2 build                 # parse, link, partition, reports (reproducibility-checked)
uv run compassio-v2 worksheets            # pilot sample + blind reviewer sheets
uv run compassio-v2 validate-reviews      # validate returned sheets, agreement statistics
```

## Retrieval provenance

`external_raw/<source_id>/<retrieval_id>/retrieval_manifest.json` records, per file: the
requested, fetched (HTTPS-upgraded) and final URLs, UTC retrieval time, HTTP status, content
type, byte count, SHA-256 and role (`data`, `index`, `terms`), plus failures, request
parameters, user agent and rate limit. Files are never overwritten; a new retrieval gets a new
directory. The fetcher is HTTPS-only, host-allowlisted per source, size-bounded, rate-limited
(≥1.5 s per host) and stops on non-200 responses, so blocked or credential-protected
endpoints are reported, not bypassed.

## Manual dependencies

- **OECD CRS**: download `CRS <year> data.zip` (or `CRS.parquet`) in a browser from the CRS
  dataflow's related files, record URL/date/terms, and place it under
  `data/ml_v2/manual_downloads/oecd_crs/`. A registration step and parser are a follow-up task.
- **IATI Datastore v3**: requires a subscription key from the IATI developer portal; supply it
  via an environment variable in a future task (never committed).
