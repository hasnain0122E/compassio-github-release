# MVP feature contract (Task 004.5)

**Global rules:**

- Every feature is decision support. Compassio does **not** predict financial return, prove
  climate impact, detect fraud or verify that funding is available.
- **Public display of any source is blocked** until its rights review is complete
  (`docs/data/source_rights_matrix.md`).
- Feasibility below means *technically* feasible with registered data.

**Two distinct concepts:**

- **Historical / current projects:** projects that were financed or approved.
- **Available-to-fund opportunities:** projects currently seeking finance. **No registered source
  provides this today.**

| Feature | Required source fields | Method | User output | Limitations | Must not claim | Feasible now? | Blocked by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Historical project explorer** | Research/AidData: id, cleaned title and description, recipient, year, sector, flow type, commitment amount, currency, status. ADB, GCF and CFU project fields. | Filter and search over processed tables, per source and never merged | List with source badge, original fields, provenance link | Chinese finance only up to 2021; descriptions are retrospective; cross-source duplicates exist | Completeness of Pakistan climate finance | **Yes** (research data); other sources need processed tables | Rights review; processed tables for ADB, GCF and CFU |
| **Current verified portfolio** | GCF project pages (approval date, status, financing); ADB IATI status and dates | Status as published, with snapshot date | Projects with status, approval date and source date | GCF export lacks dates (project pages needed); "current" = as of the snapshot | That projects are seeking or accepting new funding | **Partial**: ADB yes; GCF dates need a new source | Register GCF project pages; rights |
| **Project detail and provenance** | All fields plus manifest SHA-256, source URL reference, `research_text_originals` | Join by stable id within one source | Fields, original text, source file hash, cleaning steps, labels with "authors' annotation" note | Labels are the authors' annotations (Qi et al. 2026) | Independent verification of labels | **Yes** | Rights |
| **Climate relevance screening** | `title_clean`, `description_clean` | Frozen classifier (`ClimateRelevanceClassifier`) at the locked threshold | Flag, score (a probability only for probabilistic models), model version, sector-specific reliability note | Validation non-ENERGY recall 0.39; retrospective-text confound; untested on other publishers' text and on proposals | Impact, funding quality, approval. A negative never means "not climate". | **Yes, for research-style text**, with warnings | Task 005 test results; external validation for other text types |
| **Top 10 review-priority** | Screening score, `retrospective_text_warning`, missing or conflicting evidence flags, user-chosen filters | Rank by a **transparent, user-visible rule**: e.g. uncertain scores near the threshold plus evidence gaps, *"what to review next"* | 10 projects with the reason for each rank | It is a review queue, not a quality ranking | "Best", "highest impact" or "highest return" projects | **Yes** (rule-based) | — |
| **Project comparison** | Same-source fields; `MonetaryAmount` records | Side by side, per flow kind; amounts only where comparable (§3 of the financial contract) | Table with flow kind, unit, currency and date per amount | Different flow kinds are not comparable | That one project is a better investment | **Yes** within one source | Rights |
| **Funding trends** | AidData commitments (Recommended For Aggregates, constant 2021 USD); ADB transactions by type; CFU approvals by year | `compassio_ml.finance.aggregate` per flow kind, currency and level; count of missing values shown | Time series per flow kind, labelled with source and coverage | AidData amounts missing for 39%; CFU has no IDs; GCF has no dates in the export | Totals across sources or flow kinds; "climate finance to Pakistan" as one number | **Partial**: AidData and ADB yes | Rights; GCF dates; a cross-source dedup policy |
| **Hypothetical budget scenario planner** | User-entered budget and constraints; project list with user-chosen weights | Transparent allocation under user constraints (e.g. linear rules). Historical amounts shown as context only. | Scenario table with every assumption visible | Hypothetical; no outcome model | Optimal return, impact or "recommended investment" | **Feasible** as a pure scenario tool | Defining the allowed inputs; UI disclaimers |
| **Missing / conflicting evidence flags** | `exclusion_reasons`, `retrospective_text_warning`, missing-amount, multi-country, estimated, quarantined-conflict, rights status | Rule-based from existing columns | Badges per project with explanation | Flags are only as complete as the fields | That unflagged data is verified | **Yes** | — |

## Required disclaimers on every screen with scores or amounts

1. Decision support only; not funding approval.
2. Climate relevance means text similarity to annotated projects, not proven impact.
3. Amounts are as published; flow kinds are never added together; no currency conversion.
4. Historical projects are not available-to-fund opportunities.
