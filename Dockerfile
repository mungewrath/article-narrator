FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
RUN pip install uv && uv sync --no-install-project

COPY src ./src

RUN uv sync

COPY docker ./docker

ENTRYPOINT ["uv", "run"]
CMD ["article-sqs-bridge"]
