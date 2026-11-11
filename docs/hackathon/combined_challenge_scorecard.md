# Compassio Trust & Resilience — combined scorecard

All recorded figures below come from the original committed challenge evidence.
They are development challenge measurements, not independent scientific validation.
Live sample demonstrations have their own results and are not substituted into
the original benchmark. No registered model was retrained.

## C05 Data Integrity Shield

Real FCDO/EC development batch: 13,317 records; 666 inverted labels, final seed
20261112. Original A is the challenge default; B remains a hardened candidate.

| Attack / measure | A | B candidate |
|---|---:|---:|
| Uniform poison caught | 245/666 | 164/666 |
| Uniform precision / recall | 40.5% / 36.8% | 48.4% / 24.6% |
| Uniform false-quarantine rate | 2.85% | 1.38% |
| Uniform poisoned accepted | 421 | 502 |
| Targeted poison caught | 56/666 | 187/666 |
| Targeted precision / recall | 12.2% / 8.4% | 54.0% / 28.1% |
| Targeted false-quarantine rate | 3.18% | 1.26% |
| Targeted clean positives quarantined | 370 | 79 |
| Targeted poisoned accepted | 610 | 479 |

B reduces false quarantine and improves targeted detection but accepts 81 more
uniform poisoned labels and increases review workload. Targeted adaptation recall
after B is 0.6240, below naive poisoned training's 0.6473. This does not establish
protection against targeted poisoning. Review records remain in training under the
challenge's accept-and-review policy.

Fresh task demonstrations on 3,001 records, seed 7: A uniform catches 42/150
(28.00% recall, 35.90% precision); A targeted catches 18/150 (12.00%, 17.65%);
B targeted catches 48/150 (32.00%, 50.00%). These execute attack/detector/gate,
not registered-model training. Base and addendum manifest verification passes.

Evidence: [full C05 scorecard](../challenges/c05_scorecard.md),
[base summary](../challenges/c05_experiment_summary.json),
[addendum summary](../challenges/c05_addendum_summary.json).
Fresh logs: `artifacts/task012/c05-live-*.txt`. Dependencies and commands are in
the final judge runbook; the cached development batches stay ignored.

## C09 Input Protection

Development-record challenge assessment: 256 records, with a separate disjoint
64-record tuning sample. Model weights, artifact hashes and threshold are unchanged.

| Attack set | Raw flips | Guarded flips | Pairs |
|---|---:|---:|---:|
| Fixed | 5 | 2 | 1,280 |
| Transferred search | 8 | 2 | 512 |
| Adaptive search | 6 | 5 | 512 |
| Clean consistency | 256 unchanged | 256 unchanged | 256 |

Pair counts are not independent population observations. Five adaptive guarded
flips remain, all unflagged in the recorded assessment. The guard does not repair
all typos or all unsupported scripts. Review is a burden to report, not a prevented
flip. Normal API preprocessing is distinct from the raw predictor used in this
benchmark; the live adapter exposes both, with appropriate explanations.

Evidence: [C09 scorecard](../challenges/c09_scorecard.md),
[full committed aggregates](../challenges/c09_benchmark_aggregates.json).
Fresh task reproduction: `artifacts/c09/task012/`, including receipts, all queried
candidates and repeat-output hashes. Final reproduction status is recorded in
`task012_verification.md`.

## C11 Availability Shield

Original recorded test: fixture-backed local HTTP endpoints, real artificial-model
inference; about 200 abusive rps (199.79–200.77 across eight shield runs).

| Measure | Recorded result |
|---|---:|
| Abusive requests returned 429 | 5,953 / 6,400 |
| Independent legitimate requests succeeded | 96 / 96 |
| Shared-IP legitimate success | 50% |
| Maximum peer state | 1,024 keys |

Shared-IP users can collide with abusive traffic. One-worker in-process budgets
do not provide distributed botnet fairness. Original capacity results are not
evidence that the canonical backend sustains 200 rps.

Fresh canonical functional probe: 64/64 reads succeed with C11 off; enabled with
an explicitly reduced 1/s burst-four read budget gives 4 HTTP 200 and 60 HTTP 429.
An independent loopback peer succeeds in both modes. Concurrency is eight. Both
declared and chunked oversized bodies yield complete JSON 413. Canonical DB hash
is unchanged; production source/model/adapter requests fail closed. These results
establish local functional integration under controlled load, not capacity.

Evidence: [C11 scorecard](../challenges/c11_scorecard.md),
[original receipts](../challenges/c11_metrics.json),
`artifacts/task012/canonical-probe.json`. Fresh repository Ruff supersedes the
historical discrepancy in the challenge report generator.
