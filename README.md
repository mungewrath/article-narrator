# Article Audio

Initial local implementation for the home-lab side of the article-to-podcast pipeline.

## Included

- `article-sqs-bridge` Python CLI that long-polls SQS
- local durable job directories under `ARTICLE_AUDIO_JOBS_ROOT`
- optional local handoff command that must succeed before the SQS message is deleted
- Docker Compose service for the SQS bridge
- Prefect server and worker services for local orchestration
- host bridge support for reaching a fish TTS process running on the same machine

## Job directory layout

For each accepted SQS message, the bridge creates:

- `<jobs_root>/<job_id>/input.json`
- `<jobs_root>/<job_id>/received.json`
- `<jobs_root>/<job_id>/handoff.json`
- `<jobs_root>/<job_id>/chunks/`
- `<jobs_root>/<job_id>/audio/`

This keeps the durable local receipt marker in place before any later worker or Prefect flow takes over.

## Expected SQS payload

```json
{
  "job_id": "00000000-0000-0000-0000-000000000000",
  "url": "https://example.com/article",
  "submitted_at": "2026-05-21T12:34:56Z"
}
```

## Local setup

```bash
cp config/article-sqs-bridge.env.example config/article-sqs-bridge.env
cp config/prefect.env.example config/prefect.env
mkdir -p var/jobs
```

Update the copied env files with real values before starting services.

## Docker Compose

```bash
mkdir -p var/jobs
docker compose up --build -d
```

This starts:

- `elasticmq` for local SQS-compatible testing
- `article-sqs-bridge`
- `prefect-server` on `http://localhost:4200`
- `prefect-worker`
- `prefect-bootstrap`, which creates the work pool and registers the demo deployment

To watch logs:

```bash
docker compose logs -f article-sqs-bridge
```

To stop the stack:

```bash
docker compose down
```

The stack includes an ElasticMQ SQS-compatible endpoint, so it is testable without a real AWS queue.

## Local verification

Run a full smoke test against the local ElasticMQ queue:

```bash
mkdir -p var/jobs
docker compose up --build -d
```

Wait a few seconds for ElasticMQ to initialize, then enqueue a test message.
The host-side `aws` CLI still needs dummy credentials even though this is not real AWS:

```bash
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_REGION=us-east-1 \
AWS_ENDPOINT_URL=http://localhost:9324 \
ARTICLE_AUDIO_QUEUE_URL=http://localhost:9324/queue/article-audio-jobs \
./scripts/send-test-job.sh
```

Inspect the bridge output and generated job directories:

```bash
docker compose logs -f article-sqs-bridge
ls var/jobs
```

You should see log lines showing that the bridge received the SQS message, wrote the local job directory, and deleted the message after durable handoff.

Inspect the generated files for a specific job:

```bash
JOB_ID="<job-id-from-send-test-job-or-var-jobs>"
ls "var/jobs/$JOB_ID"
sed -n '1,120p' "var/jobs/$JOB_ID/input.json"
sed -n '1,120p' "var/jobs/$JOB_ID/received.json"
sed -n '1,120p' "var/jobs/$JOB_ID/handoff.json"
```

You should see `input.json`, `received.json`, and `handoff.json` in that directory.

When you are done:

```bash
docker compose down
```

If you want the bridge to hit real AWS instead, replace the values in `config/article-sqs-bridge.env` with your real queue URL and AWS settings.

## Manual local run

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
source .venv/bin/activate
article-sqs-bridge --once
```

## Host fish TTS bridge

The bridge container adds `host.docker.internal` via Docker's `host-gateway` mapping.
That gives future worker code a stable way to reach a fish TTS server running directly on the host machine, for example `http://host.docker.internal:8888`.

## Prefect

The local Prefect UI is available at `http://localhost:4200`.

The Compose stack registers a demo deployment named `hello-world-tts/hello-world-tts`.
It runs through the Prefect worker, calls the host fish server at `http://host.docker.internal:8888/v1/tts`, and writes the generated audio under `var/jobs/prefect-demo/`.

Trigger the demo deployment from the repo root:

```bash
./scripts/run-prefect-hello-tts.sh
```

Or override the text:

```bash
./scripts/run-prefect-hello-tts.sh "Hello from Prefect and Fish Speech"
```

Watch the worker logs while the deployment runs:

```bash
docker compose logs -f prefect-worker prefect-bootstrap prefect-server
```

## Notes

- Invalid payloads or failed local handoffs are left on SQS for retry/DLQ handling.
- The bridge currently stops at durable local handoff. Prefect worker integration is the next layer.
