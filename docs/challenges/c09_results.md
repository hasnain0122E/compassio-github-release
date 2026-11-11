# C09 measured results

Challenge benchmark evidence only; not independent external evaluation. Results below were
observed on the frozen 256-record assessment sample (98 donor-positive, 245 non-energy,
36 adaptation-only), after reserving 64 group/family/text-disjoint tuning records.
The final committed-run evidence is regenerated with the command in
[judge demo](c09_judge_demo.md); full metrics and receipts remain Git-ignored.
Both final runs used clean implementation commit `1a53cb63697efffce49cee6d7eb570938e0c1183`.
All nine deterministic JSON outputs matched byte-for-byte, including every queried candidate.
Safe full aggregates and output hashes are committed in
[c09_benchmark_aggregates.json](c09_benchmark_aggregates.json).

| Attack set | Pairs | Raw flips | Guarded flips | Raw P95 absolute shift | Guarded P95 |
|---|---:|---:|---:|---:|---:|
| Five fixed perturbations | 1,280 | 5 (0.390625%) | 2 (0.15625%) | 0.009420 | 0.004246 |
| Raw-selected search, same inputs | 512 | 8 (1.5625%) | 2 (0.390625%) | 0.016876 | 0.008627 |
| Fresh guard-targeted search | 512 | 6 (1.171875%) | 5 (0.9765625%) | 0.011073 | 0.009989 |

Fixed attacks changed 849/1,280 inputs; transferred searches changed 356/512; adaptive searches
changed 348/512. Zero-edit cases remain in denominators. Maximum verified edit share was 2.0%
of eligible original characters. Each search used 12 shared directional requests per record.
These are pair rates, not independent observations or population robustness estimates.
Across tuning and assessment, the raw and adaptive searches each issued 3,840 oracle requests.
The guard used 5,949 model evaluations for its search requests; including all diagnostics,
the baseline used 6,400 model evaluations and the guarded stage 13,644. Every discarded
candidate's seed, receipt, score and response is retained locally.

For fixed attacks, mean absolute shift fell from 0.001889 to 0.000579; the maximum fell from
0.031504 to 0.017114. Transferred-search mean fell from 0.004777 to 0.001239, with residual
maximum 0.073985. Adaptive guarded mean was 0.002267 and maximum 0.047043.

Fixed score inflation >=0.01 occurred in 20 raw versus 5 guarded pairs; reduction >=0.01 in
37 versus 13. Transferred search produced 38 versus 11 inflations and 35 versus 8 reductions.
Fresh guard-targeted attacks retained 10 inflations and 16 reductions >=0.01. Scores indicate
relevance to donor labels; these increases are not improvements in a numerical green rating.

Fixed attacks introduced one positive false negative with either pipeline. Transferred search
introduced three raw versus two guarded positive false negatives. Adaptive guarded attacks
introduced two. Non-energy new positive false negatives were respectively 0/0, 2/2 and 1/1
(raw/guarded). No new adaptation-only false negative occurred in this sample; this does not
establish robustness for adaptation generally. Pair-based baseline false negatives repeat
the same clean record for each attack; inspect unique counts in `metrics.json`.

All 256 clean assessment scores and predictions were exactly unchanged. One clean input was
flagged for review. The 64 tuning scores also stayed unchanged; one tuning input was flagged.
Guard review flags covered 33 fixed, 21 transferred-search and 25 adaptive pairs. The fixed
guarded residual flips were flagged, but one transferred residual flip and all five adaptive
residual flips were unflagged. Review flags are reported as burden, never successful prevention.

The guard does not repair duplicated-letter typos. Its conservative per-field confusable
limit can retain lookalikes in short fields; unsupported scripts/controls are retained for
review. A small raw-versus-normalized change does not reveal every near-threshold attack.
Actual failure texts, receipts and scores are in the local HTML, with failures shown first.

Final warmed measurement: raw mean 1.914 ms versus guarded 2.716 ms (192 calls each), a 1.419x
ratio. The repeat measured 2.752 ms versus 2.772 ms (1.007x), illustrating timing variability;
do not interpret either run as a stable throughput guarantee. Python traced peak incremental
allocations were 706,248 versus 712,392 bytes (+6,144), and +5,646 bytes in the repeat. Native
memory, RSS and model loading are excluded. Measurements are saved separately in each run's
`performance.json`. An explicitly artificial Decimal reporting control (100.00, 98.00, 102.00 USD) produced
identical scores, absolute shift zero. No actual numeric project-finance vulnerability is claimed.

V2 hash remained `65433605…858574`; v1 remained `53b226f6…d3656`; original SQLite remained
`d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385`.
Finance and tracked v1 evaluation ledgers were byte-unchanged. No sealed evaluation payloads,
model weights, labels or training artifacts were modified. Main and frozen tag still identify
`8c083509…`; C05 remains `7253c15…`. The concurrently developed frontend advanced from
`f6d32f3…` to `a832bd3…` during early investigation, before the experiment snapshot; C09 made
no writes in that worktree or branch. Before/after experiment snapshots track subsequent changes.
It subsequently advanced independently to `b03a3af…`; this reference stayed unchanged during
both final runs. External frontend observations are separate from deterministic score metrics.

Validation: final full Python suite **780 passed, 65 skipped** (204.01 seconds); skips cover absent
local-data fixtures and the unconfigured disposable PostgreSQL server. The final C09 tests
also passed independently: **54 passed**. Repository-wide Ruff lint, formatting (311 files)
and strict mypy (227 source files) passed. Frontend gates were outside this backend-only
change; no frontend files were edited or built.
The original registered source manifest validated all nine entries, and the v1 frozen
dataset/split integrity check passed without evaluating a consumed test partition.
