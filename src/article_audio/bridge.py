from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
from prefect.deployments import run_deployment

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
            decoded_body = base64.b64decode(message.body).decode("utf-8")
            body_as_json = json.loads(decoded_body)
            job = ArticleJob.from_payload(body_as_json)
            job_dir = self._prepare_job_directory(job, message)
            self._durable_handoff(job, job_dir)
        except Exception as e:
            LOGGER.exception(
                "Failed to process SQS message %s. Error message: %s",
                message.message_id,
                str(e),
            )
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
        deployment_name = self.config.prefect_deployment
        if not deployment_name:
            self._write_json(
                job_dir / "handoff.json",
                job.status_document(
                    JobStatus.RECEIVED,
                    handoff="local-only",
                    note="No ARTICLE_AUDIO_PREFECT_DEPLOYMENT configured",
                ),
            )
            LOGGER.info(
                "Prepared local job directory for %s without external handoff",
                job.job_id,
            )
            return

        parameters: dict[str, Any] = {"voice": job.voice}
        if job.text:
            parameters["text"] = job.text
            parameters["title"] = job.title or "Pasted Article"
        else:
            parameters["url"] = job.url

        LOGGER.info(
            "Running prefect deployment %s for %s",
            deployment_name,
            job.job_id,
        )
        flow_run = run_deployment(
            name=deployment_name,
            parameters=parameters,
        )

        handoff_record = job.status_document(
            JobStatus.RECEIVED,
            handoff="prefect",
            deployment=deployment_name,
            flow_run_id=str(flow_run.id),
        )
        self._write_json(job_dir / "handoff.json", handoff_record)

    @staticmethod
    def _write_json(path: Path, document: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
