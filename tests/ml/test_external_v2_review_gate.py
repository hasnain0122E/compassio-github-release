"""Task 006-ML review gate: rights isolation, consumed-v1-test exclusion, evaluation
independence and the human-review workflow.

All fixtures are ARTIFICIAL (``example_*`` / ``fixture_*`` identifiers). Reviewer fixtures stand
in for registered people only to exercise validation logic; no real review is simulated.
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from compassio_ml.external.development import (
    ForbiddenPoolError,
    load_aiddata_development_ids,
    load_development_pool,
)
from compassio_ml.external.labeling import (
    ADJUDICATION_CONTEXT_COLUMNS,
    REVIEWER_COLUMNS,
    LabelRecord,
    ReviewerLabel,
    ReviewerRegistry,
    ReviewWorkflowError,
    SealedTestAccessError,
    agreement,
    build_worksheet,
    cohen_kappa,
    load_reviewers,
    open_sealed_labels,
    validate_completed,
)
from compassio_ml.external.partition import (
    CONSUMED,
    EXCL_LINKED,
    EXCL_RIGHTS_TRAINING,
    EXTERNAL,
    RESTRICTED,
    TRAIN,
    VALID,
    PoolIntegrityError,
    assign_partitions,
    check_pool_integrity,
    n_for_half_width,
    sample_pilot,
    stratum,
    wilson_half_width,
)
from compassio_ml.external.paths import UnsafePathError, V2Paths
from compassio_ml.external.rights import DEFAULT_RIGHTS_CONFIG, Use, UseStatus, load_rights

REPO = Path(__file__).resolve().parents[2]
EXTERNAL_PKG = REPO / "packages" / "compassio_ml" / "src" / "compassio_ml" / "external"


# ------------------------------------------------------------------ rights
def test_committed_rights_restrict_gcf_and_backend_snapshot() -> None:
    rights = load_rights(REPO / DEFAULT_RIGHTS_CONFIG)

    for use in Use:
        assert rights.status("gcf_project_pages", use) == UseStatus.RESTRICTED
        assert rights.status("gcf_api_snapshot_backend", use) == UseStatus.RESTRICTED
    assert rights.permitted("iati_fcdo", Use.TRAINING)
    assert rights.status("worldbank_projects", Use.TRAINING) == UseStatus.NOT_APPLICABLE
    assert {"gcf_project_pages", "gcf_api_snapshot_backend"} <= rights.restricted_sources()


def test_unknown_source_fails_closed() -> None:
    rights = load_rights(REPO / DEFAULT_RIGHTS_CONFIG)

    assert rights.status("example_unregistered_source", Use.TRAINING) == UseStatus.RESTRICTED


def test_ml_code_never_references_backend_snapshot_or_database() -> None:
    sources = "\n".join(p.read_text(encoding="utf-8") for p in EXTERNAL_PKG.glob("*.py"))

    for forbidden in ("gcf_api_projects", "backend_source_registry", "compassio_dev.sqlite"):
        assert forbidden not in sources


def test_readable_forbids_raw_db_and_db(tmp_path: Path) -> None:
    paths = V2Paths(
        tmp_path / "repo", tmp_path / "repo" / "out", tmp_path / "v1" / "data", tmp_path / "v1"
    )

    with pytest.raises(UnsafePathError):
        paths.readable(tmp_path / "v1" / "data" / "raw_db" / "example" / "projects.json")
    with pytest.raises(UnsafePathError):
        paths.readable(tmp_path / "v1" / "data" / "db" / "example.sqlite")
    assert paths.readable(tmp_path / "v1" / "data" / "processed" / "x.parquet").name == "x.parquet"


# ------------------------------------------------------------------ partitions
def _meta(rows: list[dict[str, object]]) -> pd.DataFrame:
    base = {"v1_consumed_test": False, "v1_primary_split": None, "v1_eligibility": None}
    return pd.DataFrame([{**base, **r} for r in rows])


RESTRICTED_SOURCES = ("gcf_project_pages",)


def _roles(meta: pd.DataFrame, **kwargs: Any) -> dict[str, str]:
    out = assign_partitions(meta, restricted_sources=RESTRICTED_SOURCES, **kwargs)
    return dict(zip(out["candidate_id"], out["v2_partition"], strict=True))


def test_partition_rules_v2() -> None:
    meta = _meta(
        [
            {
                "candidate_id": "worldbank_projects:P1",
                "source_id": "worldbank_projects",
                "partition_group_id": "g1",
            },
            {"candidate_id": "iati_fcdo:x", "source_id": "iati_fcdo", "partition_group_id": "g1"},
            {
                "candidate_id": "gcf_project_pages:FP1",
                "source_id": "gcf_project_pages",
                "partition_group_id": "g2",
            },
            {
                "candidate_id": "iati_fcdo:linked",
                "source_id": "iati_fcdo",
                "partition_group_id": "g2",
            },
            {"candidate_id": "iati_fcdo:y", "source_id": "iati_fcdo", "partition_group_id": "g3"},
            {
                "candidate_id": "aiddata:2",
                "source_id": "aiddata",
                "partition_group_id": "g3",
                "v1_consumed_test": True,
                "v1_eligibility": "eligible",
                "v1_primary_split": "train",
            },
            {
                "candidate_id": "aiddata:3",
                "source_id": "aiddata",
                "partition_group_id": "g4",
                "v1_eligibility": "eligible",
                "v1_primary_split": "validation",
            },
            {
                "candidate_id": "worldbank_projects:P2",
                "source_id": "worldbank_projects",
                "partition_group_id": "g5",
            },
            {
                "candidate_id": "aiddata:5",
                "source_id": "aiddata",
                "partition_group_id": "g5",
                "v1_eligibility": "eligible",
                "v1_primary_split": "train",
            },
        ]
    )
    roles = _roles(meta)

    assert roles["worldbank_projects:P1"] == roles["iati_fcdo:x"] == EXTERNAL
    assert roles["gcf_project_pages:FP1"] == roles["iati_fcdo:linked"] == RESTRICTED
    assert roles["iati_fcdo:y"] == roles["aiddata:2"] == CONSUMED
    assert roles["aiddata:3"] == VALID
    assert roles["worldbank_projects:P2"] == roles["aiddata:5"] == EXCL_LINKED


def test_consumed_v1_test_never_in_any_development_or_test_pool() -> None:
    rows = []
    for i in range(60):
        rows.append(
            {
                "candidate_id": f"aiddata:{i}",
                "source_id": "aiddata",
                "partition_group_id": f"g{i}",
                "v1_consumed_test": i % 3 == 0,
                "v1_eligibility": "eligible",
                "v1_primary_split": "test" if i % 3 == 0 else "train",
            }
        )
    roles = _roles(_meta(rows))

    consumed = {f"aiddata:{i}" for i in range(0, 60, 3)}
    assert {roles[c] for c in consumed} == {CONSUMED}
    assert {roles[c] for c in roles if c not in consumed} <= {TRAIN, VALID}


def test_untrainable_source_never_in_development_pool() -> None:
    meta = _meta(
        [{"candidate_id": "example_src:1", "source_id": "example_src", "partition_group_id": "g1"}]
    )

    roles = _roles(meta, trainable_sources=["iati_fcdo"])

    assert roles["example_src:1"] == EXCL_RIGHTS_TRAINING


def _membership(rows: list[dict[str, object]]) -> pd.DataFrame:
    base = {"v1_consumed_test": False}
    frame = pd.DataFrame([{**base, **r} for r in rows])
    frame["project_family_id"] = frame.get("project_family_id", frame["partition_group_id"])
    return frame


def test_pool_integrity_accepts_valid_and_rejects_each_violation() -> None:
    good = _membership(
        [
            {
                "candidate_id": "iati_fcdo:a",
                "source_id": "iati_fcdo",
                "partition_group_id": "g1",
                "v2_partition": TRAIN,
            },
            {
                "candidate_id": "gcf_project_pages:FP1",
                "source_id": "gcf_project_pages",
                "partition_group_id": "g2",
                "v2_partition": RESTRICTED,
            },
        ]
    )
    assert check_pool_integrity(good, RESTRICTED_SOURCES)["records_checked"] == 2

    violations: list[list[dict[str, object]]] = [
        [
            {
                "candidate_id": "a",
                "source_id": "iati_fcdo",
                "partition_group_id": "g1",
                "v2_partition": TRAIN,
            },
            {
                "candidate_id": "b",
                "source_id": "iati_fcdo",
                "partition_group_id": "g1",
                "v2_partition": VALID,
            },
        ],
        [
            {
                "candidate_id": "aiddata:1",
                "source_id": "aiddata",
                "partition_group_id": "g1",
                "v2_partition": TRAIN,
                "v1_consumed_test": True,
            }
        ],
        [
            {
                "candidate_id": "gcf_project_pages:FP1",
                "source_id": "gcf_project_pages",
                "partition_group_id": "g1",
                "v2_partition": EXTERNAL,
            }
        ],
        [
            {
                "candidate_id": "worldbank_projects:P1",
                "source_id": "worldbank_projects",
                "partition_group_id": "g1",
                "v2_partition": VALID,
            }
        ],
    ]
    for rows in violations:
        with pytest.raises(PoolIntegrityError):
            check_pool_integrity(_membership(rows), RESTRICTED_SOURCES)


def test_family_spanning_partitions_is_rejected() -> None:
    frame = _membership(
        [
            {
                "candidate_id": "a",
                "source_id": "iati_fcdo",
                "partition_group_id": "g1",
                "project_family_id": "f1",
                "v2_partition": TRAIN,
            },
            {
                "candidate_id": "b",
                "source_id": "iati_fcdo",
                "partition_group_id": "g2",
                "project_family_id": "f1",
                "v2_partition": VALID,
            },
        ]
    )

    with pytest.raises(PoolIntegrityError, match="project_family_id"):
        check_pool_integrity(frame, RESTRICTED_SOURCES)


def test_pilot_strata_exclude_gcf_and_keep_one_per_group() -> None:
    assert (
        stratum(
            pd.Series(
                {
                    "source_id": "gcf_project_pages",
                    "gcf_theme": "Adaptation",
                    "sector_family": "unknown",
                    "wb_climate_themes": "",
                }
            )
        )
        is None
    )
    rows = [
        {
            "candidate_id": f"worldbank_projects:P{i:06d}",
            "source_id": "worldbank_projects",
            "gcf_theme": None,
            "wb_climate_themes": "",
            "sector_family": "transport",
            "is_pakistan": i < 10,
            "partition_group_id": f"g{i // 2}",
        }
        for i in range(40)
    ]
    pilot = sample_pilot(pd.DataFrame(rows), targets={"wb_priority_non_energy_untagged": 10})

    assert len(pilot) == 10 and pilot["partition_group_id"].is_unique
    assert pilot["is_pakistan"].sum() >= 3
    assert (pilot["inclusion_probability"] == 10 / 20).all()


def test_wilson_sample_size() -> None:
    n = n_for_half_width(0.75, 0.10)

    assert wilson_half_width(0.75, n) <= 0.10 < wilson_half_width(0.75, n - 1)


# ------------------------------------------------------------------ development loader
def _fake_build(
    tmp_path: Path, candidates: pd.DataFrame, membership: pd.DataFrame | None = None
) -> V2Paths:
    paths = V2Paths(REPO, tmp_path / "out", None, None)
    build = paths.datasets / "v2build_example"
    build.mkdir(parents=True)
    (build / "build_manifest.json").write_text("{}", encoding="utf-8")
    candidates.to_parquet(build / "candidates.parquet", index=False)
    if membership is not None:
        membership.to_parquet(build / "partition_membership.parquet", index=False)
    return paths


def _dev_rows(**overrides: object) -> pd.DataFrame:
    row = {
        "candidate_id": "iati_fcdo:example",
        "source_id": "iati_fcdo",
        "v2_partition": TRAIN,
        "v1_consumed_test": False,
    }
    return pd.DataFrame([{**row, **overrides}])


def test_development_loader_refuses_sealed_and_restricted_partitions(tmp_path: Path) -> None:
    paths = _fake_build(tmp_path, _dev_rows())

    assert len(load_development_pool(paths, "v2build_example")) == 1
    for partition in (EXTERNAL, RESTRICTED, CONSUMED):
        with pytest.raises(ForbiddenPoolError):
            load_development_pool(paths, "v2build_example", partitions=[partition])


@pytest.mark.parametrize(
    "overrides",
    [
        {"v2_partition": EXTERNAL},
        {"source_id": "worldbank_projects"},
        {"source_id": "gcf_project_pages"},
        {"v1_consumed_test": True},
    ],
)
def test_development_loader_detects_contaminated_file(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    paths = _fake_build(tmp_path, _dev_rows(**overrides))

    with pytest.raises(PoolIntegrityError):
        load_development_pool(paths, "v2build_example")


def test_aiddata_development_ids_exclude_consumed(tmp_path: Path) -> None:
    membership = pd.DataFrame(
        [
            {
                "candidate_id": "aiddata:1",
                "source_id": "aiddata",
                "v2_partition": TRAIN,
                "v1_consumed_test": False,
                "partition_group_id": "g1",
            },
            {
                "candidate_id": "aiddata:2",
                "source_id": "aiddata",
                "v2_partition": CONSUMED,
                "v1_consumed_test": True,
                "partition_group_id": "g2",
            },
        ]
    )
    paths = _fake_build(tmp_path, _dev_rows(), membership)

    ids = load_aiddata_development_ids(paths, "v2build_example")

    assert ids["record_id"].tolist() == ["1"]


def test_development_loader_rejects_sealed_directory(tmp_path: Path) -> None:
    paths = _fake_build(tmp_path, _dev_rows())

    with pytest.raises((ForbiddenPoolError, FileNotFoundError)):
        load_development_pool(paths, "../sealed_external_test/v2build_example")


def test_sealed_labels_need_frozen_plan(tmp_path: Path) -> None:
    with pytest.raises(SealedTestAccessError):
        open_sealed_labels(tmp_path, None, tmp_path / "final_evaluation_v2.sha256")
    (tmp_path / "final_evaluation_v2.sha256").write_text("abc  plan\n", encoding="utf-8")
    with pytest.raises(SealedTestAccessError, match="does not match"):
        open_sealed_labels(tmp_path, "def", tmp_path / "final_evaluation_v2.sha256")


def test_reporting_counts_verified_metadata_without_opening_labels(tmp_path: Path) -> None:
    from compassio_ml.cli.v2_cli import _human_verified_count

    paths = V2Paths(REPO, tmp_path / "out", None, None)
    sealed = paths.sealed / "v2build_example"
    sealed.mkdir(parents=True)
    # Deliberately unreadable as Parquet: only aggregate metadata may be read.
    (sealed / "external_test_labels.parquet").write_bytes(b"example sealed sentinel")
    assert _human_verified_count(paths, "v2build_example") == 0
    (sealed / "external_test_labels.lock.json").write_text(
        json.dumps({"items": 3, "verified_items": 2, "needs_review_items": 1}), encoding="utf-8"
    )
    assert _human_verified_count(paths, "v2build_example") == 2


def test_aiddata_loader_rechecks_revoked_rights(tmp_path: Path) -> None:
    paths = _fake_build(tmp_path, _dev_rows())
    rights = load_rights(REPO / DEFAULT_RIGHTS_CONFIG).model_dump(mode="json")
    rights["sources"]["aiddata"]["ml_training"] = "restricted"
    config = tmp_path / "example_rights.json"
    config.write_text(json.dumps(rights), encoding="utf-8")

    with pytest.raises(PoolIntegrityError, match="not permitted for training"):
        load_aiddata_development_ids(paths, "v2build_example", rights_path=config)


def test_development_loader_refuses_escape_to_other_directory(tmp_path: Path) -> None:
    paths = _fake_build(tmp_path, _dev_rows())
    outside = paths.output_root / "example_untrusted"
    outside.mkdir()
    (outside / "build_manifest.json").write_text("{}", encoding="utf-8")
    _dev_rows().to_parquet(outside / "candidates.parquet", index=False)

    with pytest.raises(ForbiddenPoolError):
        load_development_pool(paths, "../example_untrusted")


# ------------------------------------------------------------------ reviewers + worksheets
TEXT = "Example irrigation scheme to reduce drought vulnerability of example farmers."


def _items(n: int = 2) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate_id": f"worldbank_projects:P{i:06d}",
                "source_id": "worldbank_projects",
                "publisher": "Example",
                "source_record_id": f"P{i:06d}",
                "document_url": "https://example.invalid/x",
                "retrieval_id": "example",
                "raw_file_sha256": "0" * 64,
                "text_date": None,
                "text_timing": "unknown",
                "country_iso3": "EXA",
                "title_clean": f"Example title {i}",
                "description_clean": TEXT,
            }
            for i in range(n)
        ]
    )


def _registry() -> ReviewerRegistry:
    return ReviewerRegistry.model_validate(
        {
            "reviewers": [
                {
                    "reviewer_id": "fixture_a",
                    "is_human": True,
                    "roles": ["reviewer_a"],
                    "attestation": "fixture standing in for a registered human reviewer",
                },
                {
                    "reviewer_id": "fixture_b",
                    "is_human": True,
                    "roles": ["reviewer_b"],
                    "attestation": "fixture standing in for a registered human reviewer",
                },
            ]
        }
    )


def test_registry_refuses_placeholders_non_humans_and_unknown_roles(tmp_path: Path) -> None:
    base = {"is_human": True, "roles": ["reviewer_a"], "attestation": "x" * 25}
    for bad in (
        {**base, "reviewer_id": "example_reviewer_a"},
        {**base, "reviewer_id": "r1", "is_human": False},
        {**base, "reviewer_id": "r1", "roles": ["model"]},
    ):
        with pytest.raises(ValueError):
            ReviewerRegistry.model_validate({"reviewers": [bad]})
    with pytest.raises(ReviewWorkflowError, match="No reviewer registry"):
        load_reviewers(tmp_path / "reviewers.yaml")


def test_worksheet_columns_blind_and_empty() -> None:
    sheet = build_worksheet(_items(), "example_ws")

    assert not set(ADJUDICATION_CONTEXT_COLUMNS) & set(sheet.columns)
    assert "insufficient_information" in sheet.columns
    assert (sheet[REVIEWER_COLUMNS] == "").all().all()


def _fill(sheet: pd.DataFrame, row: int, **values: str) -> None:
    for key, value in values.items():
        sheet.loc[row, key] = value


def test_validate_completed_rules(tmp_path: Path) -> None:
    issued = build_worksheet(_items(5), "example_ws")
    done = issued.copy()
    ok = {
        "reviewer_id": "fixture_a",
        "rio_mitigation": "0",
        "rio_adaptation": "1",
        "rio_overall": "1",
        "confidence": "medium",
        "evidence_quote": "reduce drought   VULNERABILITY",
        "rationale": "states drought vulnerability",
    }
    _fill(done, 0, **ok)
    _fill(
        done,
        1,
        **{
            **ok,
            "rio_mitigation": "",
            "rio_adaptation": "",
            "rio_overall": "",
            "evidence_quote": "",
            "insufficient_information": "true",
            "confidence": "low",
            "rationale": "description too generic to decide",
        },
    )
    _fill(done, 2, **{**ok, "evidence_quote": "invented phrase not in the text"})
    _fill(done, 3, **{**ok, "reviewer_id": "unregistered_person"})
    done.loc[4, "description"] = "edited text"
    done.to_csv(tmp_path / "reviewer_A.csv", index=False)

    result = validate_completed(
        tmp_path / "reviewer_A.csv", expected=issued, registry=_registry(), role="reviewer_a"
    )

    assert [x.insufficient_information for x in result.valid] == [False, True]
    joined = " ".join(result.errors)
    assert "not found verbatim" in joined and "not registered" in joined and "edited" in joined
    assert not result.complete


def test_role_is_enforced(tmp_path: Path) -> None:
    issued = build_worksheet(_items(1), "example_ws")
    done = issued.copy()
    _fill(
        done,
        0,
        reviewer_id="fixture_a",
        rio_mitigation="0",
        rio_adaptation="0",
        rio_overall="0",
        confidence="high",
        evidence_quote="Example irrigation scheme",
        rationale="no climate objective stated",
    )
    done.to_csv(tmp_path / "reviewer_B.csv", index=False)

    result = validate_completed(
        tmp_path / "reviewer_B.csv", expected=issued, registry=_registry(), role="reviewer_b"
    )

    assert not result.valid and "role reviewer_b" in result.errors[0]


def _label(
    reviewer: str,
    mit: int | None,
    ada: int | None,
    *,
    item: str = "itm_x",
    insufficient: bool = False,
) -> ReviewerLabel:
    return ReviewerLabel(
        item_id=item,
        reviewer_id=reviewer,
        rio_mitigation=mit,
        rio_adaptation=ada,
        rio_overall=None if insufficient else max(mit or 0, ada or 0),
        confidence="low" if insufficient else "high",
        insufficient_information=insufficient,
        evidence_quote="" if insufficient else "example quote",
        rationale="example rationale text",
    )


def test_reviewer_label_rules() -> None:
    with pytest.raises(ValueError, match="rio_overall"):
        ReviewerLabel(
            item_id="i",
            reviewer_id="r",
            rio_mitigation=1,
            rio_adaptation=2,
            rio_overall=1,
            confidence="low",
            evidence_quote="q",
            rationale="example rationale",
        )
    with pytest.raises(ValueError, match="evidence_quote"):
        ReviewerLabel(
            item_id="i",
            reviewer_id="r",
            rio_mitigation=0,
            rio_adaptation=0,
            rio_overall=0,
            confidence="low",
            rationale="example rationale",
        )
    with pytest.raises(ValueError, match="blank"):
        ReviewerLabel(
            item_id="i",
            reviewer_id="r",
            rio_mitigation=0,
            rio_adaptation=None,
            rio_overall=None,
            confidence="low",
            insufficient_information=True,
            rationale="example rationale",
        )


def test_agreement_excludes_insufficient_and_refuses_same_person() -> None:
    a = [_label("r1", 1, 0, item=f"i{k}") for k in range(4)]
    b = [_label("r2", 1, 0, item=f"i{k}") for k in range(2)]
    b += [_label("r2", 0, 0, item="i2"), _label("r2", None, None, item="i3", insufficient=True)]

    out = agreement(a, b)

    assert out["items_double_reviewed"] == 4 and out["items_both_scored"] == 3
    assert out["disagreements"] == ["i2"]
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    with pytest.raises(ValueError, match="same reviewer"):
        agreement(a, [x.model_copy(update={"reviewer_id": "r1"}) for x in b])


def test_label_record_final_requires_two_humans_and_third_adjudicator() -> None:
    base: dict[str, Any] = {
        "item_id": "i",
        "source_id": "s",
        "publisher": "p",
        "source_project_id": "x",
        "document_url": None,
        "description_sha256": None,
        "document_date": None,
        "document_version": "v",
        "split_eligibility": "external_test",
        "final_rio_mitigation": 1,
        "final_rio_adaptation": 0,
        "final_label_status": "verified",
    }
    with pytest.raises(ValueError, match="two completed human reviews"):
        LabelRecord(**base)
    with pytest.raises(ValueError, match="different people"):
        LabelRecord(
            **base,
            reviewer_a=_label("r1", 1, 0),
            reviewer_b=_label("r1", 1, 0),
            disagreement_status="agree",
        )
    with pytest.raises(ValueError, match="third person"):
        LabelRecord(
            **base,
            reviewer_a=_label("r1", 1, 0),
            reviewer_b=_label("r2", 0, 0),
            disagreement_status="disagreement",
            adjudicated_by="r1",
        )
    with pytest.raises(ValueError, match="only allowed on verified"):
        LabelRecord(
            **{**base, "final_label_status": "needs_review"},
            reviewer_a=_label("r1", 1, 0),
            reviewer_b=_label("r2", 1, 0),
            disagreement_status="agree",
        )
    ok = LabelRecord(
        **base,
        reviewer_a=_label("r1", 1, 0),
        reviewer_b=_label("r2", 0, 0),
        disagreement_status="disagreement",
        adjudicated_by="r3",
    )
    assert ok.final_rio_mitigation == 1


def test_unreviewed_item_is_never_verified() -> None:
    record = LabelRecord(
        item_id="i",
        source_id="s",
        publisher="p",
        source_project_id="x",
        document_url=None,
        description_sha256=None,
        document_date=None,
        document_version="v",
        split_eligibility="external_test",
    )

    assert record.final_label_status == "unverified"
    with pytest.raises(ValueError, match="needs final Rio values"):
        LabelRecord(**{**record.model_dump(), "final_label_status": "verified"})


@pytest.mark.parametrize("mit,ada", [(-1, 0), (0, 3), (None, 1), (1, None)])
def test_final_labels_require_both_scores_in_rio_range(mit: int | None, ada: int | None) -> None:
    with pytest.raises(ValueError):
        LabelRecord(
            item_id="example_item",
            source_id="example_source",
            publisher="example_publisher",
            source_project_id="example_project",
            document_url=None,
            description_sha256=None,
            document_date=None,
            document_version="example_v1",
            split_eligibility="external_test",
            reviewer_a=_label("fixture_a", 1, 0),
            reviewer_b=_label("fixture_b", 0, 0),
            adjudicated_by="fixture_c",
            final_label_status="verified",
            final_rio_mitigation=mit,
            final_rio_adaptation=ada,
        )


def test_needs_review_adjudicator_must_also_be_third_person() -> None:
    with pytest.raises(ValueError, match="third person"):
        LabelRecord(
            item_id="example_item",
            source_id="example_source",
            publisher="example_publisher",
            source_project_id="example_project",
            document_url=None,
            description_sha256=None,
            document_date=None,
            document_version="example_v1",
            split_eligibility="external_test",
            reviewer_a=_label("fixture_a", 1, 0),
            reviewer_b=_label("fixture_b", 0, 0),
            adjudicated_by="fixture_a",
            final_label_status="needs_review",
        )


def test_worksheet_issue_refuses_current_human_review_restriction(tmp_path: Path) -> None:
    from compassio_ml.external.worksheets import create_worksheets

    paths = _fake_build(tmp_path, _dev_rows(source_id="gcf_api_snapshot_backend"))
    sealed = paths.sealed / "v2build_example"
    sealed.mkdir(parents=True)
    _dev_rows(source_id="worldbank_projects").to_parquet(
        sealed / "candidate_pool.parquet", index=False
    )

    with pytest.raises(ReviewWorkflowError, match="not permitted for human review"):
        create_worksheets(paths, paths.datasets / "v2build_example")
    assert not (sealed / "pilot_v1.parquet").exists()
    assert not (paths.labeling / "v2build_example").exists()


def test_freeze_refuses_without_completed_reviews(tmp_path: Path) -> None:
    from compassio_ml.external.worksheets import freeze_pilot_labels

    paths = V2Paths(REPO, tmp_path / "out", None, None)
    build = paths.datasets / "v2build_example"
    build.mkdir(parents=True)
    (paths.labeling / "v2build_example").mkdir(parents=True)
    (paths.labeling / "v2build_example" / "reviewers.yaml").write_text(
        json.dumps({"reviewers": []}), encoding="utf-8"
    )
    issued = paths.labeling / "v2build_example" / "external_test_pilot_v1"
    issued.mkdir()
    build_worksheet(_items(1), "external_test_pilot_v1")[
        ["item_id", "title", "description"]
    ].to_parquet(issued / "issued_items.parquet", index=False)
    (paths.labeling / "v2build_example" / "training_label_audit_v1").mkdir()
    build_worksheet(_items(1), "training_label_audit_v1")[
        ["item_id", "title", "description"]
    ].to_parquet(
        paths.labeling / "v2build_example" / "training_label_audit_v1" / "issued_items.parquet",
        index=False,
    )

    with pytest.raises(ReviewWorkflowError, match=r"reviewer_A\.csv and reviewer_B\.csv"):
        freeze_pilot_labels(paths, build)
    assert not (paths.sealed / "v2build_example" / "external_test_labels.parquet").exists()
