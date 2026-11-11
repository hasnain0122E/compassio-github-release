"""Local, append-only experiment registry (JSON lines) with immutable configuration hashes.

Every trial is written as ``started`` before it runs and ``completed`` or ``failed`` after, so
an interrupted run leaves a visible ``started`` record with no matching completion.
"""

import json
import platform
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from compassio_ml.modeling.config import stable_hash
from compassio_ml.modeling.frozen import sha256_file

TRACKED_PACKAGES = ("compassio-ml", "scikit-learn", "scipy", "numpy", "pandas", "pyarrow", "joblib")


class RunExistsError(FileExistsError):
    """The deterministic run directory already exists and overwrite was not requested."""


def git_state(repo: Path) -> dict[str, object]:
    def run(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", *args], cwd=repo, capture_output=True, text=True, check=True, timeout=30
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip()

    status = run("status", "--porcelain")
    return {
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(status) if status is not None else None,
    }


def environment(repo: Path) -> dict[str, object]:
    lock = repo / "uv.lock"
    manifest = repo / "data" / "manifests" / "source_manifest.json"
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {p: version(p) for p in TRACKED_PACKAGES},
        "uv_lock_sha256": sha256_file(lock) if lock.is_file() else None,
        "source_manifest_sha256": sha256_file(manifest) if manifest.is_file() else None,
        "git": git_state(repo),
    }


@dataclass
class Registry:
    run_dir: Path
    run_id: str

    @property
    def path(self) -> Path:
        return self.run_dir / "trials.jsonl"

    def log(self, record: dict[str, object]) -> None:
        payload = {"run_id": self.run_id, "logged_at": datetime.now(UTC).isoformat(), **record}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")


def trial_id(run_id: str, spec: dict[str, object]) -> str:
    return "t_" + stable_hash({"run": run_id, **spec})[:12]


def prepare_run_dir(root: Path, run_id: str, *, overwrite: bool) -> Path:
    run_dir = root / run_id
    if run_dir.exists():
        if not overwrite:
            raise RunExistsError(
                f"{run_dir} already exists; pass --overwrite to replace it or change --seed/--suite"
            )
        for child in sorted(run_dir.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            else:
                child.rmdir()
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def read_trials(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
