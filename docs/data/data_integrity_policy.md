# Data integrity policy

Applies to all code, documentation, UI copy, tests and reports in this repository.

## 1. Real data only

- No synthetic, simulated, imputed or LLM-generated records may be presented as real project
  observations — anywhere.
- Test fixtures must be visibly artificial (`example_*`, `example.invalid`, all-zero hashes) and
  test logic only. They are never used to claim dataset coverage.
- Placeholders in the UI say "not yet available" rather than showing sample numbers.

## 2. Immutability and provenance

- Raw files are byte-identical to what was downloaded and are never modified. Hashing
  (`compassio-hash`) opens files read-only.
- Every derived dataset is reproducible from raw files + committed code and records its inputs' hashes.
- If a required file is missing, code raises `MissingSourceDataError`; it never falls back to other data.
- Replacement datasets are not downloaded and sources are not scraped without explicit approval.

## 3. Rights and redistribution

- Every source starts as `rights_status: not_reviewed`. A source is marked `permitted`,
  `permitted_with_conditions` or `restricted` only with written `rights_evidence`; the manifest
  model enforces this.
- Raw and processed datasets are never committed to Git or bundled into the web app.
  `.gitignore` blocks `data/raw/*`, `data/interim/*`, `data/processed/*` and common dataset formats.
- Any future public display of source-derived data must respect the reviewed licence terms and
  attribute the publisher.

## 4. No silent merging or double counting

- Records keep their `source_id` and source-native ID.
- Cross-source matches are stored as an explicit, reviewable linkage table with match method and
  confidence. Aggregates state which sources they include and how overlaps were handled.
- Project-level and country-aggregate amounts are never summed together.

## 5. Honest interpretation

- Climate-relevance classification describes text, not real-world environmental outcomes.
- Financing commitments are not profits or returns; approval does not mean a project is seeking funds.
- Rankings are prioritization aids under stated criteria, never "objectively best" claims.
- Compassio supports human decisions; it does not approve funding.

## 6. Reporting

Every reported count or metric states the command run, the input manifest hashes, and the date.
Exploratory results are labelled exploratory. Unreproduced numbers (e.g. the earlier 20,985-record
audit) are not quoted as results.
