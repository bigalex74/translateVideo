"""Сериализуемые схемы проекта, используемые во всем движке."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from translate_video.core.config import PipelineConfig


class SegmentStatus(StrEnum):
    """Состояния жизненного цикла одного текстового/аудио сегмента."""

    DRAFT = "draft"
    TRANSCRIBED = "transcribed"
    TRANSLATED = "translated"
    TTS_READY = "tts_ready"
    FAILED = "failed"


class ProjectStatus(StrEnum):
    """Состояния жизненного цикла одного проекта перевода."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Stage(StrEnum):
    """Этапы пайплайна для задач, артефактов и webhook-событий."""

    INIT = "init"
    PROBE = "probe"
    EXTRACT_AUDIO = "extract_audio"
    TRANSCRIBE = "transcribe"
    REGROUP = "regroup"     # перегруппировка по предложениям (TVIDEO-039)
    TRANSLATE = "translate"
    VOICE_CAST = "voice_cast"
    TTS = "tts"
    TIMING_FIT = "timing_fit"
    MIX = "mix"
    RENDER = "render"
    QA = "qa"
    EXPORT = "export"


class ArtifactKind(StrEnum):
    """Стабильные категории артефактов внутри папки проекта."""

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
    """Статус одного перезапускаемого выполнения этапа."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class ArtifactRecord:
    """Типизированные метаданные артефакта с путем относительно проекта."""

    kind: ArtifactKind
    path: str
    stage: Stage
    content_type: str = "application/json"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    checksum: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Вернуть JSON-совместимую запись артефакта."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArtifactRecord":
        """Создать запись артефакта и восстановить enum-значения."""

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
    """Одна попытка выполнения этапа пайплайна."""

    stage: Stage
    status: JobStatus = JobStatus.PENDING
    id: str = field(default_factory=lambda: f"stage_{uuid4().hex[:12]}")
    started_at: str | None = None
    finished_at: str | None = None
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    error: str | None = None
    attempt: int = 1
    progress_current: int | None = None
    progress_total: int | None = None
    progress_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Вернуть JSON-совместимую запись запуска этапа."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StageRun":
        """Создать запись запуска этапа и восстановить enum-значения."""

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
            progress_current=payload.get("progress_current"),
            progress_total=payload.get("progress_total"),
            progress_message=payload.get("progress_message"),
        )


@dataclass(slots=True)
class Segment:
    """Один речевой сегмент и состояние его перевода."""

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
    tts_text: str = ""  # текст реально отправленный в TTS (пусто = translated_text)
    qa_flags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("конец сегмента должен быть больше или равен началу")
        self.status = SegmentStatus(self.status)

    @property
    def duration(self) -> float:
        """Длительность сегмента в секундах."""

        return self.end - self.start

    def to_dict(self) -> dict[str, Any]:
        """Вернуть JSON-совместимое представление сегмента."""

        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Segment":
        """Создать сегмент из JSON-данных."""

        data = dict(payload)
        data["status"] = SegmentStatus(data.get("status", "draft"))
        return cls(**data)


@dataclass(slots=True)
class VideoProject:
    """Сохраняемые метаданные одного запуска перевода."""

    input_video: Path
    work_dir: Path
    config: PipelineConfig
    id: str = field(default_factory=lambda: f"project_{uuid4().hex[:12]}")
    segments: list[Segment] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    artifact_records: list[ArtifactRecord] = field(default_factory=list)
    stage_runs: list[StageRun] = field(default_factory=list)
    status: ProjectStatus = ProjectStatus.CREATED
    # Снапшоты баланса до/после пайплайна — для вычисления реального расхода.
    # Ключи: "polza_before", "polza_after", "neuroapi_before", "neuroapi_after"
    billing_snapshots: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.status = ProjectStatus(self.status)

    def to_dict(self) -> dict[str, Any]:
        """Вернуть JSON-совместимое представление проекта."""

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
            "billing_snapshots": self.billing_snapshots,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VideoProject":
        """Создать проект из JSON-данных."""

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
            billing_snapshots=dict(payload.get("billing_snapshots", {})),
        )
