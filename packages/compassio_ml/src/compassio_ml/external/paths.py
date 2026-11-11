"""Separate, read-only INPUT roots and a writable OUTPUT root for ML v2 work.

The v1 tooling (``compassio_ml.data.layout``) uses one data root from ``COMPASSIO_DATA_DIR`` for
both reading and writing, and is left unchanged. ML v2 work in a separate worktree must read the
original project's registered files without ever writing into them, so it uses:

* ``COMPASSIO_DATA_ROOT`` - the original project's ``data/`` directory (raw/, processed/,
  manifests/). **Read-only.** Required for commands that need v1 inputs.
* ``COMPASSIO_V1_PROJECT_ROOT`` - optional; the original project root holding ``models/`` and
  ``experiments/``. Defaults to the parent of ``COMPASSIO_DATA_ROOT``. **Read-only.**
* ``COMPASSIO_V2_OUTPUT_ROOT`` - optional; owned v2 output directory, default ``data/ml_v2``.
* ``COMPASSIO_V2_EXTERNAL_INPUT_ROOT`` - optional, read-only directory containing existing
  per-source retrievals; acquisition writes are refused while this input override is active.

In a combined checkout, only its own canonical ``data/`` input root permits sibling v2
outputs. Raw/interim/processed/manifests/backend staging/database/model/experiment roots remain
protected. Separate-worktree mode retains its original whole-input-root isolation.

:meth:`V2Paths.writable` refuses any path outside the output root or inside an input root, and
:meth:`V2Paths.check_separation` refuses overlapping roots, so no v2 command can modify v1 raw
files, the database, the released model or the frozen evaluation artifacts.
"""

import os
from dataclasses import dataclass
from pathlib import Path

INPUT_DATA_ROOT_ENV = "COMPASSIO_DATA_ROOT"
V1_PROJECT_ROOT_ENV = "COMPASSIO_V1_PROJECT_ROOT"
OUTPUT_ROOT_ENV = "COMPASSIO_V2_OUTPUT_ROOT"
EXTERNAL_INPUT_ROOT_ENV = "COMPASSIO_V2_EXTERNAL_INPUT_ROOT"
DEFAULT_OUTPUT_SUBDIR = Path("data") / "ml_v2"
# Input sub-directories ML v2 must never read: the backend GCF API snapshot (ai-train=no)
# and the application database.
FORBIDDEN_INPUT_SUBDIRS = ("raw_db", "db")


class UnsafePathError(RuntimeError):
    """A v2 write would land outside the output root or inside a read-only input root."""


class MissingInputRootError(RuntimeError):
    """The read-only v1 input root is not configured or does not exist."""


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


@dataclass(frozen=True, slots=True)
class V2Paths:
    """Resolved roots. ``input_data_root``/``v1_project_root`` may be ``None`` if unconfigured."""

    repo_root: Path
    output_root: Path
    input_data_root: Path | None
    v1_project_root: Path | None
    external_input_root: Path | None = None

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "V2Paths":
        repo = (repo_root or Path.cwd()).resolve()
        out_env = os.environ.get(OUTPUT_ROOT_ENV)
        output = Path(out_env).resolve() if out_env else (repo / DEFAULT_OUTPUT_SUBDIR).resolve()
        data_env = os.environ.get(INPUT_DATA_ROOT_ENV)
        data_root = Path(data_env).resolve() if data_env else None
        proj_env = os.environ.get(V1_PROJECT_ROOT_ENV)
        if proj_env:
            project: Path | None = Path(proj_env).resolve()
        else:
            project = data_root.parent if data_root is not None else None
        external_env = os.environ.get(EXTERNAL_INPUT_ROOT_ENV)
        external = Path(external_env).resolve() if external_env else None
        paths = cls(repo, output, data_root, project, external)
        paths.check_separation()
        return paths

    # ------------------------------------------------------------------ safety
    def _input_roots(self) -> list[Path]:
        if self._combined_checkout():
            assert self.input_data_root is not None
            roots = [
                self.input_data_root / name
                for name in ("raw", "interim", "processed", "manifests", "raw_db", "db")
            ]
            roots.extend([self.repo_root / "models", self.repo_root / "experiments"])
        else:
            roots = [r for r in (self.input_data_root, self.v1_project_root) if r is not None]
        if self.external_input_root is not None:
            roots.append(self.external_input_root)
        return [r.resolve() for r in roots]

    def _combined_checkout(self) -> bool:
        """Only the checkout's own canonical data root admits sibling v2 outputs."""
        return (
            self.v1_project_root is not None
            and self.input_data_root is not None
            and self.v1_project_root.resolve() == self.repo_root.resolve()
            and self.input_data_root.resolve() == (self.repo_root / "data").resolve()
        )

    def check_separation(self) -> None:
        """Refuse configurations where the output root and an input root overlap."""
        out = self.output_root.resolve()
        if self._combined_checkout() and not _is_within(
            out, (self.repo_root / DEFAULT_OUTPUT_SUBDIR).resolve()
        ):
            raise UnsafePathError("Combined-checkout outputs must stay under data/ml_v2/")
        if self.external_input_root is not None:
            self.readable(self.external_input_root)
            if not self.external_input_root.is_dir():
                raise MissingInputRootError(
                    f"External input root not found: {self.external_input_root}"
                )
        for root in self._input_roots():
            if _is_within(out, root) or _is_within(root, out):
                raise UnsafePathError(
                    f"Output root {out} overlaps read-only input root {root}. Set "
                    f"{OUTPUT_ROOT_ENV} to a directory inside the ML v2 worktree."
                )

    def writable(self, path: Path) -> Path:
        """Return ``path`` resolved if it is safe to write, else raise ``UnsafePathError``."""
        self.check_separation()
        target = path.resolve()
        if not _is_within(target, self.output_root.resolve()):
            raise UnsafePathError(f"Refusing to write outside the v2 output root: {target}")
        for root in self._input_roots():
            if _is_within(target, root):
                raise UnsafePathError(f"Refusing to write inside read-only input root: {target}")
        return target

    def readable(self, path: Path) -> Path:
        """Return ``path`` resolved unless it is inside a forbidden input sub-directory."""
        target = path.resolve()
        data_roots = {self.repo_root / "data"}
        if self.input_data_root is not None:
            data_roots.add(self.input_data_root)
        for data_root in data_roots:
            for name in FORBIDDEN_INPUT_SUBDIRS:
                if _is_within(target, (data_root / name).resolve()):
                    raise UnsafePathError(f"ML v2 must not read {target} ({name}/ is forbidden)")
        return target

    def require_input(self) -> Path:
        if self.input_data_root is None:
            raise MissingInputRootError(
                f"{INPUT_DATA_ROOT_ENV} is not set. Point it at the original project's data/ "
                "directory (read-only) to verify v1 inputs."
            )
        if not self.input_data_root.is_dir():
            raise MissingInputRootError(f"Input data root not found: {self.input_data_root}")
        return self.input_data_root

    def require_v1_project(self) -> Path:
        self.require_input()
        if self.v1_project_root is None or not self.v1_project_root.is_dir():
            raise MissingInputRootError(f"v1 project root not found: {self.v1_project_root}")
        return self.v1_project_root

    # ------------------------------------------------------------------ output layout
    @property
    def external_raw(self) -> Path:
        """Immutable retrieved files, one directory per source and retrieval."""
        return self.external_input_root or self.output_root / "external_raw"

    @property
    def interim(self) -> Path:
        return self.output_root / "interim"

    @property
    def datasets(self) -> Path:
        return self.output_root / "datasets"

    @property
    def labeling(self) -> Path:
        return self.output_root / "labeling"

    @property
    def sealed(self) -> Path:
        """External-test labels; readable only through the sealed-access guard."""
        return self.output_root / "sealed_external_test"

    @property
    def restricted_reference(self) -> Path:
        """Rights-restricted records kept for separately authorised reference use only."""
        return self.output_root / "restricted_reference"

    @property
    def reports(self) -> Path:
        return self.output_root / "reports"
