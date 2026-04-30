"""Text-to-speech provider contracts."""

from __future__ import annotations

from typing import Protocol

from translate_video.core.schemas import Segment, VideoProject


class TTSProvider(Protocol):
    """Synthesizes translated segments and returns updated segment metadata."""

    def synthesize(self, project: VideoProject, segments: list[Segment]) -> list[Segment]:
        """Generate TTS files and return segments with `tts_path` populated."""
