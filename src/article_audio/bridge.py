from __future__ import annotations

import json
import logging
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3

from article_audio.config import BridgeConfig
from article_audio.models import ArticleJob, JobStatus, utc_now_iso


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReceivedMessage:
    message_id: str
    receipt_handle: str
    body: str


class ArticleSqsBridge:
    def __init__(self, config: BridgeConfig):
        self.config = config
        client_kwargs = {
            "region_name": config.region_name,
        }
        if config.endpoint_url:
            client_kwargs["endpoint_url"] = config.endpoint_url
        if config.aws_access_key_id:
            client_kwargs["aws_access_key_id"] = config.aws_access_key_id
        if config.aws_secret_access_key:
            client_kwargs["aws_secret_access_key"] = config.aws_secret_access_key
        self.sqs = boto3.client("sqs", **client_kwargs)

    def run_forever(self) -> None:
        self.config.jobs_root.mkdir(parents=True, exist_ok=True)
        while True:
            processed = self.process_one_message()
            if self.config.once:
                return
            if not processed:
                time.sleep(self.config.idle_sleep_seconds)

    def process_one_message(self) -> bool:
        response = self.sqs.receive_message(
            QueueUrl=self.config.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=self.config.wait_time_seconds,
            VisibilityTimeout=self.config.visibility_timeout,
        )
        messages = response.get("Messages", [])
        if not messages:
            return False

        raw_message = messages[0]
        message = ReceivedMessage(
            message_id=raw_message["MessageId"],
            receipt_handle=raw_message["ReceiptHandle"],
            body=raw_message["Body"],
        )
        self._handle_message(message)
        return True

    def _handle_message(self, message: ReceivedMessage) -> None:
        LOGGER.info("Received SQS message %s", message.message_id)
        try:
            payload = json.loads(message.body)
            job = ArticleJob.from_payload(payload)
            job_dir = self._prepare_job_directory(job, message)
            self._durable_handoff(job, job_dir)
        except Exception:
            LOGGER.exception("Failed to process SQS message %s", message.message_id)
            return

        self.sqs.delete_message(
            QueueUrl=self.config.queue_url,
            ReceiptHandle=message.receipt_handle,
        )
        LOGGER.info("Deleted SQS message %s after durable handoff", message.message_id)

    def _prepare_job_directory(self, job: ArticleJob, message: ReceivedMessage) -> Path:
        job_dir = self.config.jobs_root / job.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "chunks").mkdir(exist_ok=True)
        (job_dir / "audio").mkdir(exist_ok=True)

        self._write_json(job_dir / "input.json", job.input_document())
        self._write_json(
            job_dir / "received.json",
            job.status_document(
                JobStatus.RECEIVED,
                sqs_message_id=message.message_id,
                received_at=utc_now_iso(),
            ),
        )
        return job_dir

    def _durable_handoff(self, job: ArticleJob, job_dir: Path) -> None:
        handoff_command = self.config.handoff_command
        if not handoff_command:
            self._write_json(
                job_dir / "handoff.json",
                job.status_document(
                    JobStatus.RECEIVED,
                    handoff="local-only",
                    note="No ARTICLE_AUDIO_HANDOFF_COMMAND configured",
                ),
            )
            LOGGER.info(
                "Prepared local job directory for %s without external handoff",
                job.job_id,
            )
            return

        env = {
            **self._stringified_env(),
            "ARTICLE_JOB_ID": job.job_id,
            "ARTICLE_JOB_URL": job.url,
            "ARTICLE_JOB_SUBMITTED_AT": job.submitted_at,
            "ARTICLE_JOB_DIR": str(job_dir),
        }
        LOGGER.info("Running handoff command for %s: %s", job.job_id, handoff_command)
        result = subprocess.run(
            [self.config.handoff_shell, "-lc", handoff_command],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        handoff_record = job.status_document(
            JobStatus.RECEIVED,
            handoff="command",
            command=handoff_command,
            command_argv=shlex.split(handoff_command),
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        self._write_json(job_dir / "handoff.json", handoff_record)

        if result.returncode != 0:
            raise RuntimeError(
                f"handoff command failed with exit code {result.returncode}"
            )

    @staticmethod
    def _write_json(path: Path, document: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _stringified_env() -> dict[str, str]:
        import os

        return {
            key: value for key, value in os.environ.items() if isinstance(value, str)
        }


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
