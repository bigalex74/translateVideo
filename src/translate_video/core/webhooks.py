"""Schema-versioned webhook events for future API and n8n integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from translate_video.core.schemas import JobStatus, Stage


class WebhookEventType(StrEnum):
    """Public event names consumed by API clients and future n8n workflows."""

    PROJECT_CREATED = "project.created"
    JOB_STARTED = "job.started"
    JOB_STAGE_STARTED = "job.stage.started"
    JOB_STAGE_COMPLETED = "job.stage.completed"
    JOB_STAGE_FAILED = "job.stage.failed"
    QA_COMPLETED = "qa.completed"
    RENDER_COMPLETED = "render.completed"


@dataclass(slots=True)
class WebhookEvent:
    """A JSON-ready event emitted by the future job runner."""

    event: WebhookEventType
    project_id: str
    status: JobStatus
    stage: Stage | None = None
    job_id: str | None = None
    artifact_path: str | None = None
    error: str | None = None
    idempotency_key: str | None = None
    schema_version: str = "1.0"
    id: str = field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.event = WebhookEventType(self.event)
        self.status = JobStatus(self.status)
        if self.stage is not None:
            self.stage = Stage(self.stage)
        if self.idempotency_key is None:
            stage_part = self.stage.value if self.stage else "project"
            self.idempotency_key = f"{self.project_id}:{self.event.value}:{stage_part}:{self.id}"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready event payload for external orchestrators."""

        return asdict(self)
