"""Source B: GCF funded projects export (379 FP/SAP projects).

* Identity: the GCF reference code (``Ref #``).
* Countries: comma-separated names mapped to ISO3 **only** through GCF's own registered country
  export (``gcf_countries``: exact name match). Unmatched names keep ``iso3 = None``.
* ``FA Financing``: the header states no currency or unit (financial_fields_audit.md). Both are
  kept **unknown**; the amount is shown as published and is never used in a total.
* The export has no description, approval date or status. Board meeting code (``BM``) is kept
  as an attribute, not converted into a date.
* GCF approval does not mean a project is open to new funding.
"""

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

SOURCE_ID = "gcf_projects"


def gcf_country_map(countries: pd.DataFrame) -> dict[str, tuple[str, str | None]]:
    """Exact ``Country Name`` -> (ISO3, GCF region) from the GCF countries export."""
    mapping: dict[str, tuple[str, str | None]] = {}
    for row in frame_rows(countries):
        name, iso3 = text_or_none(row.get("Country Name")), text_or_none(row.get("ISO3"))
        if name and iso3:
            mapping[name] = (iso3, text_or_none(row.get("Region")))
    return mapping


def build_gcf_records(
    projects: pd.DataFrame, country_map: dict[str, tuple[str, str | None]]
) -> list[ProjectRec]:
    records: list[ProjectRec] = []
    for row in frame_rows(projects):
        ref = text_or_none(row.get("Ref #")) or ""
        names = split_country_list(text_or_none(row.get("Countries")))
        multi = len(names) != 1
        board = text_or_none(row.get("BM"))
        theme = text_or_none(row.get("Theme"))
        rec = ProjectRec(
            source_id=SOURCE_ID,
            source_project_id=ref,
            record_level="gcf_funded_project",
            title=text_or_none(row.get("Project Name")) or "",
            source_reference=f"GCF funded projects export, Ref # {ref}",
            recipient_label=text_or_none(row.get("Countries")),
            multi_country=multi,
            attributes={
                "gcf_reference_code": ref,
                "modality": text_or_none(row.get("Modality")),
                "accredited_entity": text_or_none(row.get("Entity")),
                "board_meeting": board,
                "gcf_sector_type": text_or_none(row.get("Sector")),
                "theme": theme,
                "project_size": text_or_none(row.get("Project Size")),
                "ess_category": text_or_none(row.get("ESS Category")),
                "approval_note": "Approved by the GCF Board; not an open funding opportunity.",
            },
        )
        regions: set[str] = set()
        for name in names:
            match = country_map.get(name)
            if match is None:
                rec.countries.append(CountryRec(name, None, "unmatched_in_gcf_countries"))
                rec.warn(
                    "country_name_not_mapped",
                    f"Country '{name}' has no exact match in the GCF countries export.",
                    "Countries",
                )
            else:
                rec.countries.append(CountryRec(name, match[0], "gcf_countries_exact_name"))
                if match[1]:
                    regions.add(match[1])
        rec.region = regions.pop() if len(regions) == 1 else None
        if multi:
            rec.warn(
                "multi_country_whole_project_amount",
                f"Multi-country project ({len(names)} countries): the amount is for the whole "
                "project and is never attributed to one country.",
                "FA Financing",
            )
        rec.warn(
            "no_description_or_approval_date",
            f"The export has no description or approval date (board meeting {board}).",
        )
        rec.warn(
            "currency_and_unit_not_stated",
            "The export does not state the currency or unit of 'FA Financing'; it is shown as "
            "published and is not used in any total.",
            "FA Financing",
        )
        if theme:
            rec.annotations.append(
                AnnotationRec(
                    annotation_source_id=SOURCE_ID,
                    scheme="gcf_theme",
                    kind="source_classification",
                    label=theme,
                    raw_value=theme,
                    provenance="GCF 'Theme' as published (Adaptation, Mitigation, Cross-cutting).",
                )
            )
        amount, status = parse_decimal(row.get("FA Financing"))
        rec.observations.append(
            ObservationRec(
                key=f"{ref}:fa_financing",
                flow_kind="gcf_financing",
                level="project",
                amount=amount,
                raw_value=text_or_none(row.get("FA Financing")),
                value_status=status,
                unit=None,
                currency=None,
                unit_status="not_stated_in_source",
                price_basis="unspecified",
                date_meaning=f"GCF Board approval at meeting {board}; no calendar date in export",
                source_reference="GCF export 'FA Financing' (GCF funding only; no co-finance)",
                multi_country=multi,
            )
        )
        records.append(rec)
    return records
