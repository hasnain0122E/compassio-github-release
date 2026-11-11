"""``compassio-hash`` command: print SHA-256 digests of files without modifying them.

Output format matches ``sha256sum``: ``<digest>  <path>``.
"""

import argparse
import sys
from collections.abc import Sequence

from compassio_ml.integrity.hashing import sha256_file


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="compassio-hash",
        description="Compute SHA-256 digests of files (read-only).",
    )
    parser.add_argument("paths", nargs="+", help="Files to hash.")
    args = parser.parse_args(argv)

    exit_code = 0
    for raw_path in args.paths:
        try:
            digest = sha256_file(raw_path)
        except (FileNotFoundError, IsADirectoryError) as exc:
            print(f"compassio-hash: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        print(f"{digest}  {raw_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
