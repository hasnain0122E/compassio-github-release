"""search indexes: SQLite FTS5 trigram pre-filter / PostgreSQL pg_trgm GIN

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-09

SQLite: an external-content FTS5 table over projects(title, description) with the TRIGRAM
tokenizer (case-insensitive substring matching), kept in sync by triggers. It is used only to
pre-select candidate rows; the original literal LIKE condition still decides every match, so
search results are unchanged (docs/architecture/search_performance.md).

PostgreSQL (NOT executed in this environment): pg_trgm GIN indexes, which ILIKE uses directly.
Creating the extension may need a privileged role.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SQLITE_UP = (
    "CREATE VIRTUAL TABLE projects_fts USING fts5("
    "title, description, content='projects', content_rowid='rowid', tokenize='trigram')",
    "CREATE TRIGGER projects_fts_ai AFTER INSERT ON projects BEGIN "
    "INSERT INTO projects_fts(rowid, title, description) "
    "VALUES (new.rowid, new.title, new.description); END",
    "CREATE TRIGGER projects_fts_ad AFTER DELETE ON projects BEGIN "
    "INSERT INTO projects_fts(projects_fts, rowid, title, description) "
    "VALUES ('delete', old.rowid, old.title, old.description); END",
    "CREATE TRIGGER projects_fts_au AFTER UPDATE ON projects BEGIN "
    "INSERT INTO projects_fts(projects_fts, rowid, title, description) "
    "VALUES ('delete', old.rowid, old.title, old.description); "
    "INSERT INTO projects_fts(rowid, title, description) "
    "VALUES (new.rowid, new.title, new.description); END",
    "INSERT INTO projects_fts(projects_fts) VALUES ('rebuild')",
)
SQLITE_DOWN = (
    "DROP TRIGGER IF EXISTS projects_fts_au",
    "DROP TRIGGER IF EXISTS projects_fts_ad",
    "DROP TRIGGER IF EXISTS projects_fts_ai",
    "DROP TABLE IF EXISTS projects_fts",
)
POSTGRES_UP = (
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    "CREATE INDEX IF NOT EXISTS ix_projects_title_trgm ON projects USING gin (title gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS ix_projects_description_trgm "
    "ON projects USING gin (description gin_trgm_ops)",
)
POSTGRES_DOWN = (
    "DROP INDEX IF EXISTS ix_projects_description_trgm",
    "DROP INDEX IF EXISTS ix_projects_title_trgm",
)


def _run(statements: Sequence[str]) -> None:
    for statement in statements:
        op.execute(statement)


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _run(SQLITE_UP)
    elif dialect == "postgresql":
        _run(POSTGRES_UP)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _run(SQLITE_DOWN)
    elif dialect == "postgresql":
        _run(POSTGRES_DOWN)
