# External-source acquisition and inspection report (Task 006-ML)

Retrieved 2026-11-09 by `uv run compassio-v2 acquire <source>`; parsed, linked and partitioned by
`uv run compassio-v2 build` → build **`v2build_dd7b091eb19e`** (rebuilt twice, byte-identical).
Every figure here comes from `data/ml_v2/reports/v2build_dd7b091eb19e/*.json` (git-ignored).
Units are stated with each number. Labels: **observed** = measured on the retrieved files.

## 1. What was actually acquired

| Source | Retrieval | Files | Bytes | Failures | Retrieval manifest SHA-256 |
| --- | --- | ---: | ---: | ---: | --- |
| `worldbank_projects` | `20261109T143438Z` | 9 (8 API pages + terms) | 5,777,425 | 0 | `aa31868d1a5b9160…` |
| `gcf_project_pages` | `20261109T143506Z` | 350 (ODL list + terms + 348 pages) | 97,742,442 | 31 (HTTP 404) | `029edd2a4eefd8c4…` |
| `iati_fcdo` | `20261109T143506Z` | 21 (registry list + 20 XML) | 269,046,843 | 0 | `f95079481fa42743…` |
| `oecd_crs` | — | 0 | 0 | blocked (Cloudflare HTTP 403) | — |
| IATI Datastore v3 | — | 0 | 0 | HTTP 401 (key required) | — |

Every file's SHA-256 is in its retrieval manifest; `uv run compassio-v2 verify-retrievals`
re-hashed all three retrievals: **OK**.

**GCF 404s (observed):** FP303–FP328 and SAP070–SAP074, i.e. the 31 most recently approved
projects listed in the ODL, have no public project page yet. They are not in the data.

## 2. Per-source inspection

### World Bank Projects API (category D indicator; unit = one project / P-code)

- Countries queried: PK, BD, NP, LK, KE, MZ (Pakistan + comparison portfolios).
  **2,369 projects**; Pakistan **640**. Board-approval years 1952–2027.
- Usable text (title + ≥100-char PDO/abstract): **1,743**; 587 have no PDO or abstract
  (mostly older projects). Median description 677 chars (10th pct 0, 90th pct 2,270).
- Status: Closed 1,581; Dropped 521; Active 240; **Pipeline 27**.
- Sector family (primary, from major-sector shares): agriculture 343, multisector 381,
  unknown 340, governance 256, transport 206, education 181, water/sanitation/waste 152,
  energy 145, finance 118, health 107, industry 79, communications 55, social protection 6.
- Climate theme tags: **82** projects (Adaptation+Mitigation 55, Adaptation 23,
  Mitigation 4); 2,287 have none (unknown, not negative).
- Explicit identifiers in text linking World Bank projects: 24 pairs.

### GCF project pages (category C; unit = one approved project, FP/SAP)

- **348 projects** with pages (ODL lists 379); all 348 have usable overview prose
  (median 1,280 chars). Pakistan **11**; 86 multi-country; 134 countries; approvals 2015–2026.
- Theme: Adaptation 159, Cross-cutting 114, Mitigation 75. Sector: none published
  (`unknown` for all; reviewers assign).
- 319 of 348 pages list a dated **approved funding proposal** document; 348 list a
  "funding proposal received" date. The PDFs were not downloaded.
- Observed quality issue: some served pages contain U+FFFD replacement characters.
- Parser note: the first build parsed 105 overviews as empty because of HTML void elements;
  fixed (regression test added) and that build was discarded before any use.

### FCDO IATI activity files (category B; unit = one IATI activity)

- **22,232 activities**: 5,124 programmes (hierarchy 1), 17,108 components (hierarchy 2);
  133 resolved countries; Pakistan **610**; usable text **21,155**.
  Median description 348 chars. Start dates include a placeholder year 1900 (data quality).
- Activity status: 4 (closed) 17,570; 2 (implementation) 4,649; **1 (pipeline) 13**.
- **Donor Rio markers (explicit, both codes 6 and 7) on 5,114 activities — all on programmes;
  components carry none.** No invalid significance values.

  | Mitigation \ Adaptation | 0 | 1 | 2 |
  | --- | ---: | ---: | ---: |
  | **0** | 4,204 | 208 | 107 |
  | **1** | 54 | 276 | 30 |
  | **2** | 53 | 13 | 169 |

- Registry licence for all 31 FCDO datasets (20 downloaded): `uk-ogl` (observed).
- 898 country codes could not be mapped to ISO3 (territories and countries absent from the
  GCF ISO2/ISO3 list, e.g. SH, MS, UA, LY, XK); they stay visible as `ISO2:XX`.

## 3. Usable labels (source-reported, not verified)

Among records with usable text: **4,441** carry explicit donor markers — **830** positive
(non-energy **770**, adaptation > 0 **731**, adaptation-only **297**, mitigation > 0 **533**)
and **3,611** explicit "not targeted" negative controls. **18,805** usable records have no
source label and are **not** counted as negatives. Human-verified labels: **0**.

Training + validation pools by priority sector (FCDO donor labels, usable text):

| Sector family | Records | Donor + | Adapt. + | Adapt.-only | Mitig. + | Explicit 0 | No label |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| multisector | 3,326 | 99 | 94 | 33 | 66 | 725 | 2,502 |
| disaster risk & emergency | 2,438 | 59 | 56 | 47 | 12 | 377 | 2,002 |
| health | 2,392 | 39 | 37 | 23 | 16 | 479 | 1,874 |
| environment & ecosystems | 1,654 | 255 | 232 | 60 | 195 | 34 | 1,365 |
| agriculture/forestry/fishing | 877 | 87 | 83 | 38 | 49 | 77 | 713 |
| water/sanitation/waste | 493 | 47 | 46 | 36 | 11 | 62 | 384 |
| **transport** | 246 | **13** | 11 | 3 | 10 | 44 | 189 |
| **urban development** | 159 | **10** | 9 | 0 | 10 | 12 | 137 |

Transport and urban positives are very thin — the sectors where v1 recall was worst.
Environment is 255 positive vs 34 negative: sector strongly predicts the donor label there
(shortcut risk).

## 4. Overlap and leakage

Evidence-backed links (pairs): IATI parent–child 17,108; exact description duplicates
AidData–AidData 837, FCDO–FCDO 459, World Bank–World Bank 66, GCF–GCF 1; exact title+text
duplicates FCDO 122, World Bank 10, AidData 6; explicit identifiers in text World Bank 24,
GCF 5. Suspected (review required, partition-only): same title 1,255 (FCDO–FCDO 1,192, World
Bank–World Bank 62, FCDO–World Bank 1); text similarity ≥ 0.85 1,105 (FCDO 1,035, World Bank
69, GCF 1). **Total suspected pairs: 2,360** → `suspected_matches_for_review.csv`.

**Cross-source overlap with AidData: none found** — no exact-text, identifier or
suspected-similarity link between AidData and any external record. This is what the methods
detect; it does not prove that no co-financed project appears in both with different text.

## 5. Resulting pools (build `v2build_dd7b091eb19e`)

| Pool | External records (usable) | Donor-labelled | Donor + | Non-energy + | Adapt.-only | Pakistan | AidData records (IDs) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| training_candidate | 17,060 (FCDO) | 3,564 | 679 | 629 | 239 | 440 | 10,203 |
| validation_candidate | 4,087 (FCDO) | 877 | 151 | 141 | 58 | 145 | 2,160 |
| external_test_candidate (sealed) | 2,099 (WB 1,743, GCF 348, FCDO 8) | — | — | — | — | 471 | 0 |
| training_only_consumed_v1_test | — | — | — | — | — | — | 8,592 |
| excluded_not_eligible | — | — | — | — | — | — | 30 |

Nine FCDO activities (one programme + eight components, one project family; eight with usable
text) were pulled into the sealed pool by one suspected same-title match
(`GB-1-107460-106` ↔ `P009353`), so they can never be used for training.

## 6. External-test pilot (sampled, **not labelled**)

300 items, one per partition group, seed 20261109, source-metadata strata only:

| Stratum | Population (partition groups with usable text) | Sampled | Pakistan |
| --- | ---: | ---: | ---: |
| World Bank, priority non-energy sector, untagged | 871 | 90 | 27 |
| World Bank, control sector, untagged | 534 | 60 | 18 |
| GCF adaptation / cross-cutting | 268 | 50 | 9 |
| World Bank, climate-theme tagged | 59 | 40 | 12 |
| GCF mitigation | 74 | 30 | 2 |
| World Bank, energy | 115 | 30 | 9 |

Pakistan: 77 of 300 (26 %); GCF has too few Pakistan projects to meet the 30 % target.
Inclusion probabilities are stored per item for weighted estimates.

## 7. Review-gate additions (build `v2build_274957046f51`)

**New source: EC INTPA IATI** (`iati_ec_intpa`), retrieval `20261109T161933Z`: 157 files
(Commission legal notice + registry index + 155 activity files), 124,134,888 bytes, **0
failures**. A first attempt (`20261109T161101Z`, kept on disk) had 4 DNS failures and HTTP 429
on the legal notice and is not used.

- **12,240 activities** (2,935 decisions, 9,305 contracts), 132 countries, Pakistan **121**;
  usable text **11,484**. Explicit Rio markers on **all** 12,240:

  | Mitigation \ Adaptation | 0 | 1 | 2 |
  | --- | ---: | ---: | ---: |
  | **0** | 7,782 | 877 | 263 |
  | **1** | 543 | 1,445 | 369 |
  | **2** | 281 | 305 | 375 |

- Sector families: governance 4,274; multisector 2,303; agriculture 1,022; industry 800;
  energy 703; environment 572; education 523; health 479; transport 333;
  social protection 325; water 318; communications 234; disaster 148; finance 77; urban 75.
- End dates up to year 2100 occur (placeholder values; data quality).
- Overlap: 9,845 parent–child links, 387 exact-description and 74 exact-text duplicates within
  EC, 1 explicit World Bank P-code reference (to a project outside the six acquired countries),
  4 suspected same-title matches with FCDO, 5,882 suspected text-similarity pairs within EC
  (contracts repeating decision text). **No link to AidData.**

**Rights changes:** GCF pages (348) moved to `restricted_reference_only` (robots.txt
`ai-train=no`). **v1 consumed tests:** all 8,592 AidData records from any v1 test partition are
now `excluded_consumed_v1_test` (previously training-only).

**Totals:** 37,189 external records; donor-labelled usable records **15,925** (5,055 positive,
4,469 non-energy positive, 4,170 adaptation > 0, 1,379 adaptation-only, 10,870 explicit
not-targeted); 18,805 unlabelled usable records (not negatives); 8,533 suspected pairs for review.
