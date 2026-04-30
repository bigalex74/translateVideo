"""Schema-versioned webhook events for future API and n8n integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class WebhookEvent:
    """A JSON-ready event emitted by the future job runner."""

    event: str
    project_id: str
    status: str
    stage: str | None = None
    job_id: str | None = None
    artifact_path: str | None = None
    schema_version: str = "1.0"
    id: str = field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready event payload for external orchestrators."""

        return asdict(self)

