"""Per-source inspection. Each inspector reads one source through ``SourceData`` and
returns observations only; units of observation are kept separate."""

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from compassio_ml.audit.loaders import SourceData
from compassio_ml.audit.models import (
    CoverageRow,
    FinancialField,
    IssueCategory,
    PakistanRow,
    QualityIssue,
    Severity,
    TableSchema,
    Year2026Row,
)
from compassio_ml.audit.profiling import (
    amounts,
    blank_mask,
    count_year,
    date_range,
    normalized_duplicates,
    parse_column,
    present_count,
    series_duplicates,
    table_schema,
)
from compassio_ml.data.parsing import (
    GCF_DATE_FORMATS,
    parse_date,
    parse_iso_datetime_date,
    parse_year,
    split_codes,
    split_country_list,
)
from compassio_ml.research.labels import parse_rio_marker

TARGET_YEAR = 2026
PAKISTAN_NAME = "Pakistan"


@dataclass
class SourceAudit:
    source_id: str
    primary_record_count: int
    schemas: list[TableSchema] = field(default_factory=list)
    coverage: list[CoverageRow] = field(default_factory=list)
    pakistan: list[PakistanRow] = field(default_factory=list)
    year2026: list[Year2026Row] = field(default_factory=list)
    financial: list[FinancialField] = field(default_factory=list)
    issues: list[QualityIssue] = field(default_factory=list)
    facts: dict[str, object] = field(default_factory=dict)

    def issue(
        self,
        issue_id: str,
        severity: Severity,
        category: IssueCategory,
        field_name: str,
        affected: int,
        description: str,
        recommendation: str,
    ) -> None:
        self.issues.append(
            QualityIssue(
                source_id=self.source_id,
                issue_id=issue_id,
                severity=severity,
                category=category,
                field=field_name,
                affected_records=affected,
                description=description,
                recommendation=recommendation,
            )
        )


def _sum_amounts(series: pd.Series) -> float:
    return float(sum(v for v in amounts(series).values if v is not None))


def _strip(series: pd.Series) -> pd.Series:
    return series.map(lambda v: v.strip() if isinstance(v, str) else v)


def _dup_id_rows(series: pd.Series) -> int:
    present = series[~blank_mask(series)]
    return int(present.duplicated(keep=False).sum())


def _fin(
    audit: SourceAudit,
    table: str,
    frame: pd.DataFrame,
    column: str,
    *,
    flow_kind: str,
    level: str,
    unit: str,
    currency: str,
    notes: str,
) -> list[float]:
    parsed = amounts(frame[column])
    audit.financial.append(
        FinancialField(
            source_id=audit.source_id,
            table=table,
            field=column,
            flow_kind=flow_kind,
            level=level,
            unit=unit,
            currency=currency,
            non_blank=parsed.present,
            parse_failures=parsed.failures,
            notes=notes,
        )
    )
    if parsed.failures:
        audit.issue(
            f"{table}_{re.sub(r'[^a-z0-9]+', '_', column.lower()).strip('_')}_unparseable",
            Severity.WARNING,
            IssueCategory.FINANCIAL,
            column,
            parsed.failures,
            f"Non-numeric values in amount field (examples: {list(parsed.failure_examples)})",
            "Treat as missing; do not coerce to zero.",
        )
    return [float(v) for v in parsed.values if v is not None]


# ------------------------------------------------------------------------ research paper
def inspect_research(data: SourceData) -> SourceAudit:
    cf = data.research_climate
    audit = SourceAudit("research_paper", primary_record_count=len(cf))
    unit = "AidData project/activity record"
    audit.schemas.append(table_schema(audit.source_id, "climate_workbook", unit, cf))

    labels = parse_column(cf["rio_marker"], parse_rio_marker)
    positive = [lab is not None and lab.is_climate_related for lab in labels.values]
    is_pk = _strip(cf["Recipient"]) == PAKISTAN_NAME
    years = parse_column(cf["Commitment_Year"], parse_year)
    earliest, latest = date_range(years.values)
    amount_present = present_count(cf["Amount_Constant_USD_2021"])

    audit.coverage.append(
        CoverageRow(
            source_id=audit.source_id,
            table="climate_workbook",
            unit_of_observation=unit,
            record_count=len(cf),
            distinct_id_count=int(cf["AidData_Record_ID"].nunique()),
            duplicate_id_rows=_dup_id_rows(cf["AidData_Record_ID"]),
            title_present=present_count(cf["Title"]),
            description_present=present_count(cf["Description"]),
            amount_present=amount_present,
            date_field="Commitment_Year",
            date_meaning="year of official commitment (AidData definition; may be proxied by "
            "first implementation year when unknown)",
            earliest=earliest,
            latest=latest,
            pakistan_records=int(is_pk.sum()),
            records_dated_2026=count_year(years.values, TARGET_YEAR),
            notes="Rows are a re-representation of AidData GCDF 3.0 records with a climate label",
        )
    )
    pk_positive = sum(p for p, k in zip(positive, is_pk.tolist(), strict=True) if k)
    audit.pakistan.append(
        PakistanRow(
            source_id=audit.source_id,
            table="climate_workbook",
            unit_of_observation=unit,
            filter_rule="Recipient == 'Pakistan'",
            records=int(is_pk.sum()),
            climate_flagged=pk_positive,
            notes="climate_flagged = rio_marker overall score > 0",
        )
    )
    audit.year2026.append(
        Year2026Row(
            source_id=audit.source_id,
            table="climate_workbook",
            date_field="Commitment_Year",
            date_meaning="commitment year",
            records=count_year(years.values, TARGET_YEAR),
            notes=f"Commitment years span {earliest}-{latest}",
        )
    )
    _fin(
        audit,
        "climate_workbook",
        cf,
        "Amount_Constant_USD_2021",
        flow_kind="commitment (or pledge) value",
        level="project/activity",
        unit="USD (units)",
        currency="constant 2021 USD (AidData conversion and OECD deflator)",
        notes="Equals AidData 'Amount (Constant USD 2021)' rounded to cents",
    )

    missing_labels = sum(v is None for v in labels.values)
    audit.facts.update(
        {
            "records": len(cf),
            "climate_positive": sum(positive),
            "climate_negative": len(cf) - sum(positive) - missing_labels,
            "label_missing_or_invalid": missing_labels,
            "pakistan_records": int(is_pk.sum()),
            "pakistan_climate_positive": pk_positive,
            "id_unique": bool(cf["ID"].is_unique),
            "aiddata_id_unique": bool(cf["AidData_Record_ID"].is_unique),
            "recipients": int(cf["Recipient"].nunique()),
            "pakistan_by_year": {
                str(y): [int(n), int(p)]
                for y, n, p in zip(
                    *_pk_year_counts(cf, is_pk, positive),
                    strict=True,
                )
            },
            "pakistan_positive_by_sector": {
                str(k): int(v)
                for k, v in cf[is_pk & pd.Series(positive, index=cf.index)]["Sector_Name"]
                .value_counts()
                .items()
            },
        }
    )
    if missing_labels:
        audit.issue(
            "research_rio_marker_missing_or_invalid",
            Severity.CRITICAL,
            IssueCategory.LABEL,
            "rio_marker",
            missing_labels,
            "rio_marker is blank or not three integer scores in 0-2",
            "Exclude from supervised training; report separately.",
        )

    for col in ("Implementation_Start_Year", "Completion_Year", "Grant_Element_OECD_Cash-Flow"):
        blanks = int(blank_mask(cf[col]).sum())
        if blanks:
            audit.issue(
                f"research_{col.lower().replace('-', '_')}_missing",
                Severity.INFO,
                IssueCategory.MISSING_VALUES,
                col,
                blanks,
                f"{col} blank in {blanks} of {len(cf)} rows",
                "Do not impute for modelling targets; may be used only as optional context.",
            )
    audit.issue(
        "research_amount_missing",
        Severity.WARNING,
        IssueCategory.FINANCIAL,
        "Amount_Constant_USD_2021",
        len(cf) - amount_present,
        "No commitment amount recorded (AidData has no monetary value for these records)",
        "Show as 'amount not reported'; never treat as zero in aggregates.",
    )

    desc_dups = normalized_duplicates(cf["Description"])
    title_dups = normalized_duplicates(cf["Title"])
    title_series = series_duplicates(cf["Title"])
    audit.facts.update(
        {
            "description_dup_rows": desc_dups.rows_in_duplicate_groups,
            "description_dup_groups": desc_dups.groups,
            "title_dup_rows": title_dups.rows_in_duplicate_groups,
            "title_dup_groups": title_dups.groups,
            "title_series_rows": title_series.rows_in_duplicate_groups,
            "title_series_groups": title_series.groups,
        }
    )
    audit.issue(
        "research_duplicate_descriptions",
        Severity.CRITICAL,
        IssueCategory.LEAKAGE,
        "Description",
        desc_dups.rows_in_duplicate_groups,
        f"{desc_dups.rows_in_duplicate_groups} rows share a normalized description with at least "
        f"one other row ({desc_dups.groups} groups)",
        "Group identical/near-identical descriptions into the same split fold.",
    )
    audit.issue(
        "research_duplicate_titles",
        Severity.WARNING,
        IssueCategory.DUPLICATES,
        "Title",
        title_dups.rows_in_duplicate_groups,
        f"{title_dups.rows_in_duplicate_groups} rows share a normalized title ({title_dups.groups} "
        f"groups); {title_series.rows_in_duplicate_groups} rows share a title once tranche/phase "
        f"numbers are removed ({title_series.groups} groups)",
        "Treat as related records (not necessarily duplicates); keep within one split fold.",
    )
    return audit


def _pk_year_counts(
    cf: pd.DataFrame, is_pk: pd.Series, positive: list[bool]
) -> tuple[list[str], list[int], list[int]]:
    sub = cf.assign(_pos=positive)[is_pk.tolist()]
    grouped = sub.groupby("Commitment_Year")["_pos"].agg(["size", "sum"]).sort_index()
    return (
        [str(i) for i in grouped.index],
        [int(v) for v in grouped["size"]],
        [int(v) for v in grouped["sum"]],
    )


# ------------------------------------------------------------------------ AidData
_AIDDATA_DATE_FIELDS = (
    ("Commitment Date (MM/DD/YYYY)", "official commitment date (signing)"),
    ("Actual Implementation Start Date (MM/DD/YYYY)", "actual implementation start"),
    ("Planned Completion Date (MM/DD/YYYY)", "planned completion (forecast)"),
    ("Actual Completion Date (MM/DD/YYYY)", "actual completion"),
    ("First Loan Repayment Date", "scheduled first repayment (contractual, future dates allowed)"),
    ("Last Loan Repayment Date", "scheduled last repayment (contractual, future dates allowed)"),
)


def inspect_aiddata(data: SourceData) -> SourceAudit:
    ad = data.aiddata
    audit = SourceAudit("aiddata", primary_record_count=len(ad))
    unit = "project/activity commitment record"
    audit.schemas.append(table_schema(audit.source_id, "GCDF_3.0", unit, ad))
    is_pk = _strip(ad["Recipient ISO-3"]) == "PAK"
    years = parse_column(ad["Commitment Year"], parse_year)
    earliest, latest = date_range(years.values)
    recommended = _strip(ad["Recommended For Aggregates"]) == "Yes"

    audit.coverage.append(
        CoverageRow(
            source_id=audit.source_id,
            table="GCDF_3.0",
            unit_of_observation=unit,
            record_count=len(ad),
            distinct_id_count=int(ad["AidData Record ID"].nunique()),
            duplicate_id_rows=_dup_id_rows(ad["AidData Record ID"]),
            title_present=present_count(ad["Title"]),
            description_present=present_count(ad["Description"]),
            amount_present=present_count(ad["Amount (Original Currency)"]),
            date_field="Commitment Year",
            date_meaning="year of official commitment",
            earliest=earliest,
            latest=latest,
            pakistan_records=int(is_pk.sum()),
            records_dated_2026=count_year(years.values, TARGET_YEAR),
            notes=f"{int(recommended.sum())} rows 'Recommended For Aggregates' = Yes",
        )
    )
    pk_constant = amounts(ad["Amount (Constant USD 2021)"])
    audit.facts["pakistan_recommended_commitments_constant_usd_2021"] = {
        "records_with_amount": sum(
            1
            for v, k, r in zip(pk_constant.values, is_pk, recommended, strict=True)
            if k and r and v is not None
        ),
        "sum": float(
            sum(
                v
                for v, k, r in zip(pk_constant.values, is_pk, recommended, strict=True)
                if k and r and v is not None
            )
        ),
        "note": "Commitments only; Recommended For Aggregates == Yes; not disbursements",
    }
    audit.pakistan.append(
        PakistanRow(
            source_id=audit.source_id,
            table="GCDF_3.0",
            unit_of_observation=unit,
            filter_rule="Recipient ISO-3 == 'PAK'",
            records=int(is_pk.sum()),
            climate_flagged=None,
            notes=f"{int((is_pk & recommended).sum())} of these are Recommended For Aggregates",
        )
    )
    for col, meaning in _AIDDATA_DATE_FIELDS:
        parsed = parse_column(ad[col], parse_iso_datetime_date)
        lo, hi = date_range(parsed.values)
        audit.facts[f"date_range::{col}"] = [lo, hi, parsed.present]
        n2026 = count_year(parsed.values, TARGET_YEAR)
        if n2026:
            audit.year2026.append(
                Year2026Row(
                    source_id=audit.source_id,
                    table="GCDF_3.0",
                    date_field=col,
                    date_meaning=meaning,
                    records=n2026,
                    notes="Planned/scheduled dates, not 2026 projects",
                )
            )
        if parsed.failures:
            audit.issue(
                f"aiddata_{re.sub(r'[^a-z0-9]+', '_', col.lower()).strip('_')}_unparseable",
                Severity.WARNING,
                IssueCategory.DATE,
                col,
                parsed.failures,
                f"Unparseable dates (examples {list(parsed.failure_examples)})",
                "Treat as missing.",
            )
    audit.year2026.append(
        Year2026Row(
            source_id=audit.source_id,
            table="GCDF_3.0",
            date_field="Commitment Year",
            date_meaning="commitment year",
            records=count_year(years.values, TARGET_YEAR),
            notes=f"Commitment years span {earliest}-{latest}; dataset released 2023-11-07",
        )
    )

    currency_missing = int(
        (~blank_mask(ad["Amount (Original Currency)"]) & blank_mask(ad["Original Currency"])).sum()
    )
    audit.facts["amount_without_currency"] = currency_missing
    if currency_missing:
        audit.issue(
            "aiddata_amount_without_currency",
            Severity.CRITICAL,
            IssueCategory.FINANCIAL,
            "Original Currency",
            currency_missing,
            "Original-currency amount present but currency code blank",
            "Exclude from any original-currency view.",
        )
    for col, kind, ccy in (
        ("Amount (Original Currency)", "commitment (or pledge)", "see 'Original Currency'"),
        ("Amount (Constant USD 2021)", "commitment (or pledge)", "constant 2021 USD"),
        ("Amount (Nominal USD)", "commitment (or pledge)", "nominal USD, commitment-year rate"),
        ("Adjusted Amount (Original Currency)", "adjusted commitment", "see 'Original Currency'"),
        ("Adjusted Amount (Constant USD 2021)", "adjusted commitment", "constant 2021 USD"),
        ("Adjusted Amount (Nominal USD)", "adjusted commitment", "nominal USD"),
    ):
        _fin(
            audit,
            "GCDF_3.0",
            ad,
            col,
            flow_kind=kind,
            level="project/activity",
            unit="units",
            currency=ccy,
            notes="Commitment value, not disbursement or repayment",
        )
    estimated = int((_strip(ad["Amount Estimated"]) == "Yes").sum())
    audit.issue(
        "aiddata_amount_estimated",
        Severity.INFO,
        IssueCategory.FINANCIAL,
        "Amount Estimated",
        estimated,
        "Commitment amount estimated by AidData rather than taken from official documents",
        "Surface the estimate flag wherever amounts are shown.",
    )
    not_recommended = int((~recommended).sum())
    audit.issue(
        "aiddata_not_recommended_for_aggregates",
        Severity.WARNING,
        IssueCategory.DUPLICATES,
        "Recommended For Aggregates",
        not_recommended,
        "Records AidData advises excluding from counts and sums (pledges, cancelled, suspended, "
        "umbrella and other potentially double-counted records)",
        "Exclude from funding totals; keep for text classification only with justification.",
    )
    parents = ad["AidData Parent ID"][~blank_mask(ad["AidData Parent ID"])]
    parent_counts = parents.value_counts()
    linked_rows = int(parent_counts[parent_counts > 1].sum())
    audit.facts.update(
        {
            "parent_id_present": len(parents),
            "parent_groups_multi": int((parent_counts > 1).sum()),
            "rows_in_multi_record_packages": linked_rows,
            "recommended_for_aggregates": int(recommended.sum()),
            "umbrella_yes": int((_strip(ad["Umbrella"]) == "Yes").sum()),
            "commitment_date_estimated_yes": int(
                (_strip(ad["Commitment Date Estimated"]) == "Yes").sum()
            ),
            "status": {str(k): int(v) for k, v in ad["Status"].value_counts().items()},
            "flow_type": {str(k): int(v) for k, v in ad["Flow Type"].value_counts().items()},
            "original_currencies": int(ad["Original Currency"].nunique()),
            "sheets": data.aiddata_sheets,
        }
    )
    audit.issue(
        "aiddata_linked_packages",
        Severity.WARNING,
        IssueCategory.LEAKAGE,
        "AidData Parent ID",
        linked_rows,
        f"{linked_rows} records belong to {int((parent_counts > 1).sum())} linked packages "
        "(same Parent ID) that describe related transactions",
        "Use Parent ID as a grouping key so related records never straddle train/test.",
    )
    audit.issue(
        "aiddata_retrospective_descriptions",
        Severity.CRITICAL,
        IssueCategory.LEAKAGE,
        "Description",
        present_count(ad["Description"]),
        "AidData defines Description as including implementation timing, challenges, "
        "achievements and shortcomings: text was written after commitment",
        "Do not claim point-in-time availability; chronological evaluation tests year shift, "
        "not real-time forecasting.",
    )
    return audit


# ------------------------------------------------------------------------ ADB IATI
IATI_TRANSACTION_TYPES = {
    "1": "Incoming Funds",
    "2": "Outgoing Commitment",
    "3": "Disbursement",
    "4": "Expenditure",
    "5": "Interest Payment",
    "6": "Loan Repayment",
    "7": "Reimbursement",
    "8": "Purchase of Equity",
    "9": "Sale of Equity",
    "10": "Credit Guarantee",
    "11": "Incoming Commitment",
    "12": "Outgoing Pledge",
    "13": "Incoming Pledge",
}
IATI_ACTIVITY_STATUS = {
    "1": "Pipeline/identification",
    "2": "Implementation",
    "3": "Finalisation",
    "4": "Closed",
    "5": "Cancelled",
    "6": "Suspended",
}
_ADB_PROJECT = re.compile(r"^XM-DAC-46004-(\d+-\d+)-")


def adb_project_number(identifier: str | None) -> str | None:
    if identifier is None:
        return None
    match = _ADB_PROJECT.match(identifier)
    return match.group(1) if match else None


def inspect_adb(data: SourceData) -> SourceAudit:
    adb = data.adb
    acts, txs = adb.activities, adb.transactions
    audit = SourceAudit("adb_pakistan", primary_record_count=len(acts))
    audit.schemas.append(table_schema(audit.source_id, "activities", "IATI activity", acts))
    audit.schemas.append(table_schema(audit.source_id, "transactions", "IATI transaction", txs))
    audit.schemas.append(
        table_schema(
            audit.source_id, "policy_markers", "activity policy marker", adb.policy_markers
        )
    )
    audit.schemas.append(table_schema(audit.source_id, "sectors", "activity sector", adb.sectors))

    projects = acts["iati_identifier"].map(adb_project_number)
    is_pk = acts["recipient_countries"].map(lambda v: "PK" in str(v).split("|"))
    starts = parse_column(acts["actual_start"], parse_iso_datetime_date)
    lo, hi = date_range(starts.values)
    audit.coverage.append(
        CoverageRow(
            source_id=audit.source_id,
            table="activities",
            unit_of_observation="IATI activity (one ADB loan or grant instrument)",
            record_count=len(acts),
            distinct_id_count=int(acts["iati_identifier"].nunique()),
            duplicate_id_rows=_dup_id_rows(acts["iati_identifier"]),
            title_present=present_count(acts["title"]),
            description_present=present_count(acts["description"]),
            amount_present=None,
            date_field="actual_start (activity-date type 2)",
            date_meaning="actual start of the financing instrument",
            earliest=lo,
            latest=hi,
            pakistan_records=int(is_pk.sum()),
            records_dated_2026=count_year(starts.values, TARGET_YEAR),
            notes=f"{projects.nunique()} distinct ADB project numbers; "
            f"{acts['title'].nunique()} distinct titles",
        )
    )
    tx_dates = parse_column(txs["transaction_date"], parse_iso_datetime_date)
    tlo, thi = date_range(tx_dates.values)
    audit.coverage.append(
        CoverageRow(
            source_id=audit.source_id,
            table="transactions",
            unit_of_observation="IATI transaction (commitment, disbursement, repayment...)",
            record_count=len(txs),
            distinct_id_count=None,
            duplicate_id_rows=None,
            title_present=None,
            description_present=None,
            amount_present=present_count(txs["value"]),
            date_field="transaction-date",
            date_meaning="date of the financial transaction",
            earliest=tlo,
            latest=thi,
            pakistan_records=len(txs),
            records_dated_2026=count_year(tx_dates.values, TARGET_YEAR),
            notes="Transactions are NOT projects; most are repayments",
        )
    )
    audit.pakistan.append(
        PakistanRow(
            source_id=audit.source_id,
            table="activities",
            unit_of_observation="IATI activity",
            filter_rule="recipient-country code == 'PK'",
            records=int(is_pk.sum()),
            climate_flagged=None,
            notes=f"Grouped under {projects.nunique()} ADB project numbers",
        )
    )

    for code, label, meaning in (
        ("1", "planned_start", "planned start"),
        ("2", "actual_start", "actual start"),
        ("3", "planned_end", "planned end (forecast)"),
        ("4", "actual_end", "actual end"),
    ):
        parsed = parse_column(acts[label], parse_iso_datetime_date)
        audit.facts[f"activity_date::{label}"] = [*date_range(parsed.values), parsed.present]
        audit.year2026.append(
            Year2026Row(
                source_id=audit.source_id,
                table="activities",
                date_field=f"activity-date type {code} ({label})",
                date_meaning=meaning,
                records=count_year(parsed.values, TARGET_YEAR),
                notes="Activities (instruments), not distinct projects",
            )
        )

    tx_types = txs["transaction_type"].map(lambda c: IATI_TRANSACTION_TYPES.get(str(c), "UNKNOWN"))
    unknown_tx = int((tx_types == "UNKNOWN").sum())
    if unknown_tx:
        audit.issue(
            "adb_unknown_transaction_type",
            Severity.CRITICAL,
            IssueCategory.FINANCIAL,
            "transaction-type",
            unknown_tx,
            "Transaction type code not in the IATI TransactionType codelist",
            "Exclude from every financial view until mapped.",
        )
    effective_ccy = txs["value_currency"].where(
        ~blank_mask(txs["value_currency"]), txs["default_currency"]
    )
    missing_ccy = int(blank_mask(effective_ccy).sum())
    if missing_ccy:
        audit.issue(
            "adb_transaction_missing_currency",
            Severity.CRITICAL,
            IssueCategory.FINANCIAL,
            "value/@currency",
            missing_ccy,
            "Transaction has no currency and its activity has no default-currency",
            "Exclude; never assume USD.",
        )
    values = amounts(txs["value"])
    by_type: dict[str, dict[str, object]] = {}
    for code in sorted(txs["transaction_type"].dropna().unique(), key=lambda c: int(str(c))):
        mask = (txs["transaction_type"] == code).tolist()
        vals = [v for v, m in zip(values.values, mask, strict=True) if m and v is not None]
        dates = [d for d, m in zip(tx_dates.values, mask, strict=True) if m]
        by_type[f"{code} {IATI_TRANSACTION_TYPES.get(str(code), 'UNKNOWN')}"] = {
            "count": sum(mask),
            "negative_values": sum(v < 0 for v in vals),
            "sum_usd_within_type": float(sum(vals)),
            "dated_2026": count_year(dates, TARGET_YEAR),
            "earliest": date_range(dates)[0],
            "latest": date_range(dates)[1],
        }
        audit.year2026.append(
            Year2026Row(
                source_id=audit.source_id,
                table="transactions",
                date_field="transaction-date",
                date_meaning=f"type {code} {IATI_TRANSACTION_TYPES.get(str(code), 'UNKNOWN')}",
                records=count_year(dates, TARGET_YEAR),
                notes="Transaction events in 2026, not new projects",
            )
        )
    audit.facts["transactions_by_type"] = by_type
    committed = set(txs.loc[txs["transaction_type"] == "2", "iati_identifier"])
    commitment_counts = txs.loc[txs["transaction_type"] == "2", "iati_identifier"].value_counts()
    audit.facts["activities_without_commitment"] = sorted(
        str(i) for i in acts["iati_identifier"] if i not in committed
    )
    audit.facts["activities_with_multiple_commitments"] = int((commitment_counts > 1).sum())
    audit.facts["activities_actual_start_2026"] = sorted(
        str(i)
        for i, d in zip(acts["iati_identifier"], starts.values, strict=True)
        if d is not None and d.year == TARGET_YEAR
    )
    audit.facts["commitment_transactions_2026"] = sorted(
        str(i)
        for i, t, d in zip(
            txs["iati_identifier"], txs["transaction_type"], tx_dates.values, strict=True
        )
        if t == "2" and d is not None and d.year == TARGET_YEAR
    )
    for code, kind in (
        ("2", "commitment"),
        ("3", "disbursement"),
        ("5", "interest repayment (inflow to ADB)"),
        ("6", "principal repayment (inflow to ADB)"),
    ):
        sub = txs[txs["transaction_type"] == code]
        _fin(
            audit,
            "transactions",
            sub.reset_index(drop=True),
            "value",
            flow_kind=kind,
            level="transaction",
            unit="units",
            currency="USD via activity default-currency",
            notes=f"IATI transaction type {code}",
        )
        audit.financial[-1] = audit.financial[-1].model_copy(
            update={"field": f"value[type={code}]"}
        )
    negatives = sum(1 for v in values.values if v is not None and v < 0)
    audit.issue(
        "adb_negative_transaction_values",
        Severity.WARNING,
        IssueCategory.FINANCIAL,
        "transaction/value",
        negatives,
        "Negative transaction values (reversals/cancellations) - see transactions_by_type",
        "Keep sign; never net across transaction types.",
    )
    audit.issue(
        "adb_repayments_dominate_transactions",
        Severity.WARNING,
        IssueCategory.UNIT_OF_OBSERVATION,
        "transaction-type",
        int(txs["transaction_type"].isin(["5", "6"]).sum()),
        "Most transactions are interest/principal repayments, which are not new funding",
        "Report commitments, disbursements and repayments separately.",
    )

    title_dups = normalized_duplicates(acts["title"])
    audit.facts.update(
        {
            "project_numbers": int(projects.nunique()),
            "activities_without_project_number": int(projects.isna().sum()),
            "title_dup_rows": title_dups.rows_in_duplicate_groups,
            "title_dup_groups": title_dups.groups,
            "activity_status": {
                f"{k} {IATI_ACTIVITY_STATUS.get(str(k), 'UNKNOWN')}": int(v)
                for k, v in acts["activity_status"].value_counts().items()
            },
            "generated_datetime": adb.generated_datetime,
            "iati_version": adb.iati_version,
            "policy_marker_vocabularies": sorted(
                str(v) for v in adb.policy_markers["vocabulary"].dropna().unique()
            ),
            "policy_marker_significance_present": present_count(adb.policy_markers["significance"]),
            "climate_policy_marker_activities": int(
                adb.policy_markers.loc[
                    adb.policy_markers["code"].fillna("").str.lower().str.contains("climate"),
                    "iati_identifier",
                ].nunique()
            ),
        }
    )
    audit.issue(
        "adb_shared_titles_across_instruments",
        Severity.WARNING,
        IssueCategory.UNIT_OF_OBSERVATION,
        "title",
        title_dups.rows_in_duplicate_groups,
        f"{title_dups.rows_in_duplicate_groups} activities share a title with another activity "
        f"({title_dups.groups} groups): several loans/grants finance one project",
        "Count projects by ADB project number, instruments by IATI identifier.",
    )
    audit.issue(
        "adb_policy_markers_not_rio",
        Severity.WARNING,
        IssueCategory.LABEL,
        "policy-marker",
        len(adb.policy_markers),
        "Policy markers use vocabulary 99 (ADB operational priorities) with no significance; "
        "they are not OECD Rio climate markers",
        "Never map to the research climate label without an explicit, reviewed crosswalk.",
    )
    return audit


# ------------------------------------------------------------------------ GCF
def inspect_gcf_projects(data: SourceData) -> SourceAudit:
    gp = data.gcf_projects
    audit = SourceAudit("gcf_projects", primary_record_count=len(gp))
    unit = "GCF funded project (FP/SAP)"
    audit.schemas.append(table_schema(audit.source_id, "Sheet 1", unit, gp))
    countries = gp["Countries"].map(split_country_list)
    is_pk = countries.map(lambda cs: PAKISTAN_NAME in cs)
    single = countries.map(len) == 1
    audit.coverage.append(
        CoverageRow(
            source_id=audit.source_id,
            table="Sheet 1",
            unit_of_observation=unit,
            record_count=len(gp),
            distinct_id_count=int(gp["Ref #"].nunique()),
            duplicate_id_rows=_dup_id_rows(gp["Ref #"]),
            title_present=present_count(gp["Project Name"]),
            description_present=0,
            amount_present=present_count(gp["FA Financing"]),
            date_field="BM (board meeting code)",
            date_meaning="board meeting that approved the project; no calendar date in file",
            earliest=None,
            latest=None,
            pakistan_records=int(is_pk.sum()),
            records_dated_2026=None,
            notes=f"{int((countries.map(len) > 1).sum())} multi-country projects; no descriptions",
        )
    )
    audit.pakistan.append(
        PakistanRow(
            source_id=audit.source_id,
            table="Sheet 1",
            unit_of_observation=unit,
            filter_rule="'Pakistan' in comma-separated Countries",
            records=int(is_pk.sum()),
            climate_flagged=int(is_pk.sum()),
            notes=f"{int((is_pk & single).sum())} single-country, {int((is_pk & ~single).sum())} "
            "multi-country; all GCF projects are climate-dedicated by mandate",
        )
    )
    audit.year2026.append(
        Year2026Row(
            source_id=audit.source_id,
            table="Sheet 1",
            date_field="BM",
            date_meaning="board meeting code",
            records=None,
            notes="Cannot be determined from the file: no approval dates; board-meeting dates "
            "would need a separately registered GCF reference",
        )
    )
    _fin(
        audit,
        "Sheet 1",
        gp,
        "FA Financing",
        flow_kind="GCF approved funding (assumed)",
        level="project (full amount, including multi-country projects)",
        unit="units (assumed)",
        currency="USD (assumed; not stated)",
        notes="Not total project cost; excludes co-finance",
    )
    pk = gp[is_pk.tolist()]
    audit.facts.update(
        {
            "theme": {str(k): int(v) for k, v in gp["Theme"].value_counts().items()},
            "modality": {str(k): int(v) for k, v in gp["Modality"].value_counts().items()},
            "board_meetings": sorted(gp["BM"].dropna().unique(), key=lambda b: float(b[2:])),
            "pakistan_refs": sorted(pk["Ref #"].tolist()),
            "pakistan_single_country_refs": sorted(gp[(is_pk & single).tolist()]["Ref #"].tolist()),
            "pakistan_fa_financing": {
                "single_country_sum": _sum_amounts(gp[(is_pk & single).tolist()]["FA Financing"]),
                "multi_country_full_amount_sum": _sum_amounts(
                    gp[(is_pk & ~single).tolist()]["FA Financing"]
                ),
                "note": "Multi-country amounts are whole-project, not Pakistan's share",
            },
        }
    )
    audit.issue(
        "gcf_projects_no_dates_or_descriptions",
        Severity.WARNING,
        IssueCategory.SCHEMA,
        "BM",
        len(gp),
        "Export has no approval date and no project description",
        "Use board-meeting code only as an ordinal; obtain dated records before trend views.",
    )
    audit.issue(
        "gcf_projects_multicountry_amounts",
        Severity.WARNING,
        IssueCategory.FINANCIAL,
        "FA Financing",
        int((countries.map(len) > 1).sum()),
        "Multi-country projects carry the full amount; per-country share is not in this export",
        "Never attribute a multi-country amount wholly to one country.",
    )
    audit.issue(
        "gcf_exports_rewritten_by_openpyxl",
        Severity.WARNING,
        IssueCategory.PROVENANCE,
        "(file)",
        len(gp),
        "Workbook core properties show creator 'openpyxl'; all cells stored as text",
        "Confirm the download origin; record the GCF ODL URL used.",
    )
    return audit


def inspect_gcf_readiness(data: SourceData) -> SourceAudit:
    gr = data.gcf_readiness
    audit = SourceAudit("gcf_readiness", primary_record_count=len(gr))
    unit = "readiness grant/activity row"
    audit.schemas.append(table_schema(audit.source_id, "Sheet 1", unit, gr))
    dates = parse_column(gr["Approved Date"], lambda v: parse_date(v, GCF_DATE_FORMATS))
    lo, hi = date_range(dates.values)
    is_pk = _strip(gr["Country"]) == PAKISTAN_NAME
    audit.coverage.append(
        CoverageRow(
            source_id=audit.source_id,
            table="Sheet 1",
            unit_of_observation=unit,
            record_count=len(gr),
            distinct_id_count=int(gr["Ref #"].nunique()),
            duplicate_id_rows=_dup_id_rows(gr["Ref #"]),
            title_present=present_count(gr["Project Title"]),
            description_present=present_count(gr["Activity"]),
            amount_present=present_count(gr["Financing"]),
            date_field="Approved Date",
            date_meaning="approval date of the readiness grant",
            earliest=lo,
            latest=hi,
            pakistan_records=int(is_pk.sum()),
            records_dated_2026=count_year(dates.values, TARGET_YEAR),
            notes="'Activity' is a category, not a description",
        )
    )
    audit.pakistan.append(
        PakistanRow(
            source_id=audit.source_id,
            table="Sheet 1",
            unit_of_observation=unit,
            filter_rule="Country == 'Pakistan'",
            records=int(is_pk.sum()),
            climate_flagged=None,
            notes="Readiness/capacity support, not investment projects",
        )
    )
    audit.year2026.append(
        Year2026Row(
            source_id=audit.source_id,
            table="Sheet 1",
            date_field="Approved Date",
            date_meaning="approval date",
            records=count_year(dates.values, TARGET_YEAR),
            notes=f"Approvals span {lo} to {hi}",
        )
    )
    fin = _fin(
        audit,
        "Sheet 1",
        gr,
        "Financing",
        flow_kind="readiness grant approved (assumed)",
        level="readiness grant",
        unit="units (assumed)",
        currency="USD (assumed; not stated)",
        notes="Readiness finance; never add to funded-project totals",
    )
    placeholder = sum(1 for v in fin if v <= 1)
    dup_ref = _dup_id_rows(gr["Ref #"])
    audit.facts.update(
        {
            "status": {str(k): int(v) for k, v in gr["Status"].value_counts().items()},
            "placeholder_financing_le_1": placeholder,
            "ref_blank": int(blank_mask(gr["Ref #"]).sum()),
            "ref_duplicate_rows": dup_ref,
            "ref_top_duplicates": {
                str(k): int(v) for k, v in gr["Ref #"].value_counts().head(4).items() if v > 1
            },
        }
    )
    audit.issue(
        "gcf_readiness_ref_not_unique",
        Severity.WARNING,
        IssueCategory.DUPLICATES,
        "Ref #",
        dup_ref,
        "Ref # repeats (e.g. 'PwC' used for many country rows) and is blank in some rows",
        "Do not use Ref # alone as a key; use (Ref #, Country, Project Title, Approved Date).",
    )
    audit.issue(
        "gcf_readiness_placeholder_amounts",
        Severity.WARNING,
        IssueCategory.FINANCIAL,
        "Financing",
        placeholder,
        "Financing <= 1 (observed on cancelled grants): placeholder, not an amount",
        "Treat Financing <= 1 as missing.",
    )
    return audit


def inspect_gcf_countries(data: SourceData) -> SourceAudit:
    gc = data.gcf_countries
    audit = SourceAudit("gcf_countries", primary_record_count=len(gc))
    unit = "country (aggregate)"
    audit.schemas.append(table_schema(audit.source_id, "Sheet 1", unit, gc))
    pk = gc[_strip(gc["ISO3"]) == "PAK"]
    audit.coverage.append(
        CoverageRow(
            source_id=audit.source_id,
            table="Sheet 1",
            unit_of_observation=unit,
            record_count=len(gc),
            distinct_id_count=int(gc["ISO3"].nunique()),
            duplicate_id_rows=_dup_id_rows(gc["ISO3"]),
            title_present=None,
            description_present=None,
            amount_present=present_count(gc["FA Financing $"]),
            date_field="(none)",
            date_meaning="snapshot at export time; no as-of date in file",
            earliest=None,
            latest=None,
            pakistan_records=len(pk),
            records_dated_2026=None,
            notes="Aggregates; not project records",
        )
    )
    pk_row = pk.iloc[0].to_dict() if len(pk) == 1 else {}
    audit.pakistan.append(
        PakistanRow(
            source_id=audit.source_id,
            table="Sheet 1",
            unit_of_observation=unit,
            filter_rule="ISO3 == 'PAK'",
            records=len(pk),
            climate_flagged=None,
            notes="; ".join(f"{k}={v}" for k, v in pk_row.items() if k not in {"ISO3"}),
        )
    )
    for col, kind in (
        ("RP Financing $", "readiness programme"),
        ("FA Financing $", "funded activities"),
    ):
        _fin(
            audit,
            "Sheet 1",
            gc,
            col,
            flow_kind=f"{kind} (aggregate)",
            level="country aggregate",
            unit="units",
            currency="USD (header '$')",
            notes="Country share; never sum with project-level amounts",
        )
    audit.facts["pakistan"] = pk_row
    return audit


def inspect_gcf_historical(data: SourceData) -> SourceAudit:
    gh = data.gcf_historical
    gh = gh[~blank_mask(gh["Ref_N"])].reset_index(drop=True)
    audit = SourceAudit("gcf_historical", primary_record_count=len(gh))
    unit = "GCF funded project with co-financing breakdown"
    audit.schemas.append(table_schema(audit.source_id, "Portfolio", unit, gh))
    audit.coverage.append(
        CoverageRow(
            source_id=audit.source_id,
            table="Portfolio",
            unit_of_observation=unit,
            record_count=len(gh),
            distinct_id_count=int(gh["Ref_N"].nunique()),
            duplicate_id_rows=_dup_id_rows(gh["Ref_N"]),
            title_present=None,
            description_present=None,
            amount_present=present_count(gh["Tot_Fin"]),
            date_field="(none)",
            date_meaning="no approval date column despite 'TO READ' documentation",
            earliest=None,
            latest=None,
            pakistan_records=None,
            records_dated_2026=None,
            notes="Workbook last modified 2020-03-26; no country column (continent only)",
        )
    )
    audit.pakistan.append(
        PakistanRow(
            source_id=audit.source_id,
            table="Portfolio",
            unit_of_observation=unit,
            filter_rule="(no country field) - only via Ref_N join to gcf_projects",
            records=0,
            climate_flagged=None,
            notes="See cross_source_overlap for Ref_N matches to Pakistan GCF projects",
        )
    )
    _fin(
        audit,
        "Portfolio",
        gh,
        "Tot_Fin",
        flow_kind="total project financing incl. co-finance",
        level="project",
        unit="USD thousands ('TO READ' sheet)",
        currency="USD",
        notes="Total cost basis, not GCF funding alone",
    )
    dup_cols = data.gcf_historical_header_raw
    audit.facts.update(
        {
            "duplicate_header_columns": dup_cols,
            "theme": {str(k): int(v) for k, v in gh["Theme"].value_counts().items()},
            "ref_range": [str(gh["Ref_N"].iloc[0]), str(gh["Ref_N"].iloc[-1])],
        }
    )
    audit.issue(
        "gcf_historical_duplicate_headers",
        Severity.WARNING,
        IssueCategory.SCHEMA,
        ", ".join(dup_cols),
        len(gh),
        f"Portfolio sheet repeats column names ({len(dup_cols)} duplicates)",
        "Disambiguate by position before any use; meaning of each copy is undocumented.",
    )
    audit.issue(
        "gcf_historical_missing_documented_columns",
        Severity.WARNING,
        IssueCategory.SCHEMA,
        "Project Name, Date of Approval, Country",
        len(gh),
        "'TO READ' describes columns that are not present in the Portfolio sheet",
        "Join to gcf_projects by Ref_N for names/countries; dates remain unavailable.",
    )
    return audit


# ------------------------------------------------------------------------ CFU
def inspect_cfu(data: SourceData) -> SourceAudit:
    sheets = data.cfu
    projects = sheets["Projects"]
    audit = SourceAudit("climate_funds_update", primary_record_count=len(projects))
    units = {
        "Projects": "fund-approved project",
        "Pledges": "contributor pledge to a fund",
        "Fund Status": "fund (aggregate)",
    }
    for name, frame in sheets.items():
        audit.schemas.append(table_schema(audit.source_id, name, units.get(name, "?"), frame))
    years = parse_column(projects["Approved year"], parse_year)
    lo, hi = date_range(years.values)
    is_pk = _strip(projects["Country"]) == PAKISTAN_NAME
    south_asia_regional = (
        projects["Country"].fillna("").str.contains("South Asia", case=False) & ~is_pk
    )
    amount_col = next(c for c in projects.columns if c.startswith("Amount of Funding Approved"))
    disb_col = next(c for c in projects.columns if "Disbursed" in c)
    audit.coverage.append(
        CoverageRow(
            source_id=audit.source_id,
            table="Projects",
            unit_of_observation=units["Projects"],
            record_count=len(projects),
            distinct_id_count=None,
            duplicate_id_rows=None,
            title_present=present_count(projects["Name of Project"]),
            description_present=present_count(projects["Summary"]),
            amount_present=present_count(projects[amount_col]),
            date_field="Approved year",
            date_meaning="year the fund approved the project",
            earliest=lo,
            latest=hi,
            pakistan_records=int(is_pk.sum()),
            records_dated_2026=count_year(years.values, TARGET_YEAR),
            notes="No stable project identifier column",
        )
    )
    for name in ("Pledges", "Fund Status"):
        audit.coverage.append(
            CoverageRow(
                source_id=audit.source_id,
                table=name,
                unit_of_observation=units[name],
                record_count=len(sheets[name]),
                distinct_id_count=None,
                duplicate_id_rows=None,
                title_present=None,
                description_present=None,
                amount_present=None,
                date_field="(none)",
                date_meaning="cumulative snapshot",
                earliest=None,
                latest=None,
                pakistan_records=None,
                records_dated_2026=None,
                notes="Fund-level; not project records",
            )
        )
    audit.pakistan.append(
        PakistanRow(
            source_id=audit.source_id,
            table="Projects",
            unit_of_observation=units["Projects"],
            filter_rule="Country == 'Pakistan'",
            records=int(is_pk.sum()),
            climate_flagged=int(is_pk.sum()),
            notes=f"Excludes {int(south_asia_regional.sum())} regional 'South Asia' rows that may "
            "include Pakistan; all CFU projects are from dedicated climate funds",
        )
    )
    audit.year2026.append(
        Year2026Row(
            source_id=audit.source_id,
            table="Projects",
            date_field="Approved year",
            date_meaning="approval year",
            records=count_year(years.values, TARGET_YEAR),
            notes=f"Approval years span {lo}-{hi}",
        )
    )
    _fin(
        audit,
        "Projects",
        projects,
        amount_col,
        flow_kind="approval",
        level="project",
        unit="USD millions",
        currency="USD (current, per header)",
        notes="Approved amount",
    )
    _fin(
        audit,
        "Projects",
        projects,
        disb_col,
        flow_kind="disbursement (cumulative)",
        level="project",
        unit="USD millions",
        currency="USD",
        notes="Cumulative disbursed; blank != 0",
    )
    for col in ("Concessional loan", "Grant", "Guarantee", "Equity"):
        _fin(
            audit,
            "Projects",
            projects,
            col,
            flow_kind=f"approval by instrument: {col.lower()}",
            level="project",
            unit="USD millions",
            currency="USD",
            notes="Instrument split of the approved amount",
        )
    pledges = sheets["Pledges"]
    for col in pledges.columns:
        if "Pledged" in col or "Deposited" in col:
            _fin(
                audit,
                "Pledges",
                pledges,
                col,
                flow_kind="pledge" if "Pledged" in col else "deposit",
                level="contributor-to-fund",
                unit="USD millions",
                currency="USD current",
                notes="Money into funds, not to projects",
            )
    fs = sheets["Fund Status"]
    for col in fs.columns:
        if "USD mn" in col:
            _fin(
                audit,
                "Fund Status",
                fs,
                col,
                flow_kind=col.split(" (")[0].lower(),
                level="fund aggregate",
                unit="USD millions",
                currency="USD",
                notes="Fund-level cumulative",
            )
    missing_year = int(blank_mask(projects["Approved year"]).sum())
    dup_keys = projects.assign(
        _k=projects["Fund"].fillna("")
        + "|"
        + projects["Country"].fillna("")
        + "|"
        + projects["Name of Project"].map(lambda v: str(v).lower().strip())
    )["_k"]
    dup_rows = int(dup_keys.duplicated(keep=False).sum())
    blank_disb = int(
        projects[disb_col].map(lambda v: isinstance(v, str) and v != "" and v.strip() == "").sum()
    )
    gcf_rows = int(projects["Fund"].fillna("").str.contains("GCF").sum())
    audit.facts.update(
        {
            "approved_year_missing": missing_year,
            "approved_year_counts": {
                str(y): int(n)
                for y, n in sorted(Counter(v for v in years.values if v is not None).items())
            },
            "same_fund_country_name_rows": dup_rows,
            "whitespace_only_disbursed": blank_disb,
            "gcf_fund_rows": gcf_rows,
            "funds": {str(k): int(v) for k, v in projects["Fund"].value_counts().items()},
            "theme": {
                str(k): int(v) for k, v in projects["Theme/Objective"].value_counts().items()
            },
            "fund_status_blank_fund_rows": int(blank_mask(fs["Fund"]).sum()),
            "south_asia_regional_rows": int(south_asia_regional.sum()),
        }
    )
    audit.issue(
        "cfu_no_project_identifier",
        Severity.WARNING,
        IssueCategory.DUPLICATES,
        "(none)",
        len(projects),
        f"No project ID; {dup_rows} rows share (Fund, Country, Name) with another row",
        "Cross-source matches are 'possible' only; never merge on names alone.",
    )
    audit.issue(
        "cfu_missing_approved_year",
        Severity.INFO,
        IssueCategory.DATE,
        "Approved year",
        missing_year,
        "Approved year blank",
        "Exclude from year-based trend views.",
    )
    audit.issue(
        "cfu_theme_case_variants",
        Severity.INFO,
        IssueCategory.SCHEMA,
        "Theme/Objective",
        int((projects["Theme/Objective"] == "Multiple foci").sum()),
        "'Multiple foci' and 'Multiple Foci' both occur",
        "Normalize case in Task 003 cleaning (documented transformation).",
    )
    audit.issue(
        "cfu_gcf_rows_overlap_gcf_exports",
        Severity.WARNING,
        IssueCategory.DUPLICATES,
        "Fund",
        gcf_rows,
        "CFU includes GCF projects and GCF readiness (IRM) rows already present in GCF exports",
        "Never add CFU GCF totals to GCF export totals.",
    )
    audit.issue(
        "cfu_workbook_author_metadata",
        Severity.INFO,
        IssueCategory.PROVENANCE,
        "(file)",
        len(projects),
        "Workbook author metadata names an individual; download origin not recorded",
        "Record the URL the file was downloaded from.",
    )
    if audit.facts["fund_status_blank_fund_rows"]:
        audit.issue(
            "cfu_fund_status_unnamed_row",
            Severity.INFO,
            IssueCategory.SCHEMA,
            "Fund",
            int(blank_mask(fs["Fund"]).sum()),
            "Fund Status sheet has a row with a blank Fund name (likely a total row)",
            "Exclude from per-fund views; do not double count it.",
        )
    return audit


# ------------------------------------------------------------------------ CPE
def inspect_cpe(data: SourceData) -> SourceAudit:
    cpe = data.cpe
    families = cpe["Family URL"].nunique()
    audit = SourceAudit("climate_project_explorer", primary_record_count=families)
    audit.schemas.append(table_schema(audit.source_id, "search_results", "document", cpe))
    pub = parse_column(cpe["Family Publication Date"], parse_iso_datetime_date)
    lo, hi = date_range(pub.values)
    geos = cpe["Geographies"].map(lambda v: split_codes(v if isinstance(v, str) else None))
    is_pk = geos.map(lambda gs: "PAK" in gs)
    fam_2026 = cpe.loc[[d is not None and d.year == TARGET_YEAR for d in pub.values], "Family URL"]
    audit.coverage.append(
        CoverageRow(
            source_id=audit.source_id,
            table="search_results",
            unit_of_observation="document",
            record_count=len(cpe),
            distinct_id_count=int(cpe["Document URL"].nunique()),
            duplicate_id_rows=_dup_id_rows(cpe["Document URL"]),
            title_present=present_count(cpe["Document Title"]),
            description_present=present_count(cpe["Family Summary"]),
            amount_present=None,
            date_field="Family Publication Date",
            date_meaning="publication date of the family on the explorer (not approval)",
            earliest=lo,
            latest=hi,
            pakistan_records=int(is_pk.sum()),
            records_dated_2026=count_year(pub.values, TARGET_YEAR),
            notes="Documents, not projects",
        )
    )
    audit.coverage.append(
        CoverageRow(
            source_id=audit.source_id,
            table="search_results (families)",
            unit_of_observation="project family (Family URL)",
            record_count=families,
            distinct_id_count=families,
            duplicate_id_rows=0,
            title_present=int(cpe.groupby("Family URL")["Family Name"].first().notna().sum()),
            description_present=int(
                cpe.groupby("Family URL")["Family Summary"].first().notna().sum()
            ),
            amount_present=None,
            date_field="Family Publication Date",
            date_meaning="publication date on the explorer",
            earliest=lo,
            latest=hi,
            pakistan_records=int(cpe.loc[is_pk.tolist(), "Family URL"].nunique()),
            records_dated_2026=int(fam_2026.nunique()),
            notes=f"{cpe['Family Name'].nunique()} distinct names for {families} family URLs",
        )
    )
    audit.pakistan.append(
        PakistanRow(
            source_id=audit.source_id,
            table="search_results",
            unit_of_observation="project family",
            filter_rule="'PAK' in Geographies codes",
            records=int(cpe.loc[is_pk.tolist(), "Family URL"].nunique()),
            climate_flagged=None,
            notes=f"{int(is_pk.sum())} document rows",
        )
    )
    audit.year2026.append(
        Year2026Row(
            source_id=audit.source_id,
            table="search_results",
            date_field="Family Publication Date",
            date_meaning="explorer publication date (not approval)",
            records=int(fam_2026.nunique()),
            notes=f"families; {count_year(pub.values, TARGET_YEAR)} document rows",
        )
    )
    name_dups = cpe.groupby("Family Name")["Family URL"].nunique()
    audit.facts.update(
        {
            "documents": len(cpe),
            "families": families,
            "family_names": int(cpe["Family Name"].nunique()),
            "family_names_with_multiple_urls": int((name_dups > 1).sum()),
            "by_fund_source": {
                str(k): int(v)
                for k, v in cpe.drop_duplicates("Family URL")["Source"].value_counts().items()
            },
            "document_type_blank": int(blank_mask(cpe["Document Type"]).sum()),
            "html_in_summary": int(cpe["Family Summary"].fillna("").str.contains("<p>").sum()),
            "content_url_duplicates": _dup_id_rows(cpe["Document Content URL"]),
        }
    )
    audit.issue(
        "cpe_documents_not_projects",
        Severity.WARNING,
        IssueCategory.UNIT_OF_OBSERVATION,
        "Family URL",
        len(cpe) - families,
        f"{len(cpe)} document rows describe {families} families",
        "Count projects by Family URL; never by row.",
    )
    audit.issue(
        "cpe_family_name_reused",
        Severity.INFO,
        IssueCategory.DUPLICATES,
        "Family Name",
        int((name_dups > 1).sum()),
        "Same family name used by more than one family URL (e.g. generic policy documents)",
        "Use Family URL as the key.",
    )
    audit.issue(
        "cpe_html_in_summaries",
        Severity.INFO,
        IssueCategory.TEXT,
        "Family Summary",
        int(audit.facts["html_in_summary"]),  # type: ignore[call-overload]
        "Summaries contain HTML markup",
        "Strip markup with a documented, non-executing parser before text use.",
    )
    audit.issue(
        "cpe_publication_date_not_approval",
        Severity.WARNING,
        IssueCategory.DATE,
        "Family Publication Date",
        len(cpe),
        "Only date is the explorer publication date",
        "Do not present as project approval or funding year.",
    )
    return audit


INSPECTORS: dict[str, Callable[[SourceData], SourceAudit]] = {
    "research_paper": inspect_research,
    "aiddata": inspect_aiddata,
    "adb_pakistan": inspect_adb,
    "gcf_projects": inspect_gcf_projects,
    "gcf_readiness": inspect_gcf_readiness,
    "gcf_countries": inspect_gcf_countries,
    "gcf_historical": inspect_gcf_historical,
    "climate_funds_update": inspect_cfu,
    "climate_project_explorer": inspect_cpe,
}
