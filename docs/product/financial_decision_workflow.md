# Financial decision workflow (Task 008 backend; UI in Task 010)

**The user problem:** "People researching environmental funding struggle to discover relevant
projects, understand where money has gone and compare project information reliably."

Compassio is **decision support**. It helps a person decide which historical records deserve
due diligence. It never approves, recommends or allocates real funding.

## The six steps a frontend can now support

| Step | User goal | Endpoint(s) | What the user must be told |
| --- | --- | --- | --- |
| 1. Find records | Find suitable historical project records | `GET /projects` (search and filters), `GET /analytics/coverage` | Records are historical, from sources with unreviewed rights (local only) |
| 2. Understand the landscape | See where money went | `GET /analytics/country-profile/PAK`, `/analytics/funding-by-country`, `/analytics/funding-by-sector`, `/analytics/trends`, `/analytics/approved-vs-disbursed`, `/analytics/institutions`, `/analytics/climate-distribution` | Each figure is one metric from one source, with a declared universe, meaning, currency and exclusions. Figures are never added across metrics |
| 3. Compare | Put 2–10 records side by side | `POST /decision/compare` | Only figures with the same comparability key are aligned. Totals appear only when safe; otherwise the reason is shown |
| 4. Understand every figure | Know what an amount means | `GET /decision/evidence/{id}` | `meaning_label`, `fact_type`, `country_attribution`, `verified_approval`, `completeness.missing`, `limitations` |
| 5. Decide what to review | Rank records with criteria the user chooses | `POST /decision/prioritize` | A rank means "worth reviewing under these criteria". It does not mean attractive, eligible or effective |
| 6. Explore a budget | Try a hypothetical allocation | `POST /decision/scenarios` | A simulation only. Historical figures are context, not costs |

## Three things the UI must keep apart

1. **Relevant to the search.** The record matches the user's filters (`matched_filters`).
2. **Has documented historical funding.** A reported funding-flow amount exists. Repayments,
   pledges and total project cost do not count.
3. **Is a currently available opportunity.** This is always `not_determinable`, because
   Compassio has no data on open calls.

## Reading a figure

Each amount comes with:
- its flow (commitment, approval, disbursement, pledge, repayment, co-financing, total cost,
  readiness grant);
- its level (project, instrument, transaction);
- its currency and unit, and its price basis (nominal, or AidData constant 2021 USD);
- its date meaning;
- whether it is a source fact or a derived sum of that record's own transactions;
- for multi-country records, the fact that it is a whole-project value.

A missing value is shown as missing, never as 0.

## Human review

Climate labels are classifications, not measured impact. Model screening (Task 007) is a
separate, local-only, human-reviewed step:
- `POST /screening/projects/{id}`, with ML v2 only in the authorized demo;
- `POST /reviews`, which records the decision with provenance.

The decision engine never runs a model and never writes data.
