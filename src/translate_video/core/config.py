"""Конфигурация пайплайна, общая для CLI, UI и будущего API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class TranslationMode(StrEnum):
    """Способ доставки переведенного контента в итоговом экспорте."""

    VOICEOVER = "voiceover"
    DUB = "dub"
    SUBTITLES = "subtitles"
    DUAL_AUDIO = "dual_audio"
    LEARNING = "learning"


class TranslationStyle(StrEnum):
    """Тон перевода, который видит пользователь."""

    NEUTRAL = "neutral"
    BUSINESS = "business"
    CASUAL = "casual"
    HUMOROUS = "humorous"
    EDUCATIONAL = "educational"
    CINEMATIC = "cinematic"
    CHILD_FRIENDLY = "child_friendly"


class AdaptationLevel(StrEnum):
    """Степень допустимого отхода перевода от буквального текста."""

    LITERAL = "literal"
    NATURAL = "natural"
    LOCALIZED = "localized"
    SHORTENED_FOR_TIMING = "shortened_for_timing"


class VoiceStrategy(StrEnum):
    """Стратегия назначения голосов найденным спикерам."""

    SINGLE = "single"
    BY_GENDER = "by_gender"
    TWO_VOICES = "two_voices"
    PER_SPEAKER = "per_speaker"


class QualityGate(StrEnum):
    """Строгость автоматической финальной QA-проверки."""

    FAST = "fast"
    BALANCED = "balanced"
    STRICT = "strict"


@dataclass(slots=True)
class PipelineConfig:
    """Языконезависимые настройки одного проекта перевода видео."""

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
    # ── Адаптивный rate TTS (TVIDEO-040b) ────────────────────────────────────
    # Если TTS-аудио длиннее слота более чем на tts_rate_slack,
    # автоматически переозвучиваем с бОльшим rate (без изменения тона).
    tts_base_rate: int = 5          # базовый rate TTS в % (+5 = чуть быстрее нормы)
    tts_max_rate: int = 40          # максимальный rate при адаптации
    tts_rate_slack: float = 1.03    # 3% запас перед решением об ускорении

    # ── Перегруппировка по предложениям (TVIDEO-039) ─────────────────────────
    # Максимальная длительность слота после слияния фрагментов Whisper.
    # Если предложение длиннее — сбрасываем буфер принудительно.
    regroup_max_slot: float = 8.0

    do_not_translate: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Вернуть JSON-совместимое представление конфигурации."""

        payload = asdict(self)
        payload["glossary_path"] = str(self.glossary_path) if self.glossary_path else None
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PipelineConfig":
        """Создать конфигурацию из JSON-данных и восстановить enum-значения."""

        data = dict(payload)
        if data.get("glossary_path"):
            data["glossary_path"] = Path(data["glossary_path"])
        # Удаляем устаревшие поля Ollama-compress (TVIDEO-037→040b)
        for old_key in ("compress_llm_url", "compress_llm_model",
                         "compress_slack", "compress_max_retries"):
            data.pop(old_key, None)

        return cls(
            **{
                **data,
                "translation_mode": TranslationMode(data.get("translation_mode", "voiceover")),
                "translation_style": TranslationStyle(data.get("translation_style", "neutral")),
                "adaptation_level": AdaptationLevel(data.get("adaptation_level", "natural")),
                "voice_strategy": VoiceStrategy(data.get("voice_strategy", "single")),
                "quality_gate": QualityGate(data.get("quality_gate", "balanced")),
                # Адаптивный TTS rate — дефолты для совместимости со старыми project.json
                "tts_base_rate": int(data.get("tts_base_rate", 5)),
                "tts_max_rate": int(data.get("tts_max_rate", 40)),
                "tts_rate_slack": float(data.get("tts_rate_slack", 1.03)),
                # Regroup — дефолт для совместимости
                "regroup_max_slot": float(data.get("regroup_max_slot", 8.0)),
            }
        )

