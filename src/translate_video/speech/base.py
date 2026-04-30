"""Speech recognition provider contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment


class Transcriber(Protocol):
    """Turns an audio file into timestamped source-language segments."""

    def transcribe(self, audio_path: Path, config: PipelineConfig) -> list[Segment]:
        """Return source segments for an audio artifact."""
