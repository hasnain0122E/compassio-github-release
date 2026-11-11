"""Readiness, documents, country aggregates, historical staging, groups (ARTIFICIAL)."""

from datetime import date
from pathlib import Path

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from compassio_api.db.models import (
    CountryAggregate,
    Document,
    DocumentLink,
    FinancialObservation,
    HistoricalStagingRecord,
    Project,
    RecordGroup,
)
from compassio_api.ingest import remaining
from compassio_api.services.access import resolve_policy

from .conftest import EXAMPLE_COUNTRIES, cpe_frame, readiness_frame, seed_extended


def test_readiness_identity_dates_and_amounts() -> None:
    recs = remaining.build_readiness_records(readiness_frame(), dict(EXAMPLE_COUNTRIES))
    ids = [r.source_project_id for r in recs]

    assert ids == ["ZZA-RS-001", "row-3", "row-4", "row-5"]  # repeated/blank refs -> row
    assert all(r.record_level == "gcf_readiness_grant" for r in recs)
    assert (
        str(recs[0].date_value) == "2015-05-01" and recs[0].year_type == "readiness_approval_year"
    )
    assert recs[2].date_value is None  # unparseable date not guessed
    obs = recs[0].observations[0]
    assert obs.flow_kind == "readiness_grant" and obs.currency is None and obs.unit is None
    assert any(w.code == "placeholder_amount" for w in recs[1].warnings)
    assert recs[3].countries[0].iso3 is None


def test_readiness_grants_are_not_funded_projects(write_engine: Engine) -> None:
    seed_extended(write_engine)
    with Session(write_engine) as session:
        gcf = session.scalar(
            select(func.count()).select_from(Project).where(Project.source_id == "gcf_projects")
        )
        readiness = session.scalar(
            select(func.count()).select_from(Project).where(Project.source_id == "gcf_readiness")
        )

    assert (gcf, readiness) == (2, 4)


def test_documents_are_not_projects_and_link_only_by_gcf_code(write_engine: Engine) -> None:
    report = seed_extended(write_engine)
    with Session(write_engine) as session:
        docs = session.scalar(select(func.count()).select_from(Document))
        cpe_projects = session.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.source_id == "climate_project_explorer")
        )
        links = {
            (link.document_id.split(":", 1)[1], link.project_id, link.verification_state)
            for link in session.scalars(select(DocumentLink))
        }

    assert (docs, cpe_projects) == (4, 0)
    assert links == {
        ("doc-one", "gcf_projects:FP901", "deterministic_identifier_match"),
        ("doc-two", "gcf_projects:FP901", "candidate_requires_review"),
        ("doc-two", "gcf_projects:FP902", "candidate_requires_review"),
    }  # GEF doc ignored; FP777 has no export row
    assert report["document_links"]["codes_without_gcf_project"] == 1


def test_document_date_is_a_catalogue_date_not_approval() -> None:
    doc = remaining.build_documents(cpe_frame())[0]

    assert doc["document_date"] == date(2025, 2, 3)
    assert "not a project approval date" in doc["document_date_type"]
    assert doc["id"] == "climate_project_explorer:doc-one"


def test_country_aggregates_are_separate_snapshots(write_engine: Engine) -> None:
    seed_extended(write_engine)
    with Session(write_engine) as session:
        rows = {a.measure: a for a in session.scalars(select(CountryAggregate))}
        in_obs = session.scalar(
            select(func.count())
            .select_from(FinancialObservation)
            .where(FinancialObservation.source_id == "gcf_countries")
        )

    assert set(rows) == {
        "readiness_count",
        "funded_activity_count",
        "readiness_financing",
        "funded_activity_financing",
    }
    assert rows["funded_activity_financing"].currency == "USD"
    assert rows["funded_activity_count"].currency is None
    assert str(rows["readiness_financing"].amount) == "100.5"
    assert in_obs == 0


def test_snapshot_date_from_export_file_name() -> None:
    assert remaining.export_snapshot_date(Path("ODL-Export-countries-1794139570848.xlsx")) == date(
        2026, 11, 8
    )
    assert remaining.export_snapshot_date(Path("no-epoch.xlsx")) is None


def test_historical_is_staged_restricted_and_never_served(write_engine: Engine) -> None:
    report = seed_extended(write_engine)["gcf_historical"]
    with Session(write_engine) as session:
        rows = {r.source_record_id: r for r in session.scalars(select(HistoricalStagingRecord))}
        policy = resolve_policy(session, "local_development")

    assert report["matched_to_current_export"] == 1
    assert rows["FP901"].total_financing is not None and rows["FP901"].unit == "thousands"
    assert rows["FP888"].value_status == "unparseable"
    assert not policy.allows("gcf_historical")  # even in local development


def test_record_groups_carry_method_and_verification(write_engine: Engine) -> None:
    seed_extended(write_engine)
    with Session(write_engine) as session:
        groups = {g.group_key: g for g in session.scalars(select(RecordGroup))}

    adb = groups["adb_project:99999-001"]
    assert adb.member_count == 2 and adb.member_relation_type == "instrument_of_adb_project"
    assert adb.verification_state == "deterministic_identifier_structure"
    assert groups["aiddata_parent:77"].member_count == 2
