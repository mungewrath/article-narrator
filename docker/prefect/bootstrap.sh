#!/bin/sh
set -eu

python - <<'PY'
import os
import time
import urllib.request

base_url = os.environ["PREFECT_API_URL"].removesuffix("/api")
health_url = f"{base_url}/api/health"

for _ in range(60):
    try:
        with urllib.request.urlopen(health_url, timeout=5) as response:
            if response.status == 200:
                break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit(f"Prefect server did not become healthy: {health_url}")
PY

prefect work-pool inspect "$PREFECT_WORK_POOL_NAME" >/dev/null 2>&1 || \
  prefect work-pool create --type process "$PREFECT_WORK_POOL_NAME" >/dev/null 2>&1 || \
  prefect work-pool inspect "$PREFECT_WORK_POOL_NAME" >/dev/null 2>&1

python -m article_audio.prefect_flows deploy-hello

python -m article_audio.prefect_flows deploy-article

python -m article_audio.prefect_flows deploy-url
