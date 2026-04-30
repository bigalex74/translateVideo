"""Final rendering provider contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from translate_video.core.schemas import Segment, VideoProject


class Renderer(Protocol):
    """Creates final video/audio outputs for a project."""

    def render(self, project: VideoProject, segments: list[Segment]) -> Path:
        """Create a final output artifact and return its path."""
