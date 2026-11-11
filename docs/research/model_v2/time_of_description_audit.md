# Time-of-description audit (v2 external sources)

Source: `data/ml_v2/reports/v2build_dd7b091eb19e/timing_audit.json` (from `compassio-v2 build`).

## Definitions

| Date | Meaning | Available in |
| --- | --- | --- |
| Commitment date | Funds legally committed | **None** of the acquired external sources (AidData only, v1) |
| Approval date | Board approval | World Bank `boardapprovaldate` (2,320 of 2,369); GCF Board meeting date (348 of 348); not in FCDO IATI files |
| Document creation / publication date | When the text used was written | **Unknown for every acquired text** |
| Latest update date | Last modification of the record | GCF ODL `ProjectLastModifiedOn` (348); FCDO activities in these files carry no `last-updated-datetime` (0) |
| Evaluation date | When we captured the text | Retrieval timestamp in each retrieval manifest |

## Text timing per record (`text_timing`)

| Source | Value | Records | Meaning |
| --- | --- | ---: | --- |
| World Bank | `pre_approval_pipeline` | 27 | Status Pipeline and approval date after retrieval: verifiably pre-approval text |
| World Bank | `approval_stage_statement_current_snapshot` | 2,342 | PDO/abstract as currently served; may have been revised by restructuring |
| GCF | `portfolio_summary_undated` | 348 | GCF-written overview, no date on the page |
| FCDO IATI | `pre_approval_pipeline` | 13 | Activity status 1 (pipeline/identification) |
| FCDO IATI | `publisher_current_snapshot` | 22,219 | Current publisher text; drafting date unknown |

Contemporaneous-proposal evidence that exists but is **not** the text used: 319 GCF projects
list a dated approved funding proposal, and all 348 list a "funding proposal received" date.
Extracting those PDFs (with a reviewed PDF dependency) is the route to genuine
proposal-time text.

## Conclusions

1. No acquired text has a verified authoring date. Only 40 records (27 World Bank, 13 FCDO)
   are verifiably pre-approval at retrieval, before any filtering for usable text.
2. Approval-time forecasting validity **cannot** be claimed from these texts. A v2
   "proposal-time" evaluation is possible only on those records or on extracted, dated GCF
   proposals, and must be reported separately with its count.
3. Dropped World Bank projects (521) were never approved; their text is pre-approval in
   substance, but the API does not date it, so they stay `approval_stage_..._snapshot`.
4. AidData (v1) descriptions remain retrospective (Task 003 finding).
