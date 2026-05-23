from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse
from uuid import UUID


class JobStatus(StrEnum):
    SUBMITTED = "submitted"
    RECEIVED = "received"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class ArticleJob:
    job_id: str
    url: str
    submitted_at: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ArticleJob":
        job_id = str(payload.get("job_id", "")).strip()
        url = str(payload.get("url", "")).strip()
        submitted_at = str(payload.get("submitted_at", "")).strip()

        if not job_id:
            raise ValueError("job_id is required")
        try:
            UUID(job_id)
        except ValueError as exc:
            raise ValueError("job_id must be a UUID") from exc

        if not url:
            raise ValueError("url is required")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute http(s) URL")

        if not submitted_at:
            raise ValueError("submitted_at is required")

        return cls(job_id=job_id, url=url, submitted_at=submitted_at)

    def input_document(self) -> dict[str, Any]:
        return asdict(self)

    def status_document(self, status: JobStatus, **extra: Any) -> dict[str, Any]:
        document = {
            "job_id": self.job_id,
            "status": status.value,
            "updated_at": utc_now_iso(),
        }
        document.update(extra)
        return document
