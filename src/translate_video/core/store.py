"""Сохранение артефактов и метаданных проектов перевода."""

from __future__ import annotations

import json
import hashlib
import re
import shutil
from pathlib import Path
from uuid import uuid4

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import (
    ArtifactKind,
    ArtifactRecord,
    Segment,
    Stage,
    StageRun,
    VideoProject,
)


class ProjectStore:
    """Создает и сохраняет папки проектов со стабильными именами артефактов."""

    PROJECT_FILE = "project.json"
    SETTINGS_FILE = "settings.json"
    SOURCE_TRANSCRIPT_FILE = "transcript.source.json"
    TRANSLATED_TRANSCRIPT_FILE = "transcript.translated.json"
    SRT_FILE = "subtitles/translated.srt"
    VTT_FILE = "subtitles/translated.vtt"

    def __init__(self, root: Path | str = "runs") -> None:
        self.root = Path(root)

    def create_project(
        self,
        input_video: Path | str,
        config: PipelineConfig | None = None,
        project_id: str | None = None,
    ) -> VideoProject:
        """Создать папку проекта и записать начальные метаданные."""

        input_path = Path(input_video)
        resolved_config = config or PipelineConfig()
        resolved_id = sanitize_project_id(project_id) if project_id else sanitize_project_id(
            f"{input_path.stem}-{uuid4().hex[:8]}"
        )
        project = VideoProject(
            id=resolved_id,
            input_video=input_path,
            work_dir=self.root / resolved_id,
            config=resolved_config,
        )
        self._ensure_layout(project)
        self.save_project(project)
        return project

    def list_projects(self) -> list[VideoProject]:
        """Вернуть проекты из корня хранения, отсортированные по обновлению."""

        if not self.root.exists():
            return []

        projects: list[VideoProject] = []
        for candidate in self.root.iterdir():
            if not candidate.is_dir() or candidate.name.startswith("_"):
                continue
            project_file = candidate / self.PROJECT_FILE
            if not project_file.is_file():
                continue
            projects.append(self.load_project(candidate))

        return sorted(
            projects,
            key=lambda project: ((project.work_dir / self.PROJECT_FILE).stat().st_mtime, project.id),
            reverse=True,
        )

    def attach_input_video(
        self,
        project: VideoProject,
        source_path: Path | str,
        filename: str = "input.mp4",
    ) -> Path:
        """Скопировать исходное видео в папку проекта и обновить метаданные."""

        safe_filename = sanitize_filename(filename, fallback="input.mp4")
        destination = project.work_dir / safe_filename
        source = Path(source_path)
        if not source.is_file():
            raise FileNotFoundError(f"исходный файл не найден: {source}")
        if source.resolve() != destination.resolve():
            shutil.copyfile(source, destination)
        project.input_video = destination
        self.save_project(project)
        return destination

    def save_project(self, project: VideoProject) -> None:
        """Сохранить метаданные проекта и настройки в JSON."""

        self._ensure_layout(project)
        self._write_json(project.work_dir / self.PROJECT_FILE, project.to_dict())
        self._write_json(project.work_dir / self.SETTINGS_FILE, project.config.to_dict())

    def load_project(self, work_dir: Path | str) -> VideoProject:
        """Загрузить проект из его рабочей папки."""

        payload = self._read_json(Path(work_dir) / self.PROJECT_FILE)
        return VideoProject.from_dict(payload)

    def save_segments(
        self,
        project: VideoProject,
        segments: list[Segment],
        translated: bool = False,
    ) -> Path:
        """Сохранить исходные или переведенные сегменты расшифровки."""

        project.segments = segments
        filename = self.TRANSLATED_TRANSCRIPT_FILE if translated else self.SOURCE_TRANSCRIPT_FILE
        output_path = project.work_dir / filename
        self._write_json(output_path, [segment.to_dict() for segment in segments])
        kind = ArtifactKind.TRANSLATED_TRANSCRIPT if translated else ArtifactKind.SOURCE_TRANSCRIPT
        relative_path = output_path.relative_to(project.work_dir).as_posix()
        project.artifacts[kind.value] = relative_path
        project.artifact_records = [
            record for record in project.artifact_records if record.kind != kind
        ]
        project.artifact_records.append(
            ArtifactRecord(
                kind=kind,
                path=relative_path,
                stage=Stage.TRANSLATE if translated else Stage.TRANSCRIBE,
                content_type="application/json",
                metadata={"segments": len(segments)},
            )
        )
        self.save_project(project)
        return output_path

    def add_artifact(
        self,
        project: VideoProject,
        kind: ArtifactKind,
        path: Path | str,
        stage: Stage,
        content_type: str,
        metadata: dict | None = None,
    ) -> ArtifactRecord:
        """Зарегистрировать путь артефакта относительно папки проекта."""

        absolute_path = Path(path).resolve()
        work_dir_abs = project.work_dir.resolve()
        try:
            relative_path = absolute_path.relative_to(work_dir_abs).as_posix()
        except ValueError:
            raise ValueError(
                f"Путь артефакта выходит за пределы рабочей директории проекта: "
                f"{absolute_path} not under {work_dir_abs}"
            )
        record = ArtifactRecord(
            kind=kind,
            path=relative_path,
            stage=stage,
            content_type=content_type,
            metadata=metadata or {},
        )
        project.artifacts[kind.value] = relative_path
        project.artifact_records = [
            existing for existing in project.artifact_records if existing.kind != kind
        ]
        project.artifact_records.append(record)
        self.save_project(project)
        return record

    def get_artifact(
        self,
        project: VideoProject,
        kind: ArtifactKind,
    ) -> ArtifactRecord | None:
        """Вернуть последнюю запись артефакта указанного типа."""

        for record in reversed(project.artifact_records):
            if record.kind == kind:
                return record
        return None

    def record_stage_run(self, project: VideoProject, run: StageRun) -> None:
        """Вставить или заменить запись запуска этапа по ID."""

        project.stage_runs = [existing for existing in project.stage_runs if existing.id != run.id]
        project.stage_runs.append(run)
        self.save_project(project)

    def export_subtitles(
        self,
        project: VideoProject,
        fmt: str = "srt",
    ) -> Path:
        """
        Сгенерировать и записать файл субтитров (SRT или VTT).

        Регистрирует артефакт ``ArtifactKind.SUBTITLES`` в проекте.
        Возвращает абсолютный путь к созданному файлу.
        """

        from translate_video.export.srt import segments_to_srt  # noqa: PLC0415
        from translate_video.export.vtt import segments_to_vtt  # noqa: PLC0415

        if fmt == "srt":
            content = segments_to_srt(project.segments)
            relative = self.SRT_FILE
            content_type = "text/srt"
        elif fmt == "vtt":
            content = segments_to_vtt(project.segments)
            relative = self.VTT_FILE
            content_type = "text/vtt"
        else:
            raise ValueError(f"неподдерживаемый формат субтитров: {fmt}")

        output = project.work_dir / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]

        self.add_artifact(
            project,
            kind=ArtifactKind.SUBTITLES,
            path=output,
            stage=Stage.EXPORT,
            content_type=content_type,
            metadata={"format": fmt, "lines": content.count("\n"), "checksum": checksum},
        )
        return output

    def artifact_path(self, project: VideoProject, *parts: str) -> Path:
        """Вернуть путь внутри папки проекта без создания файла."""

        return project.work_dir.joinpath(*parts)

    def resolve_project_file(self, project: VideoProject, relative_path: str) -> Path:
        """Вернуть безопасный абсолютный путь к файлу внутри папки проекта."""

        candidate = (project.work_dir / relative_path).resolve()
        root = project.work_dir.resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("путь артефакта выходит за пределы проекта")
        return candidate

    def _ensure_layout(self, project: VideoProject) -> None:
        project.work_dir.mkdir(parents=True, exist_ok=True)
        for folder in ("subtitles", "tts", "output"):
            (project.work_dir / folder).mkdir(exist_ok=True)

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))


def sanitize_project_id(value: str) -> str:
    """Вернуть безопасный идентификатор проекта для имени папки."""

    raw = value.strip()
    if "/" in raw or "\\" in raw or raw in {".", ".."}:
        raise ValueError("идентификатор проекта содержит недопустимый путь")
    cleaned = re.sub(r"[^\w.-]+", "-", raw).strip(".-_")
    if not cleaned:
        raise ValueError("идентификатор проекта не может быть пустым")
    return cleaned


def sanitize_filename(value: str, fallback: str = "file") -> str:
    """Вернуть безопасное имя файла без директорий."""

    name = Path(value or fallback).name
    cleaned = re.sub(r"[^\w.-]+", "-", name).strip(".-_")
    if not cleaned:
        cleaned = fallback
    if cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        raise ValueError("имя файла содержит недопустимый путь")
    return cleaned
