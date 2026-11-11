"""Source C: Climate Funds Update (CFU) ``Projects`` sheet.

* CFU publishes **no project identifier**. Identity is the sheet row number of the registered
  file (``projects-r<row>``), valid only for that file's SHA-256 (recorded per import run).
* Amounts are in **USD millions** (stated in the headers). ``Amount of Funding Approved`` is an
  approval total; instrument columns (grant, loan, guarantee, equity) are *components* of that
  total and are flagged so they are never added to it. ``Disbursed`` is cumulative as of the
  workbook snapshot, not dated.
* GCF rows in CFU duplicate the GCF export: a GCF code in the name becomes an explicit
  ``probable_match_reference_code`` link, and amounts are never summed across the two sources.
"""

import re

import pandas as pd

from compassio_api.ingest.records import (
    AnnotationRec,
    CountryRec,
    ObservationRec,
    ProjectRec,
    blank,
    frame_rows,
    parse_decimal,
    text_or_none,
)

SOURCE_ID = "climate_funds_update"
GCF_CODE = re.compile(r"\(((?:FP|SAP)\d{3})\)")
APPROVED = "Amount of Funding Approved (USD millions)"
DISBURSED = "Disbursed (USD millions)"
COMPONENTS = {
    "Concessional loan": "concessional_loan",
    "Grant": "grant",
    "Guarantee": "guarantee",
    "Equity": "equity",
}
SNAPSHOT = "workbook snapshot (file modified 2026-03-18)"


def is_multi_country_label(country: str) -> bool:
    """CFU labels that denote several countries rather than one."""
    text = country.strip().lower()
    return text == "not reported" or text.startswith(("multi-country", "global", "regional"))


def build_cfu_records(
    projects: pd.DataFrame, country_lookup: dict[str, tuple[str, str]]
) -> list[ProjectRec]:
    """``country_lookup``: exact published name -> (ISO3, mapping method), built only from
    registered sources (GCF countries export, AidData recipient/ISO-3 pairs)."""
    records: list[ProjectRec] = []
    for index, row in enumerate(frame_rows(projects)):
        sheet_row = index + 2  # header is row 1
        name = text_or_none(row.get("Name of Project")) or ""
        country = text_or_none(row.get("Country")) or "not reported"
        mapped = country_lookup.get(country)
        multi = is_multi_country_label(country)
        year_text = text_or_none(row.get("Approved year"))
        year = int(year_text) if year_text and year_text.isdigit() else None
        code_match = GCF_CODE.search(name)
        theme = text_or_none(row.get("Theme/Objective"))
        rec = ProjectRec(
            source_id=SOURCE_ID,
            source_project_id=f"projects-r{sheet_row}",
            record_level="cfu_project_row",
            title=name,
            description=text_or_none(row.get("Summary")),
            source_reference=f"CFU workbook, sheet 'Projects', row {sheet_row}",
            recipient_label=country,
            region=text_or_none(row.get("World Bank Region")),
            multi_country=multi,
            sector_name=text_or_none(row.get("Sector (OECD)")),
            sector_code=text_or_none(row.get("DAC 5 Code")),
            sector_vocabulary="cfu_oecd_sector",
            year=year,
            year_type="approval_year" if year else None,
            date_precision="year" if year else None,
            attributes={
                "fund": text_or_none(row.get("Fund")),
                "fund_type": text_or_none(row.get("Fund Type")),
                "theme_objective": theme,
                "sub_sector": text_or_none(row.get("Sub-Sector")),
                "key_words": text_or_none(row.get("Key words")),
                "implementing_agency": text_or_none(row.get("Implementing Agency")),
                "recipient_institution": text_or_none(row.get("Recipient Institution")),
                "recipient_institution_type": text_or_none(row.get("Recipient Institution type")),
                "income_classification": text_or_none(row.get("Income Classification")),
                "end_year": text_or_none(row.get("End year")),
                "least_developed_country": text_or_none(row.get("Least Developed Country")),
                "small_island_developing_state": text_or_none(
                    row.get("Small Island Developing Nation")
                ),
                "fragile_or_conflict_affected": text_or_none(
                    row.get("Fragile or Conflict Affected State")
                ),
                "gcf_reference_code": code_match.group(1) if code_match else None,
            },
        )
        if multi:
            rec.countries.append(CountryRec(country, None, "multi_country_label"))
            rec.warn(
                "country_not_attributable",
                f"Country '{country}' denotes several countries; amounts are whole-project values "
                "and are not attributed to any one country.",
                "Country",
            )
        elif mapped:
            rec.countries.append(CountryRec(country, mapped[0], mapped[1]))
        else:
            rec.countries.append(CountryRec(country, None, "unmatched_exact_name"))
            rec.warn(
                "country_name_not_mapped",
                f"Country '{country}' has no exact match in a registered country list; it is "
                "kept as published without an ISO3 code (not guessed).",
                "Country",
            )
        rec.warn(
            "no_source_identifier",
            "CFU publishes no project ID; this row's identity is its position in the "
            "registered workbook and is valid only for that file version.",
        )
        if code_match:
            rec.warn(
                "names_gcf_project",
                f"The CFU name cites GCF project {code_match.group(1)}, which GCF also publishes; "
                "never add CFU and GCF amounts for it.",
            )
        if year is None:
            rec.warn("approval_year_missing", "No approval year is published.", "Approved year")
        if theme:
            rec.annotations.append(
                AnnotationRec(
                    annotation_source_id=SOURCE_ID,
                    scheme="cfu_theme_objective",
                    kind="source_classification",
                    label=theme,
                    raw_value=theme,
                    provenance="CFU 'Theme/Objective' as published.",
                )
            )
        _amounts(rec, row, year, multi)
        records.append(rec)
    return records


def _amounts(rec: ProjectRec, row: dict[str, object], year: int | None, multi: bool) -> None:
    def observation(
        key: str, column: str, flow: str, financing: str, component: bool, meaning: str
    ) -> ObservationRec:
        raw = row.get(column)
        amount, status = parse_decimal(raw)
        return ObservationRec(
            key=f"{rec.source_project_id}:{key}",
            flow_kind=flow,
            level="project",
            amount=amount,
            raw_value=None if blank(raw) else str(raw),
            value_status=status,
            unit="millions",
            currency="USD",
            unit_status="stated_in_source",
            price_basis="nominal",
            effective_year=year if flow == "approval" else None,
            date_meaning=meaning,
            source_reference=f"CFU '{column}'",
            multi_country=multi,
            financing_type=financing,
            is_component=component,
        )

    approval_meaning = "CFU approval year" if year else "approval (year not published)"
    rec.observations.append(
        observation("approved", APPROVED, "approval", "all_instruments", False, approval_meaning)
    )
    for column, financing in COMPONENTS.items():
        if not blank(row.get(column)):
            rec.observations.append(
                observation(
                    f"approved_{financing}", column, "approval", financing, True, approval_meaning
                )
            )
    rec.observations.append(
        observation(
            "disbursed_cumulative",
            DISBURSED,
            "disbursement",
            "all_instruments",
            False,
            f"cumulative disbursement as of the {SNAPSHOT}; not dated",
        )
    )
