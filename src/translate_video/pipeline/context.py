"""Общий контекст, который передается каждому этапу пайплайна."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from translate_video.core.schemas import VideoProject
from translate_video.core.store import ProjectStore


@dataclass(slots=True)
class StageContext:
    """Изменяемый контекст проекта, общий для этапов пайплайна."""

    project: VideoProject
    store: ProjectStore
    cancel_event: threading.Event = field(default_factory=threading.Event)
