"""Alembic environment: online migrations only, URL supplied by compassio_api.db.migrate.

SQLite note: batch migrations rebuild a table (copy -> drop -> rename) to change constraints.
With ``PRAGMA foreign_keys=ON`` the drop of a referenced table (e.g. ``sources``) fails on a
populated database, so foreign-key enforcement is switched off for the migration only, and
``PRAGMA foreign_key_check`` must report no violations before it is switched back on.
"""

from alembic import context

from compassio_api.db.migrate import include_object
from compassio_api.db.models import Base
from compassio_api.db.session import create_write_engine

config = context.config
target_metadata = Base.metadata


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("sqlalchemy.url is not configured")
    engine = create_write_engine(url)
    with engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()  # a PRAGMA inside a transaction would be ignored
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=sqlite,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()
        if sqlite:
            connection.commit()
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
            if violations:
                raise RuntimeError(f"foreign key violations after migration: {violations[:5]}")
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("offline (SQL script) migrations are not supported; run online")
run_migrations_online()
