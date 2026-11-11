"""Remaining registered sources (canonical manifest, audited loaders; nothing re-parsed).

* ``gcf_readiness`` -> project rows of record_level ``gcf_readiness_grant`` (own identity
  namespace; never counted as funded projects). ``Financing`` has no stated currency or unit.
* ``gcf_countries`` -> ``country_aggregates`` (source-published country totals; never summed
  with project rows).
* ``climate_project_explorer`` -> ``documents`` (+ links to GCF projects only through a GCF
  reference code in the document's own metadata). Documents are never projects.
* ``gcf_historical`` -> ``historical_staging`` (provenance unverified: restricted, never served).
"""

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from compassio_api.ingest.records import (
    AnnotationRec,
    CountryRec,
    ObservationRec,
    ProjectRec,
    frame_rows,
    parse_decimal,
    text_or_none,
)
from compassio_ml.data.parsing import split_country_list

READINESS_SOURCE = "gcf_readiness"
COUNTRIES_SOURCE = "gcf_countries"
CPE_SOURCE = "climate_project_explorer"
HISTORICAL_SOURCE = "gcf_historical"

READINESS_CODE = re.compile(r"^[A-Z]{3}-RS-\d{3}$")
GCF_CODE = re.compile(r"\b(?:FP|SAP)\d{3}\b")
EXPORT_EPOCH = re.compile(r"(\d{13})")


def _date_long(text: str | None) -> date | None:
    """GCF readiness dates are published like 'May 1, 2015'."""
    if not text:
        return None
    try:
        return datetime.strptime(text.strip(), "%b %d, %Y").replace(tzinfo=UTC).date()
    except ValueError:
        return None


# ------------------------------------------------------------------------------ readiness
def build_readiness_records(
    frame: pd.DataFrame, country_map: dict[str, tuple[str, str | None]]
) -> list[ProjectRec]:
    rows = frame_rows(frame)
    refs = [text_or_none(r.get("Ref #")) for r in rows]
    counts: dict[str, int] = {}
    for ref in refs:
        if ref:
            counts[ref] = counts.get(ref, 0) + 1
    records: list[ProjectRec] = []
    for index, row in enumerate(rows):
        sheet_row = index + 2
        ref = refs[index]
        stable = ref is not None and counts[ref] == 1 and bool(READINESS_CODE.match(ref))
        approved = _date_long(text_or_none(row.get("Approved Date")))
        country = text_or_none(row.get("Country")) or "not reported"
        names = split_country_list(country)
        rec = ProjectRec(
            source_id=READINESS_SOURCE,
            source_project_id=ref if stable and ref else f"row-{sheet_row}",
            record_level="gcf_readiness_grant",
            title=text_or_none(row.get("Project Title")) or "",
            source_reference=f"GCF readiness export, row {sheet_row}, Ref # {ref or 'blank'}",
            recipient_label=country,
            region=text_or_none(row.get("Region")),
            multi_country=len(names) != 1,
            year=approved.year if approved else None,
            year_type="readiness_approval_year" if approved else None,
            date_value=approved,
            date_precision="day" if approved else None,
            status=text_or_none(row.get("Status")),
            attributes={
                "readiness_ref": ref,
                "activity": text_or_none(row.get("Activity")),
                "delivery_partner": text_or_none(row.get("Delivery Partner")),
                "sids": text_or_none(row.get("SIDS")),
                "ldcs": text_or_none(row.get("LDCs")),
                "nap": text_or_none(row.get("NAP")),
                "not_a_funded_project": True,
            },
        )
        for name in names:
            match = country_map.get(name)
            rec.countries.append(
                CountryRec(name, match[0], "gcf_countries_exact_name")
                if match
                else CountryRec(name, None, "unmatched_in_gcf_countries")
            )
        if not stable:
            rec.warn(
                "no_stable_readiness_reference",
                f"'Ref #' ({ref or 'blank'}) is missing, repeated or not a readiness code; the "
                "row position identifies this record and is valid only for this file version.",
                "Ref #",
            )
        if approved is None:
            rec.warn("approval_date_unparsed", "No parseable approval date.", "Approved Date")
        rec.warn(
            "readiness_grant_not_funded_project",
            "A GCF readiness/preparatory grant, not a GCF funded project (FP/SAP).",
        )
        rec.warn(
            "currency_and_unit_not_stated",
            "The readiness export states no currency or unit for 'Financing'; it is shown as "
            "published and never summed.",
            "Financing",
        )
        amount, status = parse_decimal(row.get("Financing"))
        if amount is not None and amount <= 1:
            rec.warn(
                "placeholder_amount",
                f"Financing {amount} looks like a placeholder (audit: values <= 1 on cancelled "
                "grants); kept as published.",
                "Financing",
            )
        rec.observations.append(
            ObservationRec(
                key=f"{rec.source_project_id}:financing",
                flow_kind="readiness_grant",
                level="project",
                amount=amount,
                raw_value=text_or_none(row.get("Financing")),
                value_status=status,
                unit=None,
                currency=None,
                unit_status="not_stated_in_source",
                price_basis="unspecified",
                effective_date=approved,
                effective_year=approved.year if approved else None,
                date_meaning="GCF readiness approval date ('Approved Date')",
                source_reference="GCF readiness export 'Financing'",
                multi_country=rec.multi_country,
            )
        )
        activity = text_or_none(row.get("Activity"))
        if activity:
            rec.annotations.append(
                AnnotationRec(
                    annotation_source_id=READINESS_SOURCE,
                    scheme="gcf_readiness_activity",
                    kind="source_classification",
                    label=activity,
                    raw_value=activity,
                    provenance="GCF readiness 'Activity' as published.",
                )
            )
        records.append(rec)
    return records


# ------------------------------------------------------------------------- country summaries
def export_snapshot_date(path: Path) -> date | None:
    """GCF ODL export file names embed the export time as a 13-digit ms epoch."""
    match = EXPORT_EPOCH.search(path.name)
    if not match:
        return None
    return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=UTC).date()


COUNTRY_MEASURES = (
    ("# RP", "readiness_count", "Number of readiness grants (GCF count)", "count"),
    ("# FA", "funded_activity_count", "Number of funded activities (GCF count)", "count"),
    ("RP Financing $", "readiness_financing", "Readiness financing (GCF country total)", "money"),
    (
        "FA Financing $",
        "funded_activity_financing",
        "Funded-activity financing attributed to the country by GCF",
        "money",
    ),
)


def build_country_aggregates(frame: pd.DataFrame, snapshot: date | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    meaning = (
        "GCF Open Data Library export time encoded in the file name (ms epoch); assumed to be "
        "the snapshot date of these cumulative country figures"
        if snapshot
        else "snapshot date not available"
    )
    for row in frame_rows(frame):
        iso3 = text_or_none(row.get("ISO3"))
        if not iso3:
            continue
        for column, measure, label, kind in COUNTRY_MEASURES:
            amount, status = parse_decimal(row.get(column))
            rows.append(
                {
                    "source_id": COUNTRIES_SOURCE,
                    "iso3": iso3,
                    "country_name": text_or_none(row.get("Country Name")) or iso3,
                    "region": text_or_none(row.get("Region")),
                    "measure": measure,
                    "measure_label": label,
                    "value_kind": kind,
                    "amount": amount,
                    "raw_value": text_or_none(row.get(column)),
                    "value_status": status,
                    "unit": "units" if kind == "money" else None,
                    "currency": "USD" if kind == "money" else None,
                    "unit_status": "stated_in_source" if kind == "money" else "not_applicable",
                    "snapshot_date": snapshot,
                    "date_meaning": meaning,
                    "attributes": {
                        "sids": text_or_none(row.get("SIDS")),
                        "ldcs": text_or_none(row.get("LDCs")),
                        "column": column,
                    },
                }
            )
    return rows


# ------------------------------------------------------------------------------- documents
def _slug(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] or None


def _cpe_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def build_documents(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """One row per catalogue document. GCF codes found in a GCF-sourced document's own metadata
    are kept in ``attributes['gcf_codes_in_metadata']``; links are resolved against the
    database by ``extended.rebuild_document_links``."""
    documents: list[dict[str, Any]] = []
    for row in frame_rows(frame):
        doc_slug = _slug(text_or_none(row.get("Document URL")))
        if doc_slug is None:
            continue
        fund = text_or_none(row.get("Source"))
        family_name = text_or_none(row.get("Family Name"))
        title = text_or_none(row.get("Document Title")) or family_name or doc_slug
        geographies = [
            g.strip()
            for g in re.split(r"[;,]", text_or_none(row.get("Geographies")) or "")
            if g.strip()
        ]
        codes: list[str] = []
        if fund == "GCF":  # GCF codes are only meaningful in GCF-sourced documents
            haystack = " ".join(
                text_or_none(row.get(k)) or ""
                for k in ("Family Name", "Document Title", "Family Summary")
            )
            codes = sorted(set(GCF_CODE.findall(haystack)))
        documents.append(
            {
                "id": f"{CPE_SOURCE}:{doc_slug}",
                "source_id": CPE_SOURCE,
                "source_document_id": doc_slug,
                "family_id": _slug(text_or_none(row.get("Family URL"))),
                "family_name": family_name,
                "title": title,
                "document_type": text_or_none(row.get("Document Type")),
                "publisher_fund": fund,
                "document_date": _cpe_date(text_or_none(row.get("Family Publication Date"))),
                "document_date_type": (
                    "Climate Project Explorer family publication date (catalogue listing); not "
                    "the document's own date and not a project approval date"
                ),
                "geographies": geographies,
                "languages": text_or_none(row.get("Languages")),
                "catalogue_url": text_or_none(row.get("Document URL")),
                "content_url": text_or_none(row.get("Document Content URL")),
                "attributes": {
                    "category": text_or_none(row.get("Category")),
                    "family_url": text_or_none(row.get("Family URL")),
                    "gcf_codes_in_metadata": codes,
                },
            }
        )
    return documents


# ----------------------------------------------------------------------------- historical
def build_historical(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in frame_rows(frame):
        ref = text_or_none(row.get("Ref_N"))
        if not ref:
            continue
        raw = text_or_none(row.get("Tot_Fin"))
        amount, status = parse_decimal(raw)
        rows.append(
            {
                "source_id": HISTORICAL_SOURCE,
                "source_record_id": ref,
                "theme": text_or_none(row.get("Theme")),
                "accredited_entity": text_or_none(row.get("AccEnt")),
                "total_financing_raw": raw,
                "total_financing": amount,
                "value_status": status,
                "unit": "thousands",
                "currency": "USD",
                "unit_status": "stated_in_source",
                "attributes": {
                    "continent": text_or_none(row.get("Continent")),
                    "access_modality": text_or_none(row.get("Acc_mod")),
                    "unit_evidence": "Archive 'TO READ' sheet: amounts in USD thousands "
                    "(financial_fields_audit.md)",
                },
            }
        )
    return rows


def decimal_or_none(value: object) -> Decimal | None:
    amount, _ = parse_decimal(value)
    return amount
