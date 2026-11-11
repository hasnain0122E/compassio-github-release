# Data contracts

## 1. Data stages

| Stage | Location | Tracked in Git | Contract |
| --- | --- | --- | --- |
| Raw | `data/raw/<source_id>/` | No | Byte-identical to the downloaded file. Read-only. Hash recorded in a manifest. |
| Interim | `data/interim/` | No | Reproducible from raw + committed code. Never hand-edited. |
| Processed | `data/processed/` | No | Reproducible; records the `source_id` + `sha256` of every input. |
| Manifests | `data/manifests/` | **Yes** | Provenance records conforming to the schema below. |

The data root can be relocated with `COMPASSIO_DATA_DIR` (see `compassio_ml.data.DataLayout`).

## 2. Source manifest format (schema version 2)

Canonical definition: `compassio_ml.data.manifest.SourceManifest` (Pydantic, tested in
`tests/ml/test_manifest.py`). There is **one committed file**, `data/manifests/source_manifest.json`,
with one entry per raw file. Each registered source currently holds exactly one file, so
`source_id` is unique.

```json
{
  "schema_version": 2,
  "entries": [ { "...": "one SourceManifestEntry per raw file" } ]
}
```

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| `source_id` | string | yes | `lower_snake_case`; equals the `data/raw/` folder name; registered in `compassio_ml.data.sources` |
| `original_filename` | string | yes | Name exactly as on disk |
| `file_relpath` | string | yes | `raw/<source_id>/<original_filename>` (relative to the data root) |
| `file_size_bytes` | int ≥ 0 | yes | Measured |
| `file_format` | enum | yes | `zip`, `xlsx`, `xml`, `csv` (content-verified, not just the extension) |
| `publisher` | string | yes | Organization that published the file |
| `source_url` | URL \| null | no | Only if confirmed; never guessed from a filename |
| `sha256` | string | yes | 64 lowercase hex chars |
| `acquisition_date` | date \| null | no | Download date, only if recorded by the person who downloaded it |
| `inspected_at` | timezone-aware datetime | yes | When `compassio-manifest write` measured the file |
| `source_publication_date` | date \| null | no | Publisher's release/update date, only if stated |
| `rights_status` | enum | default `not_reviewed` | `not_reviewed`, `under_review`, `permitted`, `permitted_with_conditions`, `restricted` |
| `rights_evidence` | string \| null | **required** for `permitted*` / `restricted` | Licence URL/text and date reviewed |
| `unit_of_observation` | string | yes | What one record represents |
| `record_count_after_inspection` | int ≥ 0 \| null | no | Primary-unit count from the audit command |
| `related_sources` | list of `source_id` | no | Sources that may describe the same projects; not self |
| `known_duplicates_notes` | string \| null | no | |
| `confirmed_facts` | list of strings | no | Statements verified from the file bytes |
| `assumptions` | list of strings | no | Plausible but unverified statements; **disjoint from `confirmed_facts`** |
| `limitations` | list of strings | no | Coverage gaps, caveats |

Unknown fields are rejected. Version 1 manifests are rejected (none were ever written).

## 3. Registering a source (procedure)

1. Copy the original file into `data/raw/<source_id>/` without opening or re-saving it in another
   tool. For a new source, first add a `SourceDefinition` to `compassio_ml.data.sources`.
2. `uv run compassio-data inventory`: verifies the format, hashes the file and inspects archives
   safely. Files are refused with a reason if they are unsupported, corrupt, unsafe, misplaced or
   in an unregistered folder.
3. `uv run compassio-manifest write`: runs the audit for record counts and writes
   `data/manifests/source_manifest.json`. Rights are always written as `not_reviewed`.
4. `uv run compassio-manifest validate`: re-hashes every file and checks that every raw file is
   registered. Run this before any work that reads `data/raw`.
5. A rights decision is recorded **by a human** by editing the entry, with `rights_evidence`.

## 4. Record-level contract for processed tables

Implemented for the research table in Task 003: see `research_cleaning_spec.md` (columns,
transformations, eligibility) and `leakage_group_audit.md`. The general rules below still apply
to future processed tables.

Every processed project record must carry: `source_id`, the source-native record identifier,
the manifest `sha256` of its input file, and original-currency amount with currency code and
amount type (commitment/disbursement/approval) as stated by the source. Currency conversion,
deflation and cross-source linkage are separate, documented transformations. The concrete
schema is defined in Task 003, based on the Task 002 audit (`docs/data/`).
