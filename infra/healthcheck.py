"""Container liveness only: success does not imply authorized data/model readiness."""

import json
import os
from urllib.request import urlopen

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    with urlopen(f"http://127.0.0.1:{port}/health", timeout=4) as response:
        payload = json.load(response)
        if response.status != 200 or payload.get("status") != "ok":
            raise SystemExit(1)
