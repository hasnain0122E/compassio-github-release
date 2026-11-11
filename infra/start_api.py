"""Single-worker cloud entrypoint. No artifact download or policy override."""

import os
import subprocess
import sys
from urllib.parse import urlsplit

from compassio_api.core.config import Settings


def command() -> list[str]:
    settings = Settings()
    if settings.environment != "production":
        raise ValueError("Cloud launcher requires COMPASSIO_ENVIRONMENT=production")
    if settings.review_api_token is not None:
        raise ValueError("Cloud deployment does not enable review writes")

    def safe_origin(origin: str) -> bool:
        parsed = urlsplit(origin)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
            and "*" not in origin
        )

    if not settings.cors_origins or not all(map(safe_origin, settings.cors_origins)):
        raise ValueError("Cloud launcher requires explicit HTTPS frontend origins")
    port = int(os.environ.get("PORT", "10000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "compassio_api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--workers",
        "1",
        "--no-proxy-headers",
        "--no-access-log",
        "--timeout-keep-alive",
        "5",
    ]


if __name__ == "__main__":
    argv = command()
    if os.environ.get("COMPASSIO_RUNTIME_DOWNLOADS_FILE"):
        subprocess.run([sys.executable, "infra/provision_runtime.py"], check=True)
    os.execv(sys.executable, argv)
