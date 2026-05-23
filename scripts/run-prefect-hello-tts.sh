#!/bin/sh
set -eu

TEXT="${1:-Hello from Prefect and Fish Speech}"

docker compose exec -T prefect-server \
  env PREFECT_API_URL=http://prefect-server:4200/api \
  prefect deployment run hello-world-tts/hello-world-tts \
  --param "text=${TEXT}"
