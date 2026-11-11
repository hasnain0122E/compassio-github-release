"""Checksum-verified LOCAL transfer of the five git-ignored runtime artifacts.

    uv run python scripts/runtime_artifacts.py verify                  # this checkout
    uv run python scripts/runtime_artifacts.py verify --root E:\\compassio_runtime
    uv run python scripts/runtime_artifacts.py export --dest E:\\compassio_runtime
    uv run python scripts/runtime_artifacts.py import --src E:\\compassio_runtime

``export`` copies the five files (same relative paths) into a local folder such as a USB drive,
re-hashes every copy and writes ``SHA256SUMS.txt``. ``import`` verifies the source copy first,
then copies into this checkout; it never overwrites a different existing file. Nothing is sent
over a network. Do not put the folder in a public repository or cloud service
(docs/hackathon/data_permission_scope.md). Raw ML v2 training data is deliberately excluded:
it is not needed for prediction (docs/hackathon/local_demo_runbook.md section 2).
"""

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
V2 = "data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550"
# relative path -> (expected SHA-256, purpose). Pinned at the backend freeze.
ARTIFACTS: dict[str, tuple[str, str]] = {
    "data/db/compassio_dev.sqlite": (
        "d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385",
        "canonical project database (read-only at runtime)",
    ),
    "models/compassio_ccrc_v1/model.joblib": (
        "53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656",
        "ML v1 trusted research release (fallback engine)",
    ),
    "models/compassio_ccrc_v1/release_manifest.json": (
        "bc3c8f78c5a42aa434da8c72459cf49e80d8f41300aaa478468802facd595282",
        "ML v1 release manifest (checked by the loader)",
    ),
    f"{V2}/model.joblib": (
        "654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574",
        "ML v2 development candidate (local-demo default engine)",
    ),
    f"{V2}/candidate_manifest.json": (
        "72b78bbb6eb02679acbbcfc1f90c2feeb13b0b42dbf597d65e4db86701e36ca5",
        "ML v2 candidate manifest (checked by the loader)",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(root: Path) -> bool:
    ok = True
    for rel, (expected, purpose) in ARTIFACTS.items():
        path = root / rel
        if not path.is_file():
            print(f"MISSING  {rel}  ({purpose})")
            ok = False
            continue
        actual = sha256(path)
        good = actual == expected
        ok &= good
        print(f"{'OK      ' if good else 'MISMATCH'}  {rel}  {actual}")
    print("All 5 runtime artifacts verified" if ok else "Verification FAILED")
    return ok


def _copy(src_root: Path, dst_root: Path, overwrite_same_only: bool) -> bool:
    for rel, (expected, _) in ARTIFACTS.items():
        src, dst = src_root / rel, dst_root / rel
        if dst.is_file():
            if sha256(dst) == expected:
                print(f"present  {rel}")
                continue
            if overwrite_same_only:
                print(f"REFUSED  {rel}: destination exists with a different checksum")
                return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if sha256(dst) != expected:
            print(f"COPY FAILED CHECKSUM  {rel}")
            return False
        print(f"copied   {rel}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--root", type=Path, default=REPO)
    e = sub.add_parser("export")
    e.add_argument("--dest", type=Path, required=True)
    i = sub.add_parser("import")
    i.add_argument("--src", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "verify":
        return 0 if verify(args.root) else 1
    if args.command == "export":
        if args.dest.resolve() == REPO:
            print("export --dest must be outside the repository")
            return 1
        if not verify(REPO) or not _copy(REPO, args.dest, overwrite_same_only=True):
            return 1
        lines = [f"{exp}  {rel}" for rel, (exp, _) in ARTIFACTS.items()]
        (args.dest / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 0 if verify(args.dest) else 1
    if not verify(args.src) or not _copy(args.src, REPO, overwrite_same_only=True):
        return 1
    return 0 if verify(REPO) else 1


if __name__ == "__main__":
    sys.exit(main())
