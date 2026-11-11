# Task 005: Reproducibility and integrity record

## 1. Chain of custody (local commits, never pushed)

| Commit | Content |
| --- | --- |
| `17a2c71` | Task 004.5 checkpoint |
| `6bb4668` | Final-evaluation module (no test accessed) |
| `f14f397` | Fingerprint, release builder and loader, safeguard tests. **The plan's guarded source commit.** |
| `153dce8` | `configs/final_evaluation_v1.yaml` + `.sha256` + pre-test development report, **frozen before any test access** |
| (Task 005 final commit) | Docs, committed result copies and the trusted release registry. No guarded code changed before the three evaluations ran. |

## 2. Pre-test reproduction of the Task 004 primary model (clean tree `6bb4668`)

| Check | Result |
| --- | --- |
| Validation scores (3,140 records) vs Task 004 run | identical (maximum difference 0.0) |
| Predictions at 0.474 | identical |
| Train-OOF threshold | 0.4740212723792222, bit-identical |
| Artifact file SHA-256 | **differs** (`111a7341…` vs `20846c7e…`) |
| Content fingerprint (parameters, vocabulary, IDF, coefficients, intercept) | **identical** (`3023fe3d…`) |

**Mismatch investigated and explained.** scikit-learn's `TfidfVectorizer` stores
`_stop_words_id = id(self.stop_words)`, a per-process memory address, so the pickled bytes
differ between processes for identical models. Every learned attribute was compared and found
equal.

Consequences:

- A file SHA-256 verifies **integrity** of one artifact file. `model_fingerprint()` verifies
  **reproducibility**.
- Task 004's byte-identical reproducibility check passed only because both of its runs were in
  one process.

## 3. Plan and one-shot access

```
uv run compassio-ml final-dev --model-spec <spec.json> --out <report>   # thresholds, validation only
sha256sum configs/final_evaluation_v1.yaml   # c4760503f4b8798706e24cccfe7b87a4203751b8722d946984ebf76a47b8b3cb
uv run compassio-ml final-evaluate --protocol primary          --plan-sha256 c476…b3cb
uv run compassio-ml final-evaluate --protocol chronological    --plan-sha256 c476…b3cb
uv run compassio-ml final-evaluate --protocol pakistan_holdout --plan-sha256 c476…b3cb
uv run compassio-ml final-error-analysis --protocol <p>        # post-hoc only
uv run compassio-ml release --plan-sha256 c476…b3cb            # builds models/compassio_ccrc_v1
uv run compassio-ml release-predict --title "..." --description "..."
```

`final-evaluate` refuses when any of these hold:

- the plan hash differs;
- the frozen data or lock differs from the plan;
- guarded code or configs differ from commit `f14f397` (including uncommitted edits);
- `test_access.json` already exists for that protocol.

The access record is written with exclusive create **before** the test partition is loaded. It
is marked `completed` (or `failed`) with SHA-256s of every output, and all outputs are made
read-only. A second primary attempt was run deliberately and **refused**.

**Re-running the evaluation is impossible by design.** To re-evaluate, create
`final_evaluation_v2` with new, independent test data.

## 4. Release integrity

| Item | Value |
| --- | --- |
| Release artifact SHA-256 | `53b226f6…3656` (a copy of the read-only primary final-evaluation model) |
| Trusted registry | Committed in `configs/trusted_model_releases.json` |
| Fingerprint | `3023fe3d…` (equals the validated model) |
| Smoke test | `release-predict` on an example solar-PV description returned `is_climate_related: true`, label score 0.99999, with the limitation message. Blank input refused with exit 2. |

Tests:

- `tests/test_local_final_eval.py` (local data) verifies:
  - the plan hash;
  - per-protocol completed records, output checksums and read-only status;
  - Pakistan count consistency;
  - that the release is the evaluated model and reloads stably.
- Artificial-data tests (`tests/ml/test_final_eval.py`, `tests/ml/test_release.py`) cover:
  - the plan, data and code guards;
  - one-shot refusal, including after a failure;
  - expected-size checks;
  - Pakistan-leakage refusal;
  - metric consistency and fingerprint stability;
  - untrusted, tampered, unknown-version and unknown-schema releases;
  - blank input;
  - acceptance failing closed.

## 5. Environment

| Item | Value |
| --- | --- |
| OS | Windows 11 |
| Python | 3.12.15 |
| scikit-learn | 1.9.1 |
| numpy | 2.5.4 |
| scipy | 1.18.1 |
| pandas | 3.1.1 |
| joblib | 1.6.0 |
| Lockfile | `uv.lock` |

Latency figures are from this workstation and are indicative only.
