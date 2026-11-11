# Task 012 verification ledger

Verified implementation: `c5900acb860c91df4b0266cd3c1be3a79586c1f5`.
Final commits preserve the tested backend/frontend implementation and add the
final browser regression, correct probe pagination to `page_size=5`, and reports. Local Windows run on
2026-11-12, Python 3.12.15, locked uv environment, Node 24 and pnpm 11.21.0.

## Fresh results

| Check | Command / configuration | Actual result | Local evidence |
|---|---|---|---|
| Python install | `uv sync --locked --offline` | 56 locked packages installed | session output |
| Frontend install | `pnpm.cmd install --frozen-lockfile --offline --store-dir D:/.pnpm-store` | 379 packages, no downloads | session output |
| Repository Ruff | `.venv/Scripts/ruff check .` | All checks passed | `artifacts/task012/ruff.txt` |
| Formatting | `.venv/Scripts/ruff format --check .` | 365 files already formatted | `format.txt` |
| Strict mypy | `.venv/Scripts/mypy` | no issues, 246 source files | `mypy.txt` |
| Probe/C11 script mypy | `.venv/Scripts/mypy scripts/task012_probe.py scripts/c11_benchmark.py scripts/c11_report.py` | no issues, 3 files | `scripts-mypy.txt` |
| Full available pytest | `.venv/Scripts/python -m pytest -q -p no:cacheprovider --basetemp=artifacts/task012/release-final-tmp` | 862 passed, 49 skipped, 264.10 s | `pytest-release.txt` |
| Focused adapter, hardening, availability | `pytest -q -p no:cacheprovider tests/api/test_task012_integration.py tests/api/test_hardening.py tests/api/test_c11_availability.py` with isolated basetemp | 38 passed, 19.08 s | `integration-tests.txt` |
| Dedicated C05/C09/C11 | `pytest -q -p no:cacheprovider tests/ml/test_c05_quarantine.py tests/ml/test_c09.py tests/test_local_c05.py tests/api/test_c11_availability.py` | 113 passed, 8.91 s | `challenge-tests.txt` |
| Frontend lint | `pnpm.cmd lint` | exit 0 | `web-lint.txt` |
| Frontend typecheck | `pnpm.cmd typecheck` | generated route types; exit 0 | `web-types.txt` |
| Frontend units | `pnpm.cmd test` | 2 files, 16 tests passed | `web-unit.txt` |
| Production frontend build | `pnpm.cmd build` with API 8032 | compiled/prerendered successfully; exit 0 | `web-build.txt` |
| Generated API/TS | `.venv/Scripts/python scripts/generate_api_types.py --check` | up to date | `contracts.txt` |
| Product browser journeys | `pnpm.cmd test:e2e` with web 3032/API 8032, installed Chromium 1248 executable | 15 passed (54.0 s), including all original 11 and 4 new challenge journeys | `browser-final.txt` |
| Real API smoke, default defense modes | `scripts/smoke_api.py --base http://127.0.0.1:8033` | 27 requests, zero failed checks | `smoke.txt` |
| Runtime artifacts | `scripts/runtime_artifacts.py verify` | all 5 full frozen hashes verified | `runtime.txt` |
| Canonical database | `compassio-db verify` | all 27 audited comparisons match; integrity report ok | `db-verify.txt` |
| SQLite internal integrity | `PRAGMA integrity_check; PRAGMA foreign_key_check` via read-only URI | ok; no FK violations | `sqlite-integrity.txt` |
| C05 base/addendum | `python -m compassio_ml.challenges.c05.cli verify` | 12 + 6 files match their manifests | terminal output; dedicated local pytest checks also pass |
| C05 live A uniform / A targeted / B targeted | `cli live --sample 3000`, targeted option and hardened option | 42 / 18 / 48 caught of 150 respectively | `c05-live-A.txt`, `c05-live-targeted-A.txt`, `c05-live-B.txt` |
| C09 fresh full reproduction | `python -m compassio_ml.c09.demo --source-root <authorized-original-checkout> --output artifacts/c09/task012 --check-reproducible` | all 9 deterministic output files identical on repeat AND byte-identical to original C09 judge outputs | `c09-reproduction.txt`; `artifacts/c09/task012/reproducibility.json` |
| Real canonical TCP integration/load | `python scripts/task012_probe.py` | PASS: C09/C11 off/on; 413 declared/chunked; mixed reads; independent peer; production refusal | `probe.txt`, `canonical-probe.json` |
| Protected paths / landing | `git diff --exit-code` against frozen backend protected paths and approved frontend landing | exit 0, byte-identical | task transcript; path list below |

Except where given in full, evidence filenames above are under `artifacts/task012`.
The complete browser JSON report is `artifacts/frontend/browser-results.json`.
Screenshots include light layouts at 390/768/1440 and the challenge showcase in dark
mode at each size. Browser tests use real API responses and canonical artifacts;
the existing explicit network-error recovery test intentionally aborts a request.
The live challenge tests assert the exact v2 artifact hash. Load tests run in separate
processes; the small read budget is explicitly configured and does not imply default
capacity or 200-rps canonical performance.

## Exact boundaries checked

Normal model scores, explanations, hashes and threshold are equal with C09 off/on.
The separate adapter's raw/guarded scores match direct registered-predictor/guard
calls, and normalized explanations match the scored text. Its standard API result
is separate because the original sanitizer has different Unicode behavior.
Production/public source and inference checks fail closed; GCF project inference
remains denied; save requests require existing permissions. The legacy Task 009
limiter remains active when C11 is off; C11 replaces it when on. The full suite
covers bounded state, cleanup, spoofed forwarding headers, CORS, OPTIONS, typed
403/413/429, review tokens and fail-closed source access.

Unchanged protected paths: `packages/compassio_ml/src/compassio_ml/finance`,
`apps/api/src/compassio_api/services/finance.py`, `services/finance_rows.py`,
`db/models.py`, `configs/inference_models.yaml`, `configs/trusted_model_releases.json`,
`configs/ml_rights_eligibility_v2.yaml`, `data/manifests`. The landing page
`apps/web/src/app/page.tsx` is identical to frontend `e0c71af`.

Official smoke reproduces PAK ADB disbursements **21,549,925,012.94 USD**, equal to
the protected trend total; same-package/cross-source selections are flagged and
never totalled. A hypothetical budget of 1,000,000 conserves exactly as 333,333.34
+ 333,333.33 + 333,333.33 + 0.00 unallocated. These are financial evidence and
hypothetical allocation checks, not financial-return predictions.

## Provenance detail and failed attempts

Fresh C09 metrics SHA-256:
`53cfd6924ea3e51a2a60976624efb1ae03841fda927e55763846941aec0625c2`.
The fresh receipt pins implementation commit c5900ac and all C09 source hashes;
those hashes were independently recomputed and match. The command started on a
clean committed tree; its completed receipt records `dirty=true` because final
documentation and an additional browser test were edited during the long run.
No C09 source was changed during either run, both deterministic outputs agree,
and all nine agree with the original challenge run. The dirty flag is preserved,
not edited away. Machine-readable safe evidence is in `task012_evidence.json`.

Initial sandbox-denied temp/cache attempts are invalid, not regression passes.
The unrestricted isolated-temp/no-cache full rerun is the final result above.
The first default browser attempt lacked Chromium revision 1254; final runs use
the installed 1248 executable. The extra 429 browser test initially used a heading
locator for text rendered inside an alert; this test locator was corrected without
changing product behavior or weakening its status/header/recovery assertions.

## All 49 skipped cases

These remain skipped, not passed. Canonical runtime verification and real-model/DB
functional tests DO run; the absent inputs below concern rebuilding/auditing source
or training artifacts and unavailable PostgreSQL. Sealed final-test payloads were
not obtained or consumed to remove skips.

```text
SKIPPED [1] tests\api\test_postgres_portability.py:45: PostgreSQL verification pending: set COMPASSIO_TEST_POSTGRES_URL to a disposable DB
SKIPPED [1] tests\test_local_data.py:29: real source files not present in data/raw
SKIPPED [1] tests\test_local_data.py:36: real source files not present in data/raw
SKIPPED [1] tests\test_local_data.py:43: real source files not present in data/raw
SKIPPED [1] tests\test_local_db.py:57: local source data absent
SKIPPED [1] tests\test_local_db.py:71: local source data absent
SKIPPED [1] tests\test_local_db.py:82: local source data absent
SKIPPED [1] tests\test_local_db.py:98: local source data absent
SKIPPED [1] tests\test_local_db.py:113: local source data absent
SKIPPED [1] tests\test_local_db.py:127: local source data absent
SKIPPED [1] tests\test_local_db.py:142: local source data absent
SKIPPED [1] tests\test_local_db_extended.py:59: local data or snapshot absent
SKIPPED [1] tests\test_local_db_extended.py:65: local data or snapshot absent
SKIPPED [1] tests\test_local_db_extended.py:74: local data or snapshot absent
SKIPPED [1] tests\test_local_db_extended.py:87: local data or snapshot absent
SKIPPED [1] tests\test_local_db_extended.py:95: local data or snapshot absent
SKIPPED [1] tests\test_local_db_extended.py:120: local data or snapshot absent
SKIPPED [1] tests\test_local_db_extended.py:138: local data or snapshot absent
SKIPPED [1] tests\test_local_final_eval.py:33: final evaluation outputs not present
SKIPPED [3] tests\test_local_final_eval.py:41: final evaluation outputs not present
SKIPPED [1] tests\test_local_final_eval.py:57: final evaluation outputs not present
SKIPPED [1] tests\test_local_final_eval.py:66: final evaluation outputs not present
SKIPPED [1] tests\test_local_ml.py:34: research dataset not built
SKIPPED [3] tests\test_local_ml.py:40: research dataset not built
SKIPPED [1] tests\test_local_ml.py:54: research dataset not built
SKIPPED [1] tests\test_local_ml.py:62: no benchmark artifact present
SKIPPED [1] tests\test_local_ml_v2.py:56: COMPASSIO_DATA_ROOT or v2 retrievals not present
SKIPPED [1] tests\test_local_ml_v2.py:61: COMPASSIO_DATA_ROOT or v2 retrievals not present
SKIPPED [1] tests\test_local_ml_v2.py:68: no review-gate build present
SKIPPED [1] tests\test_local_ml_v2.py:79: no review-gate build present
SKIPPED [1] tests\test_local_ml_v2.py:94: no review-gate build present
SKIPPED [1] tests\test_local_ml_v2.py:109: no review-gate build present
SKIPPED [1] tests\test_local_ml_v2_fast.py:27: local ML2 run absent
SKIPPED [1] tests\test_local_ml_v2_fast.py:36: local ML2 run absent
SKIPPED [1] tests\test_local_ml_v2_fast.py:45: local ML2 run absent
SKIPPED [1] tests\test_local_ml_v2_fast.py:53: local ML2 run absent
SKIPPED [1] tests\test_local_research_dataset.py:45: research dataset not built
SKIPPED [1] tests\test_local_research_dataset.py:52: research dataset not built
SKIPPED [1] tests\test_local_research_dataset.py:60: research dataset not built
SKIPPED [1] tests\test_local_research_dataset.py:74: research dataset not built
SKIPPED [1] tests\test_local_research_dataset.py:87: research dataset not built
SKIPPED [1] tests\test_local_research_dataset.py:92: research dataset not built
SKIPPED [1] tests\test_local_research_dataset.py:98: research dataset not built
SKIPPED [1] tests\test_local_research_dataset.py:106: research dataset not built
SKIPPED [1] tests\test_local_research_dataset.py:113: research dataset not built
```

## Remaining unmeasured checks

Physically disconnected-laptop rehearsal, PostgreSQL execution, Linux/provider
runtime, distributed/multiple-worker operation, public-serving rights and canonical
200-rps capacity are not verified. None is represented as a local passing test.
