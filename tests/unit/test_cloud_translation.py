"""Тесты облачного LLM-перевода с fallback на Google Translate."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from translate_video.core.config import AdaptationLevel, PipelineConfig, TranslationStyle
from translate_video.core.schemas import Segment
from translate_video.translation.cloud import (
    CloudFallbackSegmentTranslator,
    GeminiTranslationProvider,
    OpenAICompatibleTranslationProvider,
    TranslationProviderError,
    build_translation_prompt,
)


class CloudFallbackSegmentTranslatorTest(unittest.TestCase):
    """Проверяет рейтинг LLM-провайдеров и fallback на legacy-перевод."""

    def test_from_config_skips_paid_polza_by_default(self):
        """Polza.ai не подключается к переводу без явного разрешения платного fallback."""

        env = {
            "GEMINI_API_KEY": "g",
            "OPENROUTER_API_KEY": "o",
            "AIHUBMIX_API_KEY": "a",
            "POLZA_API_KEY": "p",
        }
        with patch("translate_video.translation.cloud.load_env_file", lambda: None), \
                patch.dict("os.environ", env, clear=True):
            translator = CloudFallbackSegmentTranslator.from_config(PipelineConfig())

        names = [provider.name for provider in translator.providers or []]
        self.assertEqual(names, ["gemini", "aihubmix", "openrouter"])

    def test_translator_passes_context_and_project_style_to_provider(self):
        """LLM-переводчик получает два соседних сегмента и настройки проекта."""

        provider = _RecordingProvider("gemini", "перевод")
        translator = CloudFallbackSegmentTranslator(providers=[provider], rate_limits_rpm={})
        segments = [
            Segment(id="s1", start=0, end=1, source_text="before one"),
            Segment(id="s2", start=1, end=2, source_text="current"),
            Segment(id="s3", start=2, end=3, source_text="after one"),
        ]
        config = PipelineConfig(translation_style=TranslationStyle.BUSINESS)

        result = translator.translate(segments, config)

        self.assertEqual([segment.translated_text for segment in result], ["перевод"] * 3)
        self.assertEqual(provider.calls[1]["before"][0].id, "s1")
        self.assertEqual(provider.calls[1]["after"][0].id, "s3")
        self.assertEqual(provider.calls[1]["style"], TranslationStyle.BUSINESS)
        self.assertIn("translation_provider_gemini", result[1].qa_flags)

    def test_failed_cloud_provider_falls_back_to_google_segment(self):
        """Если все LLM-провайдеры упали, один сегмент переводится fallback-переводчиком."""

        translator = CloudFallbackSegmentTranslator(
            providers=[_FailingProvider("gemini")],
            fallback=_StaticFallbackTranslator("резервный перевод"),
            rate_limits_rpm={},
        )
        segment = Segment(id="s1", start=0, end=1, source_text="hello")

        result = translator.translate([segment], PipelineConfig())

        self.assertEqual(result[0].translated_text, "резервный перевод")
        self.assertIn("translation_google_fallback", result[0].qa_flags)

    def test_progress_callback_receives_translation_progress(self):
        """LLM-перевод отдаёт прогресс по сегментам для UI."""

        translator = CloudFallbackSegmentTranslator(
            providers=[_RecordingProvider("gemini", "перевод")],
            rate_limits_rpm={},
        )
        events = []

        translator.translate(
            [
                Segment(id="s1", start=0, end=1, source_text="one"),
                Segment(id="s2", start=1, end=2, source_text="two"),
            ],
            PipelineConfig(),
            progress_callback=lambda current, total, message: events.append(
                (current, total, message)
            ),
        )

        self.assertEqual(events[0], (0, 2, "Подготовка LLM-перевода"))
        self.assertIn((1, 2, "Готово 1/2"), events)
        self.assertEqual(events[-1], (2, 2, "Готово 2/2"))

    def test_professional_profile_uses_only_selected_paid_provider(self):
        """Профессиональный профиль собирает один выбранный провайдер и модель."""

        config = PipelineConfig(
            translation_quality="professional",
            professional_translation_provider="neuroapi",
            professional_translation_model="gpt-5",
        )
        with patch("translate_video.translation.cloud.load_env_file", lambda: None), \
                patch.dict("os.environ", {"NEUROAPI_API_KEY": "secret"}, clear=True):
            translator = CloudFallbackSegmentTranslator.from_config(config)

        self.assertEqual([provider.name for provider in translator.providers or []], ["neuroapi"])
        self.assertEqual(translator.providers[0].model, "gpt-5")

    def test_professional_profile_does_not_fallback_to_google_when_provider_missing(self):
        """Профессиональный профиль должен явно падать, а не менять качество на Google."""

        config = PipelineConfig(
            translation_quality="professional",
            professional_translation_provider="neuroapi",
        )
        with patch("translate_video.translation.cloud.load_env_file", lambda: None), \
                patch.dict("os.environ", {}, clear=True):
            translator = CloudFallbackSegmentTranslator.from_config(config)

        with self.assertRaises(ValueError):
            translator.translate([Segment(id="s1", start=0, end=1, source_text="hello")], config)


class TranslationProviderPayloadTest(unittest.TestCase):
    """Проверяет payload провайдеров без реальной сети."""

    def test_gemini_provider_parses_response(self):
        """Gemini-провайдер достаёт текст из generateContent-ответа."""

        calls = []

        def fake_post(url, payload, *, headers, timeout):
            calls.append((url, payload, headers, timeout))
            return {"candidates": [{"content": {"parts": [{"text": "перевод"}]}}]}

        provider = GeminiTranslationProvider(
            api_key="secret",
            model="gemini-test",
            http_post=fake_post,
        )
        result = provider.translate_segment(
            Segment(start=0, end=1, source_text="hello"),
            config=PipelineConfig(),
            context_before=[],
            context_after=[],
        )

        self.assertEqual(result, "перевод")
        self.assertIn("gemini-test:generateContent", calls[0][0])
        self.assertIn("Переведи ТОЛЬКО текущий сегмент", calls[0][1]["contents"][0]["parts"][0]["text"])

    def test_openai_compatible_provider_uses_translation_model(self):
        """OpenAI-compatible провайдер отправляет chat/completions с моделью перевода."""

        calls = []

        def fake_post(url, payload, *, headers, timeout):
            calls.append((url, payload, headers, timeout))
            return {"choices": [{"message": {"content": "перевод"}}]}

        provider = OpenAICompatibleTranslationProvider(
            name="openrouter",
            api_key="secret",
            base_url="https://example.test/v1",
            model="translation-model",
            http_post=fake_post,
        )
        result = provider.translate_segment(
            Segment(start=0, end=1, source_text="hello"),
            config=PipelineConfig(),
            context_before=[],
            context_after=[],
        )

        self.assertEqual(result, "перевод")
        self.assertEqual(calls[0][0], "https://example.test/v1/chat/completions")
        self.assertEqual(calls[0][1]["model"], "translation-model")
        self.assertEqual(calls[0][2]["Authorization"], "Bearer secret")

    def test_build_translation_prompt_contains_style_glossary_and_context(self):
        """Промпт перевода содержит стиль, глоссарий и соседние сегменты."""

        with tempfile.TemporaryDirectory() as temp_dir:
            glossary = Path(temp_dir) / "glossary.md"
            glossary.write_text("Antigravity = Антигравити\nCodex = Кодекс", encoding="utf-8")
            config = PipelineConfig(
                source_language="en",
                target_language="ru",
                translation_style=TranslationStyle.EDUCATIONAL,
                adaptation_level=AdaptationLevel.LOCALIZED,
                glossary_path=glossary,
                do_not_translate=["Google Antigravity"],
            )

            prompt = build_translation_prompt(
                Segment(start=1, end=2, source_text="This changes coding."),
                config=config,
                context_before=[Segment(start=0, end=1, source_text="Before context.")],
                context_after=[Segment(start=2, end=3, source_text="After context.")],
            )

        self.assertIn("Целевой язык: русский", prompt)
        self.assertIn("объясняющий", prompt)
        self.assertIn("Antigravity = Антигравити", prompt)
        self.assertIn("Google Antigravity", prompt)
        self.assertIn("Before context", prompt)
        self.assertIn("After context", prompt)

    def test_provider_defaults_match_free_models(self):
        """Дефолтные модели перевода используют бесплатные/выбранные пользователем варианты."""

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "secret"}, clear=True):
            openrouter = OpenAICompatibleTranslationProvider.openrouter_from_env()
        with patch.dict("os.environ", {"AIHUBMIX_API_KEY": "secret"}, clear=True):
            aihubmix = OpenAICompatibleTranslationProvider.aihubmix_from_env()
        with patch.dict("os.environ", {"POLZA_API_KEY": "secret"}, clear=True):
            polza = OpenAICompatibleTranslationProvider.polza_from_env()
        with patch.dict("os.environ", {"NEUROAPI_API_KEY": "secret"}, clear=True):
            neuroapi = OpenAICompatibleTranslationProvider.neuroapi_from_env()

        self.assertEqual(openrouter.model, "openai/gpt-oss-20b:free")
        self.assertEqual(aihubmix.model, "gemini-3-flash-preview-free")
        self.assertEqual(polza.model, "google/gemini-2.5-flash-lite-preview-09-2025")
        self.assertEqual(neuroapi.base_url, "https://neuroapi.host/v1")
        self.assertEqual(neuroapi.model, "gpt-5-mini")


class _RecordingProvider:
    """Тестовый LLM-провайдер, который запоминает входной контекст."""

    def __init__(self, name: str, response: str) -> None:
        self.name = name
        self.response = response
        self.calls = []

    def translate_segment(self, segment, *, config, context_before, context_after):
        self.calls.append({
            "segment": segment,
            "before": context_before,
            "after": context_after,
            "style": config.translation_style,
        })
        return self.response


class _FailingProvider:
    """Тестовый LLM-провайдер, который всегда падает."""

    def __init__(self, name: str) -> None:
        self.name = name

    def translate_segment(self, segment, *, config, context_before, context_after):
        raise TranslationProviderError("HTTP 429: quota exceeded")


class _StaticFallbackTranslator:
    """Тестовый fallback-переводчик с фиксированным ответом."""

    def __init__(self, response: str) -> None:
        self.response = response

    def translate(self, segments, config):
        return [
            Segment(
                id=segment.id,
                start=segment.start,
                end=segment.end,
                source_text=segment.source_text,
                translated_text=self.response,
                qa_flags=list(segment.qa_flags),
            )
            for segment in segments
        ]


if __name__ == "__main__":
    unittest.main()
