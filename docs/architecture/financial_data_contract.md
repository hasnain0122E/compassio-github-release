# Financial data contract (design for the future database and API)

**Reference implementation:** `compassio_ml.finance` (`MonetaryAmount`, `aggregate`), tested in
`tests/ml/test_finance_contract.py`. **No currency conversion, deflation or allocation is
performed.**

## 1. Amount record (one published number)

| Field | Type | Meaning |
| --- | --- | --- |
| `source_id`, `source_record_id` | str | Which file and which row or transaction it came from |
| `project_key` | str or null | A *reviewed* cross-source project identity (e.g. a reviewed GCF FP code link). Null if none. |
| `flow_kind` | enum | One of the flow kinds in §2 |
| `level` | enum | `project`, `financing_instrument` (e.g. one ADB loan or grant), `transaction`, `country_aggregate`, `fund_aggregate` |
| `value` | decimal or **null** | As published. **Null = not reported, never 0.** |
| `unit` | enum | `units`, `thousands`, `millions`, as stated by the source |
| `currency` | ISO 4217 or **null** | Null = unknown, which blocks aggregation |
| `price_basis` | enum | `nominal`, `constant_2021_usd` (AidData's own conversion; never re-derived), `unspecified` |
| `observation_date`, `date_meaning` | date or null, str | e.g. "commitment date", "transaction date", "export snapshot 2026-11-08" |
| `multi_country` | bool | The value is for the whole multi-country project |
| `estimated` | bool or null | The source flags the value as an estimate (AidData `Amount Estimated`) |

**Validators:**

- currency must be ISO 4217 or null;
- the value must be finite;
- negative values only for transaction-level disbursement or repayment reversals;
- `constant_2021_usd` requires USD.

## 2. Flow kinds and their sources

| Flow kind | Example sources | Level |
| --- | --- | --- |
| `commitment` | AidData `Amount (…)`; ADB transaction type 2 | project / transaction |
| `approval` | CFU `Amount of Funding Approved`; GCF project page approval | project |
| `pledge`, `deposit` | CFU `Pledges` sheet | contributor → fund |
| `disbursement` | ADB type 3; CFU `Disbursed` (cumulative) | transaction / project |
| `repayment_principal`, `repayment_interest` | ADB types 6 and 5 | transaction (inflows to the lender, **not funding**) |
| `gcf_financing` | GCF `FA Financing`; project page "Total GCF-financing" | project |
| `co_financing` | GCF project page "Total co-financing"; GCF historical matrix | project |
| `total_project_cost` | GCF historical `Tot_Fin` (USD thousands); project page total value | project |
| `readiness_grant` | GCF readiness `Financing` | grant |
| Aggregates | GCF countries `FA/RP Financing $`; CFU `Fund Status` | country / fund aggregate |

## 3. Summation rules (enforced by `aggregate`)

| Rule | Allowed? |
| --- | --- |
| Same flow kind, currency, price basis and level; no duplicates | **Yes**: the total is reported with `summed_records`, `missing_value_records` and `estimated_records` |
| Commitment + disbursement, approval + commitment, GCF financing + co-financing, pledge + approval | **No** (different meanings) |
| Repayments + any funding flow | **No** |
| Different currencies, or unknown currency | **No** (no conversion) |
| Country or fund aggregates with anything, including each other | **No** |
| Multi-country project values summed or attributed to one country | **No**. Show the whole-project value labelled "multi-country". The GCF country summary is the only source of a Pakistan share. |
| The same project from two sources (e.g. a GCF export row and a CFU row linked by FP code) | **No** until one source is chosen per project (deduplication) |
| `total_project_cost` = `gcf_financing` + `co_financing` | **Not computed**. Show each as published; totals differ by source and date. |
| Units (thousands or millions) | Normalised to units **within one currency** only |

## 4. Missing, unknown and provenance behaviour

- **Missing amount:** show "amount not reported". Exclude it from sums and always display how
  many records were excluded. Never impute.
- **Unknown currency:** show the raw value with "currency unknown". Exclude it from every
  aggregate.
- **Estimated:** carry the source's estimate flag to the UI.
- **Status and dates:**
  - always show the status, approval or commitment date, and their source and date meaning;
  - GCF export rows have only a board-meeting code. Approval dates come from GCF project pages
    once registered, with the page URL and retrieval date;
  - AidData `Commitment Date Estimated = Yes` is shown as "estimated date".
- **Observation date:** every displayed amount states the source snapshot date. ADB's IATI file
  was generated 2026-10-21; the GCF exports are from 2026-11-08 (assumed); CFU's workbook was
  modified 2026-03-18.

## 5. Mandatory user-facing disclaimers

1. "Amounts are as published by the source; commitments, approvals and disbursements are
   different things and are never added together."
2. "Historical finance is not evidence of project success, environmental benefit or financial
   return."
3. "An approved or funded project is not necessarily open to new funding."
4. "Multi-country amounts are whole-project values."
5. "No currency conversion has been applied unless labelled 'AidData constant 2021 USD'."
