#!/bin/sh
set -eu

TITLE="${1:-Untitled Article}"
DESCRIPTION="${2:-}"

TEXT=$(cat)

docker compose exec -T prefect-server \
  env PREFECT_API_URL=http://prefect-server:4200/api \
  prefect deployment run article-to-podcast/article-to-podcast \
  --param "text=${TEXT}" \
  --param "title=${TITLE}" \
  --param "description=${DESCRIPTION}"
