# Leakage group audit (research dataset v1)

Implementation: `compassio_ml.research.grouping`. Reports:
`artifacts/research_v1/leakage_largest_groups.csv`, `leakage_group_size_distribution.csv` and
`build_summary.json` → `leakage`. Every number below was computed on the 20,985 real records.

## 1. Relations and rule selection

Records are linked by four explicit relations. `leakage_group_id` is the **transitive connected
component** (union-find): if A–B share a parent ID and B–C share a description, then A, B and C
form one group.

| Relation | Rule | Edge groups | Records touched |
| --- | --- | ---: | ---: |
| `parent_id` | Identical AidData `Parent ID` (a linked package, verified by AidData) | 1,949 | 6,066 |
| `description` | Identical description after `normalize_text` (case-, accent-, punctuation- and whitespace-insensitive) | 514 | 1,351 |
| `title` | Identical title after `normalize_text` | 98 | 248 |
| `title_series` | **Restricted:** the title has explicit tranche/phase/stage/subprogram/part numbering, **and** the series key (numbering removed) is the same, **and** the recipient is the same | 84 | 189 |

**Why exact-title grouping was kept:**

- The largest exact-title group has **15 records**: the same oil-company newspaper-subscription
  donation, repeated.
- Generic titles do recur: 58 of 96 case-insensitive title groups span several recipients, e.g.
  identical "donates batch of anti-malarial drugs" records.
- Grouping them is the conservative choice, because they are templated text a model would
  memorise. Adding title edges leaves the largest component at 82 records. It creates one
  additional 80-record component, which links two COVID-19 vaccine Parent-ID packages.

**Why the broad title-series rule was rejected:**

- Stripping all digits and series words from titles merges **unrelated** records. Examples:
  "Chinese government provides RMB *X* million grant via ETCA for unspecified purposes" across
  10 recipients (25 records), and COVID-19 vaccine donations across 15 recipients.
- That rule touches 1,883 records in 623 groups. The restricted rule above keeps only explicit,
  same-recipient project series: 84 groups, at most 5 records each.

**Ambiguous relations not used,** and why:

- **Fuzzy or near-duplicate text similarity:** risks merging unrelated projects. It is
  preserved as a candidate for review in Task 004 error analysis.
- **Funding agency, year or amount alone:** these are not identity evidence.

**Group IDs:** `g_` + the first 16 hex characters of SHA-256 over the sorted member record IDs.
They are deterministic, independent of row order (tested) and never use Python's `hash()`.

## 2. Group statistics

| Statistic | Value |
| --- | ---: |
| Records | 20,985 |
| Leakage groups | 16,358 |
| Singleton groups | 14,194 |
| Multi-record groups | 2,164 |
| Records in multi-record groups | **6,791 (32.4%)** |
| Largest group | 82 |
| Records without a Parent ID | 14,569 |
| …of which are also singletons after all relations | 13,847 |
| Multi-record groups spanning more than one recipient | 80 |
| Multi-record groups spanning more than one commitment year | 1,131 |
| Multi-record groups spanning more than one sector | 535 |
| Multi-record groups with mixed labels (some positive, some not) | 159 |

**Size distribution:**

| Group size | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10–19 | 20–49 | ≥ 50 |
| --- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| Groups | 14,194 | 1,318 | 428 | 194 | 74 | 38 | 30 | 22 | 9 | 39 | 7 | 5 |

**Largest groups (no identifying text; see the CSV):**

| Size | Recipients | Years | Year span | Positive | Pakistan | Sectors |
| ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 82 | 1 | 15 | 2002–2020 | 14 | 0 | 12 |
| 80 | 1 | 7 | 2010–2020 | 17 | 0 | 10 |
| 80 | 29 | 1 | 2021 | 0 | 7 | 3 |
| 70 | 17 | 9 | 2013–2021 | 24 | 0 | 11 |
| 54 | 1 | 6 | 2004–2012 | 5 | 0 | 8 |

The large single-recipient components are long-running AidData packages, such as framework
agreements with many sub-projects over a decade. The 29-recipient group is a 2021 COVID-19
vaccine-donation package (two Parent IDs joined by identical normalized titles or descriptions), and it includes 7
Pakistan records.

These sizes are plausible for the documented relations, so no rule was revised further.
Grouping them is required because their members share text and context.

## 3. What ordinary random splitting would have leaked

A record-level random 70/15/15 split of the eligible records, using the same seed and
deterministic ordering, would have placed members of **1,268 groups** in more than one split.
That puts **4,686 records** in a group that straddles train and evaluation. The group-disjoint
protocol (`model_evaluation_protocol.md`) reduces this to **0** in every protocol, verified by
`check_disjoint` at build time and by tests.

## 4. Duplicate text

- Normalized-description groups: 514, covering 1,351 records. The largest has 12 records.
- Exact cleaned-description groups (case and punctuation preserved): 494 groups, 1,280 records.
  The normalized key was chosen because it is stricter for leakage control.
- Normalized-title groups: 98, covering 248 records.

## 5. Conflicting-label groups (quarantined, pending review)

**15 normalized-description groups (49 records)** contain both positive and negative labels.
All 49 are `quarantined` with `conflicting_label_same_description`; none was relabelled and
their original `rio_marker_src` values are kept. Row-level evidence:
`artifacts/research_v1/conflicting_label_review.csv` (`review_status = pending_human_review`).

**Investigation of whether the differences reflect context:**

| Field differing *within* the group | Groups |
| --- | ---: |
| Title | **15 of 15** |
| Original amount | 10 |
| Funding agencies | 8 |
| Commitment year | 4 |
| Currency | 3 |
| Recipient | 1 |
| Flow type | 1 |
| Status | 1 |

The description is identical in every group, but **titles always differ**: different tranches,
agencies or amounts of one package. Annotators judged title plus description, so the
disagreement may reflect real title content rather than error.

13 of the 15 groups disagree only between overall 0 and overall 1 ("significant"), i.e.
borderline judgments. The other 2 involve a principal (2) score; one of them spans `0,0,0` /
`2,2,0` with differing years, flow types and amounts.

**Conclusion:** these are **not assumed to be labelling mistakes**. They are excluded from
supervised training and evaluation until a person reviews them.

## 6. Cross-country and cross-year groups

- 80 multi-record groups span several recipients. Through these, records of different countries
  are linked, and the Pakistan holdout excludes the non-Pakistan members of such groups (74
  records in 2 groups).
- 1,131 groups span several commitment years. This is why the chronological protocol excludes
  groups that span periods (2,176 eligible records; `model_evaluation_protocol.md` §B).
