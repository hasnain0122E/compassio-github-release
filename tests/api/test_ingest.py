"""Builders and the idempotent loader, on ARTIFICIAL frames (logic only, not data)."""

from collections import Counter
from decimal import Decimal

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from compassio_api.db.models import (
    FinancialObservation,
    Project,
    ProjectRelationship,
)
from compassio_api.ingest.cfu import build_cfu_records, is_multi_country_label
from compassio_api.ingest.gcf import build_gcf_records
from compassio_api.ingest.loader import finish_run, start_run, write_records
from compassio_api.ingest.records import ObservationRec, ProjectRec, parse_decimal
from compassio_api.ingest.research import build_research_records
from compassio_api.ingest.runner import country_lookup

from .conftest import (
    EXAMPLE_COUNTRIES,
    adb_frames,
    cfu_frame,
    cfu_lookup,
    example_research_records,
    gcf_frame,
    research_frames,
    research_row,
    seed,
)


def _obs(rec: ProjectRec, suffix: str) -> ObservationRec:
    return next(o for o in rec.observations if o.key.endswith(suffix))


def _ingest(engine: Engine, source_id: str, records: list[ProjectRec]) -> dict[str, int]:
    with Session(engine) as session:
        run = start_run(session, "example", {})
        result = write_records(session, run, source_id, records)
        finish_run(run, "completed")
        session.commit()
    return {
        "inserted": result.inserted,
        "updated": result.updated,
        "unchanged": result.unchanged,
        "rejected": result.rejected,
        "removed": result.removed,
    }


def _count(engine: Engine, model: type) -> int:
    with Session(engine) as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


# ------------------------------------------------------------------------------- parsing
def test_parse_decimal_never_turns_missing_into_zero() -> None:
    assert parse_decimal(None) == (None, "not_reported")
    assert parse_decimal("  ") == (None, "not_reported")
    assert parse_decimal(float("nan")) == (None, "not_reported")
    assert parse_decimal("USD 220 000,00") == (None, "unparseable")
    assert parse_decimal("0") == (Decimal("0"), "reported")
    assert parse_decimal(0.1) == (Decimal("0.1"), "reported")  # shortest repr, not 0.1000000001
    assert parse_decimal("1,250.5") == (Decimal("1250.5"), "reported")


# ------------------------------------------------------------------------------- builders
def test_research_records_keep_annotation_provenance_and_missing_amounts() -> None:
    recs = {r.source_project_id: r for r in example_research_records()}

    climate = recs["1"]
    assert climate.id == "aiddata:1"
    assert climate.annotations[0].kind == "research_annotation"
    assert climate.annotations[0].is_climate_related is True
    assert climate.annotations[0].annotation_source_id == "research_paper"
    original = _obs(climate, "amount_original_currency")
    assert original.amount == Decimal("100.10")
    assert original.currency == "USD"

    missing = recs["3"]
    for suffix in ("amount_original_currency", "amount_constant_usd_2021"):
        obs = _obs(missing, suffix)
        assert obs.amount is None
        assert obs.value_status == "not_reported"
    assert any(w.code == "amount_not_reported" for w in missing.warnings)
    assert missing.group_key == "aiddata_parent:77"


def test_research_regional_recipient_is_not_attributed_and_pledge_is_not_commitment() -> None:
    recs = {r.source_project_id: r for r in example_research_records()}

    regional = recs["4"]
    assert regional.multi_country is True
    assert regional.countries[0].iso3 is None
    assert all(o.multi_country for o in regional.observations)

    pledge = recs["5"]
    assert {o.flow_kind for o in pledge.observations} == {"pledge"}
    assert {w.code for w in pledge.warnings} >= {
        "pledge_not_commitment",
        "not_recommended_for_aggregates",
    }


def test_unparseable_research_label_is_not_invented() -> None:
    table, originals = research_frames([research_row("9", label_error="example parse error")])

    rec = build_research_records(table, originals)[0]

    assert rec.annotations == []
    assert any(w.code == "climate_annotation_unparseable" for w in rec.warnings)


def test_gcf_currency_unknown_and_multi_country_kept_whole() -> None:
    recs = {r.source_project_id: r for r in build_gcf_records(gcf_frame(), dict(EXAMPLE_COUNTRIES))}

    single, multi = recs["FP901"], recs["FP902"]
    assert single.multi_country is False and single.countries[0].iso3 == "ZZA"
    obs = single.observations[0]
    assert obs.currency is None and obs.unit is None
    assert obs.unit_status == "not_stated_in_source"
    assert obs.amount == Decimal("1000")
    assert multi.multi_country is True
    assert [c.iso3 for c in multi.countries] == ["ZZA", "ZZB", None]
    assert {w.code for w in multi.warnings} >= {
        "multi_country_whole_project_amount",
        "country_name_not_mapped",
    }


def test_cfu_units_components_blank_and_gcf_codes() -> None:
    recs = build_cfu_records(cfu_frame(), cfu_lookup())
    first, multi, third = recs

    approved = _obs(first, ":approved")
    assert approved.unit == "millions" and approved.currency == "USD"
    assert _obs(first, "approved_grant").is_component is True
    assert first.attributes["gcf_reference_code"] == "FP901"
    assert multi.multi_country is True and multi.countries[0].iso3 is None
    assert _obs(multi, "disbursed_cumulative").value_status == "not_reported"
    assert _obs(third, "disbursed_cumulative").amount == Decimal("-0.01")
    assert first.source_project_id == "projects-r2"


def test_cfu_multi_country_labels() -> None:
    for label in ("Multi-country", "Multi-country (A, B)", "Global", "Global (A)", "Regional - X"):
        assert is_multi_country_label(label)
    assert not is_multi_country_label("example_country_a")


def test_country_lookup_drops_conflicting_names() -> None:
    lookup = country_lookup(
        {"example_a": ("ZZA", None), "example_c": ("ZZC", None)},
        {"example_a": "ZZA", "example_b": "ZZB", "example_c": "ZZX"},
    )

    assert lookup == {
        "example_a": ("ZZA", "gcf_countries_exact_name"),
        "example_b": ("ZZB", "aiddata_recipient_exact_name"),
    }


def test_adb_transactions_keep_types_and_group_by_project_number() -> None:
    from compassio_api.ingest.adb import build_adb_records

    recs = build_adb_records(*adb_frames(), "example-time")

    assert {r.group_key for r in recs} == {"adb_project:99999-001"}
    flows = Counter(o.flow_kind for o in recs[0].observations)
    assert flows == {"commitment": 1, "disbursement": 2, "repayment_principal": 1}
    assert recs[0].year == 2019 and recs[0].year_type == "activity_actual_start"
    assert recs[1].year_type == "activity_planned_start"
    assert all(o.level == "transaction" for o in recs[0].observations)
    assert recs[0].countries[0].iso3 == "PAK"


# ------------------------------------------------------------------------------- loader
def test_reingestion_is_idempotent(write_engine: Engine) -> None:
    seed(write_engine)
    projects, observations = (
        _count(write_engine, Project),
        _count(write_engine, FinancialObservation),
    )

    result = _ingest(write_engine, "aiddata", example_research_records())

    assert result == {"inserted": 0, "updated": 0, "unchanged": 5, "rejected": 0, "removed": 0}
    assert _count(write_engine, Project) == projects
    assert _count(write_engine, FinancialObservation) == observations


def test_changed_record_is_updated_and_missing_record_removed(write_engine: Engine) -> None:
    seed(write_engine)
    records = example_research_records()
    records[0].title = "example_title_changed"

    result = _ingest(write_engine, "aiddata", records[:-1])

    assert result["updated"] == 1 and result["removed"] == 1 and result["unchanged"] == 3
    with Session(write_engine) as session:
        assert session.get_one(Project, "aiddata:1").title == "example_title_changed"
        assert session.get(Project, "aiddata:5") is None
        orphans = session.scalar(
            select(func.count())
            .select_from(FinancialObservation)
            .where(FinancialObservation.project_id == "aiddata:5")
        )
    assert orphans == 0


def test_invalid_and_duplicate_records_are_rejected(write_engine: Engine) -> None:
    seed(write_engine)
    records = example_research_records()
    records[1].title = "  "
    records.append(example_research_records()[2])  # same id twice

    result = _ingest(write_engine, "aiddata", records)

    assert result["rejected"] == 2
    assert result["removed"] == 1  # the rejected record is no longer validly present


def test_contract_violations_are_stored_as_invalid_not_coerced(write_engine: Engine) -> None:
    seed(write_engine)
    with Session(write_engine) as session:
        rows = dict(
            session.execute(
                select(FinancialObservation.observation_key, FinancialObservation.value_status)
            ).all()
        )

    assert rows["projects-r4:disbursed_cumulative"] == "invalid"  # negative project-level
    assert rows["XM-DAC-46004-99999-001-LN2:tx0"] == "invalid"  # negative commitment
    assert rows["XM-DAC-46004-99999-001-LN1:tx2"] == "reported"  # transaction-level reversal


def test_cross_source_links_are_explicit_and_rebuilt_idempotently(write_engine: Engine) -> None:
    seed(write_engine)
    seed(write_engine)

    with Session(write_engine) as session:
        links = session.scalars(select(ProjectRelationship)).all()

    assert [(x.from_project_id, x.to_project_id, x.status) for x in links] == [
        ("climate_funds_update:projects-r2", "gcf_projects:FP901", "probable_match_reference_code")
    ]
    assert links[0].human_reviewed is False
