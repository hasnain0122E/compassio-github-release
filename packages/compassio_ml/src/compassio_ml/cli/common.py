import argparse
import sys
from pathlib import Path

from compassio_ml.data.layout import DataLayout


def add_data_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Data root containing raw/ and manifests/ (default: $COMPASSIO_DATA_DIR or ./data)",
    )


def layout_from(args: argparse.Namespace) -> DataLayout:
    return DataLayout(args.data_dir) if args.data_dir else DataLayout.from_env()


def data_root_label(layout: DataLayout) -> str:
    """Repo-relative label when possible, so artifacts do not embed user paths."""
    try:
        return layout.root.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return layout.root.name


def configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")
