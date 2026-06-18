# Article Narrator

Pipeline that converts web articles into podcast episodes using a self-hosted TTS server (Fish Speech).

```
User pastes URL to Frontend → SQS → Prefect processes the rest as a job (article extraction via trafilatura → chunked TTS (Fish Speech) → ffmpeg merge → ABS podcast episode)
```

This repo contains:
- **Static frontend** for submitting URLs via browser
- **Terraform** for deploying the AWS infrastructure
- **Docker compose** backend which is intended to be self-hosted

## Architecture

```
┌──────────────┐  browser   ┌──────────────────┐
│  Frontend     │───────────▶│  API Gateway      │
│ (S3/CF, SPA)  │◀──────────│  Cognito auth     │
└──────────────┘   tokens   └────────┬─────────┘
                                     │ SQS SendMessage
                            ┌────────▼─────────┐
                            │  SQS Queue        │
                            │  (+ DLQ)          │
                            └────────┬─────────┘
                                     │ long-poll
                                     │
                            ┌────────▼─────────┐
                            │  Prefect worker   │
                            │  (flows)          │
                            └────────┬─────────┘
                                     │ MP3
                            ┌────────▼─────────┐
                            │  Audiobookshelf   │
                            │  (podcast)        │
                            └──────────────────┘
```

- **Frontend** — static SPA served from CloudFront. Cognito Hosted UI handles login. Posts article URLs to API Gateway.
- **API Gateway** — REST API with Cognito authorizer. Integrates directly with SQS (no Lambda).
- **SQS** — job queue with DLQ. Consumed by the SQS bridge.
- **Article SQS Bridge** — long-polls SQS for job messages, writes durable job directories. Runs in Docker.
- **Prefect** — orchestrates pipeline flows (extract, chunk, TTS, merge, place). Runs in Docker.
- **Fish TTS** — must be configured on the host separately from this repo. Reached from containers via `host.docker.internal:8888`.
- **Audiobookshelf** — podcast library manager. MP3 episodes placed via host-mounted directory + API scan. Runs in Docker.

## Services (Docker Compose — local dev)

| Service | Port | Purpose |
|---|---|---|
| `article-sqs-bridge` | — | Long-polls SQS, writes job dirs |
| `elasticmq` | 9324 | Local SQS-compatible queue |
| `prefect-server` | 4200 | Prefect API + UI |
| `prefect-worker` | — | Executes flow runs |
| `prefect-bootstrap` | — | One-shot: creates work pool, registers deployments |
| `audiobookshelf` | 13378 | Podcast library |

## Expected SQS payload

```json
{
  "job_id": "00000000-0000-0000-0000-000000000000",
  "url": "https://example.com/article",
  "submitted_at": "2026-05-21T12:34:56Z"
}
```

## Terraform

```
terraform/
├── main.tf       # SQS queue + DLQ, API Gateway, Cognito User Pool
├── variables.tf  # Region, queue name, allowed origins, etc.
└── outputs.tf    # API endpoint, queue URL, Cognito domain & client ID
```

The Terraform provisions:

- **Cognito User Pool** — user directory, Hosted UI domain, app client with implicit OAuth grant (openid scope).
- **API Gateway** — REST API with `POST /submit`. Cognito authorizer validates the ID token. Integrates directly with SQS via AWS service integration (no Lambda).
- **SQS Queue** — standard queue with DLQ. Receives messages from API Gateway.

### Usage

```bash
cd terraform
terraform init
terraform apply
```

After apply, set the output values in `frontend/config.js` and deploy the frontend to S3, CloudFront, or any static host.

The `allowed_origins` variable controls the Cognito callback/logout URLs. Update it to match your frontend's deployed URL.

## Local setup

```bash
cp config/article-sqs-bridge.env.example config/article-sqs-bridge.env
cp config/prefect.env.example config/prefect.env
mkdir -p var/jobs

cd frontend/
npm install
```

Update the copied env files with real values before starting services.

```bash
mkdir -p var/jobs
# Start the backend
docker compose up --build -d
# Start the frontend (optional)
npm run dev
```

## Testing

### Unit tests

```bash
uv sync --group dev
uv run pytest tests/ -v
```

To include live URL smoke tests (hits real websites):

```bash
uv run pytest tests/ -v -m network
```

### Manual Prefect flow runs

Trigger the URL-to-podcast pipeline:

```bash
./scripts/run-prefect-url-to-podcast.sh https://example.com/article
```

Trigger the article-to-podcast flow with raw text:

```bash
docker compose exec -T prefect-server \
  env PREFECT_API_URL=http://prefect-server:4200/api \
  python -m article_audio.prefect_flows run-article \
  --text "$(cat article.txt)" --title "My Article"
```

Watch worker logs:

```bash
docker compose logs -f prefect-worker
```

Prefect UI at `http://localhost:4200`.

### Local SQS verification

```bash
mkdir -p var/jobs
docker compose up --build -d
```

Enqueue a test message:

```bash
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_REGION=us-east-1 \
AWS_ENDPOINT_URL=http://localhost:9324 \
ARTICLE_AUDIO_QUEUE_URL=http://localhost:9324/queue/article-audio-jobs \
./scripts/send-test-job.sh
```

Inspect results:

```bash
docker compose logs -f article-sqs-bridge
ls var/jobs/<job-id>
```

### Manual local run end-to-end

```bash
uv run python article-sqs-bridge --once
```

## Deployment

This bundles all frontend content into a static asset, then deploys terraform:

```bash
frontend/build.sh -e <env>
```

Note that you can run `terraform plan` in the terraform/ directory to see the infra changes.

## Notes

- Invalid payloads or failed local handoffs are left on SQS for retry/DLQ handling.
- Assumes that self-hosted Fish TTS runs sequentially, one request at a time. Chunks are fed in one by one.
