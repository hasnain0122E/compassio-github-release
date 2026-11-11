# Research label audit

Source: `research_paper`, archive `30015124.zip` (sha256 `f4420394…`). Every count below was
computed by `uv run compassio-data audit` (see `artifacts/data_audit/research_label_distribution.csv`
and the `research_labels` section of `audit_facts.json`).

Each statement is tagged **[observed]** (computed from the file), **[documented]** (stated by the
authors in the paper; added in Task 003), **[inferred]** (a reasoned interpretation nobody
documents), or **[unknown]**.

## 0. Official definition (verified in Task 003)

**Citation:** Qi, J., Tang, Y., Zhang, Z., Wang, Y. & Qian, H. (2026). *A Benchmark Dataset of
Chinese Development Finance with Climate Relevance and SDG Annotations from 2000–2021.*
*Scientific Data* 13, 277 (published 2026-01-20). https://doi.org/10.1038/s41597-026-06605-9 ·
open access at https://pmc.ncbi.nlm.nih.gov/articles/PMC12921263/ · data:
https://doi.org/10.6084/m9.figshare.30015124 (version 1).

The open-access article was read on 2026-11-09. The relevant passages:

| Location in the paper | Passage (verbatim) |
| --- | --- |
| Methods › Data collection and platform establishment, **Table 1** (caption "An example of the project labelling sample in Rio Marker and SDG Marker") | Column header **"Rio Marker (Overall, Mitigation, Adaptation)"**. Examples: "Training of water-saving and drought-resisting rice technology", **2,0,2**; "Private investment in electric/hybrid vehicles production", **2,2,0** |
| Methods › Data processing | "In line with the Rio Marker system, projects were scored on a three-point scale: 0 ("not targeted"), 1 ("significant objective"), and 2 ("principal objective")." |
| Methods › Data processing | "A score of 2 indicates that climate change mitigation or adaptation is the main purpose of the project." "A score of 1 reflects projects where climate action is an important but secondary aim." |
| Methods › Data processing | "Mitigation refers to efforts that reduce greenhouse gas emissions or enhance carbon sinks"; "adaptation includes actions that address the impacts of climate change by reducing vulnerability or improving resilience." |

The data files themselves are confirmed to be the published ones: the two workbooks in our
archive are **byte-identical to Figshare 30015124 v1**, because their MD5s match the Figshare API
(`provenance_and_rights_review.md`).

**What this does and does not establish:**

- **[documented]** Positions are `rio_overall`, `rio_mitigation`, `rio_adaptation`. Scores:
  0 = not targeted, 1 = significant objective, 2 = principal objective.
- **[documented]** Each project was "independently reviewed by at least three annotators", and
  "unresolved cases were escalated to senior researchers … for final judgment". 85.38% of
  projects had complete agreement among the three annotations.
- **[documented]** The 1,383 climate-related projects were identified "after cross-verification"
  between the manual annotations and a fine-tuned **ClimateBERT** (the paper reports F1 0.918 for
  ClimateBERT). The labels are therefore **the authors' annotated labels, partly informed by a
  model**. They are not independent ground truth, and Compassio does not verify them
  independently.
- **[observed]** The paper says "the inter-annotator agreement statistics are included in the
  final dataset", but **neither published workbook contains an agreement column**, so per-record
  label confidence is unavailable.
- **[not documented]** The paper never states that `overall = max(mitigation, adaptation)`. The
  relationship holds in all 20,985 rows, but the parser *checks* it (`rio_overall_is_max`) rather
  than assuming it.
- **[documented]** The paper calls the 1,383 "climate-related" but does not define the term as
  "overall > 0". Compassio's operational target `is_climate_related = rio_overall > 0` reproduces
  exactly the 1,383 records the paper reports.
- **[documented]** The paper also reports a separate ClimateBERT screen that identified 2,640
  projects as climate-related, a figure it does not reconcile with 1,383. Compassio uses only the
  annotated `rio_marker`.

## 1. Which workbook holds which annotation

| Workbook | Sheets | Rows | Annotation |
| --- | --- | ---: | --- |
| `Chinese_Climate_Finance_2000-2021.xlsx` | `Sheet1` | 20,985 | **Climate**: one text field, `rio_marker` [observed] |
| `Chinese_Development_Finance_SDG_Categorizations_2000-2021.xlsx` | `Centralized ver.`, `Extended ver.` | 20,985 each | **SDG**: `Centralized_SDG` / `Extended_SDG` lists plus 17 binary columns `SDG1`…`SDG17` [observed] |

The rows and `AidData_Record_ID` order are identical across all three sheets [observed]. The
archive contains **no codebook or README**, so label definitions come only from the paper (§0).

## 2. Reproducing the earlier exploratory figures

| Hypothesis (earlier audit) | Recomputed | Rule used | Match |
| --- | ---: | --- | --- |
| 20,985 historical project rows | **20,985** | rows in the climate workbook (one per AidData record) | yes |
| 1,383 climate-marked records | **1,383** | `rio_marker` first score > 0 | yes |
| 496 Pakistan-related records | **496** | `Recipient == "Pakistan"` (identical to AidData `Recipient ISO-3 == "PAK"`) | yes |
| 76 Pakistan climate-marked records | **76** | both rules above | yes |

All four reproduce exactly. They are now **observed values**, tied to the file hash above.

## 3. The `rio_marker` field

**Format [observed]:** a string of three comma-separated integers, each 0, 1 or 2. All 20,985
values parse, and none are blank or malformed.

| `rio_marker` | Records | Share | Pakistan |
| --- | ---: | ---: | ---: |
| `0,0,0` | 19,602 | 93.41% | 420 |
| `2,2,0` | 450 | 2.14% | 27 |
| `1,1,0` | 267 | 1.27% | 8 |
| `2,2,1` | 232 | 1.11% | 29 |
| `1,0,1` | 220 | 1.05% | 4 |
| `2,0,2` | 90 | 0.43% | 3 |
| `1,1,1` | 81 | 0.39% | 2 |
| `2,2,2` | 35 | 0.17% | 2 |
| `2,1,2` | 8 | 0.04% | 1 |

**Structure [observed]:** in all 20,985 rows, the first score equals the maximum of the second
and third.

**Meaning [documented, §0]:** overall, mitigation and adaptation, each scored 0/1/2. Before
the paper was read, Task 002 inferred the positional assignment from lexical association. That
inference agrees with the documentation:

  | Term in title/description | Records | Pos. 2 > 0 | Pos. 3 > 0 |
  | --- | ---: | ---: | ---: |
  | hydropower/hydroelectric | 515 | 359 | 68 |
  | solar | 309 | 216 | 129 |
  | emission / low-carbon | 73 | 51 | 16 |
  | drought | 119 | 3 | 22 |
  | early warning / meteorology | 65 | 4 | 23 |

  Energy-generation terms co-occur with position 2, and hazard-preparedness terms with position 3.

Code exposes the components as `rio_overall`, `rio_mitigation`, `rio_adaptation` and
`is_climate_related` (`compassio_ml.research.labels`). The original string is preserved as
`rio_marker_src`.

**Component distributions [observed]:** overall 0/1/2 = 19,602 / 568 / 815. Mitigation = 19,912 /
356 / 717 (1,073 non-zero). Adaptation = 20,319 / 533 / 133 (666 non-zero). 356 records are non-zero
in both components.

## 4. Proposed target and its definitions

| Target candidate | Positive | Negative | Missing |
| --- | ---: | ---: | ---: |
| Binary: overall > 0 | 1,383 (6.59%) | 19,602 | 0 |
| Pakistan subset | 76 (15.3% of 496) | 420 | 0 |

- **Positive** means the annotators scored the record significant or principal for climate in at
  least one component.
- **Negative** means `0,0,0`. **[inferred]** This most likely means "not identified as
  climate-relevant from the text", not "verified to have no climate effect".
- **Uncertain or ambiguous labels:** the file has no uncertainty or confidence field and no
  annotator identity [observed]. 15 groups of identical normalized descriptions (49 rows) carry
  *conflicting* binary labels [observed], which gives a lower bound on label noise.
- **Class balance varies by year** [observed]. The positive share rises from 5.1% (11/215) in 2000
  to 11.1% (110/987) in 2013. It then falls to 2.8% in 2020 (58/2,052) and is 4.1% in 2021
  (54/1,326). Chronological splits will therefore shift the prior.

## 5. Pakistan consistency

`Recipient` is a single country name, and `"Pakistan"` appears in exactly one spelling, with no
multi-country strings containing it [observed]. The 496 rows match AidData's `Recipient ISO-3 ==
"PAK"` rows one to one. Of these, 433 are AidData "Recommended For Aggregates".

## 6. Descriptions as model input

- All 20,985 rows have a description [observed]. Lengths: min 68, median 641, max 25,936
  characters. 39 are under 100 characters.
- Descriptions are **AidData's text**. They match AidData v3.0 exactly in 20,984 rows. The one
  difference (record 54013) is a missing word "null" ("declared  and void"), which is consistent with
  NA-string scrubbing in the research pipeline [observed / inferred cause].
- **Titles are truncated to 255 characters** in 12 rows relative to AidData [observed].

## 7. Leakage assessment

| Risk | Evidence | Consequence |
| --- | --- | --- |
| **Retrospective text** | AidData defines `Description` to include implementation timing, challenges, achievements and shortcomings [observed definition]. 8,699 descriptions (999 of the positives) mention a calendar year later than their commitment year [observed]. | The model sees post-commitment information. A chronological split tests *year shift*, not prediction at approval time. Never claim the text was available at commitment. |
| **Label-bearing fields** | `rio_marker` (the target). `SDG13` and the SDG lists are a separate annotation correlated with it: of the overall=2 records, 672 have Centralized SDG13 = 1 and 143 have SDG13 = 0 [observed]. | Exclude `rio_marker`, all `SDG*` columns, `Centralized_SDG` and `Extended_SDG` from the inputs. |
| **Lexical shortcuts** | 100 records mention "climat…", and 63% of them are positive versus a 6.6% base rate. But 1,320 of the 1,383 positives don't contain the word [observed]. | Keyword baselines are needed to measure what the model adds. The word "climate" alone can't explain the labels. |
| **Sector proxy** | ENERGY: 802 of 1,381 positive. GENERAL ENVIRONMENTAL PROTECTION: 67 of 90 [observed]. | `Sector_Name` is a legitimate but strong prior. Report results with and without it. |
| **Duplicates across splits** | 1,351 rows share a normalized description (514 groups). 248 rows share a normalized title (98 groups). 1,989 rows share a title once tranche or phase numbers are removed (663 groups) [observed]. | Group by normalized description, by title series and by AidData Parent ID when splitting. |
| **Related records** | 6,066 AidData records belong to 1,949 multi-record `Parent ID` packages [observed]. | Same as above: keep each package within one fold. |
| **Staff comments** | AidData's `Staff Comments` is not in the research workbook, but it is in AidData [observed]. | Never join it in as a feature: it explains coding decisions. |

## 8. Field suitability (for Task 003 feature work; no features built here)

| Field | Use |
| --- | --- |
| `Title`, `Description` | **Primary text inputs**, with the leakage caveats above |
| `Sector_Name`, `Flow_Type`, `Funding_Agencies_Type`, `Recipient_Region` | Optional context. Report ablations. |
| `Recipient` | Needed for Pakistan evaluation slicing. As an input it risks a country prior. |
| `Commitment_Year` | **Split key** for chronological evaluation, not an input |
| `Amount_Constant_USD_2021`, `Grant_Element_OECD_Cash-Flow` | Missing in 8,186 and 18,090 rows. Not recommended as inputs. |
| `Implementation_Start_Year`, `Completion_Year` | Post-commitment information (**exclude**) |
| `rio_marker` | **Target only** |
| `ID`, `AidData_Record_ID` | Identifiers only (join and grouping keys) |
| All SDG workbook columns | **Exclude** (correlated annotation) |

## 9. Dates for chronological evaluation

- `Commitment_Year`, AidData's definition: the year the official commitment was signed. When
  that year is unknown, AidData uses the first implementation year as a proxy [observed definition].
  For 11,782 records AidData marks `Commitment Date Estimated = Yes` [observed].
- `Implementation_Start_Year` and `Completion_Year` are implementation milestones, not publication
  dates.
- **When the annotations were made [unknown]:** the files carry no annotation dates. Workbook
  metadata shows creation on 2025-08-07 and modification on 2025-08-18, which says when the files
  were made, not when labelling happened.

## 10. Can the target be built reliably?

**Yes, as a binary text-classification target over the authors' annotations. It is not a
point-in-time forecasting target.** The status of the Task 002 conditions:

1. ~~Confirm the position semantics against the paper text~~: **done** (§0).
2. Grouped splits controlling duplicate leakage: **done** in Task 003
   (`leakage_group_audit.md`, `configs/research_split_v1.yaml`).
3. Chronological results must be described as distribution shift over commitment years on
   retrospective text: **specified** in `docs/research/model_evaluation_protocol.md`.

Remaining caveats: the labels carry no per-record agreement score (§0); the 15 conflicting
description groups are quarantined pending human review (`leakage_group_audit.md` §5); and
ClimateBERT took part in label construction, so a ClimateBERT classifier is not an independent
comparison.
