# V2 dataset eligibility, leakage control and group-aware split design

Design version **`v2_partition_design_v2`** (review gate; supersedes `_v1`), seed `20261109`.
Implemented in `compassio_ml.external.linkage`, `partition` and `rights`; executed by
`uv run compassio-v2 build`, which runs `check_pool_integrity` before writing anything. The
partition rules never read labels.

## 1. Records and identity

Every record keeps `source_id` + `source_record_id` (`candidate_id = source_id:record_id`),
the retrieval ID and the SHA-256 of the raw file it came from. AidData records enter linkage
by `record_id` only; their text stays in the frozen v1 table and is never copied into v2
outputs.

## 2. Relationships (deterministic)

| Level | Built from | Merges |
| --- | --- | --- |
| Project family `fam_*` (evidence-backed) | IATI `related-activity type=1` (parent ↔ child; siblings via the parent ID), explicit World Bank P-codes and GCF FP/SAP codes in text, identical normalized title+description hash, identical normalized description hash (≥100 chars), frozen v1 `leakage_group_id` | Yes |
| Partition group `pg_*` (conservative) | Families joined by **suspected** matches: TF-IDF (word 1–2-gram, English stop words) cosine ≥ 0.85 within the same country, or identical normalized title (≥15 chars) within the same country | Partition only |

Referenced IDs that are not in the data become virtual nodes, so two records citing the same
missing project still share a family. Suspected matches are written to
`suspected_matches_for_review.csv` for human review and are **not** declared the same project.
Within-AidData similarity is not recomputed (the frozen v1 groups apply).

## 3. Eligibility

A record is usable text when the title is present and the cleaned description has >= 100
characters. Non-usable records stay in the inventory and reports but not in pools.

| Partition | Labels it may carry | Who may use it |
| --- | --- | --- |
| `training_candidate` | A (v1 primary train, not consumed), B (FCDO, EC) | Fitting, training-only resampling |
| `validation_candidate` | A (v1 primary validation, not consumed), B | Model comparison, thresholds, calibration |
| `external_test_candidate` (sealed) | E only, after review | One-shot final evaluation; never development |
| `excluded_consumed_v1_test` | A | **Nobody** in v2 (no training, validation, thresholds or tuning) |
| `restricted_reference_only` | - | Separately authorised reference use only (GCF pages, `ai-train=no`) |
| `excluded_rights_training` | - | Nobody (source not permitted for training) |
| `excluded_linked_to_v1_data` | - | Nobody (external-test publisher linked to AidData) |
| `excluded_not_eligible` | - | Nobody (v1 quarantine kept) |

## 4. Partition rules (applied to whole partition groups, in order)

1. Group contains a source restricted for training **and** evaluation
   (`configs/ml_rights_eligibility_v2.yaml`) -> `restricted_reference_only`.
2. Group contains an AidData record from **any** v1 test partition (primary, chronological or
   Pakistan holdout) -> `excluded_consumed_v1_test`.
3. Group contains a World Bank record -> `external_test_candidate`; if it also contains an
   AidData record -> `excluded_linked_to_v1_data`.
4. Group contains a source not permitted for training -> `excluded_rights_training`.
5. AidData-only group -> v1 primary validation -> validation; v1 train -> training;
   not eligible -> excluded.
6. Other groups (IATI donors) -> SHA-256(`seed:group_id`) mod 100 < 20 -> validation, else
   training.

**Invariants (checked at build, in tests, and on load):** every project family and partition
group sits in exactly one partition; no consumed v1 test record is in a development or
external-test pool; no restricted-source record is outside `restricted_reference_only`; no
World Bank record is in a development pool. Development code loads data only through
`compassio_ml.external.development`, which refuses any other partition and re-checks these
invariants.

Consequences: World Bank is an unseen publisher for every v2 model; GCF text is in no pool;
related descriptions never cross partitions; consumed v1 test records cannot influence v2.

## 5. Shortcut-learning controls

- **Source identity:** training/validation contain AidData (A), FCDO and EC (B) text; each
  experiment must report per-source validation metrics and a source-identification probe
  (can a classifier predict the source from the text?).
- **Publication conventions:** GCF text is excluded altogether (rights); the parser still
  strips GCF meta widgets (theme, status, timeline), which literally contain the label.
- **Obvious climate words:** the v1 keyword baseline remains a required comparator, and the
  external test oversamples untagged non-energy sectors, where keywords are rare.
- **Length:** description-length quantiles by pool and label are reported; experiments must
  report performance by length band.

## 6. Proposal-time evaluation

Text timing is recorded per record (`text_timing`). Only World Bank `Pipeline` projects and
IATI status-1 activities are verifiably pre-approval at retrieval. Any proposal-time claim
must be restricted to those, or to dated GCF funding-proposal documents once extracted.
