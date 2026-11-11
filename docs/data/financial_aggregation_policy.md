# Financial aggregation policy (Task 006 API)

This policy implements `docs/architecture/financial_data_contract.md`. Every total is computed by
`compassio_ml.finance.aggregate`, which raises on any unsafe combination. The API
(`compassio_api.services.finance`) adds the per-request rules below. When a total cannot be
computed safely, the response is **`unavailable` with a reason, never 0 and never a substitute
number**.

## 1. Rules and where they are enforced

| Rule | Enforcement |
| --- | --- |
| Missing amounts are not zero | `amount IS NULL` ⇔ `value_status ≠ reported` (DB CHECK); trends report `missing_value_records`; a year with only missing amounts is `unavailable` |
| Unknown currencies are not guessed | GCF `currency = NULL` (`not_stated_in_source`); trends exclude `currency_unknown_or_different` (counted); `gcf_financing` is always `unavailable` |
| No commitments + disbursements | Each metric has exactly one `flow_kind`; `aggregate` raises on mixed flow kinds |
| No cross-currency sums or conversion | Each metric has one currency; no exchange-rate code exists; constant 2021 USD is used only as AidData published it (DB CHECK: constant basis ⇒ USD, AidData only, verified by `compassio-db verify`) |
| Project-level totals are not added to transaction-level rows | Each metric has one `level`; ADB metrics are transaction-level, CFU and AidData project-level |
| Components are not added to totals | CFU instrument splits are `is_component = true` and are excluded from `cfu_approvals_usd` |
| Multi-country totals are not allocated to one country | Multi-country and regional observations are **excluded from every total** and counted as `multi_country_whole_project_value`. The country filter matches only explicitly mapped ISO3 countries. |
| GCF and CFU are not double counted | Metrics are single-source; no endpoint sums across sources. CFU rows citing a GCF code carry the warning `names_gcf_project` and an explicit link. |
| Repayments are never new funding | Repayments are their own flow kinds; `adb_principal_repayments_usd` has `is_funding: false` and its label says "inflow to ADB; NOT funding"; detail labels say "not funding" |
| Price bases are not mixed | Each metric has one `price_basis`; `aggregate` raises otherwise |
| Pledges are not commitments | AidData "Pipeline: Pledge" amounts have flow kind `pledge` and are excluded from the commitments metric |
| AidData double-count risk | The AidData metric includes only `recommended_for_aggregates = true`; the 3,028 others are excluded and counted |
| Contract violations | Stored as `invalid` (1 CFU negative disbursement) and excluded as `amount_invalid` |
| Estimates | `estimated_records` reported per year |

## 2. Units

- Source units are kept: CFU in millions, the others in units.
- Totals are expressed in **units of one currency** via `AmountUnit.scale`. For example, CFU
  1.5 USD millions is 1,500,000 USD.
- No other normalisation is applied.

## 3. Labels and limitations returned to the frontend

- **Every observation:**
  - `metric_label`, e.g. "Principal repayment (inflow to the lender; not funding)
    (transaction level)" or "…, instrument component of the stated total";
  - `date_meaning`, `unit`, `currency`, `unit_status`, `price_basis`.
- **Every metric:** `label`, `year_basis`, `is_funding`, `limitations[]`.
- **Every detail and trend response:** the five mandatory disclaimers (financial data contract
  §5).

## 4. What is deliberately not offered

- Cross-source or "all climate finance" totals.
- Pakistan shares of multi-country projects. The GCF country summary is the only source of a
  Pakistan GCF total, and that source is not ingested as project rows.
- `total_project_cost` as GCF financing plus co-financing.
- Currency conversion of AidData original-currency amounts.
- Any return, profit, impact or "funding opportunity" figure.
