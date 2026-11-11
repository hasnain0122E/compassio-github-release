"""LOCAL DATA: the API serves the REAL ML v1 release and ML v2 candidate exactly.

Skipped when the git-ignored artifacts are absent. Controlled inputs are artificial sentences;
the scores they produce are not model evidence, only proof of identical inference paths.
"""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from compassio_api.core.config import Settings
from compassio_api.main import create_app
from compassio_ml.integrity.hashing import sha256_file
from compassio_ml.model_v2.artifact import ExperimentalClassifier
from compassio_ml.modeling.release import ReleasedClassifier

REPO = Path(__file__).resolve().parents[1]
REGISTRY = yaml.safe_load((REPO / "configs" / "inference_models.yaml").read_text("utf-8"))
V1_DIR = REPO / REGISTRY["models"]["ml_v1"]["artifact_dir"]
V2_DIR = REPO / REGISTRY["models"]["ml_v2"]["artifact_dir"]
TRUSTED = REPO / "configs" / "trusted_model_releases.json"
INPUTS = [
    ("Example climate-resilient irrigation programme", "Example text about drought early warning."),
    ("Example rural road maintenance", "Example text about road repairs and school access."),
    ("Example solar mini-grid", ""),
]

pytestmark = [
    pytest.mark.local_data,
    pytest.mark.skipif(not (V1_DIR.is_dir() and V2_DIR.is_dir()), reason="model artifacts absent"),
]


def _client(**overrides: Any) -> TestClient:
    values: dict[str, Any] = {
        "environment": "development",
        "source_data_access": "local_development",
        "inference_root": str(REPO),
    }
    values.update(overrides)
    return TestClient(create_app(Settings(_env_file=None, **values)))


def test_registry_pins_match_the_real_artifacts() -> None:
    for key, directory in (("ml_v1", V1_DIR), ("ml_v2", V2_DIR)):
        assert sha256_file(directory / "model.joblib") == REGISTRY["models"][key]["artifact_sha256"]
    manifest = json.loads((V2_DIR / "candidate_manifest.json").read_text("utf-8"))
    assert manifest["model_fingerprint"] == REGISTRY["models"]["ml_v2"]["model_fingerprint"]
    assert manifest["status"] == "development_candidate"
    assert manifest["artifact_sha256"] not in json.loads(TRUSTED.read_text("utf-8")).values()


def test_api_v2_scores_equal_the_verified_local_predictor() -> None:
    client = _client(ml_v2_local_demo=True)
    reference = ExperimentalClassifier.load(V2_DIR, TRUSTED)
    for title, description in INPUTS:
        body = client.post(
            "/api/v1/screening/text", json={"title": title, "description": description}
        ).json()
        assert body["model"]["model_key"] == "ml_v2"
        assert (
            body["prediction"]["label_score"] == reference.predict(title, description).label_score
        )
        assert body["explanation"]["faithfulness_abs_error"] < 1e-12


def test_api_v1_fallback_scores_equal_the_trusted_release() -> None:
    client = _client()
    reference = ReleasedClassifier.load(V1_DIR, TRUSTED)
    for title, description in INPUTS:
        body = client.post(
            "/api/v1/screening/text", json={"title": title, "description": description}
        ).json()
        assert body["model"]["model_key"] == "ml_v1"
        assert body["model"]["status"] == "trusted_research_release"
        assert (
            body["prediction"]["label_score"] == reference.predict(title, description).label_score
        )
