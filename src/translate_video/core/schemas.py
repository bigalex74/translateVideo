"""Serializable project schemas used across the engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from translate_video.core.config import PipelineConfig


class SegmentStatus(StrEnum):
    """Lifecycle states for one text/audio segment."""

    DRAFT = "draft"
    TRANSCRIBED = "transcribed"
    TRANSLATED = "translated"
    TTS_READY = "tts_ready"
    FAILED = "failed"


class ProjectStatus(StrEnum):
    """Lifecycle states for one translation project."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Stage(StrEnum):
    """Pipeline stages used by jobs, artifacts, and webhook events."""

    INIT = "init"
    PROBE = "probe"
    EXTRACT_AUDIO = "extract_audio"
    TRANSCRIBE = "transcribe"
    SPEAKER_ANALYSIS = "speaker_analysis"
    TRANSLATE = "translate"
    TRANSLATION = "translation"
    VOICE_CAST = "voice_cast"
    TTS = "tts"
    TIMING_FIT = "timing_fit"
    MIX = "mix"
    RENDER = "render"
    QA = "qa"
    EXPORT = "export"


class ArtifactKind(StrEnum):
    """Stable artifact categories persisted inside project directories."""

    SETTINGS = "settings"
    SOURCE_AUDIO = "source_audio"
    SOURCE_TRANSCRIPT = "source_transcript"
    TRANSLATED_TRANSCRIPT = "translated_transcript"
    SPEAKERS = "speakers"
    SUBTITLES = "subtitles"
    TTS_AUDIO = "tts_audio"
    FINAL_AUDIO = "final_audio"
    OUTPUT_VIDEO = "output_video"
    QA_REPORT = "qa_report"


class JobStatus(StrEnum):
    """Status for one rerunnable stage execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class ArtifactRecord:
    """Typed artifact metadata stored relative to the project directory."""

    kind: ArtifactKind
    path: str
    stage: Stage
    content_type: str = "application/json"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    checksum: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready artifact record."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArtifactRecord":
        """Build an artifact record while restoring enum values."""

        return cls(
            kind=ArtifactKind(payload["kind"]),
            path=payload["path"],
            stage=Stage(payload["stage"]),
            content_type=payload.get("content_type", "application/json"),
            created_at=payload.get("created_at", datetime.now(UTC).isoformat()),
            metadata=dict(payload.get("metadata", {})),
            checksum=payload.get("checksum"),
        )


@dataclass(slots=True)
class StageRun:
    """One attempt to execute a pipeline stage."""

    stage: Stage
    status: JobStatus = JobStatus.PENDING
    id: str = field(default_factory=lambda: f"stage_{uuid4().hex[:12]}")
    started_at: str | None = None
    finished_at: str | None = None
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    error: str | None = None
    attempt: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready stage run."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StageRun":
        """Build a stage run while restoring enum values."""

        return cls(
            id=payload.get("id", f"stage_{uuid4().hex[:12]}"),
            stage=Stage(payload["stage"]),
            status=JobStatus(payload.get("status", "pending")),
            started_at=payload.get("started_at"),
            finished_at=payload.get("finished_at"),
            inputs=list(payload.get("inputs", [])),
            outputs=list(payload.get("outputs", [])),
            error=payload.get("error"),
            attempt=payload.get("attempt", 1),
        )


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
    status: SegmentStatus = SegmentStatus.DRAFT
    tts_path: str | None = None

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("segment end must be greater than or equal to start")
        self.status = SegmentStatus(self.status)

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

        data = dict(payload)
        data["status"] = SegmentStatus(data.get("status", "draft"))
        return cls(**data)


@dataclass(slots=True)
class VideoProject:
    """Persistent metadata for one translation run."""

    input_video: Path
    work_dir: Path
    config: PipelineConfig
    id: str = field(default_factory=lambda: f"project_{uuid4().hex[:12]}")
    segments: list[Segment] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    artifact_records: list[ArtifactRecord] = field(default_factory=list)
    stage_runs: list[StageRun] = field(default_factory=list)
    status: ProjectStatus = ProjectStatus.CREATED

    def __post_init__(self) -> None:
        self.status = ProjectStatus(self.status)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the project."""

        return {
            "id": self.id,
            "input_video": str(self.input_video),
            "work_dir": str(self.work_dir),
            "config": self.config.to_dict(),
            "segments": [segment.to_dict() for segment in self.segments],
            "artifacts": self.artifacts,
            "artifact_records": [record.to_dict() for record in self.artifact_records],
            "stage_runs": [run.to_dict() for run in self.stage_runs],
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
            artifact_records=[
                ArtifactRecord.from_dict(item) for item in payload.get("artifact_records", [])
            ],
            stage_runs=[StageRun.from_dict(item) for item in payload.get("stage_runs", [])],
            status=ProjectStatus(payload.get("status", "created")),
        )
