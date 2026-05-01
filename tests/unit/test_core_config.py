"""Модульные тесты конфигурации пайплайна."""

import unittest
from pathlib import Path

from translate_video.core.config import (
    AdaptationLevel,
    PipelineConfig,
    QualityGate,
    TranslationMode,
    TranslationStyle,
    VoiceStrategy,
)


class PipelineConfigTest(unittest.TestCase):
    """Проверяет сериализацию и восстановление настроек пайплайна."""

    def test_round_trip_restores_enums_and_paths(self):
        """Конфигурация должна восстанавливать enum-значения и пути."""

        config = PipelineConfig(
            source_language="en",
            target_language="ru",
            translation_mode=TranslationMode.DUB,
            translation_style=TranslationStyle.HUMOROUS,
            adaptation_level=AdaptationLevel.SHORTENED_FOR_TIMING,
            voice_strategy=VoiceStrategy.PER_SPEAKER,
            quality_gate=QualityGate.STRICT,
            glossary_path=Path("glossary.yaml"),
            do_not_translate=["OpenAI"],
        )

        restored = PipelineConfig.from_dict(config.to_dict())

        self.assertEqual(restored.source_language, "en")
        self.assertEqual(restored.target_language, "ru")
        self.assertEqual(restored.translation_mode, TranslationMode.DUB)
        self.assertEqual(restored.translation_style, TranslationStyle.HUMOROUS)
        self.assertEqual(restored.adaptation_level, AdaptationLevel.SHORTENED_FOR_TIMING)
        self.assertEqual(restored.voice_strategy, VoiceStrategy.PER_SPEAKER)
        self.assertEqual(restored.quality_gate, QualityGate.STRICT)
        self.assertEqual(restored.glossary_path, Path("glossary.yaml"))
        self.assertEqual(restored.do_not_translate, ["OpenAI"])

    def test_timing_safe_render_defaults_are_restored(self):
        """Старые project.json получают безопасные дефолты рендера."""

        restored = PipelineConfig.from_dict({"target_language": "ru"})

        self.assertEqual(restored.render_max_speed, 1.3)
        self.assertEqual(restored.render_gap, 0.05)
        self.assertFalse(restored.allow_render_audio_trim)


if __name__ == "__main__":
    unittest.main()
