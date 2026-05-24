#!/bin/sh
set -eu

URL="${1:-}"
if [ -z "$URL" ]; then
  echo "Usage: $0 <url>"
  echo ""
  echo "  $0 https://every.to/p/after-automation"
  exit 1
fi

docker compose exec -T prefect-server \
  env PREFECT_API_URL=http://prefect-server:4200/api \
  prefect deployment run url-to-podcast/url-to-podcast \
  --param "url=${URL}"
