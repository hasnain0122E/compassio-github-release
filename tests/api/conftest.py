"""ARTIFICIAL database fixtures for API/ingestion unit tests.

Every value here is invented to exercise logic (``example_*`` titles, ``ZZ*`` country codes,
round test amounts). None of it is a real project, amount or count and none of it may be
reported as data.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from compassio_api.core.config import Settings
from compassio_api.db.migrate import upgrade
from compassio_api.db.models import Source
from compassio_api.db.session import create_write_engine
from compassio_api.ingest.adb import build_adb_records
from compassio_api.ingest.cfu import build_cfu_records
from compassio_api.ingest.gcf import build_gcf_records
from compassio_api.ingest.loader import (
    finish_run,
    rebuild_reference_code_links,
    start_run,
    write_records,
)
from compassio_api.ingest.records import ProjectRec
from compassio_api.ingest.research import build_research_records
from compassio_api.main import create_app

SOURCE_IDS = (
    "research_paper",
    "aiddata",
    "gcf_projects",
    "gcf_countries",
    "climate_funds_update",
    "adb_pakistan",
    "gcf_readiness",
    "climate_project_explorer",
    "gcf_historical",
    "gcf_api_projects",
)
RESTRICTED = {"gcf_historical"}
BACKEND = {"gcf_api_projects"}
EXAMPLE_COUNTRIES = {
    "example_country_a": ("ZZA", "example_region"),
    "example_country_b": ("ZZB", None),
}


def research_row(record_id: str, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "record_id": record_id,
        "research_row_id": f"9{record_id}",
        "title_clean": f"example_title_{record_id}",
        "recipient": "example_country_a",
        "recipient_iso3": "ZZA",
        "recipient_region": "example_region",
        "commitment_year": 2010,
        "commitment_date": "2010-05-01",
        "commitment_date_estimated": False,
        "sector_name": "EXAMPLE SECTOR",
        "sector_code": "999",
        "flow_type": "Loan",
        "flow_class": "ODA-like",
        "intent": "Development",
        "status": "Completion",
        "funding_agencies": "example_agency",
        "funding_agencies_type": "State-owned Policy Bank",
        "recommended_for_aggregates": True,
        "umbrella": False,
        "parent_id": None,
        "amount_original_src": "100.10",
        "amount_currency": "USD",
        "amount_constant_usd_2021": 200.25,
        "amount_estimated": None,
        "rio_marker_src": "0,0,0",
        "rio_overall": 0,
        "rio_mitigation": 0,
        "rio_adaptation": 0,
        "is_climate_related": False,
        "label_error": None,
        "eligibility_status": "eligible",
        "exclusion_reasons": "",
        "retrospective_text_warning": False,
    }
    row.update(overrides)
    return row


def research_frames(rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = pd.DataFrame(rows)
    originals = pd.DataFrame(
        {
            "record_id": [r["record_id"] for r in rows],
            "title_aiddata_src": [r.get("title_src", r["title_clean"]) for r in rows],
            "description_aiddata_src": [
                r.get("description_src", f"example description {r['record_id']}") for r in rows
            ],
        }
    )
    return table, originals


def example_research_records() -> list[ProjectRec]:
    rows = [
        research_row(
            "1",
            rio_marker_src="2,2,0",
            rio_overall=2,
            rio_mitigation=2,
            is_climate_related=True,
            title_clean="example_solar_plant 100% done_ok",
            sector_name="EXAMPLE ENERGY",
        ),
        research_row("2", commitment_year=2012, commitment_date="2012-01-01", parent_id="77"),
        research_row(
            "3",
            commitment_year=2012,
            commitment_date="2012-02-01",
            parent_id="77",
            amount_original_src=None,
            amount_currency=None,
            amount_constant_usd_2021=None,
        ),
        research_row(
            "4",
            recipient="example_region, regional",
            recipient_iso3=None,
            amount_constant_usd_2021=300.0,
        ),
        research_row(
            "5",
            status="Pipeline: Pledge",
            recommended_for_aggregates=False,
            recipient="example_country_b",
            recipient_iso3="ZZB",
            commitment_year=2015,
            commitment_date="2015-01-01",
        ),
    ]
    return build_research_records(*research_frames(rows))


def gcf_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ref #": "FP901",
                "Modality": "PAP",
                "Project Name": "example_gcf_single",
                "Entity": "example_entity",
                "Countries": "example_country_a",
                "BM": "B.01",
                "Sector": "Public",
                "Theme": "Adaptation",
                "Project Size": "Small",
                "ESS Category": "Category B",
                "FA Financing": "1000",
            },
            {
                "Ref #": "FP902",
                "Modality": "SAP",
                "Project Name": "example_gcf_multi",
                "Entity": "example_entity",
                "Countries": "example_country_a, example_country_b, example_unmapped",
                "BM": "B.02",
                "Sector": "Private",
                "Theme": "Mitigation",
                "Project Size": "Micro",
                "ESS Category": "Category C",
                "FA Financing": "2000",
            },
        ],
        dtype=object,
    )


def cfu_frame() -> pd.DataFrame:
    base: dict[str, Any] = {
        "Fund": "example_fund",
        "Fund Type": "Multilateral",
        "World Bank Region": "example_wb_region",
        "Income Classification": "Low income",
        "Theme/Objective": "Adaptation",
        "Sector (OECD)": "Example sector",
        "DAC 5 Code": "DAC999_",
        "Sub-Sector": None,
        "Key words": None,
        "Summary": "example cfu summary",
        "Implementing Agency": "example_agency",
        "Recipient Institution": None,
        "Recipient Institution type": None,
        "End year": None,
        "Concessional loan": None,
        "Guarantee": None,
        "Equity": None,
        "Least Developed Country": "",
        "Small Island Developing Nation": "",
        "Fragile or Conflict Affected State": "",
    }
    rows = [
        {
            **base,
            "Country": "example_country_a",
            "Name of Project": "(FP901) example_gcf_single as listed by CFU",
            "Approved year": "2016",
            "Grant": "1.5",
            "Amount of Funding Approved (USD millions)": "1.5",
            "Disbursed (USD millions)": "0.5",
        },
        {
            **base,
            "Country": "Multi-country (example_country_a, example_country_b)",
            "Name of Project": "example_cfu_multi",
            "Approved year": "2016",
            "Grant": "2",
            "Amount of Funding Approved (USD millions)": "2",
            "Disbursed (USD millions)": " ",
        },
        {
            **base,
            "Country": "example_country_b",
            "Name of Project": "example_cfu_b",
            "Approved year": "2017",
            "Grant": "0.25",
            "Amount of Funding Approved (USD millions)": "0.25",
            "Disbursed (USD millions)": "-0.01",
        },
    ]
    return pd.DataFrame(rows, dtype=object)


def cfu_lookup() -> dict[str, tuple[str, str]]:
    return {name: (iso3, "example_lookup") for name, (iso3, _) in EXAMPLE_COUNTRIES.items()}


def adb_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    activities = pd.DataFrame(
        [
            {
                "iati_identifier": f"XM-DAC-46004-99999-001-LN{n}",
                "title": f"example_adb_instrument_{n}",
                "description": "example adb description",
                "activity_status": "2",
                "default_currency": "USD",
                "recipient_countries": "PK",
                "planned_start": "2019-01-01",
                "actual_start": "2019-03-01" if n == 1 else None,
                "planned_end": None,
                "actual_end": None,
                "document_links": 0,
                "default_finance_type": "410",
            }
            for n in (1, 2)
        ],
        dtype=object,
    )
    tx = [
        ("XM-DAC-46004-99999-001-LN1", "2", "1000", "2019-03-01"),
        ("XM-DAC-46004-99999-001-LN1", "3", "400", "2020-01-01"),
        ("XM-DAC-46004-99999-001-LN1", "3", "-10", "2020-06-01"),
        ("XM-DAC-46004-99999-001-LN1", "6", "50", "2021-01-01"),
        ("XM-DAC-46004-99999-001-LN2", "2", "-5", "2019-04-01"),
    ]
    transactions = pd.DataFrame(
        [
            {
                "iati_identifier": i,
                "transaction_type": t,
                "value": v,
                "value_currency": None,
                "default_currency": "USD",
                "value_date": None,
                "transaction_date": d,
            }
            for i, t, v, d in tx
        ],
        dtype=object,
    )
    sectors = pd.DataFrame(columns=["iati_identifier", "vocabulary", "code", "percentage"])
    return activities, transactions, sectors


def example_records() -> dict[str, list[ProjectRec]]:
    country_map = dict(EXAMPLE_COUNTRIES)
    activities, transactions, sectors = adb_frames()
    return {
        "aiddata": example_research_records(),
        "gcf_projects": build_gcf_records(gcf_frame(), {k: v for k, v in country_map.items()}),
        "climate_funds_update": build_cfu_records(cfu_frame(), cfu_lookup()),
        "adb_pakistan": build_adb_records(activities, transactions, sectors, "example-time"),
    }


def add_sources(session: Session, rights: dict[str, tuple[str, str | None]] | None = None) -> None:
    rights = rights or {}
    for source_id in SOURCE_IDS:
        status, evidence = rights.get(source_id, ("not_reviewed", None))
        session.merge(
            Source(
                source_id=source_id,
                name=f"example source {source_id}",
                publisher="example publisher",
                version_info=None,
                file_relpath=f"raw/{source_id}/example.bin",
                file_sha256="0" * 64,
                reference_url=None,
                rights_status=status,
                rights_evidence=evidence,
                license_notes=None,
                observation_type="example observation",
                audited_record_count=None,
                synced_at=datetime.now(UTC),
                source_registry="backend_staging" if source_id in BACKEND else "canonical",
                access_tier="restricted_internal" if source_id in RESTRICTED else "standard",
            )
        )


def seed(engine: Engine, rights: dict[str, tuple[str, str | None]] | None = None) -> None:
    with Session(engine) as session:
        add_sources(session, rights)
        session.commit()
        for source_id, records in example_records().items():
            run = start_run(session, f"example_{source_id}", {"example": "0" * 64})
            write_records(session, run, source_id, records)
            finish_run(run, "completed")
            session.commit()
        rebuild_reference_code_links(session)
        session.commit()


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'example.sqlite').as_posix()}"
    upgrade(url)
    return url


@pytest.fixture
def write_engine(db_url: str) -> Iterator[Engine]:
    engine = create_write_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def seeded_url(db_url: str, write_engine: Engine) -> str:
    seed(write_engine)
    return db_url


def make_client(url: str, **settings: Any) -> TestClient:
    values: dict[str, Any] = {"database_url": url, "source_data_access": "local_development"}
    values.update(settings)
    return TestClient(create_app(Settings(_env_file=None, **values)))


@pytest.fixture
def data_client(seeded_url: str) -> TestClient:
    return make_client(seeded_url)


def money(value: str) -> Decimal:
    return Decimal(value)


# ------------------------------------------------------------------ Task 006-DB (ARTIFICIAL)
API_RETRIEVED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def gcf_api_records() -> list[dict[str, Any]]:
    """Artificial GCF-API-shaped records (FP901/FP902 match the example export; FP999 does not)."""

    def country(iso3: str, gcf: int, co: int) -> dict[str, Any]:
        return {
            "ISO3": iso3,
            "CountryName": f"example_{iso3}",
            "Region": "example_region",
            "Financing": [{"Currency": "USD", "GCF": gcf, "CoFinancing": co, "Total": gcf + co}],
        }

    def line(
        bid: int, source: str, instrument: str, budget: float, currency: str, bm: str
    ) -> dict[str, Any]:
        return {
            "ProjectBudgetID": bid,
            "BM": bm,
            "Source": source,
            "Instrument": instrument,
            "Budget": budget,
            "BudgetUSDeq": budget,
            "Currency": currency,
        }

    common: dict[str, Any] = {
        "StartDate": "2099-01-01T00:00:00.000Z",  # deliberately unlike the approval date
        "EndDate": None,
        "DurationMonths": 12,
        "Size": "Micro",
        "RiskCategory": "Category C",
        "LifeTimeCO2": 999,
        "DirectBeneficiaries": 999,
        "ResultAreas": [],
        "DateClosing": None,
        "DateCompletion": None,
        "DateImplementationStart": None,
        "DateCancelled": None,
        "Entities": [{"Name": "example_entity", "Acronym": "example_entity"}],
    }
    return [
        {
            **common,
            "ProjectsID": 1,
            "ApprovedRef": "FP901",
            "BoardMeeting": "B.01",
            "ProjectName": "example_gcf_single",
            "ApprovalDate": "2016-03-01T00:00:00.000Z",
            "Theme": "Adaptation",
            "Sector": "Public",
            "Status": "Under Implementation",
            "TotalGCFFunding": 1000,
            "TotalCoFinancing": 500,
            "TotalValue": 1500,
            "ProjectURL": "https://example.invalid/project/FP901",
            "Countries": [country("ZZA", 1000, 500)],
            "Funding": [
                line(11, "GCF", "Grants", 1000, "USD", "B.01"),
                line(12, "Co-Financing", "Grants", 500, "USD", "B.01"),
            ],
            "Disbursements": [
                {
                    "ProjectDisbursementID": 21,
                    "AmountDisbursed": 400,
                    "Currency": "USD",
                    "DateEffective": "2017-01-01",
                }
            ],
        },
        {
            **common,
            "ProjectsID": 2,
            "ApprovedRef": "FP902",
            "BoardMeeting": "B.02",
            "ProjectName": "example_gcf_multi renamed",  # conflicts with the export title
            "ApprovalDate": "2017-05-05T00:00:00.000Z",
            "Theme": "Mitigation",
            "Sector": "Private",
            "Status": "Approved",
            "TotalGCFFunding": 2000,
            "TotalCoFinancing": None,
            "TotalValue": 2000,
            "ProjectURL": "https://example.invalid/project/FP902",
            "Countries": [country("ZZA", 1200, 0), country("ZZB", 800, 0)],
            "Funding": [
                line(31, "GCF", "Senior Loans", 1800, "EUR", "B.02"),
                line(31, "GCF", "Senior Loans", 1800, "EUR", "B.02"),  # identical repeat
                line(31, "GCF", "Senior Loans", 1800, "EUR", "B.09"),  # re-listed later
            ],
            "Disbursements": [],
        },
        {
            **common,
            "ProjectsID": 3,
            "ApprovedRef": "FP999",
            "BoardMeeting": "B.03",
            "ProjectName": "example_api_only",
            "ApprovalDate": "2018-01-01T00:00:00.000Z",
            "Theme": "Adaptation",
            "Sector": "Public",
            "Status": "Approved",
            "TotalGCFFunding": 10,
            "TotalCoFinancing": 0,
            "TotalValue": 10,
            "ProjectURL": "https://example.invalid/project/FP999",
            "Countries": [country("ZZA", 10, 0)],
            "Funding": [],
            "Disbursements": [],
        },
    ]


def readiness_frame() -> pd.DataFrame:
    rows = [
        ("ZZA-RS-001", "example_readiness_a", "example_country_a", "Closed", "May 1, 2015", "1000"),
        (
            "example_roster",
            "example_readiness_b",
            "example_country_b",
            "Cancelled",
            "Jun 2, 2016",
            "1",
        ),
        (
            "example_roster",
            "example_readiness_c",
            "example_country_a",
            "Disbursed",
            "bad date",
            "300",
        ),
        (None, "example_readiness_d", "example_unmapped", "Closed", "Jul 3, 2017", "400"),
    ]
    return pd.DataFrame(
        [
            {
                "Ref #": ref,
                "Activity": "example activity",
                "Project Title": title,
                "Country": country,
                "Delivery Partner": "example_partner",
                "Region": "EX",
                "SIDS": "FALSE",
                "LDCs": "FALSE",
                "NAP": "FALSE",
                "Status": status,
                "Approved Date": approved,
                "Financing": amount,
            }
            for ref, title, country, status, approved, amount in rows
        ],
        dtype=object,
    )


def countries_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ISO3": "ZZA",
                "Country Name": "example_country_a",
                "Region": "example_region",
                "SIDS": "FALSE",
                "LDCs": "TRUE",
                "# RP": "2",
                "# FA": "1",
                "RP Financing $": "100.5",
                "FA Financing $": "1000",
            }
        ],
        dtype=object,
    )


def cpe_frame() -> pd.DataFrame:
    def doc(slug: str, fund: str, title: str, summary: str) -> dict[str, Any]:
        return {
            "Family Name": f"example family {slug}",
            "Family Summary": summary,
            "Family Publication Date": "2025-02-03T00:00:00+00:00",
            "Family URL": f"https://example.invalid/document/{slug}-family",
            "Document Title": title,
            "Document URL": f"https://example.invalid/documents/{slug}",
            "Document Content URL": f"https://example.invalid/content/{slug}.pdf",
            "Document Type": "Approved funding proposal",
            "Geographies": "ZZA;ZZB",
            "Category": "MCF",
            "Languages": "English",
            "Source": fund,
        }

    return pd.DataFrame(
        [
            doc("doc-one", "GCF", "example proposal FP901", "about FP901"),
            doc("doc-two", "GCF", "example joint FP901 FP902", "covers two"),
            doc("doc-three", "GEF", "example GEF doc FP901", "not a GCF document"),
            doc("doc-four", "GCF", "example FP777 missing", "code not in export"),
        ],
        dtype=object,
    )


def historical_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ref_N": "FP901",
                "Theme": "Adaptation",
                "AccEnt": "example",
                "Tot_Fin": "1.5",
                "Continent": "example",
                "Acc_mod": "Direct",
            },
            {
                "Ref_N": "FP888",
                "Theme": "Mitigation",
                "AccEnt": "example",
                "Tot_Fin": "USD 9 000",
                "Continent": "example",
                "Acc_mod": "International",
            },
        ],
        dtype=object,
    )


def seed_extended(
    engine: Engine, rights: dict[str, tuple[str, str | None]] | None = None
) -> dict[str, Any]:
    """Core example seed plus every Task 006-DB source, through the real writers."""
    from datetime import date as _date

    from compassio_api.ingest import extended, remaining

    seed(engine, rights)
    report: dict[str, Any] = {}
    with Session(engine) as session:
        steps: list[tuple[str, Any]] = [
            (
                "gcf_readiness",
                lambda run: write_records(
                    session,
                    run,
                    "gcf_readiness",
                    remaining.build_readiness_records(readiness_frame(), dict(EXAMPLE_COUNTRIES)),
                ).as_dict(),
            ),
            (
                "gcf_countries",
                lambda run: extended.write_country_aggregates(
                    session,
                    run,
                    "gcf_countries",
                    remaining.build_country_aggregates(countries_frame(), _date(2026, 1, 1)),
                ),
            ),
            (
                "climate_project_explorer",
                lambda run: extended.write_documents(
                    session, run, "climate_project_explorer", remaining.build_documents(cpe_frame())
                ),
            ),
            (
                "gcf_historical",
                lambda run: extended.write_historical(
                    session, run, "gcf_historical", remaining.build_historical(historical_frame())
                ),
            ),
            (
                "gcf_api_projects",
                lambda run: extended.write_gcf_api_enrichment(
                    session, run, gcf_api_records(), "20260102T030405Z", API_RETRIEVED_AT
                ),
            ),
        ]
        for key, write in steps:
            run = start_run(session, f"example_{key}", {"example": "0" * 64})
            report[key] = write(run)
            finish_run(run, "completed")
            session.commit()
        report["document_links"] = extended.rebuild_document_links(session)
        report["groups"] = extended.rebuild_record_groups(session)
        session.commit()
    return report


@pytest.fixture
def extended_url(db_url: str, write_engine: Engine) -> str:
    seed_extended(write_engine)
    return db_url
