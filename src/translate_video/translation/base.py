"""Translation provider contracts."""

from __future__ import annotations

from typing import Protocol

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment


class Translator(Protocol):
    """Translates source segments according to project configuration."""

    def translate(self, segments: list[Segment], config: PipelineConfig) -> list[Segment]:
        """Return translated segments while preserving timing and IDs."""
