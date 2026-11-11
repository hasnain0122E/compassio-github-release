"""Source A: AidData GCDF 3.0 records with the Qi et al. 2026 climate annotations.

Input is the verified Task 003 research table (``data/processed/research_projects.parquet``,
checked against the committed lock) plus ``research_text_originals.parquet`` for the text as
AidData publishes it. One project row per AidData record; the research workbook is the same
population (cross_source_overlap.md §2), so it contributes the annotation, never a second row.
Rio markers are the paper authors' annotations -- NOT Compassio model predictions.
"""

from typing import Any

import pandas as pd

from compassio_api.ingest.records import (
    AnnotationRec,
    CountryRec,
    ObservationRec,
    ProjectRec,
    blank,
    frame_rows,
    parse_decimal,
    parse_iso_date,
    text_or_none,
)

SOURCE_ID = "aiddata"
ANNOTATION_SOURCE_ID = "research_paper"
RIO_SCHEME = "rio_marker_qi_et_al_2026"
RIO_PROVENANCE = (
    "Rio marker (overall, mitigation, adaptation; 0 = not targeted, 1 = significant, "
    "2 = principal) annotated by the authors of Qi et al. 2026, Scientific Data 13:277 "
    "(Figshare 30015124 v1). is_climate_related = overall > 0. A research annotation of the "
    "retrospective description, not a Compassio model prediction and not evidence of impact."
)
GROUP_MEANING = (
    "AidData Parent ID package: related financing records (tranches, umbrella and component "
    "agreements). Related, not the same record; never add them up without AidData's "
    "'Recommended For Aggregates' flag."
)


def _bool(value: object) -> bool | None:
    if blank(value):
        return None
    return bool(value)


def _int(value: object) -> int | None:
    return None if blank(value) else int(str(value))


def aiddata_country_lookup(table: pd.DataFrame) -> dict[str, str]:
    """Exact AidData ``Recipient`` name -> ``Recipient ISO-3`` (only unambiguous pairs)."""
    pairs = table[["recipient", "recipient_iso3"]].dropna().drop_duplicates()
    counts = pairs["recipient"].value_counts()
    unique = pairs[pairs["recipient"].map(counts) == 1]
    return {
        str(r): str(i) for r, i in zip(unique["recipient"], unique["recipient_iso3"], strict=True)
    }


def build_research_records(table: pd.DataFrame, originals: pd.DataFrame) -> list[ProjectRec]:
    text = originals.set_index("record_id")
    records: list[ProjectRec] = []
    for row in frame_rows(table):
        records.append(_build_one(row, text))
    return records


def _build_one(row: dict[str, Any], text: pd.DataFrame) -> ProjectRec:
    rid = str(row["record_id"])
    title = text_or_none(text.at[rid, "title_aiddata_src"]) if rid in text.index else None
    description = (
        text_or_none(text.at[rid, "description_aiddata_src"]) if rid in text.index else None
    )
    title = title or text_or_none(row.get("title_clean")) or ""
    iso3 = text_or_none(row.get("recipient_iso3"))
    recipient = text_or_none(row.get("recipient")) or "not reported"
    multi = iso3 is None
    year = _int(row.get("commitment_year"))
    commit_date = parse_iso_date(row.get("commitment_date"))
    date_estimated = _bool(row.get("commitment_date_estimated"))
    status = text_or_none(row.get("status"))
    recommended = _bool(row.get("recommended_for_aggregates"))
    estimated = _bool(row.get("amount_estimated"))
    parent = text_or_none(row.get("parent_id"))

    rec = ProjectRec(
        source_id=SOURCE_ID,
        source_project_id=rid,
        record_level="aiddata_record",
        title=title,
        description=description,
        source_reference=(
            f"AidData GCDF 3.0 AidData Record ID {rid}; research workbook row "
            f"{row.get('research_row_id')}"
        ),
        recipient_label=recipient,
        region=text_or_none(row.get("recipient_region")),
        multi_country=multi,
        sector_name=text_or_none(row.get("sector_name")),
        sector_code=text_or_none(row.get("sector_code")),
        sector_vocabulary="aiddata_crs_sector",
        year=year,
        year_type="commitment_year",
        date_value=commit_date,
        date_precision="day" if commit_date else ("year" if year else None),
        date_estimated=date_estimated,
        status=status,
        group_key=f"aiddata_parent:{parent}" if parent else None,
        group_meaning=GROUP_MEANING if parent else None,
        attributes={
            "flow_type": text_or_none(row.get("flow_type")),
            "flow_class": text_or_none(row.get("flow_class")),
            "intent": text_or_none(row.get("intent")),
            "funding_agencies": text_or_none(row.get("funding_agencies")),
            "funding_agencies_type": text_or_none(row.get("funding_agencies_type")),
            "recommended_for_aggregates": recommended,
            "umbrella": _bool(row.get("umbrella")),
            "aiddata_parent_id": parent,
            "research_row_id": text_or_none(row.get("research_row_id")),
            "research_eligibility_status": text_or_none(row.get("eligibility_status")),
        },
    )
    rec.countries.append(
        CountryRec(recipient, iso3, "aiddata_recipient_iso3" if iso3 else "regional_no_iso3")
    )
    if multi:
        rec.warn(
            "regional_or_multi_country_recipient",
            f"Recipient '{recipient}' is regional or multi-country; amounts cannot be "
            "attributed to one country.",
            "recipient",
        )
    if date_estimated:
        rec.warn("commitment_date_estimated", "AidData marks the commitment date as estimated.")
    if recommended is False:
        rec.warn(
            "not_recommended_for_aggregates",
            "AidData flags this record as not recommended for aggregates (pledge, umbrella, "
            "cancelled or duplicate-risk record); excluded from totals.",
        )
    if status and status.startswith("Pipeline: Pledge"):
        rec.warn("pledge_not_commitment", "Pipeline pledge: a promise, not a commitment.")
    if row.get("eligibility_status") == "quarantined":
        rec.warn(
            "research_label_conflict_quarantined",
            "Quarantined in the research dataset: "
            f"{row.get('exclusion_reasons') or 'conflicting labels'}.",
        )
    if row.get("retrospective_text_warning") is True:
        rec.warn(
            "retrospective_description",
            "The description was written after the fact (reports outcomes or later events).",
            "description",
        )

    _add_annotation(rec, row)
    _add_amounts(rec, row, year, commit_date, date_estimated, recommended, estimated, multi)
    return rec


def _add_annotation(rec: ProjectRec, row: dict[str, Any]) -> None:
    if not blank(row.get("label_error")):
        rec.warn("climate_annotation_unparseable", str(row["label_error"]), "rio_marker")
        return
    rec.annotations.append(
        AnnotationRec(
            annotation_source_id=ANNOTATION_SOURCE_ID,
            scheme=RIO_SCHEME,
            kind="research_annotation",
            provenance=RIO_PROVENANCE,
            overall=_int(row.get("rio_overall")),
            mitigation=_int(row.get("rio_mitigation")),
            adaptation=_int(row.get("rio_adaptation")),
            is_climate_related=_bool(row.get("is_climate_related")),
            raw_value=text_or_none(row.get("rio_marker_src")),
        )
    )


def _add_amounts(
    rec: ProjectRec,
    row: dict[str, Any],
    year: int | None,
    commit_date: Any,
    date_estimated: bool | None,
    recommended: bool | None,
    estimated: bool | None,
    multi: bool,
) -> None:
    status = text_or_none(row.get("status")) or ""
    flow = "pledge" if status.startswith("Pipeline: Pledge") else "commitment"
    meaning = "AidData commitment date" + (" (estimated)" if date_estimated else "")
    if commit_date is None:
        meaning = "AidData commitment year"
    common: dict[str, Any] = {
        "flow_kind": flow,
        "level": "project",
        "effective_date": commit_date,
        "effective_year": year,
        "date_meaning": meaning,
        "multi_country": multi,
        "estimated": estimated,
        "recommended_for_aggregates": recommended,
        "financing_type": text_or_none(row.get("flow_type")),
    }
    original, original_status = parse_decimal(row.get("amount_original_src"))
    currency = text_or_none(row.get("amount_currency"))
    rec.observations.append(
        ObservationRec(
            key=f"{rec.source_project_id}:amount_original_currency",
            amount=original,
            raw_value=text_or_none(row.get("amount_original_src")),
            value_status=original_status,
            unit="units" if original_status == "reported" else None,
            currency=currency if original_status == "reported" else None,
            unit_status="stated_in_source" if currency else "not_stated_in_source",
            price_basis="nominal",
            source_reference="AidData 'Amount (Original Currency)' + 'Original Currency'",
            **common,
        )
    )
    constant, constant_status = parse_decimal(row.get("amount_constant_usd_2021"))
    rec.observations.append(
        ObservationRec(
            key=f"{rec.source_project_id}:amount_constant_usd_2021",
            amount=constant,
            raw_value=None if constant is None else str(constant),
            value_status=constant_status,
            unit="units" if constant_status == "reported" else None,
            currency="USD" if constant_status == "reported" else None,
            unit_status="stated_in_source",
            price_basis="constant_2021_usd",
            source_reference=(
                "AidData 'Amount (Constant USD 2021)' (AidData's own conversion; not re-derived)"
            ),
            **common,
        )
    )
    if original_status == "not_reported":
        rec.warn(
            "amount_not_reported",
            "No amount is published for this record (shown as 'not reported', never zero).",
            "amount",
        )
    if estimated:
        rec.warn("amount_estimated", "AidData marks the amount as estimated.", "amount")
