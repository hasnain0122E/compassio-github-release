"""Task 007 screening API with ARTIFICIAL models (tiny pipelines trained on example_* text).

The artificial artifacts use the real release / development-candidate formats, so the real
guarded loaders, pins, access rules, explanations, fallback and review audit are exercised.
None of these scores is model evidence.
"""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from compassio_api.core.config import Settings
from compassio_api.main import create_app
from compassio_ml.integrity.hashing import sha256_file
from compassio_ml.model_v2.artifact import ExperimentalClassifier, save_candidate
from compassio_ml.modeling.final_eval import model_fingerprint
from compassio_ml.modeling.release import MODEL_VERSION, RELEASE_SCHEMA

REPO = Path(__file__).resolve().parents[2]
POS = [
    "example solar resilience adaptation",
    "example flood resilience climate",
    "example wind climate",
]
NEG = ["example school books", "example road repair", "example hospital beds"]
TOKEN = "example-review-token"


def _fit(vectorizer: TfidfVectorizer, steps: tuple[str, str]) -> Pipeline:
    pipe = Pipeline([(steps[0], vectorizer), (steps[1], LogisticRegression(C=10.0))])
    return pipe.fit(POS * 4 + NEG * 4, [1] * 12 + [0] * 12)


@pytest.fixture
def models_root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    # Artificial "trusted release" in the real release format.
    v1 = _fit(TfidfVectorizer(ngram_range=(1, 2)), ("tfidf", "clf"))
    rel = root / "models" / "example_v1"
    rel.mkdir(parents=True)
    joblib.dump(v1, rel / "model.joblib")
    v1_sha = sha256_file(rel / "model.joblib")
    (rel / "release_manifest.json").write_text(
        json.dumps(
            {
                "schema": RELEASE_SCHEMA,
                "model_version": MODEL_VERSION,
                "artifact_file": "model.joblib",
                "artifact_sha256": v1_sha,
                "model_fingerprint": model_fingerprint(v1),
                "threshold": 0.5,
                "representation": "title_description",
                "algorithm": "logistic_regression",
                "release_status": "mvp_research_screening",
            }
        )
    )
    trusted = root / "trusted.json"
    trusted.write_text(json.dumps({MODEL_VERSION: v1_sha}))
    # Artificial development candidate in the real candidate format.
    v2 = _fit(TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4)), ("features", "clf"))
    cand = root / "data" / "example_v2"
    cand.parent.mkdir(parents=True)
    manifest = save_candidate(
        v2, cand, {"candidate_id": "example_v2", "classifier": "lr", "threshold": 0.45}
    )
    registry = yaml.safe_load((REPO / "configs" / "inference_models.yaml").read_text("utf-8"))
    registry["models"]["ml_v1"].update(
        artifact_dir="models/example_v1",
        artifact_sha256=v1_sha,
        model_fingerprint=model_fingerprint(v1),
        threshold=0.5,
    )
    registry["models"]["ml_v2"].update(
        artifact_dir="data/example_v2",
        artifact_sha256=manifest["artifact_sha256"],
        model_fingerprint=manifest["model_fingerprint"],
        threshold=0.45,
        model_version="example_v2",
    )
    registry["comparison_aggregates"] = str(
        REPO / "docs/research/model_v2/fast_benchmark_aggregates.json"
    )
    registry["model_input_rights"]["rights_config"] = str(
        REPO / "configs/ml_rights_eligibility_v2.yaml"
    )
    (root / "registry.yaml").write_text(yaml.safe_dump(registry, allow_unicode=True), "utf-8")
    return root


def client(
    root: Path, db_url: str = "sqlite:///example-absent.sqlite", **overrides: Any
) -> TestClient:
    values: dict[str, Any] = {
        "environment": "development",
        "source_data_access": "local_development",
        "database_url": db_url,
        "inference_root": str(root),
        "inference_registry_path": "registry.yaml",
        "trusted_registry_path": "trusted.json",
        "review_database_url": f"sqlite:///{(root / 'reviews.sqlite').as_posix()}",
    }
    values.update(overrides)
    return TestClient(create_app(Settings(_env_file=None, **values)))


TEXT = {"title": "example flood resilience", "description": "example climate adaptation works"}


# ------------------------------------------------------------------------- modes / access
def test_default_mode_is_v1_only_and_v2_requires_the_demo(models_root: Path) -> None:
    c = client(models_root)
    models = c.get("/api/v1/models").json()

    assert models["operational"]["mode"] == "standard_local_research"
    assert {m["model_key"]: m["selectable_now"] for m in models["models"]} == {
        "ml_v2": False,
        "ml_v1": True,
    }
    assert c.post("/api/v1/screening/text", json=TEXT).json()["model"]["model_key"] == "ml_v1"
    denied = c.post("/api/v1/screening/text", json={**TEXT, "model": "ml_v2"})
    assert denied.status_code == 403 and denied.json()["code"] == "ml_v2_demo_not_authorized"


def test_demo_mode_makes_v2_default_without_changing_its_status(models_root: Path) -> None:
    c = client(models_root, ml_v2_local_demo=True)
    body = c.post("/api/v1/screening/text", json=TEXT).json()

    assert body["model"]["model_key"] == "ml_v2"
    assert body["model"]["status"] == "development_candidate"
    assert body["operational_mode"] == "authorized_local_demo"
    assert body["model"]["engine_label"] == "Compassio Climate Intelligence — ML v2"
    assert body["model"]["evaluation"]["independent_generalization_evidence"] is False
    v1 = c.post("/api/v1/screening/text", json={**TEXT, "model": "ml_v1"}).json()
    assert v1["model"]["status"] == "trusted_research_release"


@pytest.mark.parametrize(
    "overrides",
    [
        {"environment": "production", "ml_v2_local_demo": True},
        {"source_data_access": "public", "ml_v2_local_demo": True},
    ],
)
def test_inference_is_disabled_outside_local_development(
    models_root: Path, overrides: dict[str, Any]
) -> None:
    c = client(models_root, **overrides)

    assert c.get("/api/v1/models").json()["operational"]["mode"] == "inference_disabled"
    r = c.post("/api/v1/screening/text", json=TEXT)
    assert r.status_code == 403 and r.json()["code"] == "inference_not_authorized"


def test_demo_flag_is_ignored_in_the_test_environment(models_root: Path) -> None:
    c = client(models_root, environment="test", ml_v2_local_demo=True)

    assert c.get("/api/v1/models").json()["operational"]["mode"] == "standard_local_research"


# ------------------------------------------------------------------- faithful inference
def test_scores_match_the_guarded_predictor_and_explanations_are_exact(models_root: Path) -> None:
    c = client(models_root, ml_v2_local_demo=True)
    body = c.post("/api/v1/screening/text", json={**TEXT, "top_k": 25}).json()
    reference = ExperimentalClassifier.load(
        models_root / "data/example_v2", models_root / "trusted.json"
    )
    expected = reference.predict(TEXT["title"], TEXT["description"])

    assert body["prediction"]["label_score"] == pytest.approx(expected.label_score, abs=1e-12)
    exp = body["explanation"]
    assert exp["faithfulness_abs_error"] < 1e-12
    assert exp["intercept"] + exp["feature_contribution_total"] == pytest.approx(
        exp["logit"], abs=1e-9
    )
    assert exp["word_contribution_total"] == pytest.approx(
        exp["feature_contribution_total"], abs=1e-9
    )
    shown = {f["feature"] for f in exp["top_positive_features"] + exp["top_negative_features"]}
    assert len(shown) <= exp["nonzero_features"]
    assert 1 / (1 + np.exp(-exp["logit"])) == pytest.approx(body["prediction"]["label_score"])
    words = exp["top_words"]
    assert exp["word_attribution_available"] is True
    for w in words:
        field_text = TEXT[w["field"]]
        assert field_text[w["start"] : w["end"]] == w["word"]


def test_response_metadata_is_versioned_and_scoped(models_root: Path) -> None:
    body = client(models_root).post("/api/v1/screening/text", json=TEXT).json()

    model = body["model"]
    assert set(model) >= {
        "model_version",
        "artifact_sha256",
        "model_fingerprint",
        "threshold",
        "evaluation",
    }
    assert "financial return or profit" in body["not_predicted"]
    assert body["screening_id"] is None and body["saved"] is False
    assert (
        body["input_sha256"]
        == hashlib.sha256((TEXT["title"] + " \n " + TEXT["description"]).encode()).hexdigest()
    )


@pytest.mark.parametrize(
    "payload, code",
    [
        ({"title": " ", "description": ""}, "empty_input"),
        ({"title": "example\x00bad"}, "invalid_text"),
    ],
)
def test_malformed_and_empty_text(models_root: Path, payload: dict[str, str], code: str) -> None:
    r = client(models_root).post("/api/v1/screening/text", json=payload)

    assert r.status_code == 422 and r.json()["code"] == code


@pytest.mark.parametrize(
    "payload", [{"title": "x" * 1001}, {"title": "ok", "unknown": 1}, {"title": "ok", "top_k": 99}]
)
def test_bounded_inputs_are_validated(models_root: Path, payload: dict[str, Any]) -> None:
    assert client(models_root).post("/api/v1/screening/text", json=payload).status_code == 422


def test_control_characters_are_removed_before_scoring(models_root: Path) -> None:
    c = client(models_root)
    clean = c.post("/api/v1/screening/text", json=TEXT).json()
    dirty = c.post(
        "/api/v1/screening/text",
        json={"title": "example flood\u0007 resilience", "description": TEXT["description"]},
    ).json()

    assert dirty["prediction"]["label_score"] == clean["prediction"]["label_score"]


# ---------------------------------------------------------------- integrity / fallback
def test_tampered_or_mismatched_artifacts_are_refused(models_root: Path) -> None:
    (models_root / "data/example_v2/model.joblib").write_bytes(b"example corrupted")
    c = client(models_root, ml_v2_local_demo=True)

    r = c.post("/api/v1/screening/text", json={**TEXT, "model": "ml_v2"})
    assert r.status_code == 503 and r.json()["code"] == "model_unavailable"
    fallback = c.post("/api/v1/screening/text", json=TEXT).json()
    assert fallback["model"]["model_key"] == "ml_v1" and fallback["fallback_used"] is True


def test_registry_pin_mismatch_is_refused(models_root: Path) -> None:
    path = models_root / "registry.yaml"
    registry = yaml.safe_load(path.read_text("utf-8"))
    registry["models"]["ml_v1"]["model_fingerprint"] = "0" * 64
    path.write_text(yaml.safe_dump(registry, allow_unicode=True), "utf-8")

    r = client(models_root).post("/api/v1/screening/text", json=TEXT)
    assert r.status_code == 503 and "fingerprint" in r.json()["message"]


# --------------------------------------------------------------------- persistence/audit
def test_nothing_is_persisted_unless_saving_with_a_valid_token(models_root: Path) -> None:
    store = models_root / "reviews.sqlite"
    client(models_root).post("/api/v1/screening/text", json=TEXT)
    assert not store.exists()

    no_token = client(models_root).post("/api/v1/screening/text", json={**TEXT, "save": True})
    assert no_token.status_code == 403 and no_token.json()["code"] == "review_writes_disabled"
    c = client(models_root, review_api_token=TOKEN)
    bad = c.post(
        "/api/v1/screening/text",
        json={**TEXT, "save": True},
        headers={"X-Compassio-Review-Token": "wrong"},
    )
    assert bad.status_code == 401
    ok = c.post(
        "/api/v1/screening/text",
        json={**TEXT, "save": True},
        headers={"X-Compassio-Review-Token": TOKEN},
    ).json()
    assert ok["saved"] is True and len(ok["screening_id"]) == 36
    with sqlite3.connect(store) as con:
        assert con.execute("select count(*), max(saved_title) from screenings").fetchone() == (
            1,
            TEXT["title"],
        )


def test_review_chain_records_provenance_and_detects_tampering(models_root: Path) -> None:
    c = client(models_root, review_api_token=TOKEN)
    h = {"X-Compassio-Review-Token": TOKEN}
    sid = c.post("/api/v1/screening/text", json={**TEXT, "save": True}, headers=h).json()[
        "screening_id"
    ]
    for decision in ("agree", "uncertain"):
        r = c.post(
            "/api/v1/reviews",
            json={"screening_id": sid, "decision": decision, "reviewer": "example_reviewer"},
            headers=h,
        )
        assert r.status_code == 201
    listed = c.get(f"/api/v1/reviews/{sid}", headers=h).json()
    assert listed["chain_valid"] is True and listed["chain_length"] == 2
    assert listed["reviews"][1]["prev_hash"] == listed["reviews"][0]["row_hash"]
    assert listed["reviews"][0]["created_at"].endswith("Z")

    with sqlite3.connect(models_root / "reviews.sqlite") as con:
        con.execute("update review_decisions set decision = 'disagree' where id = 1")
    assert c.get(f"/api/v1/reviews/{sid}", headers=h).json()["chain_valid"] is False
    missing = c.post(
        "/api/v1/reviews",
        json={"screening_id": "0" * 36, "decision": "agree", "reviewer": "example"},
        headers=h,
    )
    assert missing.status_code == 404
    assert c.get(f"/api/v1/reviews/{sid}").status_code == 401


# ----------------------------------------------------------------- database records
def test_project_screening_enforces_model_input_rights(models_root: Path, seeded_url: str) -> None:
    c = client(models_root, db_url=seeded_url)

    ok = c.post("/api/v1/screening/projects/aiddata:1", json={})
    assert ok.status_code == 200
    assert ok.json()["source_evidence"]["model_input_permission"].startswith("aiddata:")
    gcf = c.post("/api/v1/screening/projects/gcf_projects:FP901", json={})
    assert gcf.status_code == 403 and gcf.json()["code"] == "source_not_permitted_for_model_input"
    assert c.post("/api/v1/screening/projects/aiddata:missing", json={}).status_code == 404
    public = client(models_root, db_url=seeded_url, source_data_access="public")
    assert public.post("/api/v1/screening/projects/aiddata:1", json={}).status_code == 403


# ------------------------------------------------------------------------- comparison
def test_comparison_serves_the_committed_aggregates(models_root: Path) -> None:
    body = client(models_root).get("/api/v1/models/comparison").json()
    data = json.loads(
        (REPO / "docs/research/model_v2/fast_benchmark_aggregates.json").read_text("utf-8")
    )

    assert body["records"] == data["population"]["records"] == 2550
    assert body["ml_v2"]["metrics"] == data["ml_v2"]["metrics"]
    assert body["false_positive_tradeoff"]["additional_false_positives"] == (
        data["ml_v2"]["confusion"]["fp"] - data["ml_v1"]["confusion"]["fp"]
    )
    assert body["used_for_model_selection"] is True


def test_editing_a_saved_screening_field_breaks_the_chain(models_root: Path) -> None:
    c = client(models_root, review_api_token=TOKEN)
    h = {"X-Compassio-Review-Token": TOKEN}
    sid = c.post("/api/v1/screening/text", json={**TEXT, "save": True}, headers=h).json()[
        "screening_id"
    ]
    c.post(
        "/api/v1/reviews",
        json={"screening_id": sid, "decision": "agree", "reviewer": "example"},
        headers=h,
    )
    with sqlite3.connect(models_root / "reviews.sqlite") as con:
        con.execute("update screenings set saved_title = 'example edited'")
    assert c.get(f"/api/v1/reviews/{sid}", headers=h).json()["chain_valid"] is False


def test_concurrent_reviews_keep_a_single_linear_chain(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from compassio_api.inference.store import ReviewStore

    store = ReviewStore(f"sqlite:///{(tmp_path / 'example.sqlite').as_posix()}")
    rec = store.save_screening(
        model_key="ml_v1",
        model_version="example",
        model_status="example",
        operational_mode="example",
        artifact_sha256="0" * 64,
        model_fingerprint="0" * 64,
        threshold=0.5,
        score=0.5,
        is_climate_related=True,
        input_sha256="0" * 64,
        project_id=None,
        source_id=None,
        saved_title=None,
        saved_description=None,
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                lambda i: store.add_review(rec.screening_id, "agree", None, f"example{i}"),
                range(40),
            )
        )
    status = store.verify_chain()
    assert status.valid and status.decisions == 40
