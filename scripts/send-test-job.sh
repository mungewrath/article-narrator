#!/bin/sh
set -eu

JOB_ID="${1:-$(cat /proc/sys/kernel/random/uuid)}"
ARTICLE_URL="${2:-https://example.com/article}"
SUBMITTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
QUEUE_URL="${ARTICLE_AUDIO_QUEUE_URL:-http://localhost:9324/queue/article-audio-jobs}"
ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://localhost:9324}"
REGION="${AWS_REGION:-us-east-1}"

aws --endpoint-url "$ENDPOINT_URL" sqs send-message \
  --region "$REGION" \
  --queue-url "$QUEUE_URL" \
  --message-body "{\"job_id\":\"${JOB_ID}\",\"url\":\"${ARTICLE_URL}\",\"submitted_at\":\"${SUBMITTED_AT}\"}"

printf 'Enqueued test job %s\n' "$JOB_ID"
