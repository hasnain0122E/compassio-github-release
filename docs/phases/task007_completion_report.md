# Task 006-ML2-INT + Task 007 — completion report

**Branch:** `integration/task007-ml2` (local only). **Base:** `main` at `7e8422b`.
**ML2 merge:** `70fc9d3` (`--no-ff` merge of `feature/ml-v2-training` at `34b2b1b`).
No merge into `main`, no push and no deployment were done.

## 1. Conclusion

| Question | Answer |
| --- | --- |
| Is ML v2 operational in the authorized local demo? | **Yes.** It is served by the real guarded loader with pinned hash, fingerprint and threshold (section 5 shows real HTTP responses). It is the default engine only when `COMPASSIO_ENVIRONMENT=development`, `COMPASSIO_SOURCE_DATA_ACCESS=local_development` and `COMPASSIO_ML_V2_LOCAL_DEMO=true`. Otherwise it returns `403 ml_v2_demo_not_authorized`. |
| ML v2 status | Still `development_candidate`. Nothing in the candidate manifest, trusted registry or evaluation ledgers changed. The API reports `independent_generalization_evidence: false` for it. |
| Is the v1 release intact? | **Yes.** <ul><li>`model.joblib` SHA-256 is `53b226f6…3656`.</li><li>`verify-frozen` passes.</li><li>`verify-baseline` reports "v1 baseline intact".</li><li>`configs/trusted_model_releases.json` and `compassio_ml.modeling` are unchanged versus `main`.</li><li>v1 remains the default outside the demo and is the fallback inside it.</li></ul> |
| What is still needed for a public production service | See section 8: rights review, independent evaluation of v2, authentication, hosting/security review, and separate explicit approval. |

## 2. Integration (Step 1)

- **Source branch.** `feature/ml-v2-training` HEAD was `34b2b1b` and its tree was clean. The ML2 reports are present.
- **Merge contents.** The merge changed 23 files. None are frozen-evaluation, research-split, `models/`, trusted-registry, `ml_rights*`, finance or DB files.
- **Ignored ML v2 artifact.** The merge does not carry it; it was verified separately on disk:
  - `data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/model.joblib` (1,650,643 bytes);
  - SHA-256 `654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574` (`uv run compassio-hash …`);
  - fingerprint `c76204127550fb29…` matches the candidate manifest and the registry pin (`tests/test_local_screening.py`).

## 3. What was built

| Area | Files |
| --- | --- |
| Model registry (pins, statuses, evaluation provenance, demo config, input-rights mapping) | `configs/inference_models.yaml`, `compassio_api/inference/registry.py` |
| Guarded, lazy model loading | `inference/engine.py`. The ML stack is imported on the first screening request only; `create_app()` still passes the runtime-boundary test. Loading checks SHA-256, fingerprint and threshold against the pins. The candidate loader refuses trusted-registry artifacts and non-candidate status. |
| Bounded input | `inference/text.py` (NFC, NUL rejected, control characters dropped, title ≤ 1,000, description ≤ 20,000, empty input rejected) and Pydantic `extra=forbid` |
| Faithful explanations | `inference/explain.py`: exact linear decomposition with character spans of the words in the original fields |
| Review audit store | `inference/store.py`: a separate SQLite store, append-only, SHA-256 hash chain over the decisions and every stored screening field. It is tamper **evidence**: it cannot stop an attacker who rewrites and rehashes the whole database, and it cannot detect deletion of the newest decisions without an external anchor (final integration report, section 6). |
| Service | `services/screening.py`: model choice, rights check, response building, comparison |
| Endpoints | `api/v1/screening.py`, `schemas/screening.py`, error handlers in `api/errors.py`; CORS now allows `POST` with explicit headers |
| Comparison aggregates | `compassio_ml/model_v2/aggregates.py`, `compassio-v2-train export-aggregates`, and `docs/research/model_v2/fast_benchmark_aggregates.json`, written from run `ml2fast_49317056_3bf81cd4_20261109T192725Z`. It contains no record IDs, and the source-file hashes are embedded. |
| Frontend | `apps/web/src/app/screening/` (model-details panel, form, result with word evidence, v1-vs-v2 table); `apps/web/src/lib/api-types.ts` is **generated** by `scripts/generate_api_types.py`, and its freshness is enforced by `tests/api/test_api_types.py` |

### Endpoints

| Method | Path | Access |
| --- | --- | --- |
| GET | `/api/v1/models` | Always available (metadata only; reports the operational mode) |
| GET | `/api/v1/models/comparison` | Always available (fixed committed aggregates; no data query) |
| POST | `/api/v1/screening/text` | `local_development` only. ML v2 needs the demo mode. `save=true` needs the review token. |
| POST | `/api/v1/screening/projects/{id}` | As above, plus the record's source must permit `automated_evaluation` (only `aiddata`). GCF and the other sources return 403. |
| POST | `/api/v1/reviews` | Review token required (`X-Compassio-Review-Token`); 404 if the screening is unknown |
| GET | `/api/v1/reviews/{screening_id}` | Review token required; returns the chain verification result |

### Operational statuses (Step 6)

| Kind | Value |
| --- | --- |
| Model status | `trusted_research_release` (v1) / `development_candidate` (v2) |
| Operational mode | `authorized_local_demo` / `standard_local_research` / `inference_disabled` |

The operational mode is configuration only and never changes a model's status.

**Production behaviour.** `COMPASSIO_ENVIRONMENT=production` always forces public access, so inference is disabled (`403 inference_not_authorized`). The demo flag is ignored outside `development`.

**Persistence.**
- Submitted text is never stored by default. The response contains only `input_sha256`.
- With `save=true` and a valid token, the screening (and, for free text, the title and description) is written to the review store, never to the read-only project database.

## 4. Comparison view (Step 5)

The figures are served from the committed aggregates JSON. The population is the same **2,550 FCDO + EC v2 development-validation records (827 positive)**. That set was used to select ML v2, so the scores are optimistic and are not independent generalisation. v1's AidData final-test metrics are shown only on v1's own model panel, never in this table.

| Measure | ML v1 | ML v2 |
| --- | --- | --- |
| Average precision | 0.681 | 0.839 |
| F1 | 0.441 | 0.738 |
| Non-energy recall | 0.259 | 0.766 |
| Adaptation-only recall | 0.209 | 0.733 |
| False positives | 31 | 294 |

**Trade-off:** 412 additional true positives for 263 additional false positives.

**Paired AP difference (v2 − v1):** +0.158 [0.120, 0.198] (2,000 resamples).

## 5. Real API examples (live uvicorn, authorized local demo)

**Server command:**

```
COMPASSIO_ENVIRONMENT=development COMPASSIO_SOURCE_DATA_ACCESS=local_development \
COMPASSIO_ML_V2_LOCAL_DEMO=true COMPASSIO_REVIEW_DATABASE_URL=sqlite:///<scratch>/demo_reviews.sqlite \
COMPASSIO_REVIEW_API_TOKEN=<local throwaway> uv run uvicorn compassio_api.main:app --host 127.0.0.1 --port 8017
```

The inputs below are artificial demo sentences, except the AidData record, which is a real registered database row. All scores are real model outputs; none are model evidence.

| Request | Status | Time | Result |
| --- | --- | --- | --- |
| `GET /api/v1/models` | 200 | 56 ms | Mode `authorized_local_demo`, default `ml_v2`, fallback `ml_v1` |
| `GET /api/v1/models/comparison` | 200 | 6 ms | Aggregates above |
| `POST /screening/text` (irrigation / drought early warning), first call | 200 | 3,931 ms | ML v2 lazy load; score **0.9166**, threshold 0.4447, `clearly_flagged` |
| Same request again | 200 | 10.5 ms | Identical score |
| Same text with `"model":"ml_v1"` | 200 | 2,226 ms (v1 load) | v1 score 0.7275, flagged, `trusted_research_release` |
| `POST /screening/text` "Construction of a secondary school and teacher training" | 200 | 8 ms | v2 score 0.1652, `not_flagged` |
| `POST /screening/projects/aiddata:35266` (Neelum-Jhelum hydropower, PAK) | 200 | 141 ms | v2 score 0.5945. Evidence: `source_reference` "AidData GCDF 3.0 AidData Record ID 35266; research workbook row 12390"; `model_input_permission` "aiddata: automated_evaluation permitted_pending_review" |
| `POST /screening/projects/gcf_projects:FP085` | **403** | 8 ms | `source_not_permitted_for_model_input` |
| `POST /screening/text` with an empty title and description | **422** | 4 ms | `empty_input` |
| `POST /screening/text` with `save:true` and no token | **401** | 4 ms | `invalid_review_token` |
| Same request with the token | 200 | 72 ms | `screening_id` `513de4fa-a399-4f29-bdf0-e34105d14cf1` |
| `POST /reviews` | 201 | 21 ms | `prev_hash` `000…0` (genesis), `row_hash` `7c7e84b1…7397` |
| `GET /reviews/{id}` | 200 | 9 ms | `chain_valid: true`, `chain_length: 1` |

**Explanation for the irrigation example (ML v2):**

- `intercept -0.81597 + feature_contribution_total 3.21335 = logit 2.39738`.
- σ(logit) equals the model's `predict_proba` within **2.2e-16**.
- `word_contribution_total` is 3.21335, equal to the feature total.
- 452 non-zero character n-grams.
- Top words, with their field and character span:

| Word | Field | Span | Contribution |
| --- | --- | --- | ---: |
| "Climate-resilient" | title | 0–17 | +1.953 |
| "farmers" | title | 71–78 | +0.256 |
| "systems" | description | 89–96 | +0.160 |
| "drought" | title | 33–40 | +0.153 |

**Review store after the demo:** 1 screening (title saved because the user chose `save`) and 1 review decision. The demo store and token lived only in the session scratchpad.

## 6. Proof that ML v2 inference is real

`tests/test_local_screening.py` (`local_data`) posts to the API and compares each score **exactly (`==`)** with the result of the independently loaded verified predictor:
- v2: `ExperimentalClassifier.load(...).predict`;
- v1: `ReleasedClassifier.load(...).predict`.

It also checks the registry pins against the real files and that the v2 artifact is not in the trusted registry. Result: 3 passed.

During development this test caught a 1-ULP difference between the recomposed sigmoid and `predict_proba`. The API now reports the model's own `predict_proba`, and the decomposition is only checked against it.

## 7. Verification commands and results

| Command | Result |
| --- | --- |
| `uv run ruff check .` / `uv run ruff format --check .` | All checks passed / 262 files formatted |
| `uv run mypy` | Success: no issues found in 203 source files |
| `uv run pytest tests/api/test_screening.py tests/api/test_api_types.py` | 20 passed |
| `uv run pytest tests/test_local_screening.py` | 3 passed |
| `uv run compassio-ml verify-frozen` | Frozen inputs match lock (primary test 3,142 / train 14,654 / validation 3,140) |
| `uv run compassio-v2 verify-baseline` | PASS for the consumed tests; "v1 baseline intact" |
| `uv run compassio-v2 verify-retrievals` | 5 retrievals OK (*erratum:* an earlier draft said "3 snapshots" because the output was piped through `tail -3`; there was no regression, see the final integration report) |
| `uv run compassio-db verify` | 27 `match: true`, 0 `match: false` (finance aggregation unchanged) |
| `bash scripts/check.sh` (all Python and web gates) | See section 7a |

**What the artificial API tests in `tests/api/test_screening.py` cover:**
- default v1, and the 403 for v2 without the demo;
- v2 as the demo default with its status unchanged;
- production/public modes return 403; the test environment ignores the demo flag;
- scores equal the guarded predictor; exact decomposition; spans index the original fields;
- versioned metadata; empty, NUL, too-long and unknown-field inputs;
- control-character removal;
- tampered artifacts return 503, with v1 fallback for the default choice; pin mismatches are refused;
- no persistence without save plus token; 401/403 token checks;
- hash-chain provenance and tamper detection;
- project rights (aiddata OK; GCF 403; unknown 404; public 403);
- the comparison equals the committed aggregates.

**Sealed and restricted data.** No code path reads the sealed v2 pool, the consumed test sets, `data/raw_db/` or GCF training-restricted records. Project screening refuses every source without `automated_evaluation` permission.

### 7a. Full gate run

`bash scripts/check.sh` (final run, after all edits) exited 0:

- ruff check: All checks passed. ruff format: clean.
- mypy: Success, no issues found in 203 source files.
- pytest: **669 passed, 2 skipped** (399.97 s), including `tests/api/test_screening.py` (19) and the `local_data` real-artifact tests.
- Web: `pnpm install --frozen-lockfile`, lint, typecheck and `next build` all pass. The build output includes the static route `○ /screening`.

## 8. What public production would require (not done; separate approval needed)

1. **Source-rights review.** Every source is still `not_reviewed`, and AidData's ML use is `permitted_pending_review`. Serving model outputs publicly needs a written licence review.
2. **Independent evaluation of ML v2.** It needs a one-shot sealed or human-labelled external test (still sealed and unlabelled) before any claim beyond "development candidate". Until then, production should serve v1 or nothing.
3. **Approval.** An explicit decision to expose a prediction endpoint publicly. The current code refuses inference whenever `environment=production`.
4. **Real authentication and authorisation** in place of the single shared review token, plus rate limiting and abuse controls for the POST endpoints.
5. **PostgreSQL verification** (still pending) and a production review store with backups.
6. **Security review** of the deployment: TLS, CORS origins, secrets management.

## 9. Assumptions and blockers

- **Mode separation.** "Authorized local demo" is implemented as an explicit opt-in configuration flag on a development machine. It is not a deployment.
- **Display.** The engine label "Compassio Climate Intelligence — ML v2" is shown together with the `development_candidate` status in every response and in the UI.
- **Blockers.** None for the local scope. PostgreSQL verification is still pending (no server available).
