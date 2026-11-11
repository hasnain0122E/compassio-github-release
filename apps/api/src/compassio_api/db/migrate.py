"""Programmatic Alembic configuration (no alembic.ini needed; works from any directory)."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

from compassio_api.db.session import create_write_engine

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
# Objects created by raw-SQL migrations (FTS5 virtual table + its shadow tables) that are not
# SQLAlchemy models; excluded from autogenerate / schema comparison.
UNMODELLED_PREFIXES = ("projects_fts",)


def include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    return not (type_ == "table" and name is not None and name.startswith(UNMODELLED_PREFIXES))


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    engine = create_write_engine(database_url)  # creates the SQLite folder if needed
    engine.dispose()
    command.upgrade(alembic_config(database_url), revision)


def downgrade(database_url: str, revision: str) -> None:
    command.downgrade(alembic_config(database_url), revision)


def current_revision(engine: Engine) -> str | None:
    if not inspect(engine).has_table("alembic_version"):
        return None
    with engine.connect() as connection:
        row = connection.exec_driver_sql("SELECT version_num FROM alembic_version").first()
    return None if row is None else str(row[0])
