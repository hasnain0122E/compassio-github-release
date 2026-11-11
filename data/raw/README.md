# data/raw — immutable source files (not tracked by Git)

Place original downloaded files here **exactly as acquired** (no edits, no
re-saving from Excel, no renaming after hashing). Everything in this folder
except this README is ignored by Git.

Before any code uses a file:

1. Compute its hash: `uv run compassio-hash data/raw/<file>`
2. Register it in `data/manifests/` (format: `docs/data/data_contracts.md`).
3. Leave `rights_status` as `not_reviewed` until the licence has actually been reviewed.

Suggested layout: one sub-folder per `source_id` from
`docs/data/source_register.md`, e.g. `data/raw/gcf_funded_projects/`.

As of Task 001 this folder is empty: no source files have been copied into the repository.
