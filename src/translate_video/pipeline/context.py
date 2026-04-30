"""Shared context passed to every pipeline stage."""

from __future__ import annotations

from dataclasses import dataclass

from translate_video.core.schemas import VideoProject
from translate_video.core.store import ProjectStore


@dataclass(slots=True)
class StageContext:
    """Mutable project context shared by pipeline stages."""

    project: VideoProject
    store: ProjectStore
