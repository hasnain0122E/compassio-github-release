"""GCF API enrichment: code matching, dates, units, conflicts, dedup, idempotency (ARTIFICIAL)."""

from decimal import Decimal

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from compassio_api.db.models import FinancialObservation, Project, ProjectEnrichment
from compassio_api.ingest import extended, gcf_api
from compassio_api.ingest.loader import finish_run, start_run

from .conftest import API_RETRIEVED_AT, gcf_api_records, seed, seed_extended


def _view(**overrides: object) -> gcf_api.ExportView:
    values: dict[str, object] = {
        "title": "example_gcf_single",
        "board_meeting": "B.01",
        "theme": "Adaptation",
        "sector_type": "Public",
        "entity": "example_entity",
        "iso3": frozenset({"ZZA"}),
        "fa_financing": Decimal("1000"),
    }
    values.update(overrides)
    return gcf_api.ExportView(**values)  # type: ignore[arg-type]


def _record(ref: str) -> dict[str, object]:
    return next(r for r in gcf_api_records() if r["ApprovedRef"] == ref)


def test_approval_date_comes_from_approval_field_not_other_dates() -> None:
    rec = gcf_api.build_enrichment(
        _record("FP901"), "gcf_projects:FP901", _view(), API_RETRIEVED_AT
    )

    assert str(rec.approval_date) == "2016-03-01"
    assert rec.values["start_date"] == "2099-01-01"  # kept separately, never used as approval
    assert rec.project_status == "Under Implementation"
    assert "LifeTimeCO2" not in str(rec.values.get("countries"))  # ex-ante estimates not imported


def test_top_level_totals_keep_currency_unknown_and_lines_keep_stated_currency() -> None:
    rec = gcf_api.build_enrichment(
        _record("FP901"), "gcf_projects:FP901", _view(), API_RETRIEVED_AT
    )
    by_key = {o.key: o for o in rec.observations}

    total = by_key["FP901:total_gcf"]
    assert total.currency is None and total.unit_status == "not_stated_in_source"
    country = by_key["FP901:country:ZZA:0:gcf"]
    assert (country.currency, country.country_iso3, country.is_component) == ("USD", "ZZA", True)
    assert country.recommended_for_aggregates is True
    line = by_key["FP901:funding:11:B.01"]
    assert line.currency == "USD" and line.amount == Decimal("1000")
    disbursement = by_key["FP901:disbursement:21"]
    assert disbursement.level == "transaction" and str(disbursement.effective_date) == "2017-01-01"


def test_eur_and_relisted_lines_are_kept_but_never_enter_usd_totals() -> None:
    rec = gcf_api.build_enrichment(
        _record("FP902"),
        "gcf_projects:FP902",
        _view(
            title="example_gcf_multi",
            board_meeting="B.02",
            theme="Mitigation",
            sector_type="Private",
            iso3=frozenset({"ZZA", "ZZB"}),
            fa_financing=Decimal("2000"),
        ),
        API_RETRIEVED_AT,
    )
    lines = [o for o in rec.observations if ":funding:" in o.key]

    assert [o.key for o in lines] == ["FP902:funding:31:B.02", "FP902:funding:31:B.09"]
    assert rec.values["identical_funding_lines_skipped"] == 1
    assert {o.currency for o in lines} == {"EUR"}  # never converted
    assert all(o.recommended_for_aggregates is False for o in lines)
    relisted = next(o for o in lines if o.key.endswith("B.09"))
    assert relisted.effective_year is None  # other Board meeting: no date invented
    assert rec.values["country_lines_consistent_with_total"] is True


def test_conflicts_are_recorded_not_overwritten() -> None:
    rec = gcf_api.build_enrichment(
        _record("FP901"),
        "gcf_projects:FP901",
        _view(title="example_other_title", board_meeting="B.99", fa_financing=Decimal("999")),
        API_RETRIEVED_AT,
    )
    fields = {c["field"]: c for c in rec.conflicts}

    assert set(fields) == {"title", "board_meeting", "gcf_financing_total"}
    assert fields["title"]["export_value"] == "example_other_title"
    assert fields["title"]["api_value"] == "example_gcf_single"
    assert "No value is overwritten" in fields["title"]["precedence"]


def test_enrichment_matches_by_code_only_and_reports_unmatched(write_engine: Engine) -> None:
    report = seed_extended(write_engine)["gcf_api_projects"]

    assert report["matched_export_projects"] == 2
    assert report["api_records_not_in_export"] == ["FP999"]
    with Session(write_engine) as session:
        assert session.get(Project, "gcf_projects:FP999") is None  # never created
        enrichment = session.scalars(
            select(ProjectEnrichment).where(ProjectEnrichment.project_id == "gcf_projects:FP902")
        ).one()
    assert enrichment.verification_state == "deterministic_identifier_match"
    assert [c["field"] for c in enrichment.conflicts] == ["title"]


def test_reenrichment_is_idempotent_and_never_duplicates(write_engine: Engine) -> None:
    seed_extended(write_engine)
    with Session(write_engine) as session:
        before = session.scalar(select(func.count()).select_from(FinancialObservation))
        run = start_run(session, "example_again", {})
        again = extended.write_gcf_api_enrichment(
            session, run, gcf_api_records(), "20260102T030405Z", API_RETRIEVED_AT
        )
        finish_run(run, "completed")
        session.commit()
        after = session.scalar(select(func.count()).select_from(FinancialObservation))
        projects = session.scalar(
            select(func.count()).select_from(Project).where(Project.source_id == "gcf_projects")
        )

    assert again["enrichments"] == {"inserted": 0, "updated": 0, "unchanged": 2, "removed": 0}
    assert again["observations"]["inserted"] == 0 and again["observations"]["updated"] == 0
    assert before == after
    assert projects == 2  # enrichment never adds project rows


def test_reingesting_the_export_then_enrichment_restores_links(write_engine: Engine) -> None:
    seed_extended(write_engine)
    seed(write_engine)  # export re-run: unchanged rows keep their enrichment

    with Session(write_engine) as session:
        count = session.scalar(select(func.count()).select_from(ProjectEnrichment))
    assert count == 2
