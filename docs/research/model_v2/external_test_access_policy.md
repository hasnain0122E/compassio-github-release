# Locked external-test access policy (v2)

## Scope

The v2 external test is built **only** from the `external_test_candidate` pool: World Bank
text, in partition groups with no link to v1 AidData records. GCF text was removed at the
review gate (`ai-train=no`; `rights_and_attribution_matrix.md`) and is not used for
automated evaluation unless a person records reviewed evidence that this is permitted. It is stored under
`$COMPASSIO_V2_OUTPUT_ROOT/sealed_external_test/<build_id>/` (git-ignored):

- `candidate_pool.parquet`: all sealed candidates;
- `pilot_v1.parquet`: the stratified pilot sample;
- later `external_test_labels.parquet` + `external_test_labels.lock.json`: adjudicated human
  labels only, written by `compassio-v2 freeze-labels` (`reviewer_workflow.md`).

## Rules

1. **No development access.** Training, model selection, threshold tuning, calibration and
   error analysis load data only through `compassio_ml.external.development`, which reads
   `datasets/<build>/candidates.parquet` and `partition_membership.parquet` only, refuses the
   sealed, restricted and consumed partitions, and re-checks that no World Bank, GCF or
   consumed v1 test record is present (unit and local-data tests enforce this).
2. **Labels open only with a frozen plan.** `compassio_ml.external.labeling.open_sealed_labels`
   refuses unless `configs/final_evaluation_v2.sha256` exists and the caller passes the same
   plan hash. That file does not exist yet, so access is impossible today.
3. **Freeze before access.** `final_evaluation_v2.yaml` must fix: the selected model, its
   threshold (from v2 validation), the metrics, slices, interval method and acceptance
   criteria. Its SHA-256 is committed before any sealed label is read.
4. **One access per protocol.** Evaluation writes an access record (as in v1). Re-evaluation
   after changes is a new plan version and is reported as such.
5. **V1 comparison:** the v1 release is scored on the same external test once, in the same
   run, as a fixed reference.
6. **Reviewer sheets** contain the sealed texts by necessity. Reviewers must not be model
   developers for that version, or, if the team is too small, the overlap must be disclosed.
7. **No copying from v1 tests.** Consumed v1 test records are in `excluded_consumed_v1_test`
   and can enter no v2 pool; AidData-linked World Bank groups are excluded.
