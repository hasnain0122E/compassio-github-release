# Task 006-ML review gate report — human-label preparation, rights isolation, clean checkpoint

Branch `feature/ml-v2`, worktree `D:\AI LEARNING\compassio-ml-v2`. Nothing merged, pushed or
deployed; no classifier trained; the sealed external test was not opened (no labels exist).

## 1. Checkpoint and reproducibility

| Step | Result |
| --- | --- |
| Review of Task 006-ML changes | 33 untracked + 4 modified files: source, configs, docs, tests only; no data, model, label or secret file; `data/ml_v2/`, `.venv/`, `data/raw/`, `models/`, `experiments/`, `artifacts/`, `.env` confirmed ignored (`git check-ignore`) |
| Gates before commit | `verify-baseline` intact; `scripts/check.sh` all passed (pytest 435 passed, 31 skipped) |
| Commit 1 | `61f180c` Task 006-ML |
| Line-ending finding | Python-edited files had CRLF in the working copy while the repo stores LF. The first build's registry hash (`490fc848…`) was taken over CRLF bytes, so a fresh clone could never reproduce that build ID. Working files restored to committed bytes; config hashes are now CRLF-normalised (`text_file_hash`) |
| Rebuild from clean commit `61f180c` | `v2build_a585f724a23a`, `dirty: false`, same code hash `5779e7c5…`. **All 5 dataset/sealed outputs and 5 of 6 reports byte-identical** to the pre-commit build; the coverage report differed only in pilot fields (pilot not yet sampled for the new build) |
| Commits 2–3 | `29485c7` review-gate code/config/docs; `e9562fb` EC legal-notice evidence |
| Build from clean commit `e9562fb` | **`v2build_274957046f51`**, `dirty: false`; second run: *Reproduced: byte-identical* |
| Source counts and hashes | All 5 retrievals re-hashed OK. World Bank 2,369, GCF 348, FCDO 22,232 records unchanged from Task 006-ML (same retrieval manifests `aa31868d…`, `029edd2a…`, `f9507948…`) |

Pool changes since Task 006-ML are intentional (§2–3): GCF moved to restricted; consumed v1
tests excluded; EC INTPA added. FCDO train/validation moved by 5 records (17,946/4,277 →
17,941/4,282) because new EC links merged some partition groups, which changes their hash
bucket.

## 2. Rights isolation

- **Evidence** (`data/ml_v2/rights_evidence/20261109T155841Z/`, `SHA256SUMS`):
  `www.greenclimate.fund/robots.txt` declares **`Content-Signal: ai-train=no, search=yes,
  ai-input=yes`**. The Task 006-ML note "robots.txt allows /" omitted this line — corrected in
  the registry and matrix. GCF Terms: non-commercial research use; no commercial derivatives
  without consent; no AI clause. No AI signals for World Bank, FCDO, IATI Registry or
  ec.europa.eu.
- **Decisions** (`configs/ml_rights_eligibility_v2.yaml`, operational, *not* legal clearance;
  `rights_status` stays `not_reviewed`): GCF pages restricted for training, automated
  evaluation and worksheets → 348 records in `restricted_reference/` only. The backend GCF API
  snapshot is never read: `V2Paths.readable` forbids `raw_db/` and `db/`, and a test asserts the
  ML code never references it. Unknown sources fail closed.
- The GCF ODL file still supplies the ISO2→ISO3 code lookup (codes only); disclosed in the
  matrix for the user to accept or replace.
- Evidence for every source and the not-acquired candidates:
  `docs/data/external_sources/rights_and_attribution_matrix.md`.

## 3. Evaluation independence

- All **8,592** AidData records in any consumed v1 test (primary, chronological, Pakistan
  holdout) are `excluded_consumed_v1_test`: no v2 training, validation, threshold or tuning use.
  v1 results and artifacts are unchanged (`verify-baseline` 11/11).
- External test = World Bank only (unseen publisher); 9 FCDO records joined it through a
  suspected link and are therefore unusable for development.
- `check_pool_integrity` (run at build, in tests and on load) enforces: one partition per
  project family and partition group (26,433 families, 26,118 groups, 58,174 records checked),
  no consumed record in use, no restricted record outside `restricted_reference_only`, no World
  Bank record in development pools.
- `compassio_ml.external.development` is the only development loader: it reads
  `datasets/<build>/` only, refuses sealed/restricted/consumed partitions and re-validates on
  load. External-test labels open only via `open_sealed_labels` with a frozen v2 plan (none
  exists).
- Tests: 28 new unit tests (`tests/ml/test_external_v2_review_gate.py`) and 10 local-data tests
  on the real build (`tests/test_local_ml_v2.py`).

## 4. Human-review preparation

`docs/research/model_v2/reviewer_workflow.md` covers opening/editing sheets (Excel/LibreOffice
UTF-8), Rio scoring, uncertain items, insufficient information, verbatim evidence quotes,
submission, validation, adjudication and freezing. Enforced in code (policy
`rio_label_policy_v2.1`): a reviewer registry of genuine people (`is_human`, role, attestation;
`example*` IDs refused); A, B and adjudicator must differ; issued text may not be edited;
`evidence_quote` must occur verbatim; insufficient-information rows must leave Rio values blank;
adjudication sheets are created only when A and B are complete and valid; freezing refuses
until every item is resolved; agreement is computed only from returned human sheets.

Issued for build `v2build_274957046f51` (`check-worksheets`: **ready, 0 errors**):

- `external_test_pilot_v1`: 300 World Bank items, one per partition group, seed 20261109 —
  priority non-energy untagged 130, control sectors 80, climate-theme tagged 50, energy 40;
  Pakistan 90 (30 %). `reviewer_A.csv`, `reviewer_B.csv`: unchanged since issue, reviewer
  columns empty.
- `training_label_audit_v1`: 100 donor-labelled training items (50 positive, non-energy first;
  50 negative), EC 71 / FCDO 29. Donor values hidden.
- `reviewers.yaml`: **not created** — only a placeholder template. `validate-reviews` reports
  "registry missing"; `adjudication-sheet` and `freeze-labels` refuse (exit 1).

The previous Task 006-ML pilot (build `v2build_dd7b091eb19e`, which included 80 GCF items) is
superseded; it was never reviewed.

## 5. Weak-sector expansion

New real source acquired within observed terms: **EC INTPA IATI** (12,240 activities, explicit
markers on all; registry `other-at`; Commission legal notice: EU content CC BY 4.0). Donor-labelled
usable records rose from 4,441 to **15,925**. Quantified requirements and the source shortlist:
`docs/research/model_v2/weak_sector_acquisition_plan.md`. Not acquired: BMZ (robots.txt disallows
`/pub/`; one probe file fetched before robots.txt was read, deleted unused), Australia
(robots disallows `/`), OECD CRS (Cloudflare 403), IATI Datastore (key). JICA reports no
markers.

## 6. Cross-branch integration risks

`main` has advanced to `bd2fe30` (Task 006-DB, 53 files). A read-only `git merge-tree` trial:

- **Conflict:** `docs/phases/phase_plan.md` (both add task rows) — manual resolution needed.
- Auto-merge: `.gitignore`, `CLAUDE.md` (both edited; review the combined text).
- No overlap with `packages/compassio_ml`, `uv.lock` or `configs/`; main adds backend code,
  `data/manifests/backend_source_registry.json` and `data/raw_db/` (the GCF API snapshot with
  `ai-train=no`).
- Risks after merge: backend and ML apply different GCF rules (backend displays GCF data; ML
  must not train on it) — keep `ml_rights_eligibility_v2.yaml` authoritative for ML; ML tests
  forbid reading `raw_db/`; run both suites after merging; the backend snapshot must never be
  added to `configs/external_sources_v2.yaml` without a rights decision.

## 7. Final status

COMMIT AND REPRODUCIBILITY — Commits `61f180c`, `29485c7`, `e9562fb` (+ this report's commit),
local only. Builds from clean commits reproduce byte-identically (`v2build_a585f724a23a`
matched the pre-commit outputs; `v2build_274957046f51` rebuilt identically). Config hashes are now
line-ending independent.

V1 INTEGRITY — `verify-baseline` 11/11 PASS before commit, after each build and at the end: raw
manifest (9 files), frozen split, evaluation plan `c4760503…`, release `53b226f6…` + fingerprint,
three consumed-test access records. No v1 asset modified.

RIGHTS RESTRICTIONS — GCF pages restricted (ai-train=no), kept for authorised reference only;
backend GCF API snapshot never read; unknown sources fail closed; FCDO (OGL), EC (CC BY 4.0
notice), World Bank (non-commercial API clause) permitted for internal research pending human
licence review. No legal clearance claimed.

V2 DATASET COUNTS — 37,189 external records (World Bank 2,369, GCF 348, FCDO 22,232, EC 12,240).
Development: training 26,861 usable external (FCDO 17,055, EC 9,806) + 10,203 AidData IDs;
validation 5,770 (FCDO 4,092, EC 1,678) + 2,160 AidData IDs. Donor-labelled: 13,369 training
(4,224 positive) and 2,556 validation (831 positive). Sealed external test: 1,751 usable
(World Bank 1,743, FCDO 8). Restricted: 348 GCF. Excluded consumed v1 tests: 8,592.

REVIEW WORKSHEETS — Issued, blind, empty, integrity-checked: 300-item external pilot (A and B
sheets) and 100-item donor-label audit. Reviewer registry template only.

HUMAN REVIEW STATUS — **0 items reviewed; 0 verified labels.** No reviewer has been registered.
Nothing was filled, inferred or marked verified by code.

WEAK-SECTOR DATA REQUIREMENTS — Per-sector targets 30 (minimum) / 70 (preferred) positives.
Validation short for transport (28) and urban (12). External test: 0 verified everywhere; the
World Bank pool has no candidates in the urban, flood/disaster and ecosystems sector families
(the taxonomy treats them as themes) → theme-based stratification or another evaluation
publisher is required; ~120 reviewed items per sector at an assumed 25 % prevalence.

TEST RESULTS — ruff ✓; ruff format ✓; mypy strict ✓ (151 files); pytest **457 passed, 31
skipped** (31 = v1 local-data tests that look for data inside the worktree; covered by
`verify-baseline`); local-data ML v2 tests 10/10; pnpm lint/typecheck/build ✓;
`check-worksheets` ready; retrievals re-hashed OK.

CROSS-BRANCH INTEGRATION RISKS — `main` is at `bd2fe30`; trial merge conflicts only in
`docs/phases/phase_plan.md`; `.gitignore` and `CLAUDE.md` auto-merge and need review; differing
GCF policies between backend display and ML training must stay explicit.

READY FOR HUMAN REVIEW? — **Yes**, once the team creates `reviewers.yaml` with genuine people
(reviewer A, reviewer B, an adjudicator, an auditor) and follows `reviewer_workflow.md`.

READY FOR V2 TRAINING? — **No: ADDITIONAL LABEL REVIEW REQUIRED.** Development pools are clean,
but the donor-label audit (0/100) and the external pilot (0/300 × 2) are not reviewed, and
transport/urban validation coverage and urban/disaster/ecosystem external-test coverage are
below the minimum.
