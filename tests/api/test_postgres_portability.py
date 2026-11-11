"""PostgreSQL portability.

* COMPILE-ONLY checks (always run): every table's DDL and the search/filter SQL compile for
  the PostgreSQL dialect. This proves SQL generation, NOT execution on a PostgreSQL server.
* EXECUTION check: runs only when ``COMPASSIO_TEST_POSTGRES_URL`` points at a disposable
  PostgreSQL database and a driver is installed; otherwise it is SKIPPED (verification pending,
  docs/architecture/postgresql_verification.md). A skip is never reported as a pass.
"""

import os
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from compassio_api.db.models import Base, Project
from compassio_api.services.access import AccessPolicy
from compassio_api.services.finance import METRICS
from compassio_api.services.finance_rows import metric_statement
from compassio_api.services.projects import ProjectQuery, _conditions

PG = postgresql.dialect()  # type: ignore[no-untyped-call]


@pytest.mark.parametrize("table", sorted(Base.metadata.tables))
def test_every_table_compiles_for_postgresql(table: str) -> None:
    ddl = str(CreateTable(Base.metadata.tables[table]).compile(dialect=PG))

    assert ddl.startswith("\nCREATE TABLE")
    if table in {"financial_observations", "country_aggregates", "historical_staging"}:
        assert "NUMERIC(38, 10)" in ddl  # exact decimal on PostgreSQL


def test_search_compiles_to_ilike_without_sqlite_fts() -> None:
    policy = AccessPolicy("local_development", frozenset({"aiddata"}), "example")
    conds = _conditions(ProjectQuery(q="example_text", country="ZZA"), policy, "postgresql")
    sql = str(select(Project.id).where(*conds).compile(dialect=PG))

    assert "ILIKE" in sql.upper()
    assert "projects_fts" not in sql  # the FTS5 pre-filter is SQLite-only


@pytest.mark.skipif(
    not os.environ.get("COMPASSIO_TEST_POSTGRES_URL"),
    reason="PostgreSQL verification pending: set COMPASSIO_TEST_POSTGRES_URL to a disposable DB",
)
def test_postgresql_migration_and_decimal_round_trip() -> None:  # pragma: no cover - env gated
    from sqlalchemy import create_engine, text

    from compassio_api.db.migrate import upgrade

    url = os.environ["COMPASSIO_TEST_POSTGRES_URL"]
    upgrade(url)
    engine = create_engine(url)
    with engine.connect() as connection:
        value = connection.execute(
            text("SELECT CAST('123456789012345.1234567891' AS NUMERIC(38,10))")
        ).scalar()
        indexes = (
            connection.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'projects'")
            )
            .scalars()
            .all()
        )
    engine.dispose()
    assert value == Decimal("123456789012345.1234567891")
    assert "ix_projects_title_trgm" in indexes


@pytest.mark.parametrize("metric_id", sorted(METRICS))
def test_task008_metric_selection_compiles_for_postgresql(metric_id: str) -> None:
    """COMPILE-ONLY (Task 009): the decision engine's metric row selection, with country and
    year filters, generates PostgreSQL SQL. Not an execution check."""
    stmt = metric_statement(METRICS[metric_id], country="ZZA", year_from=2000, year_to=2020)
    sql = str(stmt.compile(dialect=PG))

    assert "financial_observations" in sql
    assert "effective_year >=" in sql and "effective_year <=" in sql


def test_task008_candidate_selection_compiles_for_postgresql() -> None:
    """COMPILE-ONLY: the prioritization candidate query reuses the projects filters."""
    policy = AccessPolicy("hackathon_event", frozenset({"aiddata"}), "example")
    conds = _conditions(ProjectQuery(country="ZZA", sector="example_sector"), policy, "postgresql")
    sql = str(select(Project.id).where(*conds).order_by(Project.id).compile(dialect=PG))

    assert "ORDER BY projects.id" in sql
