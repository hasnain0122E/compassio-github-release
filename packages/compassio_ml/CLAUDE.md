# ML package (packages/compassio_ml) — scoped instructions

Root rules in `/CLAUDE.md` apply — especially scientific integrity, provenance and evaluation.

- This package must not depend on FastAPI/Starlette or `compassio_api` (a test enforces this).
- Read source files only through `compassio_ml.safety` (ZIP: no extraction, traversal and bomb
  checks; XML: defusedxml with DTD/entities forbidden; XLSX: read-only, `keep_links=False`,
  macro workbooks refused) and `audit.loaders.SourceData`. Run `uv run compassio-manifest
  validate` first; it re-hashes every raw file against the committed manifest.
- New sources need a `SourceDefinition` in `data/sources.py` that keeps `confirmed_facts`
  separate from `assumptions`.
- Never write into `data/raw/`. Derived outputs go to `data/interim/` or `data/processed/`,
  must be reproducible from committed code, and must record the input manifest hashes.
- Keep source identity on every record (`source_id` + source-native ID). Cross-source linkage is a
  separate, explicit, reviewable table — never an implicit merge.
- Set and record random seeds; record library versions with any reported metric.
- Do not add heavy ML dependencies until the task that needs them; add with
  `uv add --package compassio-ml <pkg>`.
- Tests live in `/tests/ml/`. Fixtures are artificial and labelled as such.
