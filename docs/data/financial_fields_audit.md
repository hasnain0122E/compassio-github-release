# Financial fields audit

Generated table: `artifacts/data_audit/financial_fields.csv` (from `uv run compassio-data audit`).
No currency conversion, deflation or cross-type summing is performed anywhere in this repository.

> Historical committed finance is not evidence of project success, environmental benefit or
> investment return. An approved project is not necessarily seeking new funding.

## 1. Field register

| Source | Field | Flow kind | Level | Unit / currency | Non-blank | Notes |
| --- | --- | --- | --- | --- | ---: | --- |
| research_paper | `Amount_Constant_USD_2021` | commitment (or pledge) | project/activity | USD, constant 2021 | 12,799 | Equals AidData `Amount (Constant USD 2021)` rounded to cents (all 20,985 within $0.005) |
| aiddata | `Amount (Original Currency)` + `Original Currency` | commitment (or pledge) | project/activity | 102 currency codes | 12,799 | 0 amounts lack a currency code |
| aiddata | `Amount (Constant USD 2021)` | commitment (or pledge) | project/activity | AidData conversion (commitment-year average rate) + OECD deflator | 12,799 | Comparable across years *as AidData defines it* |
| aiddata | `Amount (Nominal USD)` | commitment (or pledge) | project/activity | nominal USD | 12,799 | |
| aiddata | `Adjusted Amount (…)` ×3 | adjusted commitment | project/activity | as above | 11,386 | AidData's "adjusted" amount; never add it to the unadjusted amount |
| aiddata | `Amount Estimated` | flag | | | 1,408 = Yes | Amount estimated by AidData |
| adb_pakistan | transaction type 2 | **commitment** | transaction | USD (activity `default-currency`) | 192 | Sum within type: $32,126,214,330 |
| adb_pakistan | transaction type 3 | **disbursement** | transaction | USD | 7,117 | 31 negative values. Sum within type: $21,549,925,012.94 |
| adb_pakistan | transaction type 5 | **interest payment** (inflow to ADB) | transaction | USD | 14,062 | 6 negative values. Not funding. |
| adb_pakistan | transaction type 6 | **loan repayment** (inflow to ADB) | transaction | USD | 9,591 | Not funding |
| gcf_projects | `FA Financing` | GCF funding approved **[assumed]** | project (multi-country rows carry the full amount) | USD **[assumed]**, header states no unit | 379 | Excludes co-finance; not total project cost |
| gcf_readiness | `Financing` | readiness grant **[assumed]** | grant | USD **[assumed]** | 876 | 16 values ≤ 1 are placeholders on cancelled grants |
| gcf_countries | `RP Financing $`, `FA Financing $` | readiness / funded-activity **aggregates** | country | USD | 155 each | Country shares; never mix with project rows |
| gcf_historical | `Tot_Fin` | **total project financing incl. co-finance** | project | **USD thousands** (`TO READ` sheet) | 122 parsed | 5 values are text such as `USD 220 000,00` (unparseable, treated as missing) |
| gcf_historical | `GCF_*`, `i_*`, `npu_*`, `npr_*` | co-financing by funder type × instrument | project | USD thousands **[assumed]**, same as `Tot_Fin` | — | 4 duplicated column names |
| climate_funds_update | `Amount of Funding Approved (USD millions)` | **approval** | project | **USD millions** | 4,066 | |
| climate_funds_update | `Disbursed (USD millions)` | **cumulative disbursement** | project | USD millions | 3,099 | 52 whitespace-only cells (blank, not zero) |
| climate_funds_update | `Concessional loan`, `Grant`, `Guarantee`, `Equity` | approval split by instrument | project | USD millions | 331 / 3,943 / 16 / 32 | |
| climate_funds_update | `Pledges` sheet: `Pledged`, `Deposited` | pledge / deposit **into funds** | contributor → fund | USD millions, current | 564 / 557 | Money into funds, not to projects |
| climate_funds_update | `Fund Status` sheet: 4 measures | pledge / deposit / approval / disbursement | fund aggregate | USD millions | 30 each | Cumulative per fund |
| climate_project_explorer | — | none | | | | No financial fields |

## 2. What must never be combined

1. **Transaction types (ADB).** Repayments (types 5 and 6, 23,653 rows) are 76% of ADB
   transactions. Commitments, disbursements and repayments are reported separately and never
   netted.
2. **Commitment vs disbursement vs approval.** AidData and the research workbook record
   commitments. ADB has commitments and disbursements. CFU has approvals and cumulative
   disbursements. GCF exports have approved funding. These are different quantities.
3. **Units.** CFU is in USD millions and GCF historical in USD thousands, while the others are in
   units. A unit-aware conversion is mandatory before any comparison.
4. **Levels.** GCF country and CFU fund aggregates must never be added to project rows.
   - Example (Pakistan) [observed]: the GCF country summary gives `FA Financing $` =
     $331,727,118. The 8 single-country Pakistan projects sum to $258,727,978 of `FA Financing`.
     The 3 multi-country projects that include Pakistan carry $628,000,000 of whole-project
     funding.
   - Summing all 11 would overstate Pakistan's GCF funding (≈ $886.7M against $331.7M).
5. **Sources.** CFU's GCF rows (1,196) duplicate the GCF exports. AidData records marked "Not
   Recommended For Aggregates" (3,028) include pledges, cancellations and umbrella records that
   AidData warns would double count.
6. **Grant vs loan.** AidData `Flow Type` has 7 categories, and loans (5,960) are commitments to
   lend, not grants. A grant element (OECD cash-flow) exists for only 2,895 records.

## 3. Currency

- AidData already provides AidData-converted constant-2021 USD. Compassio may display it **with
  attribution and the methodology note**. It must not re-derive conversions.
- ADB transactions have no per-value currency, but all 193 activities declare
  `default-currency="USD"`. A transaction with neither would be flagged and excluded; none exist.
- GCF and CFU USD are taken as stated by the headers ("$", "USD millions"). GCF project and
  readiness units are **assumptions**, because their headers state no unit.
- **No exchange-rate methodology is registered**, so no conversion is permitted.

## 4. What can legitimately support Compassio views

| View | Legitimate basis | Not permitted |
| --- | --- | --- |
| Project financial detail | The source's own field, with flow kind, unit and currency labels, and the estimate flag where present | Merging amounts across sources |
| Historical trend (Chinese development finance) | AidData constant-2021 USD commitments by commitment year, restricted to "Recommended For Aggregates" | Including pledges or cancelled records; calling commitments disbursements |
| Pakistan ADB pipeline | ADB commitments and disbursements by date, shown separately | Netting repayments; counting instruments as projects |
| GCF Pakistan portfolio | GCF country summary for the total; project rows for detail | Summing multi-country amounts into Pakistan |
| Allocation scenarios (future) | User-entered budgets, with historical amounts as *context only* | Treating historical amounts as returns or as available funding |

## 5. Data quality flags summary

| Flag | Count |
| --- | ---: |
| AidData/research rows with no amount | 8,186 |
| AidData amounts estimated | 1,408 |
| ADB negative transaction values | 37 |
| GCF readiness placeholder amounts (≤ 1) | 16 |
| GCF historical unparseable `Tot_Fin` | 5 |
| CFU whitespace-only disbursed cells | 52 |
| Multi-country GCF projects (full amount per row) | 96 |
