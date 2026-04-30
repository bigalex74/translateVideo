"""Pipeline configuration shared by CLI, UI, and future API calls."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class TranslationMode(StrEnum):
    """How translated content should be delivered in the final export."""

    VOICEOVER = "voiceover"
    DUB = "dub"
    SUBTITLES = "subtitles"
    DUAL_AUDIO = "dual_audio"
    LEARNING = "learning"


class TranslationStyle(StrEnum):
    """Human-facing tone used by translation and adaptation providers."""

    NEUTRAL = "neutral"
    BUSINESS = "business"
    CASUAL = "casual"
    HUMOROUS = "humorous"
    EDUCATIONAL = "educational"
    CINEMATIC = "cinematic"
    CHILD_FRIENDLY = "child_friendly"


class AdaptationLevel(StrEnum):
    """How aggressively translation may move away from literal wording."""

    LITERAL = "literal"
    NATURAL = "natural"
    LOCALIZED = "localized"
    SHORTENED_FOR_TIMING = "shortened_for_timing"


class VoiceStrategy(StrEnum):
    """How many voices the engine should assign to detected speakers."""

    SINGLE = "single"
    BY_GENDER = "by_gender"
    TWO_VOICES = "two_voices"
    PER_SPEAKER = "per_speaker"


class QualityGate(StrEnum):
    """Automation strictness for final QA."""

    FAST = "fast"
    BALANCED = "balanced"
    STRICT = "strict"


@dataclass(slots=True)
class PipelineConfig:
    """Language-agnostic settings for one video translation project."""

    source_language: str = "auto"
    target_language: str = "ru"
    translation_mode: TranslationMode = TranslationMode.VOICEOVER
    translation_style: TranslationStyle = TranslationStyle.NEUTRAL
    adaptation_level: AdaptationLevel = AdaptationLevel.NATURAL
    voice_strategy: VoiceStrategy = VoiceStrategy.SINGLE
    quality_gate: QualityGate = QualityGate.BALANCED
    terminology_domain: str = "general"
    target_audience: str = "general"
    profanity_policy: str = "keep"
    units_policy: str = "preserve"
    preserve_names: bool = True
    preserve_brand_names: bool = True
    original_audio_volume: float = 0.15
    background_ducking: bool = True
    subtitle_formats: list[str] = field(default_factory=lambda: ["srt"])
    glossary_path: Path | None = None
    do_not_translate: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the config."""

        payload = asdict(self)
        payload["glossary_path"] = str(self.glossary_path) if self.glossary_path else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PipelineConfig":
        """Build a config from JSON data while restoring enum values."""

        data = dict(payload)
        if data.get("glossary_path"):
            data["glossary_path"] = Path(data["glossary_path"])
        return cls(
            **{
                **data,
                "translation_mode": TranslationMode(data.get("translation_mode", "voiceover")),
                "translation_style": TranslationStyle(data.get("translation_style", "neutral")),
                "adaptation_level": AdaptationLevel(data.get("adaptation_level", "natural")),
                "voice_strategy": VoiceStrategy(data.get("voice_strategy", "single")),
                "quality_gate": QualityGate(data.get("quality_gate", "balanced")),
            }
        )

