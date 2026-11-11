"""GCF API snapshot -> enrichment of existing GCF export rows (matched ONLY by GCF code).

Precedence: the canonical export row keeps its own values. API values are stored alongside in
``project_enrichments.values`` with their own source; every disagreement between the two (and
any internal inconsistency inside the API record) is recorded in ``conflicts`` -- nothing is
overwritten. API amounts become ``financial_observations`` owned by ``gcf_api_projects``:

* Top-level ``TotalGCFFunding`` / ``TotalCoFinancing`` / ``TotalValue``: the API states **no
  currency** for these (they are mixed-currency for projects with EUR lines), so they are stored
  with currency NULL (``not_stated_in_source``) and never summed.
* Country lines (``Countries[].Financing``): currency stated; GCF's own per-country breakdown
  (``financing_type = country_breakdown``, ``country_iso3`` set, ``is_component``).
* Funding lines (``Funding[]``: source x instrument): currency stated (USD or EUR).
* Disbursements: transaction-level, currency and date stated.

GCF's ``*USDeq`` fields (conversions at a current exchange rate) are NOT used as amounts.
Ex-ante result estimates (CO2, beneficiaries) are deliberately not imported (not impact).
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from compassio_api.core.provenance import ENRICHMENT_PRECEDENCE
from compassio_api.ingest.records import ObservationRec, parse_decimal, text_or_none, validated

SOURCE_ID = "gcf_api_projects"
RELATION = "enriched_from_official_record"
MATCH_METHOD = "Exact GCF reference code: API 'ApprovedRef' == export 'Ref #'"
PRECEDENCE = ENRICHMENT_PRECEDENCE


@dataclass
class ExportView:
    """The existing export row's comparable values (read from the database)."""

    title: str
    board_meeting: str | None
    theme: str | None
    sector_type: str | None
    entity: str | None
    iso3: frozenset[str]
    fa_financing: Decimal | None


@dataclass
class EnrichmentRec:
    project_id: str
    ref: str
    values: dict[str, Any]
    conflicts: list[dict[str, Any]]
    approval_date: date | None
    project_status: str | None
    official_url: str | None
    observations: list[ObservationRec] = field(default_factory=list)

    def content_sha256(self) -> str:
        payload = json.dumps(
            {
                "values": self.values,
                "conflicts": self.conflicts,
                "obs": [
                    o.key + "|" + str(o.amount) + "|" + str(o.currency) for o in self.observations
                ],
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _iso_date(value: object) -> date | None:
    text = text_or_none(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _iso_text(value: object) -> str | None:
    parsed = _iso_date(value)
    return parsed.isoformat() if parsed else None


def _norm(text: str | None) -> str:
    return " ".join((text or "").split()).casefold()


def _conflict(
    field_name: str, export_value: object, api_value: object, kind: str
) -> dict[str, Any]:
    return {
        "field": field_name,
        "export_value": None if export_value is None else str(export_value),
        "api_value": None if api_value is None else str(api_value),
        "kind": kind,
        "precedence": PRECEDENCE if kind == "cross_record" else "Both published values kept.",
    }


def _obs(**kwargs: Any) -> ObservationRec:
    return validated(ObservationRec(**kwargs))


def build_enrichment(
    record: dict[str, Any], project_id: str, export: ExportView, retrieved_at: datetime
) -> EnrichmentRec:
    ref = str(record["ApprovedRef"])
    approval = _iso_date(record.get("ApprovalDate"))
    board = text_or_none(record.get("BoardMeeting"))
    countries = record.get("Countries") or []
    multi = len(countries) != 1
    entities = record.get("Entities") or []
    values: dict[str, Any] = {
        "approved_ref": ref,
        "api_projects_id": record.get("ProjectsID"),
        "project_name": text_or_none(record.get("ProjectName")),
        "board_meeting": board,
        "approval_date": approval.isoformat() if approval else None,
        "start_date": _iso_text(record.get("StartDate")),
        "end_date": _iso_text(record.get("EndDate")),
        "date_implementation_start": text_or_none(record.get("DateImplementationStart")),
        "date_completion": text_or_none(record.get("DateCompletion")),
        "date_closing": text_or_none(record.get("DateClosing")),
        "date_cancelled": text_or_none(record.get("DateCancelled")),
        "duration_months": record.get("DurationMonths"),
        "status": text_or_none(record.get("Status")),
        "theme": text_or_none(record.get("Theme")),
        "sector": text_or_none(record.get("Sector")),
        "size": text_or_none(record.get("Size")),
        "risk_category": text_or_none(record.get("RiskCategory")),
        "countries": [
            {"iso3": c.get("ISO3"), "name": c.get("CountryName"), "region": c.get("Region")}
            for c in countries
        ],
        "entities": [
            {
                "name": e.get("Name"),
                "acronym": e.get("Acronym"),
                "access": e.get("Access"),
                "type": e.get("Type"),
            }
            for e in entities
        ],
        "result_areas": [
            r.get("Area") or r.get("ResultArea") or r for r in (record.get("ResultAreas") or [])
        ],
        "total_gcf_funding_as_published": record.get("TotalGCFFunding"),
        "total_co_financing_as_published": record.get("TotalCoFinancing"),
        "total_value_as_published": record.get("TotalValue"),
        "project_url": text_or_none(record.get("ProjectURL")),
        "not_imported": "LifeTimeCO2 and beneficiary estimates (ex-ante, not verified impact); "
        "*USDeq conversions at a current exchange rate",
    }

    conflicts: list[dict[str, Any]] = []
    if _norm(export.title) != _norm(values["project_name"]):
        conflicts.append(_conflict("title", export.title, values["project_name"], "cross_record"))
    if export.board_meeting != board:
        conflicts.append(_conflict("board_meeting", export.board_meeting, board, "cross_record"))
    if _norm(export.theme) != _norm(values["theme"]):
        conflicts.append(_conflict("theme", export.theme, values["theme"], "cross_record"))
    if _norm(export.sector_type) != _norm(values["sector"]):
        conflicts.append(_conflict("sector", export.sector_type, values["sector"], "cross_record"))
    api_iso3 = frozenset(str(c.get("ISO3")) for c in countries if c.get("ISO3"))
    if export.iso3 != api_iso3:
        conflicts.append(
            _conflict(
                "countries_iso3",
                ",".join(sorted(export.iso3)),
                ",".join(sorted(api_iso3)),
                "cross_record",
            )
        )
    acronyms = {_norm(e.get("Acronym")) for e in entities} | {
        _norm(e.get("Name")) for e in entities
    }
    if export.entity and _norm(export.entity) not in acronyms:
        conflicts.append(
            _conflict(
                "accredited_entity",
                export.entity,
                ";".join(sorted(a for a in acronyms if a)),
                "cross_record",
            )
        )
    api_total, _ = parse_decimal(record.get("TotalGCFFunding"))
    if (
        export.fa_financing is not None
        and api_total is not None
        and export.fa_financing != api_total
    ):
        conflicts.append(
            _conflict("gcf_financing_total", export.fa_financing, api_total, "cross_record")
        )
    country_sum = sum(
        (parse_decimal(f.get("GCF"))[0] or Decimal(0))
        for c in countries
        for f in c.get("Financing") or []
    )
    if api_total is not None and countries and country_sum != api_total:
        conflicts.append(
            _conflict(
                "api_total_vs_country_breakdown",
                f"sum of country GCF lines {country_sum}",
                f"TotalGCFFunding {api_total}",
                "within_api",
            )
        )

    rec = EnrichmentRec(
        project_id=project_id,
        ref=ref,
        values=values,
        conflicts=conflicts,
        approval_date=approval,
        project_status=values["status"],
        official_url=values["project_url"],
    )
    _observations(rec, record, approval, board, multi, retrieved_at)
    return rec


def _observations(
    rec: EnrichmentRec,
    record: dict[str, Any],
    approval: date | None,
    board: str | None,
    multi: bool,
    retrieved_at: datetime,
) -> None:
    ref = rec.ref
    year = approval.year if approval else None
    approval_meaning = f"GCF Board approval date (API ApprovalDate; meeting {board})"
    base = f"GCF API snapshot {retrieved_at.date().isoformat()}"
    lines_ok, countries_ok = consistency(record)
    rec.values["funding_lines_consistent_with_total"] = lines_ok
    rec.values["country_lines_consistent_with_total"] = countries_ok
    for key, column, flow in (
        ("total_gcf", "TotalGCFFunding", "gcf_financing"),
        ("total_co_financing", "TotalCoFinancing", "co_financing"),
        ("total_value", "TotalValue", "total_project_cost"),
    ):
        amount, status = parse_decimal(record.get(column))
        rec.observations.append(
            _obs(
                key=f"{ref}:{key}",
                flow_kind=flow,
                level="project",
                amount=amount,
                raw_value=text_or_none(record.get(column)),
                value_status=status,
                unit=None,
                currency=None,
                unit_status="not_stated_in_source",
                price_basis="unspecified",
                effective_date=approval,
                effective_year=year,
                date_meaning=approval_meaning,
                source_reference=f"{base}, '{column}' (no currency stated; never summed)",
                multi_country=multi,
            )
        )
    for country in record.get("Countries") or []:
        iso3 = text_or_none(country.get("ISO3"))
        for position, line in enumerate(country.get("Financing") or []):
            currency = text_or_none(line.get("Currency"))
            for column, flow in (
                ("GCF", "gcf_financing"),
                ("CoFinancing", "co_financing"),
                ("Total", "total_project_cost"),
            ):
                amount, status = parse_decimal(line.get(column))
                rec.observations.append(
                    _obs(
                        key=f"{ref}:country:{iso3}:{position}:{column.lower()}",
                        flow_kind=flow,
                        level="project",
                        amount=amount,
                        raw_value=text_or_none(line.get(column)),
                        value_status=status,
                        unit="units" if status == "reported" else None,
                        currency=currency if status == "reported" else None,
                        unit_status="stated_in_source" if currency else "not_stated_in_source",
                        price_basis="nominal",
                        effective_date=approval,
                        effective_year=year,
                        date_meaning=approval_meaning,
                        source_reference=f"{base}, Countries[{iso3}].Financing.{column}",
                        multi_country=False,
                        financing_type="country_breakdown",
                        is_component=True,
                        country_iso3=iso3,
                        recommended_for_aggregates=countries_ok,
                    )
                )
    seen_lines: dict[str, str] = {}
    skipped = 0
    for line in record.get("Funding") or []:
        source = text_or_none(line.get("Source"))
        flow = "gcf_financing" if source == "GCF" else "co_financing"
        line_bm = text_or_none(line.get("BM"))
        same_meeting = line_bm == board
        amount, status = parse_decimal(line.get("Budget"))
        currency = text_or_none(line.get("Currency"))
        key = f"{ref}:funding:{line.get('ProjectBudgetID')}:{line_bm}"
        fingerprint = json.dumps(line, sort_keys=True, default=str)
        if key in seen_lines:
            if seen_lines[key] == fingerprint:
                skipped += 1  # identical repeated line: stored once, never double counted
                continue
            key = f"{key}:{len(seen_lines)}"
        seen_lines[key] = fingerprint
        rec.observations.append(
            _obs(
                key=key,
                flow_kind=flow,
                level="project",
                amount=amount,
                raw_value=text_or_none(line.get("Budget")),
                value_status=status,
                unit="units" if status == "reported" else None,
                currency=currency if status == "reported" else None,
                unit_status="stated_in_source" if currency else "not_stated_in_source",
                price_basis="nominal",
                effective_date=approval if same_meeting else None,
                effective_year=year if same_meeting else None,
                date_meaning=approval_meaning
                if same_meeting
                else f"approved at Board meeting {line_bm}; no calendar date published",
                source_reference=f"{base}, Funding[{source} / {line.get('Instrument')}].Budget"
                f" (BM {line_bm})",
                multi_country=multi,
                financing_type=text_or_none(line.get("Instrument")),
                is_component=True,
                recommended_for_aggregates=lines_ok if flow == "gcf_financing" else None,
            )
        )
    rec.values["identical_funding_lines_skipped"] = skipped
    for line in record.get("Disbursements") or []:
        when = _iso_date(line.get("DateEffective"))
        amount, status = parse_decimal(line.get("AmountDisbursed"))
        currency = text_or_none(line.get("Currency"))
        rec.observations.append(
            _obs(
                key=f"{ref}:disbursement:{line.get('ProjectDisbursementID')}",
                flow_kind="disbursement",
                level="transaction",
                amount=amount,
                raw_value=text_or_none(line.get("AmountDisbursed")),
                value_status=status,
                unit="units" if status == "reported" else None,
                currency=currency if status == "reported" else None,
                unit_status="stated_in_source" if currency else "not_stated_in_source",
                price_basis="nominal",
                effective_date=when,
                effective_year=when.year if when else None,
                date_meaning="GCF disbursement effective date (API DateEffective)",
                source_reference=f"{base}, Disbursements.AmountDisbursed",
                multi_country=multi,
            )
        )


def consistency(record: dict[str, Any]) -> tuple[bool, bool]:
    """Whether GCF's own line items reproduce its published ``TotalGCFFunding`` exactly.

    * funding lines: all GCF lines are USD and their sum equals the total;
    * country lines: the per-country GCF figures sum to the total.

    Only consistent line sets may enter totals (``recommended_for_aggregates``); this guards
    against repeated listings (e.g. lines re-published under a later Board meeting).
    """
    total, _ = parse_decimal(record.get("TotalGCFFunding"))
    if total is None:
        return False, False
    gcf_lines = [f for f in record.get("Funding") or [] if f.get("Source") == "GCF"]
    usd_only = bool(gcf_lines) and all(f.get("Currency") == "USD" for f in gcf_lines)
    line_sum = sum((parse_decimal(f.get("Budget"))[0] or Decimal(0)) for f in gcf_lines)
    country_sum = sum(
        (parse_decimal(f.get("GCF"))[0] or Decimal(0))
        for c in record.get("Countries") or []
        for f in c.get("Financing") or []
    )
    return usd_only and line_sum == total, bool(record.get("Countries")) and country_sum == total
