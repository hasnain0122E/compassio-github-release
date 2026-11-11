# data/manifests — source provenance records (tracked in Git)

One JSON file per source: `<source_id>.json`, conforming to schema version 1 defined by
`compassio_ml.data.SourceManifest` and documented in `docs/data/data_contracts.md`.

Manifests are small, contain no dataset content, and **are** committed so that every
derived result can be traced to exact file hashes.

Rules:

- Write an entry only for a file that is physically present in `data/raw/`, using a hash from
  `uv run compassio-hash`.
- `record_count_after_inspection` comes only from an inspection command that was actually run.
- `rights_status` stays `not_reviewed` until a licence review with written evidence.

**As of Task 001 there are no manifest entries**, because no source files have been copied into
the repository yet. The expected sources are listed in `docs/data/source_register.md`.
