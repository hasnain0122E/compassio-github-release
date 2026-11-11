# Pre-release model risk review (Task 004.5)

**Scope:** validation-only analysis of the Task 004 provisional winner,
`logistic_regression | title_description | word_unibi`, from run
`primary__full__seed20260109__cfg2f0656ed`. **No model was retrained, no threshold changed, no
test partition opened.**

**Regenerate:**

```
uv run compassio-ml error-analysis --run-dir experiments/benchmarks/primary__full__seed20260109__cfg2f0656ed
```

This writes `error_analysis/{validation_errors,error_tag_summary,positive_recall_by_sector,top_terms}.csv`
inside the run directory (git-ignored). The command refuses any prediction outside the primary
**validation** partition.

Evidence labels: **[observed]** is computed on validation predictions or the training partition;
**[hypothesis]** is a plausible explanation that has not been tested.

## 1. Outcome counts (validation, threshold 0.474 chosen on train-OOF)

TP 175 · FP 46 · FN 64 · TN 2,855. This is identical to the Task 004 report [observed].

## 2. Error taxonomy (deterministic tags, `modeling/error_analysis.py`)

| False negatives (64) | Records | Share |
| --- | ---: | ---: |
| Non-ENERGY sector | **59** | 92% |
| No pre-registered climate keyword in the text | 45 | 70% |
| Label is "significant" (1), not "principal" (2) | 43 | 67% |
| Retrospective wording | 42 | 66% |
| Adaptation-only label | 32 | 50% |
| Mitigation-only label | 25 | 39% |
| Mitigation and adaptation | 7 | 11% |
| Description shorter than 300 characters | 7 | 11% |

| False positives (46) | Records | Share |
| --- | ---: | ---: |
| Retrospective wording | 36 | 78% |
| Non-ENERGY sector | 25 | 54% |
| ENERGY sector | 21 | 46% |
| Climate keyword present | 15 | 33% |

**Recall of validation positives by sector [observed]:**

| Sector | Positives | Recall |
| --- | ---: | ---: |
| ENERGY | 142 | 0.965 |
| Water supply and sanitation | 19 | 0.579 |
| General environmental protection | 16 | 0.500 |
| Transport and storage | 15 | **0.200** |
| Agriculture, forestry, fishing | 13 | 0.385 |
| Other multisector | 7 | **0.000** |
| Emergency response | 4 | **0.000** |

The non-ENERGY sector cells hold 1–19 positives each, so the per-sector recalls are imprecise.

**Non-ENERGY validation positives (97) by label type [observed]:**

| Label type | Positives | Recall |
| --- | ---: | ---: |
| Adaptation-only | 49 | 0.347 |
| Mitigation-only | 29 | **0.276** (mostly transport and industry) |
| Both | 19 | 0.684 |

By level, recall is 0.310 for "significant" and 0.513 for "principal". Recall is 0.317 among the
63 non-ENERGY positives with no climate keyword.

## 3. What the model has learned

**Top positive coefficients [observed]:** solar, hydropower, power, energy, hydroelectric, wind,
water, biogas, green, river, gas, dam, climate, transmission, wind farm, meteorological, forest,
photovoltaic, environmental, electricity. **Top negative:** coal, coal fired, medical, thermal
power, road, hospital, oil, school, covid, university, donated, police.

**Conclusion [observed, with interpretation]:** the model mainly detects **energy-technology and
infrastructure vocabulary**. These are genuine mitigation activities, but in a narrow set. It has
few strong cues for adaptation or non-energy mitigation.

- **Generic financing and wording artifacts** also carry weight: "was loan" (−3.7), "project
  this", "two", "international", "for unspecified". This is a sign of sensitivity to AidData's
  writing conventions rather than to climate content [observed, interpretation].
- **"gas" is a positive cue (+7.3).** It could reflect fuel-switch or LNG records that annotators
  scored "significant" [hypothesis]. The quarantined conflict groups include several gas and LNG
  packages with inconsistent labels (`docs/data/conflicting_label_review.md`).

## 4. Other factors examined

| Factor | Observation | Status |
| --- | --- | --- |
| **Retrospective wording** | It is enriched among FP (78% vs 46% of true negatives) and among TP (83% vs 66% of FN). F1 is 0.789 with the warning, 0.644 without (Task 004). Long after-the-fact narratives raise scores in both directions. | observed association; causal role is a **hypothesis** |
| **Description length** | Median characters: TP 1,728 and FP 1,798, against FN 1,084 and TN 591. Longer texts are more often scored positive. | observed |
| **Title length** | Medians FN 112.5, TP 111, FP 131.5, TN 100. No clear effect. | observed (weak) |
| **Project age** | Recall by commitment band: 0.71 (2000–05), 0.78 (06–10), 0.74 (11–15), 0.72 (16–21). No degradation in the primary protocol. The chronological protocol's validation AP is about 0.10 lower. | observed |
| **Underrepresentation in training** | 918 training positives, of which 544 are ENERGY (59%). The 374 non-ENERGY positives spread over many sectors (water 85, transport 56, agriculture 51, environment 42, emergency 26, multisector 16). 245 of the 374 are "significant" (borderline). | observed |
| **Pakistan** | Research Pakistan positives are 60 of 76 ENERGY (Task 003). Given non-ENERGY recall of about 0.39 on validation, Pakistan non-ENERGY recall (16 holdout positives) is likely to be weak. | **hypothesis**; not measured, and the test stays unopened |

## 5. Interpretation for the product

- **Strength:** in its current form the classifier reliably flags energy-mitigation projects:
  validation ENERGY recall 0.965 at precision 0.867.
- **Weakness:** it is **not reliable** for adaptation, water, agriculture, disaster resilience or
  transport. These are the categories most relevant to a Pakistan-first climate tool. A negative
  prediction outside ENERGY must not be read as "not climate-relevant".
- **What would help:**
  - more and cleaner non-ENERGY labels;
  - an independent adaptation-focused evaluation set (`external_validation_protocol.md`);
  - possibly representations that capture purpose rather than technology words.

  These are **hypotheses for a future, versioned benchmark**. Nothing was changed here.
- **Model selection is unchanged:** logistic regression remains the provisional validation
  winner, and the threshold stays locked at 0.474. The calibrated SVM shows the same sector
  pattern (Task 004 slices), so this review gives no reason to prefer one over the other.

## 6. Risk register

Machine-readable copy: `docs/research/risk_register.csv`.

| ID | Risk | Evidence | Severity | Affected feature | Mitigation | Owner | Verification | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | Low non-ENERGY recall (adaptation, water, transport) | Validation non-ENERGY recall 0.392; 59 of 64 FN | **High** | Climate relevance screening; review priority | UI shows sector-specific reliability; a negative is never shown as "not climate"; collect an external adaptation set | ML lead | External validation by sector; Task 005 test slices | Open |
| R02 | Retrospective-text confound | FP 78% vs TN 46% warned; F1 0.789 vs 0.644 | High | Screening of new proposals | Report warned/unwarned separately; claim validity only for retrospective descriptions; obtain contemporaneous proposal texts | ML lead | Task 005 slice; external proposal-text set | Open |
| R03 | Label inconsistency within financing packages | 7 of 15 conflict groups suggest inconsistent labels for the same project | Medium | Training data and metrics | Human review worksheet; keep quarantined | Data lead and reviewer | Completed worksheet | Open |
| R04 | Pakistan non-ENERGY performance unknown and likely weak | 60 of 76 Pakistan positives ENERGY; 16 non-ENERGY | High | Pakistan-first claims | Report Pakistan ENERGY / non-ENERGY with counts; no stable-performance claims | ML lead | Task 005 Pakistan holdout (once) | Open |
| R05 | Sensitivity to source writing conventions | "was loan", "project this" among top coefficients | Medium | Transfer to GCF/ADB/CFU text | External validation on other publishers' text before any cross-source screening claim | ML lead | External set by source | Open |
| R06 | Runs made from a dirty tree | `run_manifest.json` `dirty: true` (Task 004) | Low | Reproducibility | Re-run the chosen configuration from commit `35dac13`+ before Task 005 cites it | ML lead | `dirty: false` in the new manifest | Open |
| R07 | Labels partly model-informed (ClimateBERT cross-verification) | Qi et al. 2026, Methods | Medium | Any ClimateBERT comparison; label trust | Never present a ClimateBERT challenger as independent | ML lead | Doc review | Open (documented) |
| R08 | Financial misaggregation | Multi-type and multi-unit amounts across sources (Task 002) | High | Trends, comparison, scenario planner | `compassio_ml.finance.aggregate` enforces the summation rules (tested) | Data lead | Unit tests and API contract tests | Mitigated in code; API not built |
| R09 | Unreviewed source rights | All 9 sources `not_reviewed` | High | Any public display | `source_rights_matrix.md`; human legal review before public release | Product owner | Manifest `rights_status` updated with evidence | Open |
| R10 | No dated GCF approvals in the registered export | Task 002 | Medium | Current portfolio, trends | GCF project pages carry approval dates (FP085 verified); register them as a new source | Data lead | New manifest entry | Open |
| R11 | Users misread scores as impact or approval | Product risk | High | All screening outputs | Mandatory disclaimers (`mvp_feature_contract.md`) | Product owner | UI review | Open |
