"""ARTIFICIAL fixtures only: donor diagnostics and optional AI file-exchange safeguards."""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from compassio_ml.external.partition import TRAIN, VALID
from compassio_ml.external.paths import V2Paths
from compassio_ml.integrity import sha256_file
from compassio_ml.quality_v2 import audit
from compassio_ml.quality_v2.assessments import (
    PROMPTS,
    UsagePermission,
    compare_assessments,
    fixture_demo,
    import_assessments,
    make_request,
    prepare_assessments,
    validate_responses,
)

REPO = Path(__file__).resolve().parents[2]


def row(cid: str = "example_activity", **changes: Any) -> dict[str, Any]:
    return {
        "candidate_id": f"iati_fcdo:{cid}",
        "source_id": "iati_fcdo",
        "publisher": "example_artificial_publisher",
        "source_record_id": cid,
        "v2_partition": TRAIN,
        "v1_consumed_test": False,
        "project_family_id": f"example_family_{cid}",
        "partition_group_id": f"example_group_{cid}",
        "title_clean": "Example artificial solar programme",
        "description_clean": (
            "Example artificial project aims to reduce greenhouse gas emissions using solar power. "
            * 2
        ),
        "has_usable_text": True,
        "donor_rio_mitigation": 2,
        "donor_rio_adaptation": 0,
        "donor_rio_overall": 2,
        "donor_marker_status": "explicit_both",
        "extra": "",
        "text_sha256": "example_text_hash",
        "description_sha256": f"example_description_{cid}",
        "sector_family": "energy",
        "rights_status": "not_reviewed",
        **changes,
    }


def raw_values(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        r["candidate_id"]: {
            "occurrences": 1,
            "mitigation": [str(r["donor_rio_mitigation"])],
            "adaptation": [str(r["donor_rio_adaptation"])],
        }
        for r in rows
    }


def test_semantic_flags_do_not_relabel_or_exclude() -> None:
    rows = [
        row("example_negative", donor_rio_mitigation=0, donor_rio_overall=0),
        row(
            "example_positive",
            title_clean="Example unrelated service",
            description_clean="Example artificial administrative support service. " * 3,
        ),
        row(
            "example_missing",
            donor_rio_mitigation=None,
            donor_rio_adaptation=None,
            donor_rio_overall=None,
            donor_marker_status="absent",
        ),
    ]
    raw = raw_values(rows)
    raw[rows[2]["candidate_id"]].update(mitigation=[], adaptation=[])
    result = audit.audit_records(pd.DataFrame(rows), raw)
    by_id = {r["candidate_id"]: r for r in result}
    neg, pos, missing = (by_id[r["candidate_id"]] for r in rows)
    assert "negative_with_climate_lexical_evidence" in neg["flags"]
    assert neg["donor_values"]["overall"] == 0 and neg["eligible_source_label"]
    assert "positive_without_lexical_evidence" in pos["flags"]
    assert pos["donor_values"]["overall"] == 2 and pos["eligible_source_label"]
    assert not missing["eligible_source_label"] and missing["donor_values"]["overall"] is None
    assert not any(r["human_verified"] for r in result)


@pytest.mark.parametrize("value", [-1, 3, 1.5, "not-a-rio-score", True])
def test_invalid_donor_values_are_not_eligible(value: Any) -> None:
    rows = [row(donor_rio_mitigation=value)]
    result = audit.audit_records(pd.DataFrame(rows), raw_values(rows))[0]
    assert not result["eligible_source_label"] and "invalid_rio_value" in result["flags"]


def test_raw_contradictions_survive_parser_last_value() -> None:
    rows = [row()]
    raw = raw_values(rows)
    raw[rows[0]["candidate_id"]]["mitigation"] = ["0", "2"]
    result = audit.audit_records(pd.DataFrame(rows), raw)[0]
    assert "contradictory_raw_mitigation" in result["flags"]
    assert not result["eligible_source_label"]
    assert result["donor_values"]["mitigation"] == 2


def test_family_variation_and_identical_text_conflicts_are_warnings() -> None:
    rows = [
        row("example_one", project_family_id="example_family", description_sha256="example_same"),
        row(
            "example_two",
            project_family_id="example_family",
            description_sha256="example_same",
            donor_rio_mitigation=0,
            donor_rio_overall=0,
        ),
    ]
    result = audit.audit_records(pd.DataFrame(rows), raw_values(rows))
    assert all("family_label_variation" in r["flags"] for r in result)
    assert all("identical_description_label_conflict" in r["flags"] for r in result)
    assert all("multiple_records_same_family" in r["flags"] for r in result)
    assert all(r["eligible_source_label"] for r in result)


def test_retrospective_quotes_are_exact_offsets() -> None:
    text = "Example artificial project was completed after a flood."
    result = audit.evidence_spans("Example", text)
    assert result["retrospective"] and result["adaptation"]
    for spans in result.values():
        for span in spans:
            assert text[span["start"] : span["end"]] == span["quote"]


def test_shortcuts_never_fit_on_validation() -> None:
    training = [row(f"example_{i}") for i in range(12)]
    validation = [
        row(
            f"example_validation_{i}",
            v2_partition=VALID,
            source_id="iati_ec_intpa",
            description_clean="secretvalidationtoken",
        )
        for i in range(12)
    ]
    assert audit.vocabulary_shortcuts(pd.DataFrame(training)) == audit.vocabulary_shortcuts(
        pd.DataFrame(training + validation)
    )


def fake_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> V2Paths:
    """Real loader/manifest/rights/XML mechanics, explicitly artificial records."""
    repo = tmp_path / "example_repo"
    (repo / "configs").mkdir(parents=True)
    (repo / "configs/ml_rights_eligibility_v2.yaml").write_bytes(
        (REPO / "configs/ml_rights_eligibility_v2.yaml").read_bytes()
    )
    paths = V2Paths(repo, repo / "out", None, None)
    build = paths.datasets / "v2build_example"
    build.mkdir(parents=True)
    frame = pd.DataFrame([row()])
    frame.to_parquet(build / "candidates.parquet", index=False)
    frame[
        [
            "candidate_id",
            "source_id",
            "project_family_id",
            "partition_group_id",
            "v2_partition",
            "v1_consumed_test",
        ]
    ].to_parquet(build / "partition_membership.parquet", index=False)
    raw = paths.external_raw / "iati_fcdo/example_retrieval"
    raw.mkdir(parents=True)
    xml = raw / "example.xml"
    xml.write_text(
        "<iati-activities><iati-activity><iati-identifier>example_activity</iati-identifier>"
        '<policy-marker vocabulary="1" code="6" significance="2"/>'
        '<policy-marker vocabulary="1" code="7" significance="0"/>'
        "</iati-activity></iati-activities>",
        encoding="utf-8",
    )
    audit.dump_json(
        raw / "retrieval_manifest.json",
        {"files": [{"file": "example.xml", "role": "data", "sha256": sha256_file(xml)}]},
    )
    audit.dump_json(
        build / "build_manifest.json",
        {
            "outputs_sha256": {
                name: sha256_file(build / name)
                for name in ("candidates.parquet", "partition_membership.parquet")
            },
            "inputs": {
                "retrievals": {
                    "iati_fcdo": {
                        "retrieval_id": "example_retrieval",
                        "manifest_sha256": sha256_file(raw / "retrieval_manifest.json"),
                    }
                }
            },
        },
    )
    monkeypatch.setattr(audit, "git_state", lambda _: {"commit": "example_commit", "dirty": False})
    return paths


def test_audit_end_to_end_reproducible_and_input_immutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = fake_paths(tmp_path, monkeypatch)
    input_file = paths.datasets / "v2build_example/candidates.parquet"
    before = sha256_file(input_file)
    first = audit.audit_dataset(paths, "v2build_example")
    assert audit.audit_dataset(paths, "v2build_example") == first
    report = json.loads((first / "quality_report.json").read_text("utf-8"))
    assert report["counts"]["eligible_donor_labelled"] == 1
    assert report["human_verified_labels"] == report["ai_assessed_records"] == 0
    assert sha256_file(input_file) == before
    assert not paths.sealed.exists() and not paths.labeling.exists()


def test_tampered_input_and_revoked_rights_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = fake_paths(tmp_path, monkeypatch)
    source = paths.datasets / "v2build_example/candidates.parquet"
    source.write_bytes(b"example corrupt data")
    with pytest.raises(ValueError, match="checksum"):
        audit.load_verified_development(paths, "v2build_example")


def test_raw_xml_contradictions_detected_without_reading_non_development(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = fake_paths(tmp_path, monkeypatch)
    frame, provenance = audit.load_verified_development(paths, "v2build_example")
    raw_file = paths.external_raw / "iati_fcdo/example_retrieval/example.xml"
    raw_file.write_text(
        raw_file.read_text("utf-8").replace(
            "</iati-activity>",
            '<policy-marker vocabulary="1" code="6" significance="0"/></iati-activity>',
        ),
        "utf-8",
    )
    manifest_path = raw_file.parent / "retrieval_manifest.json"
    audit.dump_json(
        manifest_path,
        {"files": [{"file": raw_file.name, "role": "data", "sha256": sha256_file(raw_file)}]},
    )
    provenance["inputs"]["retrievals"]["iati_fcdo"]["manifest_sha256"] = sha256_file(manifest_path)
    observed = audit.raw_marker_audit(paths, frame, provenance["inputs"]["retrievals"])
    assert observed["iati_fcdo:example_activity"]["mitigation"] == ["2", "0"]


def response(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_id": request["item_id"],
        "input_hash": request["input_hash"],
        "status": "scored",
        "mitigation": 2,
        "adaptation": 0,
        "rationale": "Example artificial response for testing only.",
        "evidence": [
            {
                "objective": k,
                "field": "description",
                "start": 0,
                "end": len(request["description"]),
                "quote": request["description"],
            }
            for k in ("mitigation", "adaptation")
        ],
    }


def test_blind_requests_and_distinct_prompts() -> None:
    request = make_request("example_id", "Example title", "Example artificial text")
    assert set(request) == {"item_id", "input_hash", "title", "description"}
    assert "example_id" not in json.dumps(request)
    assert PROMPTS["A"] != PROMPTS["B"]


@pytest.mark.parametrize(
    "change",
    [
        {"mitigation": 3},
        {"mitigation": True},
        {"evidence": []},
        {"input_hash": "wrong"},
        {"reviewer_id": "example_fake_human"},
        {"status": "abstain"},
        {"mitigation": None},
    ],
)
def test_ai_response_schema_rejects_invalid_output(change: dict[str, Any]) -> None:
    request = make_request("example_id", "Example", "Example artificial text")
    with pytest.raises(ValueError):
        validate_responses([request], [{**response(request), **change}])


def test_ai_quotes_and_duplicate_items_rejected() -> None:
    request = make_request("example_id", "Example", "Example artificial text")
    record = response(request)
    record["evidence"][0]["quote"] = "invented text"
    with pytest.raises(ValueError, match="exact input"):
        validate_responses([request], [record])
    with pytest.raises(ValueError, match="Duplicate"):
        validate_responses([request], [response(request), response(request)])


def test_ai_agreement_abstention_and_donor_disagreement_are_not_ground_truth() -> None:
    request = make_request("example_id", "Example", "Example artificial text")
    a = validate_responses([request], [response(request)])
    b = validate_responses([request], [{**response(request), "mitigation": 1}])
    comparison = compare_assessments(a, b, {request["item_id"]: (2, 0)})
    assert comparison["exact_objective_agreement_rate"] == 0
    assert comparison["items_detail"][0]["donor_disagreement"] == {"A": False, "B": True}
    demo = fixture_demo()
    assert demo["fixture"] and demo["real_model_calls"] == demo["real_ai_labels"] == 0
    assert demo["comparison"]["abstentions_B"] == 1
    assert demo["comparison"]["exact_objective_agreement_rate"] is None


def approval() -> dict[str, Any]:
    permission = {
        "permission_id": "example_fixture_permission",
        "source_ids": ["iati_fcdo"],
        "allow_processing": True,
        "provider_is_local": True,
        "allow_external_transfer": False,
        "provider_terms_url": "https://example.invalid/terms",
        "source_terms_evidence": "Artificial fixture evidence only",
        "data_retention_policy": "Artificial local test files only",
        "reviewed_by": "example_fixture",
        "reviewed_at": "2026-11-09",
        "personal_and_third_party_rights_reviewed": True,
        "attribution": "Example artificial attribution",
        "fixture_only": False,
    }
    return {
        "runs": {
            k: {
                "identity": {
                    "provider": "example_fixture",
                    "model_id": "example_fixture_model",
                    "model_version": f"example_version_{k}",
                    "inference_settings": {},
                },
                "permission": permission,
            }
            for k in ("A", "B")
        }
    }


def test_unapproved_provider_and_external_transfer_refused(tmp_path: Path) -> None:
    paths = V2Paths(REPO, tmp_path / "out", None, None)
    with pytest.raises(PermissionError, match="No approved"):
        prepare_assessments(
            paths, "example_absent_audit", REPO / "configs/ai_assessment_permissions_v2.json"
        )
    permission = approval()["runs"]["A"]["permission"]
    with pytest.raises(ValueError, match="transfer"):
        UsagePermission.model_validate({**permission, "provider_is_local": False})


def test_fixture_pair_full_file_exchange(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = fake_paths(tmp_path, monkeypatch)
    output = audit.audit_dataset(paths, "v2build_example")
    approval_path = tmp_path / "example_approval.json"
    audit.dump_json(approval_path, approval())
    pool = prepare_assessments(paths, output.name, approval_path)
    files = []
    for name in ("A", "B"):
        run = json.loads((pool / name / "run_manifest.json").read_text("utf-8"))
        requests = audit.load_jsonl(pool / name / "requests.jsonl")
        assert set(requests[0]) == {"item_id", "input_hash", "title", "description"}
        target = tmp_path / f"example_responses_{name}.json"
        audit.dump_json(
            target,
            {
                "run_id": run["run_id"],
                "identity": run["identity"],
                "responses": [response(r) for r in requests],
                "completed_at": "2026-11-09T00:00:00Z",
                "independence_attestation": "Artificial test fixture; no real model",
            },
        )
        files.append(target)
    returned = import_assessments(paths, pool.name, files[0], files[1])
    result = json.loads((returned / "comparison.json").read_text("utf-8"))
    assert result["exact_objective_agreement_rate"] == 1
    assert result["items_detail"][0]["label_origin"] == "AI_unverified"
    assert not paths.sealed.exists() and not paths.labeling.exists()
    with pytest.raises(FileExistsError):
        import_assessments(paths, pool.name, files[0], files[1])


def test_current_rights_revocation_blocks_quality_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from compassio_ml.external.rights import load_rights

    paths = fake_paths(tmp_path, monkeypatch)
    file = paths.repo_root / "configs/ml_rights_eligibility_v2.yaml"
    rights = load_rights(file).model_dump(mode="json")
    rights["sources"]["iati_fcdo"]["automated_evaluation"] = "restricted"
    audit.dump_json(file, rights)
    with pytest.raises(PermissionError, match="not permitted"):
        audit.load_verified_development(paths, "v2build_example")


def test_eligible_loader_is_development_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = fake_paths(tmp_path, monkeypatch)
    out = audit.audit_dataset(paths, "v2build_example")
    frame = audit.load_eligible_donor_records(paths, out.name, TRAIN)
    assert list(frame["donor_rio_mitigation"]) == [2]
    assert set(frame["label_origin"]) == {"B_donor_reported_rio"}
    with pytest.raises(PermissionError):
        audit.load_eligible_donor_records(paths, out.name, "external_test_candidate")


def test_ai_import_and_permissions_refuse_human_pool_paths(tmp_path: Path) -> None:
    paths = V2Paths(REPO, tmp_path / "out", None, None)
    forbidden = paths.sealed / "example_never_open.json"
    # The file need not exist: rejection must precede any attempt to read it.
    with pytest.raises(PermissionError, match="forbidden inputs"):
        prepare_assessments(paths, "example_audit", forbidden)
    with pytest.raises(PermissionError, match="forbidden inputs"):
        import_assessments(paths, "example_pool", forbidden, forbidden)


def test_out_of_range_evidence_offset_rejected() -> None:
    request = make_request("example_id", "Example", "Example artificial text")
    record = response(request)
    record["evidence"][0]["end"] += 100
    with pytest.raises(ValueError, match="exact input"):
        validate_responses([request], [record])
