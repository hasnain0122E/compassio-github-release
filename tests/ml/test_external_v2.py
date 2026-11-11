"""Unit tests for the ML v2 external-data workflow (Task 006-ML).

All fixtures are ARTIFICIAL (``example_*`` identifiers, ``example.invalid`` hosts). They exercise
logic only and are not observations of any real project.
"""

import io
import json
import urllib.request
from pathlib import Path
from typing import IO
from xml.etree.ElementTree import fromstring

import pandas as pd
import pytest

from compassio_ml.external import gcf, iati, worldbank
from compassio_ml.external.fetch import FetchError, FetchLimits, SafeFetcher
from compassio_ml.external.linkage import assign_groups, evidence_links, link, stable_id
from compassio_ml.external.paths import UnsafePathError, V2Paths
from compassio_ml.external.records import (
    CandidateRecord,
    SectorFamily,
    dac_sector_family,
    primary_family,
    wb_sector_family,
)
from compassio_ml.external.registry import (
    DEFAULT_REGISTRY,
    ExternalSourceDefinition,
    load_registry,
)

REPO = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ paths
def _paths(tmp_path: Path) -> V2Paths:
    return V2Paths(
        tmp_path / "repo", tmp_path / "repo" / "out", tmp_path / "v1" / "data", tmp_path / "v1"
    )


def test_writable_accepts_only_output_root(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    assert paths.writable(paths.output_root / "a" / "b.json").name == "b.json"
    with pytest.raises(UnsafePathError):
        paths.writable(tmp_path / "v1" / "data" / "raw" / "x.zip")
    with pytest.raises(UnsafePathError):
        paths.writable(tmp_path / "elsewhere.txt")
    with pytest.raises(UnsafePathError):
        paths.writable(paths.output_root / ".." / ".." / "v1" / "models" / "m.joblib")


def test_overlapping_roots_are_refused(tmp_path: Path) -> None:
    paths = V2Paths(
        tmp_path, tmp_path / "v1" / "data" / "ml_v2", tmp_path / "v1" / "data", tmp_path / "v1"
    )

    with pytest.raises(UnsafePathError):
        paths.check_separation()


def test_from_env_defaults_output_inside_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("COMPASSIO_V2_OUTPUT_ROOT", raising=False)
    monkeypatch.setenv("COMPASSIO_DATA_ROOT", str(tmp_path / "v1" / "data"))
    monkeypatch.delenv("COMPASSIO_V1_PROJECT_ROOT", raising=False)

    paths = V2Paths.from_env(tmp_path / "repo")

    assert paths.output_root == (tmp_path / "repo" / "data" / "ml_v2").resolve()
    assert paths.v1_project_root == (tmp_path / "v1").resolve()


# ------------------------------------------------------------------ fetch
class _Response(io.BytesIO):
    def __init__(self, body: bytes, status: int = 200, length: str | None = None) -> None:
        super().__init__(body)
        self.status = status
        self.url = "https://example.invalid/final"
        self.headers = {"Content-Type": "application/json"}
        if length is not None:
            self.headers["Content-Length"] = length


def _fetcher(
    body: bytes, status: int = 200, length: str | None = None, sleeps: list[float] | None = None
) -> SafeFetcher:
    def opener(request: urllib.request.Request, timeout: float) -> IO[bytes]:
        return _Response(body, status, length)

    return SafeFetcher(
        frozenset({"example.invalid"}),
        FetchLimits(max_bytes=10, min_interval_s=5.0),
        opener=opener,
        sleep=(sleeps.append if sleeps is not None else lambda _s: None),
        clock=lambda: 100.0,
    )


def test_fetch_saves_hash_and_upgrades_http(tmp_path: Path) -> None:
    retrieval = _fetcher(b"example").fetch("http://example.invalid/a", tmp_path / "a.json")

    assert retrieval.fetched_url.startswith("https://")
    assert retrieval.bytes == 7
    assert (tmp_path / "a.json").read_bytes() == b"example"
    assert len(retrieval.sha256) == 64


@pytest.mark.parametrize(
    ("url", "body", "status", "length"),
    [
        ("https://not-allowed.invalid/x", b"x", 200, None),
        ("ftp://example.invalid/x", b"x", 200, None),
        ("https://example.invalid/x", b"x" * 11, 200, None),
        ("https://example.invalid/x", b"x", 200, "999"),
        ("https://example.invalid/x", b"x", 403, None),
    ],
)
def test_fetch_refusals_save_nothing(
    tmp_path: Path, url: str, body: bytes, status: int, length: str | None
) -> None:
    with pytest.raises(FetchError):
        _fetcher(body, status, length).fetch(url, tmp_path / "x.bin")

    assert list(tmp_path.iterdir()) == []


def test_fetch_never_overwrites_and_rate_limits(tmp_path: Path) -> None:
    sleeps: list[float] = []
    fetcher = _fetcher(b"ok", sleeps=sleeps)
    fetcher.fetch("https://example.invalid/1", tmp_path / "1")
    fetcher.fetch("https://example.invalid/2", tmp_path / "2")

    assert sleeps == [5.0]
    with pytest.raises(FetchError):
        fetcher.fetch("https://example.invalid/1", tmp_path / "1")


# ------------------------------------------------------------------ registry
def test_committed_registry_is_valid_and_not_cleared() -> None:
    registry = load_registry(REPO / DEFAULT_REGISTRY)

    assert {s.source_id for s in registry.sources} >= {
        "worldbank_projects",
        "gcf_project_pages",
        "iati_fcdo",
        "oecd_crs",
    }
    assert all(s.rights_status == "not_reviewed" for s in registry.sources)


def test_registry_rejects_rights_clearance_without_review() -> None:
    source = load_registry(REPO / DEFAULT_REGISTRY).sources[0].model_dump()
    source["rights_status"] = "cleared"

    with pytest.raises(ValueError, match="rights_status"):
        ExternalSourceDefinition.model_validate(source)


# ------------------------------------------------------------------ records / sectors
@pytest.mark.parametrize(
    ("code", "family"),
    [
        ("23210", SectorFamily.ENERGY),
        ("43060", SectorFamily.DISASTER_EMERGENCY),
        ("74020", SectorFamily.DISASTER_EMERGENCY),
        ("31120", SectorFamily.AGRICULTURE_FORESTRY_FISHING),
        ("14020", SectorFamily.WATER_SANITATION_WASTE),
        ("43040", SectorFamily.MULTISECTOR_OTHER),
        (None, SectorFamily.UNKNOWN),
    ],
)
def test_dac_sector_family(code: str | None, family: SectorFamily) -> None:
    assert dac_sector_family(code) == family


def test_wb_and_primary_family() -> None:
    assert wb_sector_family("LLX") == SectorFamily.ENERGY
    assert wb_sector_family("TTX") == SectorFamily.TRANSPORT
    assert (
        primary_family({SectorFamily.ENERGY: 60.0, SectorFamily.HEALTH: 40.0})
        == SectorFamily.ENERGY
    )
    assert (
        primary_family({SectorFamily.ENERGY: 0.0, SectorFamily.HEALTH: 0.0})
        == SectorFamily.MULTISECTOR_OTHER
    )
    assert primary_family({}) == SectorFamily.UNKNOWN


# ------------------------------------------------------------------ IATI
EXAMPLE_ACTIVITY = """
<iati-activity hierarchy="2" last-updated-datetime="2020-01-01T00:00:00">
  <iati-identifier>example-activity-1</iati-identifier>
  <title><narrative xml:lang="en">Example title</narrative></title>
  <description type="1"><narrative>Example general text.</narrative></description>
  <description type="2"><narrative>Example objective.</narrative></description>
  <description type="3"><narrative>Example target group.</narrative></description>
  <recipient-country code="PK" percentage="100"/>
  <sector vocabulary="1" code="31120" percentage="100"/>
  <policy-marker vocabulary="1" code="6" significance="0"/>
  <policy-marker vocabulary="1" code="7" significance="2"/>
  <activity-status code="2"/>
  <related-activity type="1" ref="example-parent"/>
</iati-activity>
"""


def _iati_candidate(xml: str) -> CandidateRecord:
    parsed = iati.parse_activity(fromstring(xml))
    return iati.to_candidate(
        parsed, retrieval_id="example", raw_file="example.xml", raw_sha256="0" * 64
    )


def test_iati_explicit_markers_and_parent() -> None:
    record = _iati_candidate(EXAMPLE_ACTIVITY)
    row = record.to_row()

    assert (record.donor_rio_mitigation, record.donor_rio_adaptation) == (0, 2)
    assert record.donor_marker_status == "explicit_both"
    assert row["donor_rio_overall"] == 2
    assert record.parent_ids == ["iati_fcdo:example-parent"]
    assert record.description == "Example general text. Example objective."
    assert record.sector_family == SectorFamily.AGRICULTURE_FORESTRY_FISHING.value


def test_iati_absent_marker_is_unknown_not_negative() -> None:
    xml = EXAMPLE_ACTIVITY.replace('<policy-marker vocabulary="1" code="6" significance="0"/>', "")
    xml = xml.replace('<policy-marker vocabulary="1" code="7" significance="2"/>', "")
    record = _iati_candidate(xml)

    assert record.donor_marker_status == "absent"
    assert record.donor_rio_mitigation is None
    assert record.to_row()["donor_rio_overall"] is None
    assert record.label_category == "none"


def test_iati_invalid_significance_is_not_a_label() -> None:
    record = _iati_candidate(EXAMPLE_ACTIVITY.replace('significance="2"', 'significance="4"'))

    assert record.donor_rio_adaptation is None
    assert record.donor_marker_status == "explicit_partial"
    assert record.extra["invalid_rio_significance"] == {"adaptation": "4"}


# ------------------------------------------------------------------ GCF
EXAMPLE_PAGE = """<html><body><h1>Example project</h1>
<dl><dt>Date approved</dt><dd>01 Jan 2020</dd></dl>
<section id="overview"><h2>Overview</h2>
 <div data-component="primitives:wysiwyg"><p>Example prose one.</p><p>Example prose two.</p></div>
 <dl><dt>Theme</dt><dd>Adaptation</dd><dt>Status</dt><dd>Under implementation</dd></dl>
 <ul><li><h5>Funding proposal received</h5><p><time datetime="02 Feb 2019">x</time></p></li></ul>
</section>
<a href="/document/example-doc"><strong aria-label="Title">Example doc</strong>
 <span aria-label="Type">Approved funding proposal</span>
 <span aria-label="Date">03 Mar 2020</span></a>
<script>var example = "Theme Mitigation";</script>
</body></html>"""


def test_gcf_overview_excludes_theme_and_status_widgets() -> None:
    page = gcf.parse_page(EXAMPLE_PAGE)

    assert page.overview == "Example prose one. Example prose two."
    assert "Adaptation" not in page.overview and "implementation" not in page.overview
    assert page.meta["Theme"] == "Adaptation"
    assert page.timeline == [("Funding proposal received", "02 Feb 2019")]
    assert [(d.title, d.type, d.date) for d in page.documents] == [
        ("Example doc", "Approved funding proposal", "03 Mar 2020")
    ]


# ------------------------------------------------------------------ World Bank
def test_worldbank_fields_exclude_staff_and_parse_example(tmp_path: Path) -> None:
    assert "teamleadname" not in worldbank.FIELDS
    assert "teamleaderupi" not in worldbank.FIELDS
    payload = {
        "total": "2",
        "projects": {
            "P000001": {
                "id": "P000001",
                "project_name": "Example pipeline",
                "pdo": "Example PDO.",
                "countrycode": ["PK"],
                "status": "Pipeline",
                "boardapprovaldate": "2999-01-01T00:00:00Z",
                "themev2_level2_exact": ["Climate Change"],
                "themev2_level3_exact": ["Adaptation", "Example"],
                "major_sectors": [
                    {
                        "major_sector": {
                            "major_sector_code": "AAX",
                            "sectors": [{"sector_percent": "100"}],
                        }
                    }
                ],
            },
            "P000002": {
                "id": "P000002",
                "project_name": "Example closed",
                "pdo": "Mentions FP001.",
                "countrycode": ["PK"],
                "status": "Closed",
                "boardapprovaldate": "2001-01-01T00:00:00Z",
                "themev2_level2_exact": ["Other"],
                "themev2_level3_exact": ["Adaptation"],
            },
        },
    }
    (tmp_path / "p.json").write_text(json.dumps(payload), encoding="utf-8")
    manifest = {
        "retrieval_id": "example",
        "files": [
            {
                "file": "p.json",
                "role": "data",
                "sha256": "0" * 64,
                "retrieved_at": "2026-01-01T00:00:00+00:00",
            }
        ],
    }
    (tmp_path / "retrieval_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    records = {r.source_record_id: r for r in worldbank.parse_retrieval(tmp_path)}

    assert records["P000001"].text_timing == "pre_approval_pipeline"
    assert records["P000001"].wb_climate_themes == ["Adaptation"]
    assert records["P000002"].wb_climate_themes == []  # level-2 "Climate Change" required
    assert records["P000002"].cross_references == ["gcf_project_pages:FP001"]
    assert records["P000001"].country_iso3 == ["ISO2:PK"]


# ------------------------------------------------------------------ linkage
def _nodes(rows: list[dict[str, object]]) -> pd.DataFrame:
    base = {
        "parent_ids": "",
        "cross_references": "",
        "text_sha256": None,
        "description_sha256": None,
        "has_usable_text": True,
        "v1_group": None,
        "country_iso3": "EXA",
        "title_clean": "",
        "description_clean": "",
        "source_id": "iati_fcdo",
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_evidence_links_parent_crossref_and_exact_text() -> None:
    nodes = _nodes(
        [
            {"candidate_id": "iati_fcdo:a", "parent_ids": "iati_fcdo:p", "text_sha256": "t1"},
            {"candidate_id": "iati_fcdo:b", "parent_ids": "iati_fcdo:p", "text_sha256": "t2"},
            {
                "candidate_id": "iati_fcdo:c",
                "cross_references": "worldbank_projects:P000009",
                "text_sha256": "t3",
            },
            {"candidate_id": "worldbank_projects:P000009", "text_sha256": "t4"},
            {
                "candidate_id": "aiddata:1",
                "source_id": "aiddata",
                "text_sha256": "t5",
                "v1_group": "g",
            },
            {"candidate_id": "gcf_project_pages:FP001", "text_sha256": "t5"},
        ]
    )
    links = evidence_links(nodes)
    groups = assign_groups(list(nodes["candidate_id"]), links, links.head(0))
    fam = dict(zip(groups["candidate_id"], groups["project_family_id"], strict=True))

    assert fam["iati_fcdo:a"] == fam["iati_fcdo:b"]  # siblings via virtual parent node
    assert fam["iati_fcdo:c"] == fam["worldbank_projects:P000009"]
    assert fam["aiddata:1"] == fam["gcf_project_pages:FP001"]  # exact duplicate text
    assert fam["iati_fcdo:a"] != fam["iati_fcdo:c"]


def test_fuzzy_matches_join_partition_groups_not_families() -> None:
    text = "example irrigation canal rehabilitation programme for example district farmers " * 3
    frame = _nodes(
        [
            {
                "candidate_id": "worldbank_projects:P1",
                "source_id": "worldbank_projects",
                "title_clean": "Example canal programme",
                "description_clean": text,
                "text_sha256": "x1",
            },
            {
                "candidate_id": "iati_fcdo:z",
                "title_clean": "Example canal programme phase",
                "description_clean": text + " additional",
                "text_sha256": "x2",
            },
            {
                "candidate_id": "iati_fcdo:other",
                "title_clean": "Example unrelated school",
                "description_clean": "example classroom construction and teacher training " * 3,
                "text_sha256": "x3",
            },
        ]
    )
    result = link(frame)
    rows = result.assignments.set_index("candidate_id").to_dict("index")
    fam = {k: str(v["project_family_id"]) for k, v in rows.items()}
    grp = {k: str(v["partition_group_id"]) for k, v in rows.items()}

    suspected = result.links[result.links["strength"] == "suspected_requires_review"]
    assert len(suspected) == 1
    assert fam["worldbank_projects:P1"] != fam["iati_fcdo:z"]
    assert grp["worldbank_projects:P1"] == grp["iati_fcdo:z"]
    assert grp["iati_fcdo:other"] != grp["iati_fcdo:z"]


def test_stable_id_is_order_independent() -> None:
    assert stable_id("fam", ["b", "a"]) == stable_id("fam", ["a", "b"])


def test_gcf_overview_survives_void_and_stray_tags() -> None:
    page = gcf.parse_page(
        '<section id="overview"><div data-component="primitives:wysiwyg"><p>Example a.</p>'
        "<p>Example<br>b.</p></div></span>"
        '<figure><img src="example.invalid/x.jpg"><video><source src="x"></video></figure>'
        "<dl><dt>Theme</dt><dd>Mitigation</dd></dl></section><h1>Example title</h1>"
    )

    assert page.overview == "Example a. Example b."
    assert page.title == "Example title"
    assert page.meta["Theme"] == "Mitigation"
