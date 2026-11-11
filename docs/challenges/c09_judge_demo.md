# Offline judge demonstration

Work only in `challenge/c09-adversarial-robustness`. Install the existing locked environment
once with `uv sync --locked`; subsequent commands use its Python directly and need no network.
The original root must already contain the registered model, development build and audit.
No download, training, backend database query or API server is involved.

From the C09 worktree in PowerShell, after committing safe C09 source and reports:

```powershell
.venv/Scripts/python -m compassio_ml.c09.demo --source-root 'D:/AI LEARNING/Compassio - Give Green Funding a Better Direction' --output artifacts/c09/judge --check-reproducible
```

Use a fresh output directory for a new run. Existing frozen memberships cannot be overwritten.
The command verifies pinned resources, creates the group-disjoint split, runs raw/fixed/search/
guarded/adaptive stages, validates receipts/idempotence, writes the scorecard, repeats all
stages and compares deterministic JSON hashes. Timing/memory are deliberately excluded from
the equality check. Expect partial protection and measured failures, not perfect consistency.

To inspect a completed run quickly, without repeating model calls:

```powershell
.venv/Scripts/python -m compassio_ml.c09.demo --source-root 'D:/AI LEARNING/Compassio - Give Green Funding a Better Direction' --output artifacts/c09/judge --existing
```

Read `artifacts/c09/judge/scorecard.html` in a browser. The CLI prints original and manipulated
text (Unicode escaped for terminal portability), verified edit share, scores and flip/review
status for measured examples. `metrics.json` has per-attack distributions and slices;
`baseline_queries.json` and `guarded_queries.json` distinguish oracle requests from actual
frozen-model evaluations, including diagnostic rescoring. `run_receipt.json` pins code,
commit, model, inputs and output hashes. `reproducibility.json` records exact repeat equality.
`baseline_trials.json` and `guarded_trials.json` retain every queried candidate, including
discarded candidates, with seed, complete edit receipt, oracle score and model response.

For stage-by-stage inspection, replace `demo` with `benchmark prepare`, `benchmark baseline`,
`benchmark guarded`, then `benchmark report` (as modules under `compassio_ml.c09`) using the
same `--source-root` and `--output`. This is also the implementation execution order.

Relevant Python gates:

```powershell
.venv/Scripts/ruff check .
.venv/Scripts/ruff format --check .
.venv/Scripts/python -m mypy
.venv/Scripts/python -m pytest -p no:cacheprovider
```

Local-data integration checks skip when their git-ignored inputs are absent in this worktree;
the C09 benchmark explicitly reads only the authorized original development artifacts. Do
not point the general test suite at the original database or sealed evaluation pools.
