# Combined checkout: data paths and independent permissions

Run commands from the repository root. A Git merge transfers source and registered metadata;
it does **not** transfer ignored databases, raw data, model releases or evaluation artifacts.

| Resource | Selection | Integration write policy |
| --- | --- | --- |
| Nine original raw sources | `COMPASSIO_DATA_DIR` for legacy/backend tooling; `COMPASSIO_DATA_ROOT` for read-only ML v1 inputs; `data/raw/` | Immutable; no acquisition/ingestion command writes these originals |
| Canonical manifest | `data/manifests/source_manifest.json` under the selected data root | Frozen nine-source registration; backend snapshots are not inserted |
| Frozen v1 processed data | Read-only `COMPASSIO_DATA_ROOT/processed/` | No v1 builder, split writer or lock override runs during integration |
| Backend snapshots | `COMPASSIO_DATA_DIR/raw_db/` plus local `registry.json` and tracked `manifests/backend_source_registry.json` | Existing snapshot read/verified only; separate from canonical/ML source registries |
| Backend database | `COMPASSIO_DATABASE_URL`, default `sqlite:///data/db/compassio_dev.sqlite` | API and `status`, `verify`, `report` open SQLite read-only; ingestion/migration retain explicit write engines |
| ML v2 acquired sources | `COMPASSIO_V2_EXTERNAL_INPUT_ROOT` when set; otherwise `<v2-output>/external_raw/` | An override is a read-only input directory; acquisition refuses writes there |
| ML v2 datasets/reports/audits/assessments | `COMPASSIO_V2_OUTPUT_ROOT`, default `<checkout>/data/ml_v2/` | Owned output namespace, separate from the original ML worktree |
| Existing v1 model/experiment artifacts | `COMPASSIO_V1_PROJECT_ROOT/models/` and `experiments/` | Read-only; release fingerprint and consumed-test ledgers are checked, never re-evaluated |
| Protected evaluation data | Original ML worktree's `sealed_external_test/` and `labeling/`; new build's sealed candidate output is versioned separately | Original files unchanged; no sealed label access or new human-label claims |

`COMPASSIO_DATA_DIR` and `COMPASSIO_DATA_ROOT` are deliberately **not aliases**. The former is
the legacy read/write data root. The latter is an input root for new ML tooling. The database
URL is configured independently; changing a raw-data root never silently selects another DB.

`V2Paths` recognizes the same-checkout layout only when the configured v1 project is exactly
the current repository and the input data root is exactly its own `data/`. In that case all
ML outputs must remain under this checkout's `data/ml_v2/`. Raw/interim/processed/manifests,
backend staging/DB, models and experiments remain protected. Separate-worktree operation
keeps its original whole-input-root isolation. Every `writable()` call rechecks separation.
Resolved paths prevent traversal/symlink escapes. Backend `raw_db/` and `db/` are forbidden
ML read locations in both the current checkout and the configured v1 input root.

An existing external source directory can be reused without copying or mutating it:

```powershell
$compassioRoot = (Get-Location).Path
$env:COMPASSIO_DATA_ROOT = Join-Path $compassioRoot 'data'
$env:COMPASSIO_V1_PROJECT_ROOT = $compassioRoot
$env:COMPASSIO_V2_OUTPUT_ROOT = Join-Path $compassioRoot 'data/ml_v2'
$env:COMPASSIO_V2_EXTERNAL_INPUT_ROOT = 'D:/path/to/ml-worktree/data/ml_v2/external_raw'
uv run compassio-v2 paths
uv run compassio-v2 verify-baseline
uv run compassio-v2 verify-retrievals
uv run compassio-v2 build
```

These ML CLI variables are process environment variables, not automatically loaded from
the API's `.env`. `.env.example` documents both sets. When acquiring **new** snapshots, unset
the external input override and use the owned output root; never point it at backend staging.
This integration acquires no new sources and copies no datasets into Git.

## Independent permissions

There is no universal "source allowed" switch:

| Use | Authority / enforcement |
| --- | --- |
| Public display | Source-table rights and `AccessPolicy`; production forces public mode; uncleared sources denied; historical restricted tier never served |
| Internal research | Documented source terms and operational ML eligibility; still `not_reviewed`, internal scope only |
| ML training / automated evaluation / reviewer reference | Separate fields in `configs/ml_rights_eligibility_v2.yaml`; enforced in partitions, development loader, quality audit and worksheet tooling |
| Third-party AI processing | Separate provider/source permission records; default `configs/ai_assessment_permissions_v2.json` has no approved runs |
| External data transfer | Explicit transfer grant and retention/third-party-rights evidence; not inferred from training permission or API credentials |
| Attribution | Source-specific registry/licence evidence and quality-report/AI-permission attribution fields |
| Model/data redistribution | Existing source/release limitations remain; no v2 release, publication or redistribution is authorized by integration |

The backend GCF API and GCF pages are evaluated under **separate recorded entries**. Both
currently remain restricted for ML use, based on their recorded evidence. Backend local
display does not grant ML permission. The actual backend ID `gcf_api_projects` is also denied
by ML's unknown-source default; its explicit restricted alias is `gcf_api_snapshot_backend`.
The ML source parser registry contains neither backend snapshot ID. Unknown permissions fail
closed, and no source is marked legally cleared.

Development remains donor-origin research, with FCDO and EC kept distinct. All consumed v1
test IDs stay excluded, partition groups remain disjoint, AI proposals are unverified, and
the human external-evaluation pool remains reserved. No v2 classifier is trained here.
