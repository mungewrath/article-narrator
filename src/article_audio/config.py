from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BridgeConfig:
    queue_url: str
    jobs_root: Path
    region_name: str | None
    endpoint_url: str | None
    aws_access_key_id: str | None
    aws_secret_access_key: str | None
    wait_time_seconds: int
    visibility_timeout: int
    idle_sleep_seconds: float
    handoff_command: str | None
    handoff_shell: str
    log_level: str
    once: bool

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        queue_url = os.getenv("ARTICLE_AUDIO_QUEUE_URL", "").strip()
        if not queue_url:
            raise ValueError("ARTICLE_AUDIO_QUEUE_URL is required")

        jobs_root_raw = os.getenv("ARTICLE_AUDIO_JOBS_ROOT", "./var/jobs")
        jobs_root = Path(jobs_root_raw).expanduser().resolve()

        return cls(
            queue_url=queue_url,
            jobs_root=jobs_root,
            region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
            endpoint_url=os.getenv("AWS_ENDPOINT_URL", "").strip() or None,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "").strip() or None,
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
            or None,
            wait_time_seconds=int(
                os.getenv("ARTICLE_AUDIO_SQS_WAIT_TIME_SECONDS", "20")
            ),
            visibility_timeout=int(
                os.getenv("ARTICLE_AUDIO_SQS_VISIBILITY_TIMEOUT", "300")
            ),
            idle_sleep_seconds=float(
                os.getenv("ARTICLE_AUDIO_IDLE_SLEEP_SECONDS", "2")
            ),
            handoff_command=os.getenv("ARTICLE_AUDIO_HANDOFF_COMMAND", "").strip()
            or None,
            handoff_shell=os.getenv("ARTICLE_AUDIO_HANDOFF_SHELL", "/bin/bash"),
            log_level=os.getenv("ARTICLE_AUDIO_LOG_LEVEL", "INFO"),
            once=_env_bool("ARTICLE_AUDIO_RUN_ONCE", False),
        )
