"""Artifact persistence for translation projects."""

from __future__ import annotations

import json
from pathlib import Path

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment, VideoProject


class ProjectStore:
    """Create and persist project folders with stable artifact names."""

    PROJECT_FILE = "project.json"
    SETTINGS_FILE = "settings.json"
    SOURCE_TRANSCRIPT_FILE = "transcript.source.json"
    TRANSLATED_TRANSCRIPT_FILE = "transcript.translated.json"

    def __init__(self, root: Path | str = "runs") -> None:
        self.root = Path(root)

    def create_project(
        self,
        input_video: Path | str,
        config: PipelineConfig | None = None,
        project_id: str | None = None,
    ) -> VideoProject:
        """Create a project directory and write initial metadata."""

        input_path = Path(input_video)
        resolved_config = config or PipelineConfig()
        project = VideoProject(
            id=project_id or VideoProject(input_path, self.root, resolved_config).id,
            input_video=input_path,
            work_dir=self.root / (project_id or input_path.stem),
            config=resolved_config,
        )
        self._ensure_layout(project)
        self.save_project(project)
        return project

    def save_project(self, project: VideoProject) -> None:
        """Persist project metadata and settings as JSON."""

        self._ensure_layout(project)
        self._write_json(project.work_dir / self.PROJECT_FILE, project.to_dict())
        self._write_json(project.work_dir / self.SETTINGS_FILE, project.config.to_dict())

    def load_project(self, work_dir: Path | str) -> VideoProject:
        """Load a project from its working directory."""

        payload = self._read_json(Path(work_dir) / self.PROJECT_FILE)
        return VideoProject.from_dict(payload)

    def save_segments(
        self,
        project: VideoProject,
        segments: list[Segment],
        translated: bool = False,
    ) -> Path:
        """Persist source or translated transcript segments."""

        project.segments = segments
        filename = self.TRANSLATED_TRANSCRIPT_FILE if translated else self.SOURCE_TRANSCRIPT_FILE
        output_path = project.work_dir / filename
        self._write_json(output_path, [segment.to_dict() for segment in segments])
        project.artifacts["translated_transcript" if translated else "source_transcript"] = str(output_path)
        self.save_project(project)
        return output_path

    def artifact_path(self, project: VideoProject, *parts: str) -> Path:
        """Return a path inside a project directory without creating a file."""

        return project.work_dir.joinpath(*parts)

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

