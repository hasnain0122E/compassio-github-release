# Task 007 — final integration audit and promotion to `main`

**Date:** 2026-11-10. No push and no deployment were done. No model was retrained, no sealed evaluation was opened and no data was acquired.

## 1. Checkpoints

| Item | Hash |
| --- | --- |
| Previous `main` | `7e8422b30a53560c1cd56a7fdbf3569ddfff8ec2` |
| ML2 source (`feature/ml-v2-training`) | `34b2b1be2885fcdc05f4808acac42c7f56cc49a7` (commits `3bf81cd`, `7d99628`, `34b2b1b`) |
| ML2 integration merge | `70fc9d3` |
| Task 007 implementation | `55a9e0229af2900f050e2d32ecd40569d37dd29d` |
| Audit fixes (this review) | `0a85bc6` |

**Ancestry checked with `git merge-base --is-ancestor`:**
- `7e8422b` → `integration/task007-ml2`: yes;
- `34b2b1b`, `70fc9d3` and `55a9e02` are all included.

**Working tree:** clean (`git status --porcelain` printed 0 lines) before the audit.

## 2. Audit findings and fixes

| # | Finding | Severity | Action |
| --- | --- | --- | --- |
| 1 | The review-chain screening digest hashed only 9 of 16 screening fields. An edit of `saved_title`, `saved_description`, `source_id`, `is_climate_related`, `model_status`, `operational_mode` or `created_at` went undetected, contrary to the docstring. | Medium (integrity claim) | Fixed in `0a85bc6`: every stored field is hashed. New test `test_editing_a_saved_screening_field_breaks_the_chain`. |
| 2 | `add_review` read the chain head and inserted without serialisation. Sync FastAPI handlers run in a threadpool. Reproduced without the lock: 40 concurrent writes on 8 threads produced an invalid (forked) chain in **5 of 5** trials. | Medium (audit correctness) | Fixed in `0a85bc6`: a per-process write lock. New test `test_concurrent_reviews_keep_a_single_linear_chain` gives a valid 40-entry chain. A single API process is assumed (documented). |
| 3 | The Task 007 report said `verify-retrievals` gave "3 snapshots OK", while earlier reports said five. | Reporting error | The command prints **5** OK lines (section 5). The "3" came from piping its output through `tail -3`. This was **not a regression**. The Task 007 report now carries an erratum. |
| 4 | The hash chain's threat model was not stated. | Documentation | Section 6 below; the module docstring is updated. |

No other defects were found in the inspected implementation:
- `inference/engine.py`, `inference/store.py`, `inference/text.py`, `inference/explain.py`;
- `services/screening.py`, `api/v1/screening.py`, `schemas/screening.py`, `core/config.py`;
- `configs/inference_models.yaml`.

## 3. Model integrity

| Check | Result |
| --- | --- |
| v1 `models/compassio_ccrc_v1/model.joblib` (3,615,411 bytes, Git-ignored) | SHA-256 `53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656` (`compassio-hash`) |
| v1 fingerprint after trusted load | `3023fe3d148b605c3ed9079c93f07296193fd2d8d5f77b8a82a163e58ccdc495` (`verify-baseline`: PASS) |
| v2 `data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/model.joblib` (1,650,643 bytes, Git-ignored) | SHA-256 `654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574`; fingerprint `c76204127550fb29…` equals the manifest and the registry pin (`tests/test_local_screening.py`) |
| v2 status | `development_candidate`, not in `configs/trusted_model_releases.json` |
| Trusted registry, rights config, `data/manifests` vs previous `main` | `git diff --stat` is empty (unchanged) |

### Exact score equality (real artifacts, audit script)

The audit script ran five artificial inputs, including one non-English input, through `POST /api/v1/screening/text` in demo mode. It compared each result with `ExperimentalClassifier.load(...).predict`.

| API ML v2 score | Verified predictor score | `==` |
| ---: | ---: | --- |
| 0.7491876730138389 | 0.7491876730138389 | True |
| 0.11742078012000062 | 0.11742078012000062 | True |
| 0.5582058459137409 | 0.5582058459137409 | True |
| 0.5002724970101573 | 0.5002724970101573 | True |
| 0.8423350042445532 | 0.8423350042445532 | True |

- All flags also matched.
- The maximum explanation decomposition error was 1.1e-16.
- No ML modules (sklearn, joblib, pandas) were imported at start-up or after `create_app`; they are loaded only on the first screening request.

## 4. Inference API access matrix (real artifacts)

| Configuration | Mode | Default request | `model=ml_v2` |
| --- | --- | --- | --- |
| Defaults (no env) | `inference_disabled` | 403 `inference_not_authorized` | 403 |
| development + public | `inference_disabled` | 403 | 403 |
| development + local_development, demo off | `standard_local_research` | 200 **ml_v1** | 403 `ml_v2_demo_not_authorized` |
| test + local_development + demo flag | `standard_local_research` | 200 ml_v1 | 403 |
| **production** + local_development + demo flag | `inference_disabled` (production forces public) | 403 | 403 |
| development + local_development + demo flag | `authorized_local_demo` | 200 **ml_v2** | 200 ml_v2 |

**Settings defaults:**
- `environment=development`, `source_data_access=public`;
- `ml_v2_local_demo=False`, `review_api_token=None`.

The defaults are fail-closed. No `.env` file exists in the checkout.

## 5. Rights, sealed isolation and evaluation ledgers

**Database records as model input.** Only `aiddata` is mapped to a rights key (`automated_evaluation`: `permitted_pending_review`). Every other database source (GCF, CFU, ADB, CPE, readiness, historical) has no mapping and is refused with 403 `source_not_permitted_for_model_input` (tested).

**GCF in the rights config.** `gcf_project_pages` is `restricted` (`permitted=False`).

**Static scan of the inference code path:**
- It found no references to sealed pools, `raw_db`, `external_raw`, consumed tests, final evaluation, splits or `gcf_historical`. The only matches were the word "frozen" in type names.
- The only `compassio_ml` imports are the two guarded loaders and the rights reader.

**`uv run compassio-v2 verify-baseline`:** 11/11 PASS, "v1 baseline intact". The consumed tests (primary, chronological, pakistan_holdout) are verified by **hash only**: `status=completed` with their original `opened_at` times. No evaluation was re-run.

**`uv run compassio-v2 verify-retrievals`** (exit 0), five lines:

```
external_raw/gcf_project_pages/20261109T143506Z: OK
external_raw/iati_ec_intpa/20261109T161101Z: OK
external_raw/iati_ec_intpa/20261109T161933Z: OK
external_raw/iati_fcdo/20261109T143506Z: OK
external_raw/worldbank_projects/20261109T143438Z: OK
```

**`uv run compassio-ml verify-frozen`:** frozen inputs match the lock (primary test 3,142 / train 14,654 / validation 3,140).

## 6. Review workflow and threat model

**Persistence.** Free text is persisted only if `save=true` **and** a valid `X-Compassio-Review-Token` is sent (`hmac.compare_digest`):
- with no token configured: 403 `review_writes_disabled`;
- with a wrong or missing token: 401;
- with inference disabled, writes are also disabled.

Without saving, the response holds only `input_sha256`. The project database is opened read-only and is never written.

**Input limits:**
- title ≤ 1,000 characters; description ≤ 20,000; note ≤ 2,000; reviewer 1–100;
- `screening_id` is exactly 36 characters; `top_k` is 1–25;
- unknown fields are rejected, NUL is rejected, control characters are stripped.

**Review history.** Append-only rows. Each row's hash covers the previous hash, every stored field of its screening, the decision, the note, the reviewer and the timestamp. `GET /reviews/{id}` returns `chain_valid` and `chain_length`.

**Threat model.** The chain gives **tamper evidence**, not tamper protection.
- **Detected:** edits to any stored review or screening field, and deletion or reordering of a decision that has a successor.
- **Not detected:** an attacker who can write the SQLite file and recompute every hash can rewrite the whole history undetectably. Deleting the newest decisions (the tail) leaves a valid shorter chain.
- **Closing these gaps** would need an external anchor (for example a periodically exported or signed head hash). That is not implemented.

**Concurrency.** Writes are serialised per process. Running several API worker processes against one store is not supported.

**Authentication.** There is one shared local token, with no per-user identity. The `reviewer` field is self-declared.

**Request size.** There is no request-body size cap beyond the field limits; Pydantic parses the whole body before validating it. This is acceptable for a local-only service. A public service needs a server or proxy limit.

## 7. Database integrity

**`uv run compassio-db verify`:** exit 0; **27 `match: true`, 0 `match: false`**.

**`uv run compassio-db status`:**

| Table | Rows |
| --- | ---: |
| projects | 26,499 |
| financial_observations | 93,881 |
| climate_annotations | 26,020 |
| sources | 10 |

The last import run (#23, `gcf_api_projects`) started 2026-11-09T15:15:05, before Task 007. No ingestion took place during Task 007.

**Code diff versus previous `main`:** the finance, DB, ingest, `services/finance.py` and `services/projects.py` files have an empty diff.

**Database file:** `data/db/compassio_dev.sqlite` (Git-ignored) SHA-256 `d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385`.

## 8. Test and gate results (audited branch `0a85bc6`)

`bash scripts/check.sh` exited 0:

| Gate | Result |
| --- | --- |
| ruff check | All checks passed |
| ruff format | 264 files already formatted |
| mypy (strict) | Success: no issues found in 203 source files |
| pytest | **671 passed, 2 skipped** (380.55 s), including `test_screening.py` (21) and `test_local_screening.py` (3) |
| web | pnpm frozen install, eslint, typecheck (`next typegen && tsc --noEmit`) and `next build` all pass; the route `○ /screening` is built |

**The two skips** (expected, unrelated):
- `test_postgres_portability.py`: "PostgreSQL verification pending: set COMPASSIO_TEST_POSTGRES_URL";
- `test_local_ml_v2.py`: "no worksheets issued for this build".

## 9. Git-ignored local data still available

| Path | State |
| --- | --- |
| `models/compassio_ccrc_v1/model.joblib` | Ignored, present, hash verified |
| `data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/` | Ignored, present, hash verified |
| `data/db/compassio_dev.sqlite` | Ignored, present |
| `data/raw/` | Ignored; all 9 source directories present |
| External input root `D:/AI LEARNING/compassio-ml-v2/data/ml_v2/external_raw` | Read-only; the 4 source directories are present; all 5 retrievals re-hash OK |

A Git fast-forward does not touch ignored files.

## 10. Promotion

The audit passed, so the promotion went ahead:

1. **`main` had not advanced.** `git rev-parse main` returned `7e8422b30a53560c1cd56a7fdbf3569ddfff8ec2`.
2. **Safety branch.** `safety/task007-pre-promotion-main-7e8422b` was created at `7e8422b`.
3. **Fast-forward.** `git checkout main && git merge --ff-only integration/task007-ml2` reported "Updating 7e8422b..af2160b / Fast-forward", 55 files.
4. **Evidence commit.** This section was committed on the integration branch, and `main` was fast-forwarded to it the same way (section 11).

## 11. Promotion evidence

Essential checks on `main` at `af2160b`, after the fast-forward:

| Check | Result |
| --- | --- |
| `uv sync --locked` | OK (lockfile honoured) |
| `uv run compassio-ml verify-frozen` | Frozen inputs match lock |
| `uv run compassio-v2 verify-baseline` | 11 PASS, "v1 baseline intact" |
| `uv run compassio-v2 verify-retrievals` | 5 OK |
| `uv run compassio-db verify` | exit 0, 27 true / 0 false |
| `compassio-hash` v1 / v2 / DB | `53b226f6…3656` / `654336052b…8574` / `d2b39add…d385`, all unchanged |
| `pytest` on `test_local_screening`, `test_screening`, `test_runtime_boundary`, `test_api_types`, `test_system_endpoints`, `test_local_ml_v2_fast` | 37 passed |
| `git status --porcelain` | 0 lines (clean) |

The final `main` HEAD is the commit that adds this section. It was fast-forwarded from `af2160b`; its contents are documentation only.

## 12. Remaining limitations and blockers

- **ML v2 is a development candidate.** Its validation scores were used to select it, so they are optimistic. Independent evaluation needs the sealed or human-labelled external test, which has no labels yet.
- **Rights.** Every source is still `not_reviewed`; AidData's ML use is `permitted_pending_review`.
- **Public serving.** No public prediction service is approved, and screening is refused in production.
- **Review store.** It uses a shared token and has no anchoring against a full-database rewrite or tail truncation.
- **Request bodies** have no size cap.
- **PostgreSQL** verification is still pending.
