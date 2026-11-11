"""Migrations, constraints and exact-decimal storage (artificial rows only)."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, delete, insert, inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError, StatementError
from sqlalchemy.orm import Session

from compassio_api.db.migrate import current_revision, downgrade, include_object, upgrade
from compassio_api.db.models import (
    Base,
    ClimateAnnotation,
    FinancialObservation,
    ImportRun,
    Project,
)
from compassio_api.db.session import (
    DatabaseNotReadyError,
    create_read_engine,
    create_write_engine,
)

from .conftest import add_sources


def _run(session: Session) -> int:
    run = ImportRun(
        source_key="example",
        input_sha256={},
        started_at=datetime.now(UTC),
        status="running",
        inserted=0,
        updated=0,
        unchanged=0,
        rejected=0,
        removed=0,
    )
    session.add(run)
    session.flush()
    return run.id


def _project(run_id: int, source_project_id: str = "example_1") -> dict[str, object]:
    return {
        "id": f"aiddata:{source_project_id}",
        "source_id": "aiddata",
        "source_project_id": source_project_id,
        "record_level": "aiddata_record",
        "title": "example_title",
        "multi_country": False,
        "source_reference": "example",
        "attributes": {},
        "content_sha256": "0" * 64,
        "import_run_id": run_id,
    }


def _observation(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "project_id": "aiddata:example_1",
        "source_id": "aiddata",
        "observation_key": "example_1:amount",
        "flow_kind": "commitment",
        "level": "project",
        "is_component": False,
        "amount": Decimal("0.1"),
        "value_status": "reported",
        "unit": "units",
        "currency": "USD",
        "unit_status": "stated_in_source",
        "price_basis": "nominal",
        "date_meaning": "example",
        "multi_country": False,
        "source_reference": "example",
    }
    row.update(overrides)
    return row


def test_migration_creates_schema_matching_models(db_url: str, write_engine: Engine) -> None:
    tables = set(inspect(write_engine).get_table_names())

    assert {
        "sources",
        "import_runs",
        "projects",
        "project_countries",
        "climate_annotations",
        "financial_observations",
        "project_relationships",
        "data_quality_warnings",
    } <= tables
    assert current_revision(write_engine) == "0003"
    with write_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"include_object": include_object})
        assert compare_metadata(context, Base.metadata) == []


def test_downgrade_removes_schema_and_upgrade_restores_it(db_url: str) -> None:
    downgrade(db_url, "base")
    engine = create_write_engine(db_url)
    assert "projects" not in inspect(engine).get_table_names()
    engine.dispose()

    upgrade(db_url)
    engine = create_write_engine(db_url)
    assert "projects" in inspect(engine).get_table_names()
    engine.dispose()


def test_source_project_identity_is_unique(write_engine: Engine) -> None:
    with Session(write_engine) as session:
        add_sources(session)
        run_id = _run(session)
        session.execute(insert(Project), [_project(run_id)])
        session.commit()
        duplicate = _project(run_id)
        duplicate["id"] = "aiddata:example_1_other_id"
        with pytest.raises(IntegrityError):
            session.execute(insert(Project), [duplicate])


def test_decimal_amounts_round_trip_exactly(write_engine: Engine) -> None:
    with Session(write_engine) as session:
        add_sources(session)
        session.execute(insert(Project), [_project(_run(session))])
        session.execute(
            insert(FinancialObservation),
            [
                _observation(),
                _observation(observation_key="example_1:b", amount=Decimal("0.2")),
                _observation(
                    observation_key="example_1:big", amount=Decimal("123456789012345.123456789")
                ),
            ],
        )
        session.commit()
        amounts = session.scalars(
            select(FinancialObservation.amount).order_by(FinancialObservation.observation_key)
        ).all()

    assert amounts == [Decimal("0.1"), Decimal("0.2"), Decimal("123456789012345.123456789")]
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")  # exact, unlike 0.1 + 0.2 floats


def test_binary_float_money_is_refused(write_engine: Engine) -> None:
    with Session(write_engine) as session:
        add_sources(session)
        session.execute(insert(Project), [_project(_run(session))])
        with pytest.raises(StatementError):
            session.execute(insert(FinancialObservation), [_observation(amount=0.1)])


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": None},  # reported but no amount
        {"value_status": "not_reported"},  # amount present but marked missing
        {"flow_kind": "profit"},  # unknown flow kind
        {"unit": "billions"},
        {"currency": "DOLLARS"},
        {"price_basis": "constant_2021_usd", "currency": "EUR"},
    ],
)
def test_observation_check_constraints(write_engine: Engine, overrides: dict[str, object]) -> None:
    with Session(write_engine) as session:
        add_sources(session)
        session.execute(insert(Project), [_project(_run(session))])
        with pytest.raises(IntegrityError):
            session.execute(insert(FinancialObservation), [_observation(**overrides)])


def test_annotations_can_never_be_model_predictions(write_engine: Engine) -> None:
    with Session(write_engine) as session:
        add_sources(session)
        session.execute(insert(Project), [_project(_run(session))])
        with pytest.raises(IntegrityError):
            session.execute(
                insert(ClimateAnnotation),
                [
                    {
                        "project_id": "aiddata:example_1",
                        "annotation_source_id": "research_paper",
                        "scheme": "example",
                        "kind": "research_annotation",
                        "is_model_prediction": True,
                        "provenance": "example",
                    }
                ],
            )


def test_read_engine_is_read_only(seeded_url: str) -> None:
    engine = create_read_engine(seeded_url)
    with Session(engine) as session, pytest.raises(OperationalError):
        session.execute(delete(Project))
    engine.dispose()


def test_read_engine_does_not_create_missing_database(tmp_path: Path) -> None:
    path = tmp_path / "absent.sqlite"
    engine = create_read_engine(f"sqlite:///{path.as_posix()}")

    with pytest.raises(DatabaseNotReadyError), engine.connect():
        pass
    assert not path.exists()
    engine.dispose()
