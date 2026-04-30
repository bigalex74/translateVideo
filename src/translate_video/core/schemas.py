"""Serializable project schemas used across the engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from translate_video.core.config import PipelineConfig


@dataclass(slots=True)
class Segment:
    """One speech segment and its translation state."""

    start: float
    end: float
    source_text: str
    id: str = field(default_factory=lambda: f"seg_{uuid4().hex[:12]}")
    translated_text: str = ""
    speaker_id: str | None = None
    voice: str | None = None
    confidence: float | None = None
    status: str = "draft"
    tts_path: str | None = None

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("segment end must be greater than or equal to start")

    @property
    def duration(self) -> float:
        """Duration in seconds."""

        return self.end - self.start

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the segment."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Segment":
        """Build a segment from JSON data."""

        return cls(**payload)


@dataclass(slots=True)
class VideoProject:
    """Persistent metadata for one translation run."""

    input_video: Path
    work_dir: Path
    config: PipelineConfig
    id: str = field(default_factory=lambda: f"project_{uuid4().hex[:12]}")
    segments: list[Segment] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    status: str = "created"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the project."""

        return {
            "id": self.id,
            "input_video": str(self.input_video),
            "work_dir": str(self.work_dir),
            "config": self.config.to_dict(),
            "segments": [segment.to_dict() for segment in self.segments],
            "artifacts": self.artifacts,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VideoProject":
        """Build a project from JSON data."""

        return cls(
            id=payload["id"],
            input_video=Path(payload["input_video"]),
            work_dir=Path(payload["work_dir"]),
            config=PipelineConfig.from_dict(payload["config"]),
            segments=[Segment.from_dict(item) for item in payload.get("segments", [])],
            artifacts=dict(payload.get("artifacts", {})),
            status=payload.get("status", "created"),
        )

