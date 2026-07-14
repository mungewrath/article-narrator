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
    url: str | None
    submitted_at: str
    voice: str = "tiernan"
    text: str | None = None
    title: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ArticleJob":
        job_id = str(payload.get("job_id", "")).strip()
        raw_url = payload.get("url")
        url = str(raw_url).strip() if raw_url else None
        raw_text = payload.get("text")
        text = str(raw_text).strip() if raw_text else None
        raw_title = payload.get("title")
        title = str(raw_title).strip() if raw_title else None
        submitted_at = str(payload.get("submitted_at", "")).strip()
        voice = str(payload.get("voice", "tiernan")).strip()

        if not job_id:
            raise ValueError("job_id is required")
        try:
            UUID(job_id)
        except ValueError as exc:
            raise ValueError("job_id must be a UUID") from exc

        if url and text:
            raise ValueError("provide either url or text, not both")
        if not url and not text:
            raise ValueError("url or text is required")

        if url:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("url must be an absolute http(s) URL")

        if text and not title:
            raise ValueError("title is required when text is provided")

        if not submitted_at:
            raise ValueError("submitted_at is required")

        return cls(
            job_id=job_id,
            url=url,
            submitted_at=submitted_at,
            voice=voice,
            text=text,
            title=title,
        )

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
