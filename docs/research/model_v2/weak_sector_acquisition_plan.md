# Weak-sector acquisition plan (transport, urban, flood/disaster, agriculture, water, ecosystems)

Counts come from `data/ml_v2/reports/<build_id>/weak_sector_requirements.json`, produced by
`uv run compassio-v2 build` (build `v2build_274957046f51`).
Labels counted are **source-reported** (A researcher, B donor); human-verified counts are 0.
Unlabelled records are never counted as negatives.

## 1. Targets (computed, not chosen)

Per sector, separately for the development **validation** pool and the human-verified
**external test** (Wilson interval, assumed recall 0.75):

| Level | 95 % half-width on recall | Positives needed per sector |
| --- | ---: | ---: |
| minimum | ±0.15 | **30** |
| preferred | ±0.10 | **70** |

Training counts are reported without a target: there is no principled minimum, only "more,
with audited labels".

## 2. Existing coverage

Build `v2build_274957046f51`. **Train / Validation** = source-labelled positives (+) and
negatives (-): B = donor markers (FCDO + EC INTPA, explicit), A = researcher labels (AidData, consumed
v1 tests excluded). **External test** = usable World Bank candidates (unlabelled) in that sector.

| Sector | Train B + / - | Train A + / - | Val B + / - | Val A + | **Val + total** | Val missing (min 30 / pref 70) | Ext. candidates (WB-tagged, PK) | Ext. verified + | Ext. missing (min / pref) |
| --- | --- | --- | --- | ---: | ---: | --- | --- | ---: | --- |
| Transport | 140 / 164 | 39 / 848 | 15 / 44 | 13 | **28** | **2** / 42 | 177 (9, 46) | 0 | 30 / 70 |
| Urban resilience | 52 / 23 | 0 / 0 | 12 / 9 | 0 | **12** | **18** / 58 | **0** | 0 | 30 / 70 |
| Flood & disaster preparedness | 128 / 331 | 26 / 620 | 32 / 86 | 3 | **35** | 0 / 35 | **0** | 0 | 30 / 70 |
| Agriculture | 706 / 236 | 37 / 499 | 146 / 33 | 9 | **155** | 0 / 0 | 294 (6, 64) | 0 | 30 / 70 |
| Water infrastructure | 233 / 89 | 66 / 161 | 52 / 42 | 12 | **64** | 0 / 6 | 139 (7, 30) | 0 | 30 / 70 |
| Ecosystems | 627 / 74 | 32 / 11 | 111 / 16 | 12 | **123** | 0 / 0 | **0** | 0 | 30 / 70 |

Readings:

- **Validation** meets the minimum except transport (28) and urban (12); urban also lacks any
  researcher (A) label because AidData has no urban sector.
- **External test:** no verified positives anywhere yet. The World Bank pool has **no**
  candidates in the urban, flood/disaster or ecosystems *sector* families: the World Bank sector
  taxonomy has no such sectors (they are themes, e.g. "Disaster Risk Management", "Urban
  Development"). These three need theme-based stratification of World Bank projects (theme level 1
  is in the API but not yet stored) or an additional evaluation-only publisher.
- At an assumed 25 % positive prevalence (planning assumption), reaching 30 verified positives
  needs about **120 reviewed items per sector**; transport, agriculture and water pools are large
  enough, the other three are not under the current sector mapping.
- Ecosystems: donor positives outnumber negatives 627:74 in training — sector strongly predicts
  the label (shortcut risk); experiments must report within-sector performance.

## 3. Accessible sources (shortlist, in priority order)

| # | Source | What it adds | Label | Rights / access evidence | Collection requirement | Review requirement |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **OECD CRS activity files** (all DAC donors) | The largest pool of donor-marked transport, water, agriculture, DRR and urban activities | B: Rio markers 0/1/2 per donor | Bulk files behind a Cloudflare challenge (HTTP 403 to automated clients); OECD terms not yet read | A **person** downloads selected year files (e.g. 2018–2023) in a browser into `data/ml_v2/manual_downloads/oecd_crs/`, records URL, date and terms; then a registration + parser task | Terms review; donor-label audit sample (100) per major donor |
| 2 | **IATI Datastore v3** | Server-side filtering by sector + policy marker across all publishers | B (where publishers report DAC markers) | Subscription key required (HTTP 401); per-publisher licences | Register for a key; store it in an environment variable, never committed; bounded queries per weak sector | Per-publisher licence check; audit sample |
| 3 | **Germany BMZ IATI** (DE-1) | Per-country files with Rio markers on programmes (observed in one probe); strong water, agriculture and DRR portfolio | B | Registry `cc-by`; **robots.txt disallows `/pub/`** for automated agents | Manual download by a person (robots governs crawlers, not people), or ask BMZ for permission | Audit sample; German/English narratives |
| 4 | Other open-licence IATI donors: Denmark (`other-at`), Ireland (`cc-zero`), New Zealand (`odc-pddl`), Canada (`other-at`) | Smaller portfolios; adaptation-heavy (Ireland, NZ) | B, **marker presence not yet checked** | robots not blocking (observed); registry licences above | Probe one file each for codes 6/7 before acquisition, as done for EC | Same as above |
| 5 | **World Bank projects: theme-level-1 stratification + more countries** (e.g. India, Philippines, Viet Nam, Ethiopia) | Urban, flood/disaster and ecosystem candidates for the **external test** (sector families are empty for these) | None (D indicator only); needs human labels | WBG T&C: non-commercial API use | Add `themev2_level1_exact` to the parser/stratifier; extend `DEFAULT_COUNTRIES`; re-acquire (new retrieval) | Two reviewers + adjudication; ~120 items per sector at 25 % prevalence |
| 6 | GCF funding proposals | Dated proposal-stage text, adaptation-rich | C only | **Restricted** (`ai-train=no`) | None until a person records reviewed permission | — |
| 7 | JICA IATI | Transport-heavy Asian portfolio | none (no policy markers) | `cc-by-sa` | Only as unlabelled external-test candidates | Two reviewers; English text is partial |

## 4. Label definitions

- **B (donor Rio markers):** DAC policy-marker vocabulary 1, code 6 mitigation / code 7
  adaptation, significance 0/1/2 reported by the donor. Explicit 0 = not targeted; absent =
  unknown. Not interchangeable with researcher labels; each new donor needs its own audit.
- **E (human):** `labeling_guidelines.md` and `reviewer_workflow.md`.

## 5. Collection rules

1. Every new source gets a registry entry, a rights-eligibility entry (fail-closed default),
   bounded retrieval with hashes, and a robots.txt/AI-signal check **before** download.
2. New donor-labelled data enters development pools only; it never enters the external test
   (World Bank) or overrides v1 assets.
3. Weak-sector targets are met with **audited** labels: a donor whose audit agreement with
   humans is poor is down-weighted or excluded in experiments, not silently mixed.
