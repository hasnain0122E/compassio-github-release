"""Source D: ADB Pakistan IATI activities (financing instruments) and their transactions.

* One row per IATI activity = one ADB loan/grant **financing instrument**, identified by its
  IATI identifier. Instruments are grouped (``group_key``) under the ADB project number embedded
  in the identifier (``XM-DAC-46004-<project number>-<instrument>``); a project is never counted
  once per instrument.
* Each IATI transaction is one transaction-level observation. Types are kept separate:
  2 commitment, 3 disbursement, 5 interest repayment, 6 principal repayment. Repayments are
  inflows to ADB, never funding. No netting.
* Currency is the transaction's own ``currency`` attribute, else the activity's declared
  ``default-currency`` (recorded as such).
"""

import re
from collections import defaultdict
from typing import Any

import pandas as pd

from compassio_api.ingest.records import (
    CountryRec,
    ObservationRec,
    ProjectRec,
    frame_rows,
    parse_decimal,
    parse_iso_date,
    text_or_none,
)

SOURCE_ID = "adb_pakistan"
PROJECT_NUMBER = re.compile(r"^XM-DAC-46004-(\d{4,6}-\d{3})-")
TRANSACTION_FLOWS = {
    "2": "commitment",
    "3": "disbursement",
    "5": "repayment_interest",
    "6": "repayment_principal",
}
# IATI ActivityStatus codelist (published IATI standard codes).
ACTIVITY_STATUS = {
    "1": "Pipeline/identification",
    "2": "Implementation",
    "3": "Finalisation",
    "4": "Closed",
    "5": "Cancelled",
    "6": "Suspended",
}
IATI_COUNTRY = {"PK": ("Pakistan", "PAK")}  # every activity in the file reports PK only


def build_adb_records(
    activities: pd.DataFrame,
    transactions: pd.DataFrame,
    sectors: pd.DataFrame,
    generated_datetime: str | None,
) -> list[ProjectRec]:
    tx_by_activity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tx in frame_rows(transactions):
        tx_by_activity[str(tx["iati_identifier"])].append(tx)
    sectors_by_activity: dict[str, list[dict[str, str | None]]] = defaultdict(list)
    for sec in frame_rows(sectors):
        sectors_by_activity[str(sec["iati_identifier"])].append(
            {
                "vocabulary": text_or_none(sec.get("vocabulary")),
                "code": text_or_none(sec.get("code")),
                "percentage": text_or_none(sec.get("percentage")),
            }
        )

    records: list[ProjectRec] = []
    for act in frame_rows(activities):
        identifier = text_or_none(act.get("iati_identifier")) or ""
        number = PROJECT_NUMBER.match(identifier)
        actual = parse_iso_date(act.get("actual_start"))
        planned = parse_iso_date(act.get("planned_start"))
        start = actual or planned
        status_code = text_or_none(act.get("activity_status"))
        rec = ProjectRec(
            source_id=SOURCE_ID,
            source_project_id=identifier,
            record_level="adb_financing_instrument",
            title=text_or_none(act.get("title")) or "",
            description=text_or_none(act.get("description")),
            source_reference=f"ADB IATI activity {identifier} (generated {generated_datetime})",
            year=start.year if start else None,
            year_type=(
                "activity_actual_start"
                if actual
                else ("activity_planned_start" if planned else None)
            ),
            date_value=start,
            date_precision="day" if start else None,
            status=ACTIVITY_STATUS.get(status_code or "", status_code),
            group_key=f"adb_project:{number.group(1)}" if number else None,
            group_meaning=(
                "ADB project number: financing instruments (loans/grants) of one ADB project"
                if number
                else None
            ),
            attributes={
                "iati_activity_status_code": status_code,
                "adb_project_number": number.group(1) if number else None,
                "default_currency": text_or_none(act.get("default_currency")),
                "default_finance_type": text_or_none(act.get("default_finance_type")),
                "planned_start": text_or_none(act.get("planned_start")),
                "actual_start": text_or_none(act.get("actual_start")),
                "planned_end": text_or_none(act.get("planned_end")),
                "actual_end": text_or_none(act.get("actual_end")),
                "iati_sectors": sectors_by_activity.get(identifier, []),
                "document_links": act.get("document_links"),
            },
        )
        codes = [c for c in (text_or_none(act.get("recipient_countries")) or "").split("|") if c]
        for code in codes:
            name, iso3 = IATI_COUNTRY.get(code, (code, None))
            rec.countries.append(
                CountryRec(name, iso3, "iati_recipient_country" if iso3 else "unmapped_iati_code")
            )
        rec.multi_country = len(codes) != 1
        if rec.countries and len(codes) == 1:
            rec.recipient_label = rec.countries[0].name
        if number is None:
            rec.warn("adb_project_number_not_found", "No ADB project number in the identifier.")
        rec.warn(
            "financing_instrument_not_project",
            "This row is one ADB financing instrument; see the group for the ADB project.",
        )
        for position, tx in enumerate(tx_by_activity.get(identifier, [])):
            rec.observations.append(_transaction(rec, identifier, position, tx))
        if any(o.flow_kind.startswith("repayment") for o in rec.observations):
            rec.warn(
                "repayments_are_inflows",
                "Interest and principal repayments are inflows to ADB, not funding.",
            )
        records.append(rec)
    return records


def _transaction(
    rec: ProjectRec, identifier: str, position: int, tx: dict[str, Any]
) -> ObservationRec:
    code = text_or_none(tx.get("transaction_type")) or ""
    flow = TRANSACTION_FLOWS.get(code)
    amount, status = parse_decimal(tx.get("value"))
    own = text_or_none(tx.get("value_currency"))
    default = text_or_none(tx.get("default_currency"))
    tx_date = parse_iso_date(tx.get("transaction_date"))
    if flow is None:
        amount, status = None, "invalid"
        rec.warn("unknown_transaction_type", f"IATI transaction type {code!r} is not mapped.")
    return ObservationRec(
        key=f"{identifier}:tx{position}",
        flow_kind=flow or "disbursement",
        level="transaction",
        amount=amount,
        raw_value=text_or_none(tx.get("value")),
        value_status=status,
        unit="units" if status == "reported" else None,
        currency=(own or default) if status == "reported" else None,
        unit_status="stated_in_source"
        if own
        else ("declared_default_currency" if default else "not_stated_in_source"),
        price_basis="nominal",
        effective_date=tx_date,
        effective_year=tx_date.year if tx_date else None,
        date_meaning=f"IATI transaction date (transaction type {code})",
        source_reference=f"IATI transaction #{position} of {identifier}",
        multi_country=rec.multi_country,
        financing_type=text_or_none(tx.get("finance_type")),
    )
