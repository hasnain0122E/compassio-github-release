# Cross-source relationships (Task 006-DB)

Every link is an explicit row. **No link merges records or adds their amounts.**

| Rule | Detail |
| --- | --- |
| What a link records | Type, matching evidence, match method, asserting source ID, review status, verification state and last-verified date |
| Verification states | **Categories, never probabilities:** `deterministic_identifier_match`, `deterministic_identifier_structure`, `candidate_requires_review`, `human_verified` (not used yet; nothing has been human-reviewed) |
| Title similarity | **Never creates a link.** A title-similarity review queue was **not** built, so no automatic candidates come from names. |

## Relationship types (real counts, `uv run compassio-db report reconciliation`)

| Relationship | Table | Method / evidence | Verification | Count |
| --- | --- | --- | --- | ---: |
| CFU row → GCF project (CFU cites the code) | `project_relationships` (`cross_source_reference_code`, status `probable_match_reference_code`, asserted by `climate_funds_update`) | GCF code in the CFU project name | `deterministic_identifier_match` | **329** (6 cited codes have no export row) |
| Document → GCF project | `document_links` (`document_of_project`, asserted by `climate_project_explorer`) | GCF code in the GCF document's own metadata | 280 `deterministic_identifier_match` + 8 `candidate_requires_review` (multi-code documents) | **288** links, 121 projects |
| Financing instrument → ADB parent project | `record_groups` (`instrument_of_adb_project`) + `projects.group_key` | ADB project number embedded in the IATI identifier | `deterministic_identifier_structure` | **143** groups / 193 instruments |
| AidData record → parent package | `record_groups` (`member_of_aiddata_parent_package`) | AidData `Parent ID` field | `deterministic_identifier_match` | 2,299 parent IDs / 6,416 records (related, **not** the same record) |
| Project enriched from an official record (verified cross-source representation of the same GCF project) | `project_enrichments` (`enriched_from_official_record`, status `same_record_stable_id`) | API `ApprovedRef` == export `Ref #` | `deterministic_identifier_match` | **379** |

## Duplicate-observation prevention

- **Single row per enriched project:** enrichment uses a unique `(project_id, source_id)`.
- **Single row per amount:** each API amount is one `financial_observations` row under its own
  source (`gcf_api_projects`) with a unique key. Lines re-listed under another Board meeting
  are kept apart, and only internally consistent line sets enter totals.
- **Measured in the real database:**
  - duplicate observation keys: 0;
  - duplicate enrichments: 0;
  - re-ingestion changes nothing (7,240 API observations unchanged).
- **Separate sources:**
  - The export's `FA Financing` (currency not stated) and the API lines (currency stated) stay
    as **separate observations from separate sources**.
  - Every metric is single-source, so they are never added together.
  - CFU's GCF rows and the GCF export are linked, never summed.

## Candidates not linked (documented, not automated)

- **ADB ↔ GCF Pakistan** (FP085, FP215, FP283 list ADB as accredited entity): no shared
  identifier, so **no link** is created. They stay review candidates from the Task 002 audit.
- **The 14 API-only GCF codes:** they have no export row and are reported only.
