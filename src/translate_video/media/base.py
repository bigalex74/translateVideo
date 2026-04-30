"""Media provider contracts used by pipeline stages."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from translate_video.core.schemas import VideoProject


class MediaProvider(Protocol):
    """Extracts source audio from video inputs."""

    def extract_audio(self, project: VideoProject) -> Path:
        """Create a source audio artifact and return its path."""
