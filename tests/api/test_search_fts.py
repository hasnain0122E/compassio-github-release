"""SQLite FTS5 trigram pre-filter: exact equivalence with the plain LIKE scan (ARTIFICIAL)."""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, update
from sqlalchemy.orm import Session

from compassio_api.db.models import Project

from .conftest import make_client


def _path(url: str) -> Path:
    return Path(url.removeprefix("sqlite:///"))


def _like_ids(url: str, q: str) -> set[str]:
    pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    with sqlite3.connect(_path(url)) as con:
        return {
            r[0]
            for r in con.execute(
                "select id from projects where title like ? escape '\\' "
                "or description like ? escape '\\'",
                (pattern, pattern),
            )
        }


def _api_ids(client: TestClient, q: str) -> set[str]:
    body = client.get("/api/v1/projects", params={"q": q, "page_size": 100}).json()
    return {i["id"] for i in body["items"]}


@pytest.mark.parametrize(
    "q",
    [
        "example",
        "EXAMPLE_SOLAR",
        "100%",
        "0%",
        "done_ok",
        "d_ne",
        "ple_",
        "desc",
        "xyz_nothing",
        "a",
    ],
)
def test_fts_prefilter_returns_exactly_the_like_matches(seeded_url: str, q: str) -> None:
    client = make_client(seeded_url)

    assert _api_ids(client, q) == _like_ids(seeded_url, q)


def test_fts_index_follows_inserts_updates_and_deletes(
    seeded_url: str, write_engine: Engine
) -> None:
    client = make_client(seeded_url)
    assert _api_ids(client, "renamed_marker") == set()
    with Session(write_engine) as session:
        session.execute(
            update(Project).where(Project.id == "aiddata:2").values(title="renamed_marker x")
        )
        session.commit()
    assert _api_ids(make_client(seeded_url), "renamed_marker") == {"aiddata:2"}
    with Session(write_engine) as session:
        session.execute(delete(Project).where(Project.id == "aiddata:2"))
        session.commit()
    assert _api_ids(make_client(seeded_url), "renamed_marker") == set()
    with sqlite3.connect(_path(seeded_url)) as con:
        projects = con.execute("select count(*) from projects").fetchone()[0]
        indexed = con.execute("select count(*) from projects_fts").fetchone()[0]
    assert projects == indexed


def test_fts_query_syntax_is_inert(seeded_url: str) -> None:
    client = make_client(seeded_url)
    for q in ['"', 'example" OR "x', "NEAR(example)", "example*", "title:example", "-example"]:
        response = client.get("/api/v1/projects", params={"q": q})
        assert response.status_code == 200
        assert {i["id"] for i in response.json()["items"]} == _like_ids(seeded_url, q)
