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


class TranslationQualityProfile(StrEnum):
    """Профиль качества и стоимости LLM-перевода."""

    AMATEUR = "amateur"
    PROFESSIONAL = "professional"


class TimingPolicy(StrEnum):
    """Стратегия сохранения естественности речи при подгонке таймингов."""

    NATURAL_VOICE = "natural_voice"
    SPEEDUP_ALLOWED = "speedup_allowed"
    STRICT_SLOT = "strict_slot"


@dataclass(slots=True)
class PipelineConfig:
    """Языконезависимые настройки одного проекта перевода видео."""

    source_language: str = "auto"
    target_language: str = "ru"
    translation_mode: TranslationMode = TranslationMode.VOICEOVER
    translation_quality: TranslationQualityProfile = TranslationQualityProfile.AMATEUR
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
    # ── Естественный голос и подгонка таймингов (TVIDEO-042) ─────────────────
    # По умолчанию не ускоряем голос. Сначала пытаемся сделать текст короче,
    # затем мягко сдвигаем соседние реплики, если TTS всё равно не помещается.
    timing_policy: TimingPolicy = TimingPolicy.NATURAL_VOICE
    target_chars_per_second: float = 14.0
    timing_fit_max_rewrites: int = 3
    use_cloud_timing_rewriter: bool = True
    rewrite_provider_order: list[str] = field(
        default_factory=lambda: ["gemini", "aihubmix", "openrouter", "polza", "rule_based"]
    )
    # Сетевые rewriter-провайдеры должны быстро отдавать управление fallback-цепочке:
    # бесплатные лимиты часто отвечают 429/503, и долго ждать их на каждом сегменте нельзя.
    rewrite_provider_timeout: float = 8.0
    rewrite_provider_disable_on_quota: bool = True
    # Бесплатные модели обычно дают 5-15 запросов в минуту. Держим
    # консервативный лимит, чтобы не провоцировать 429 на длинных видео.
    rewrite_provider_rpm: dict[str, float] = field(
        default_factory=lambda: {
            "gemini": 5.0,
            "openrouter": 5.0,
            "aihubmix": 5.0,
            "polza": 30.0,
        }
    )
    rewrite_provider_cooldown_seconds: float = 75.0
    rewrite_provider_wait_for_rate_limit: bool = True
    # Платный fallback должен быть явным, даже если ключ Polza.ai есть в .env.
    rewrite_allow_paid_fallback: bool = False
    allow_tts_rate_adaptation: bool = False
    allow_render_audio_speedup: bool = False
    allow_timeline_shift: bool = True
    max_timeline_shift: float = 1.5

    # ── Облачный LLM-перевод (TVIDEO-059) ───────────────────────────────────
    # Если ключей или лимитов не хватает, перевод падает обратно на Google
    # Translate. Платный Polza.ai включается только явным флагом.
    use_cloud_translation: bool = True
    translation_provider_order: list[str] = field(
        default_factory=lambda: ["gemini", "aihubmix", "openrouter", "polza", "google"]
    )
    translation_provider_timeout: float = 15.0
    translation_provider_disable_on_quota: bool = True
    translation_provider_rpm: dict[str, float] = field(
        default_factory=lambda: {
            "gemini": 5.0,
            "openrouter": 5.0,
            "aihubmix": 5.0,
            "polza": 30.0,
        }
    )
    translation_provider_cooldown_seconds: float = 75.0
    translation_provider_wait_for_rate_limit: bool = True
    translation_allow_paid_fallback: bool = False
    professional_translation_provider: str = "neuroapi"
    professional_translation_model: str = "gpt-5-mini"
    professional_rewrite_provider: str = "neuroapi"
    professional_rewrite_model: str = "gpt-5-mini"

    # ── Профессиональный TTS (TVIDEO-085) ───────────────────────────────────
    # Используется в professional режиме; "Обычный" режим — Edge TTS (бесплатный).
    # Провайдер: polza | neuroapi (поддерживают OpenAI-совместимый /audio/speech).
    # Модель: tts-1 | tts-1-hd | gpt-4o-mini-tts.
    # Голоса: alloy, echo, fable, onyx, nova, shimmer.
    professional_tts_provider: str = ""           # "” = использовать Edge TTS
    professional_tts_model: str = "tts-1"         # tts-1 | tts-1-hd | gpt-4o-mini-tts
    professional_tts_voice: str = "nova"          # голос 1 / единственный
    professional_tts_voice_2: str = "onyx"        # голос 2 (two_voices/per_speaker)
    professional_tts_role: str = "neutral"        # роль голоса 1 (Yandex SpeechKit)
    professional_tts_role_2: str = "neutral"      # роль голоса 2 (Yandex SpeechKit)
    professional_tts_speed: float = 1.0           # скорость речи (Yandex: 0.1-10.0)
    professional_tts_speed_2: float = 1.0         # скорость голоса 2
    professional_tts_pitch: int = 0               # высота голоса 1: pitchShift -1000..1000
    professional_tts_pitch_2: int = 0             # высота голоса 2: pitchShift -1000..1000
    professional_tts_stress: bool = True           # авто-ударения через ruaccent (только Yandex)
    professional_tts_emotion: int = 0              # SSML-эмоции: 0=выкл 1=мягко 2=средне 3=экспрессивно

    # ── Адаптивный rate TTS (явный fast-режим, не дефолт) ────────────────────
    tts_base_rate: int = 0          # базовый rate TTS в %; 0 = естественная скорость
    tts_max_rate: int = 0           # 0 = адаптивное ускорение выключено
    tts_rate_slack: float = 1.03    # 3% запас перед решением об ускорении

    # ── Безопасный рендер озвучки (TVIDEO-041) ───────────────────────────────
    # По умолчанию запрещаем обрезку TTS-аудио: потеря смысла хуже, чем
    # контролируемое наложение, которое видно в QA-отчёте.
    render_max_speed: float = 1.0
    render_gap: float = 0.05
    allow_render_audio_trim: bool = False

    # ── Перегруппировка по предложениям (TVIDEO-039) ─────────────────────────
    # Максимальная длительность слота после слияния фрагментов Whisper.
    # Если предложение длиннее — сбрасываем буфер принудительно.
    regroup_max_slot: float = 8.0

    do_not_translate: list[str] = field(default_factory=list)

    # ── Режим разработчика ────────────────────────────────────────────────────
    # При dev_mode=True DevLogWriter пишет все промты, ответы модели и I/O
    # этапов в {work_dir}/devlog.jsonl. Выключен по умолчанию.
    dev_mode: bool = False

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
        # Удаляем устаревшие поля (backward compatibility при загрузке старых project.json)
        for old_key in (
            # Ollama-compress (TVIDEO-037→040b)
            "compress_llm_url", "compress_llm_model",
            "compress_slack", "compress_max_retries",
            # Удалённые поля конфига
            "subtitle_embed_mode",
            "professional_tts_emotion",
            # ElevenLabs-поля (вынесены в отдельный провайдер)
            "el_stability", "el_similarity_boost", "el_style", "el_speed",
            # glossary_terms: хранятся отдельно от конфига
            "glossary_terms",
        ):
            data.pop(old_key, None)


        return cls(
            **{
                **data,
                "translation_mode": TranslationMode(data.get("translation_mode", "voiceover")),
                "translation_quality": TranslationQualityProfile(
                    data.get("translation_quality", "amateur")
                ),
                "translation_style": TranslationStyle(data.get("translation_style", "neutral")),
                "adaptation_level": AdaptationLevel(data.get("adaptation_level", "natural")),
                "voice_strategy": VoiceStrategy(data.get("voice_strategy", "single")),
                "quality_gate": QualityGate(data.get("quality_gate", "balanced")),
                "timing_policy": TimingPolicy(data.get("timing_policy", "natural_voice")),
                "target_chars_per_second": float(data.get("target_chars_per_second", 14.0)),
                "timing_fit_max_rewrites": int(data.get("timing_fit_max_rewrites", 3)),
                "use_cloud_timing_rewriter": bool(data.get("use_cloud_timing_rewriter", True)),
                "rewrite_provider_order": list(
                    data.get(
                        "rewrite_provider_order",
                        ["gemini", "aihubmix", "openrouter", "polza", "rule_based"],
                    )
                ),
                "rewrite_provider_timeout": float(data.get("rewrite_provider_timeout", 8.0)),
                "rewrite_provider_disable_on_quota": bool(
                    data.get("rewrite_provider_disable_on_quota", True)
                ),
                "rewrite_provider_rpm": dict(
                    data.get(
                        "rewrite_provider_rpm",
                        {"gemini": 5.0, "openrouter": 5.0, "aihubmix": 5.0, "polza": 30.0},
                    )
                ),
                "rewrite_provider_cooldown_seconds": float(
                    data.get("rewrite_provider_cooldown_seconds", 75.0)
                ),
                "rewrite_provider_wait_for_rate_limit": bool(
                    data.get("rewrite_provider_wait_for_rate_limit", True)
                ),
                "rewrite_allow_paid_fallback": bool(data.get("rewrite_allow_paid_fallback", False)),
                "allow_tts_rate_adaptation": bool(data.get("allow_tts_rate_adaptation", False)),
                "allow_render_audio_speedup": bool(data.get("allow_render_audio_speedup", False)),
                "allow_timeline_shift": bool(data.get("allow_timeline_shift", True)),
                "max_timeline_shift": float(data.get("max_timeline_shift", 1.5)),
                "use_cloud_translation": bool(data.get("use_cloud_translation", True)),
                "translation_provider_order": list(
                    data.get(
                        "translation_provider_order",
                        ["gemini", "aihubmix", "openrouter", "polza", "google"],
                    )
                ),
                "translation_provider_timeout": float(
                    data.get("translation_provider_timeout", 15.0)
                ),
                "translation_provider_disable_on_quota": bool(
                    data.get("translation_provider_disable_on_quota", True)
                ),
                "translation_provider_rpm": dict(
                    data.get(
                        "translation_provider_rpm",
                        {"gemini": 5.0, "openrouter": 5.0, "aihubmix": 5.0, "polza": 30.0},
                    )
                ),
                "translation_provider_cooldown_seconds": float(
                    data.get("translation_provider_cooldown_seconds", 75.0)
                ),
                "translation_provider_wait_for_rate_limit": bool(
                    data.get("translation_provider_wait_for_rate_limit", True)
                ),
                "translation_allow_paid_fallback": bool(
                    data.get("translation_allow_paid_fallback", False)
                ),
                "professional_translation_provider": str(
                    data.get("professional_translation_provider", "neuroapi")
                ),
                "professional_translation_model": str(
                    data.get("professional_translation_model", "gpt-5-mini")
                ),
                "professional_rewrite_provider": str(
                    data.get("professional_rewrite_provider", "neuroapi")
                ),
                "professional_rewrite_model": str(
                    data.get("professional_rewrite_model", "gpt-5-mini")
                ),
                # Профессиональный TTS (TVIDEO-085, TVIDEO-086)
                "professional_tts_provider": str(data.get("professional_tts_provider", "")),
                "professional_tts_model": str(data.get("professional_tts_model", "tts-1")),
                "professional_tts_voice": str(data.get("professional_tts_voice", "nova")),
                "professional_tts_voice_2": str(data.get("professional_tts_voice_2", "onyx")),
                "professional_tts_role": str(data.get("professional_tts_role", "neutral")),
                "professional_tts_role_2": str(data.get("professional_tts_role_2", "neutral")),
                "professional_tts_speed": float(data.get("professional_tts_speed", 1.0)),
                "professional_tts_speed_2": float(data.get("professional_tts_speed_2", 1.0)),
                "professional_tts_pitch": int(data.get("professional_tts_pitch", 0)),
                "professional_tts_pitch_2": int(data.get("professional_tts_pitch_2", 0)),
                "professional_tts_stress": bool(data.get("professional_tts_stress", True)),
                "professional_tts_emotion": int(data.get("professional_tts_emotion", 0)),
                # Адаптивный TTS rate — только для явного fast-режима
                "tts_base_rate": int(data.get("tts_base_rate", 0)),
                "tts_max_rate": int(data.get("tts_max_rate", 0)),
                "tts_rate_slack": float(data.get("tts_rate_slack", 1.03)),
                # Безопасный рендер — дефолты для совместимости
                "render_max_speed": float(data.get("render_max_speed", 1.0)),
                "render_gap": float(data.get("render_gap", 0.05)),
                "allow_render_audio_trim": bool(data.get("allow_render_audio_trim", False)),
                # Regroup — дефолт для совместимости
                "regroup_max_slot": float(data.get("regroup_max_slot", 8.0)),
                # Режим разработчика
                "dev_mode": bool(data.get("dev_mode", False)),
            }
        )
