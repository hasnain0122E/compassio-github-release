"""The API process must not load the ML/data stack or the research dataset."""

import subprocess
import sys

CHECK = (
    "import sys; import compassio_api.main as m; "
    "m.create_app(); "
    "heavy = sorted(n for n in ('pandas', 'sklearn', 'pyarrow', 'joblib', 'openpyxl', "
    "'compassio_ml.modeling', 'compassio_ml.research', 'compassio_api.ingest') "
    "if n in sys.modules); print(','.join(heavy))"
)


def test_api_app_does_not_import_heavy_dependencies() -> None:
    result = subprocess.run(
        [sys.executable, "-c", CHECK], capture_output=True, text=True, check=True, timeout=120
    )

    assert result.stdout.strip() == ""
