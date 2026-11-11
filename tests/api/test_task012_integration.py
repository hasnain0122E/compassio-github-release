"""Regression coverage for real integration defects and opt-in boundaries."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.pool import QueuePool

from compassio_api.core.config import Settings
from compassio_api.db.session import create_read_engine
from compassio_api.main import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_default_read_pool_survives_concurrent_workers(seeded_url: str) -> None:
    engine = create_read_engine(seeded_url)
    assert isinstance(engine.pool, QueuePool)

    def read(_: int) -> int:
        with engine.connect() as conn:
            return int(conn.execute(text("SELECT count(*) FROM projects")).scalar_one())

    with ThreadPoolExecutor(max_workers=24) as pool:
        results = list(pool.map(read, range(120)))
    assert results and min(results) == max(results) and min(results) > 0
    with engine.connect() as conn, pytest.raises(Exception, match="readonly"):
        conn.execute(text("DELETE FROM projects"))
    engine.dispose()


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("environment", ["development", "production"])
def test_c09_adapter_fail_closed(
    enabled: bool, environment: Literal["development", "production"]
) -> None:
    settings = Settings(
        _env_file=None,
        c09_enabled=enabled,
        environment=environment,
        source_data_access="public",
        ml_v2_local_demo=True,
    )
    with TestClient(create_app(settings)) as client:
        r = client.post("/api/v1/challenges/c09/screen", json={"title": "example_text"})
        assert r.status_code == 403


@pytest.mark.local_data
@pytest.mark.skipif(
    not (ROOT / "data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/model.joblib").exists(),
    reason="canonical ML v2 artifact unavailable",
)
def test_c09_real_model_contract_and_explanations() -> None:
    model = ROOT / "data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/model.joblib"
    before = hashlib.sha256(model.read_bytes()).hexdigest()
    body = {"description": "example_text: renewable sol\u200bar energy, USD 1,234.50"}
    stable = []
    for enabled in (False, True):
        settings = Settings(
            _env_file=None,
            c09_enabled=enabled,
            source_data_access="local_development",
            ml_v2_local_demo=True,
            inference_root=str(ROOT),
        )
        with TestClient(create_app(settings)) as client:
            raw = client.post("/api/v1/screening/text", json=body).json()
            stable.append((raw["prediction"], raw["explanation"], raw["model"]))
            response = client.post("/api/v1/challenges/c09/screen", json=body)
            if not enabled:
                assert response.status_code == 403
                continue
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["standard_api"]["prediction"] == raw["prediction"]
            assert result["standard_api"]["explanation"] == raw["explanation"]
            from compassio_ml.c09.guard import GuardedClassifier
            from compassio_ml.model_v2.artifact import ExperimentalClassifier

            classifier = ExperimentalClassifier.load(
                model.parent, ROOT / "configs/trusted_model_releases.json"
            )
            direct = GuardedClassifier(classifier).predict(None, body["description"])
            assert result["raw"]["prediction"]["label_score"] == pytest.approx(direct.raw_score)
            assert result["guarded"]["prediction"]["label_score"] == pytest.approx(
                direct.guarded_score
            )
            assert result["requires_review"] == direct.requires_review
            normalized = client.post(
                "/api/v1/screening/text",
                json={"description": body["description"].replace("\u200b", "")},
            ).json()
            assert result["guarded"]["prediction"] == normalized["prediction"]
            assert result["guarded"]["explanation"] == normalized["explanation"]
            assert result["guarded"]["explanation"]["faithfulness_abs_error"] < 1e-10
            assert result["raw"]["model"] == result["guarded"]["model"]
            assert "invisible_removed" in result["reasons"]
            denied = client.post(
                "/api/v1/screening/projects/gcf_projects:FP085", json={"model": "ml_v2"}
            )
            assert denied.status_code == 403
            assert (
                client.post(
                    "/api/v1/challenges/c09/screen", json={**body, "save": True}
                ).status_code
                == 422
            )
    assert stable[0] == stable[1]
    assert hashlib.sha256(model.read_bytes()).hexdigest() == before
