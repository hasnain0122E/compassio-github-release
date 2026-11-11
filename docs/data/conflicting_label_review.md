# Conflicting-label review (15 quarantined groups, 49 records)

**Source:** `artifacts/research_v1/conflicting_label_review.csv` (git-ignored; it contains the
titles), joined with `research_projects.parquet` for parent IDs.

**Status of every case: `pending_human_review`. No record was relabelled or reinstated.**

The categories below are a **preliminary reviewer categorization**, read from the titles,
amounts, lenders and parent IDs. A person must confirm each one against the full AidData
descriptions and source documents. Projects are named by short descriptors only.

## Summary

| Primary category | Groups | Records |
| --- | ---: | ---: |
| Suspected annotation inconsistency (same physical project and financing package, different labels) | **7** | 26 |
| Significant-versus-not-targeted ambiguity (borderline purpose; components of one package) | 4 | 8 |
| Different financing components with distinct physical scope (lots or sub-projects) | 2 | 5 |
| Same description but genuinely distinct project | 1 | 2 |
| Insufficient evidence (purpose unspecified) | 1 | 8 |

As a secondary attribute, 12 of 15 groups have all members under one AidData Parent ID, and
one more (the Ghana dam) shares it partially: they are financing components of one package.

## Review worksheet

| Group | Record IDs (label) | Descriptor | Category | Evidence needed to resolve |
| --- | --- | --- | --- | --- |
| d_7a72a20baf9c | 183 (2,2,0); 30086 (0,0,0); 30709 (0,0,0); 30801 (2,2,0); 95483 (2,2,0); 95484 (2,2,0) | Hydropower dam, Ghana: 4 loans 2007–2012 and 2 reschedulings | Suspected inconsistency (the same dam scored principal mitigation and not targeted) | Confirm all six finance the same dam; decide whether additional loans and reschedulings inherit the dam's purpose |
| d_aec917c989e9 | 67108 (1,1,1); 67109 (0,0,0); 67110 (2,2,0); 67111 (0,0,0) | 2,171 MW hydropower plant, Angola: four lenders' shares of one syndicated loan | Suspected inconsistency | Confirm it is one loan; apply one label to all lender shares |
| d_d027b3c3a2df | 66306 (1,1,0); 92611 (0,0,0); 92612 (0,0,0) | Gas processing plant, Russia: 3 lenders' shares of one syndicated loan | Suspected inconsistency | Is gas processing a climate objective under the paper's definition? Apply consistently |
| d_d90edbf8eb8c | 90926, 92660, 92662, 92663 (0,0,0); 92661 (1,1,0) | Gas-chemical complex, Russia: 5 lenders' shares | Suspected inconsistency | As above |
| d_43575599a7aa | 67041, 67063, 67064 (1,1,0); 67062 (0,0,0) | LNG project, Russia: 4 loans (RMB and EUR tranches) | Suspected inconsistency | As above: an LNG "significant mitigation" rationale is needed, or 0 for all |
| d_39124e921d89 | 91901 (1,1,0); 91917 (0,0,0) | Gas pipeline sections, Uzbekistan: equal shares from 2 lenders | Suspected inconsistency | As above |
| d_cf3db603e49e | 70085 (0,0,0); 70086 (1,1,0) | Cross-border railway, Ethiopia: 2 loans for one railway | Suspected inconsistency | Is electric rail scored significant mitigation? Apply to both loans |
| d_01376cfd2d92 | 50061 (1,1,0); 85155 (0,0,0) | 330 MW power plant, Bangladesh: 2 lenders of one syndicated loan | Significant-vs-not ambiguity | Fuel and technology of the plant (efficiency gain or not) |
| d_357334017264 | 54726 (1,1,0); 88262 (0,0,0) | Thermal power plant, Argentina: fixed and variable tranches | Significant-vs-not ambiguity | Whether the plant has an efficiency or combined-cycle mitigation rationale |
| d_cf2790b93277 | 92290 (1,1,0); 92291 (0,0,0) | Thermal power plant, Argentina: two loan tranches | Significant-vs-not ambiguity | As above |
| d_b5fd38b834fc | 60747 (0,0,0); 73174 (1,0,1) | Coastal road, Gabon: 2 loans | Significant-vs-not ambiguity (adaptation) | Whether resilience design is described for the road |
| d_194d7abf2f9d | 65749 (0,0,0); 65750 (1,0,1) | Water supply system, Angola: Lot 1 vs Lot 2 (2015 vs 2016) | Distinct components | Scope of each lot; whether Lot 2 alone has resilience components |
| d_e57463ff9f0f | 69336 (0,0,0, 2007); 69323 (1,1,1); 69335 (1,0,1) | Water treatment, Republic of Congo: rehabilitation vs extension vs distribution network | Distinct components | Per-sub-project scope; labels may legitimately differ |
| d_bdcf4587050a | 88165 (0,0,0; Colombia 2015; cancelled); 88167 (1,1,0; Argentina 2017) | Floating LNG units in two countries sharing a description | Genuinely distinct projects | Separate descriptions per project; apply the gas/LNG policy consistently |
| d_99e614de604d | 92312, 92372, 92376 (1,1,0); 92373, 92374, 92375, 92378, 92379 (0,0,0) | Syndicated loan to a development bank, Russia, "for unspecified purposes": 8 lenders | Insufficient evidence | Any documented use of proceeds; otherwise 0 for all, or exclude |

## Observations

- **Gas, LNG and thermal power** account for 7 of the 15 groups, plus one power plant whose fuel
  is not stated. The research labels appear
  inconsistent about whether gas infrastructure is "significant" mitigation. This links to the
  classifier's positive weight on "gas" (`pre_release_model_risk_review.md` §3). A documented
  gas/LNG labelling policy is needed before these records are reinstated.
- **Syndicated loans** (one project, many lenders) produce many of the conflicts. Labels should
  attach to the **project's purpose**, not to each lender's record.
- **Resolving these cases does not change Task 004 or the frozen splits.** Reinstating any
  record requires a new split version and lock (`research_split_v2`).
