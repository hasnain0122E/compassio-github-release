# Task 006-ML completion report — data expansion and classifier v2 foundation

Branch `feature/ml-v2` (worktree `D:\AI LEARNING\compassio-ml-v2`), base commit `7f70654`.
Nothing pushed, nothing merged, **nothing committed** (changes are in the working tree for
review). **No model was trained or evaluated.**

## 1. Pre-flight findings and the path fix

| Check | Result |
| --- | --- |
| Data-root variable in `data/layout.py` | `COMPASSIO_DATA_DIR`, **not** `COMPASSIO_DATA_ROOT`; the variable you set had no effect on v1 code |
| Inherited `VIRTUAL_ENV` | Pointed at the original project's `.venv` (editable installs of the *original* source). A worktree `.venv` was created with `uv sync --locked` |
| Nine raw source files | All present under `$COMPASSIO_DATA_ROOT/raw` |
| Manifest hashes | `compassio-manifest validate --data-dir <original>/data`: **9 entries; hashes and sizes match**; original manifest == worktree manifest |
| Cleaned Parquet + frozen v1 split | `research_projects.parquet`, `research_split_membership_v1.parquet` in the original `data/processed` — hashes match the lock |
| Single root for read+write | Not safe: aliasing `COMPASSIO_DATA_ROOT` into `COMPASSIO_DATA_DIR` would let v1 writers (`compassio-research build`, `compassio-manifest write`) write into the original project |

**Fix (backward-compatible):** v1 code is unchanged. New `compassio_ml.external.paths.V2Paths`
reads `COMPASSIO_DATA_ROOT` (+ optional `COMPASSIO_V1_PROJECT_ROOT`) **read-only** and writes
only under `COMPASSIO_V2_OUTPUT_ROOT` (default `<worktree>/data/ml_v2`, git-ignored). Every
write passes `writable()`, which refuses paths outside the output root or inside an input
root; overlapping roots are refused at start-up (verified: pointing the output root into the
original `data/` exits with code 2).

`uv run compassio-v2 verify-baseline` (read-only), run before and after all work: **11/11 PASS**
— raw manifest, manifest copy, frozen split counts, final-evaluation plan
SHA-256 `c4760503…`, plan pins = lock, release artifact `53b226f6…`, release manifest =
committed copy, fingerprint `3023fe3d…` after trusted load, and all three consumed v1 test
access records `completed` with output hashes matching.

**Observed in the original checkout (not caused by this task):** during the session, 38 paths
in the main checkout changed (backend discovery/GCF-API/staging code, `data/raw_db/`,
`data/manifests/backend_source_registry.json`; timestamps 19:44–19:50 +05:00). This task's
commands only read from the original tree. `data/db/compassio_dev.sqlite` was not hashed at
session start, so its state cannot be independently attested here.

## 2. Files changed

New: `packages/compassio_ml/src/compassio_ml/external/` (`paths`, `fetch`, `registry`,
`records`, `worldbank`, `gcf`, `iati`, `v1_inputs`, `linkage`, `partition`, `labeling`,
`worksheets`, `dataset`, `reports`, `baseline`), `cli/v2_cli.py` (`compassio-v2`),
`configs/external_sources_v2.yaml`, `configs/label_mapping_v2.yaml`,
`docs/data/external_sources/` (4 docs), `docs/research/model_v2/` (8 docs),
`tests/ml/test_external_v2.py` (39 tests), `tests/test_local_ml_v2.py` (6 local-data tests).
Modified: `packages/compassio_ml/pyproject.toml` (entry point only; **no new dependency**),
`.gitignore` (`data/ml_v2/`), `CLAUDE.md`, `docs/phases/phase_plan.md`.

## 3. Commands run (real output)

| Command | Result |
| --- | --- |
| `uv run compassio-v2 acquire worldbank_projects` | 9 files, 0 failures (PK 640, BD 548, NP 281, LK 269, KE 370, MZ 261) |
| `uv run compassio-v2 acquire iati_fcdo` | 21 files, 0 failures (20 of 20 datasets) |
| `uv run compassio-v2 acquire gcf_project_pages` | 350 files, 31 failures (HTTP 404: FP303–FP328, SAP070–SAP074) |
| `uv run compassio-v2 verify-retrievals` | all 3 retrievals OK |
| `uv run compassio-v2 build` (×2) | `v2build_dd7b091eb19e`; second run: **byte-identical** |
| `uv run compassio-v2 worksheets` | 300-item pilot; 2 blind reviewer sheets; 100-item training-label audit sheet |
| `uv run compassio-v2 validate-reviews` | 0 completed files, 0 errors, 0 verified labels |
| `bash scripts/check.sh` | uv sync ✓, ruff ✓, ruff format ✓, mypy strict ✓ (147 files), pytest **435 passed, 31 skipped**, pnpm lint/typecheck/build ✓ |

The 31 skipped tests are v1 local-data tests that look for data inside the worktree; the
equivalent artifacts are verified through the input root by `verify-baseline`.

Data hashes: v1 table `71fc5a10…`, membership `aba478d9…`; retrieval manifests World Bank
`aa31868d…`, GCF `029edd2a…`, FCDO `f9507948…`; registry `490fc848…`; v2 code
`5779e7c5…`. The build manifest records git `7f70654` with `dirty: true` (uncommitted
code); the code hash pins the exact sources. **Re-run `compassio-v2 build` after committing**
before citing these counts elsewhere (it will reproduce the same build ID).

## 4. Results

Details and tables: `docs/data/external_sources/acquisition_and_inspection_report.md`.

- **Acquired:** 22,232 FCDO IATI activities; 2,369 World Bank projects; 348 GCF projects.
  Usable text: 21,155 / 1,743 / 348.
- **Labels:** 4,441 usable records carry donor-reported Rio markers (category B): 830
  positive (770 non-energy, 731 adaptation > 0, 297 adaptation-only), 3,611 explicit "not
  targeted". 18,805 usable records have no source label and are not treated as negative.
  GCF themes (348) and World Bank theme tags (82) are indicators, not labels.
  **Human-verified labels: 0.**
- **Pakistan:** FCDO 610, World Bank 640, GCF 11.
- **Overlap:** no link of any kind between AidData and external records; 2,360 suspected
  within-source pairs for review; all handled at partition-group level.
- **Pools:** training 17,060 FCDO (679 donor +) + 10,203 AidData IDs; validation 4,087 FCDO
  (151 donor +) + 2,160 AidData IDs; sealed external test 2,099 usable (World Bank 1,743, GCF
  348, FCDO 8); 8,592 AidData IDs training-only (consumed v1 tests).
- **Timing:** no acquired text has a verified authoring date; 27 World Bank + 13 FCDO
  records are verifiably pre-approval.

## 5. Assumptions

- Sector families come from DAC purpose codes (FCDO) and World Bank major-sector shares; GCF
  has no sector field and stays `unknown`.
- Training use of consumed v1 test records is allowed but flagged; it can be disabled per
  experiment.
- Suspected matches (cosine ≥ 0.85 or identical title in the same country) keep records in
  one partition but are not declared the same project.
- The pilot strata use source metadata only, with inclusion probabilities recorded.

## 6. Final status

VERIFIED NEW DATA — Yes, acquired and hash-verified: 22,232 FCDO activities, 2,369 World Bank
projects, 348 GCF projects (24,949 records, 372 MB). OECD CRS not acquired (Cloudflare 403);
IATI Datastore not used (key required); 31 newest GCF pages do not exist yet.

USABLE LABELS — 4,441 donor-reported (category B, FCDO only, unaudited) + the existing v1
researcher labels (A). 0 human-verified. GCF/World Bank indicators are not labels.

NON-ENERGY COVERAGE — Donor positives: 770 non-energy, 297 adaptation-only. Thin where v1
failed most: transport 13 and urban 10 donor positives (training + validation).

PROPOSAL-TIME EVIDENCE — Weak. 40 records verifiably pre-approval; 319 dated GCF funding
proposals exist but were not downloaded/extracted.

DUPLICATES AND LEAKAGE — Deterministic families + conservative partition groups; no
AidData–external overlap found; 2,360 suspected pairs pending human review; sealed pool never
in development files (tested).

HUMAN REVIEW STATUS — Not started. 300-item pilot × 2 reviewers + adjudication, and a
100-item training-label audit, are prepared, blind and empty.

LICENSING — All sources `not_reviewed`. FCDO: `uk-ogl` (registry). GCF: non-commercial
research only without consent. World Bank: general T&C API clause permits non-commercial use;
dataset licence unverified. Nothing redistributed.

TEST RESULTS — ruff ✓, format ✓, mypy strict ✓, pytest 435 passed / 31 skipped, web
lint/typecheck/build ✓, baseline 11/11, retrievals re-hashed OK, build reproduced
byte-identically.

REMAINING BLOCKERS —
1. Two independent human reviewers must complete `reviewer_A.csv` / `reviewer_B.csv`
   (300 items); a third person adjudicates.
2. One reviewer completes the 100-item FCDO training-label audit.
3. Review `suspected_matches_for_review.csv` (2,360 pairs).
4. Expand the external test to ~450–550 items after the pilot (sample-size policy).
5. Acquire more transport/urban/water positives: OECD CRS manual download (multi-donor
   markers) and/or an IATI Datastore key; extract dated GCF funding proposals (needs an
   approved PDF dependency).
6. Licence review for all three sources; decide whether Compassio use is commercial.
7. Commit, then re-run `compassio-v2 build` from the commit.

READY FOR V2 TRAINING? — **ADDITIONAL LABEL REVIEW REQUIRED.** Development experiments on
A + B labels are technically possible, but v2 cannot be evaluated (0 verified external
labels), and donor labels are unaudited. Additional acquisition is also required for
transport and urban positives before claims about those sectors.
