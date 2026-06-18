# Agentic coding conventions

## Package management

- Use `uv` for all Python package operations. Project dependencies are defined in `pyproject.toml`.
- Install dependencies: `uv sync`
- Run scripts: `uv run python -m module.name` or `uv run python script.py`

## Fish TTS

- A self-hosted Fish Speech TTS server is assumed running locally on port 8888.
- From within Docker containers, reach it at `host.docker.internal:8888`.
- The TTS server is expected to handle requests sequentially (one chunk at a time).

## Project structure

- `src/article_audio/` — Python package (bridge, flows, CLI)
- `frontend/` — static SPA (vanilla JS)
- `scripts/` — utility shell scripts
- `config/` — env file templates
- `terraform/` — AWS infra (SQS, API Gateway, Cognito)
- `docker/` — Docker-related files
- `var/jobs/` — local job output directory
