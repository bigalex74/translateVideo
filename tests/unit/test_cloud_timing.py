"""Тесты облачного fallback-роутера для timing_fit."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from translate_video.core.config import AdaptationLevel, PipelineConfig, TranslationStyle
from translate_video.core.schemas import Segment
from translate_video.timing.cloud import (
    CloudFallbackTimingRewriter,
    GeminiRewriteProvider,
    OpenAICompatibleRewriteProvider,
    RewriteProviderError,
    build_rewrite_prompt,
)


class CloudFallbackTimingRewriterTest(unittest.TestCase):
    """Проверяет рейтинг провайдеров и fallback-поведение."""

    def test_from_config_skips_paid_polza_by_default(self):
        """Polza.ai не должен подключаться случайно только из-за наличия ключа."""

        env = {
            "GEMINI_API_KEY": "g",
            "OPENROUTER_API_KEY": "o",
            "AIHUBMIX_API_KEY": "a",
            "POLZA_API_KEY": "p",
        }
        with patch("translate_video.timing.cloud.load_env_file", lambda: None), \
                patch.dict("os.environ", env, clear=True):
            router = CloudFallbackTimingRewriter.from_config(PipelineConfig())

        names = [provider.name for provider in router.providers]
        self.assertEqual(names, ["gemini", "aihubmix", "openrouter"])

    def test_from_config_orders_polza_after_free_providers_when_paid_allowed(self):
        """Polza.ai остаётся последним fallback, если платные провайдеры явно разрешены."""

        env = {
            "GEMINI_API_KEY": "g",
            "OPENROUTER_API_KEY": "o",
            "AIHUBMIX_API_KEY": "a",
            "POLZA_API_KEY": "p",
            "REWRITE_ALLOW_PAID_FALLBACK": "true",
        }
        with patch("translate_video.timing.cloud.load_env_file", lambda: None), \
                patch.dict("os.environ", env, clear=True):
            router = CloudFallbackTimingRewriter.from_config(PipelineConfig())

        names = [provider.name for provider in router.providers]
        self.assertEqual(names, ["gemini", "aihubmix", "openrouter", "polza"])

    def test_professional_profile_uses_selected_rewrite_provider(self):
        """Профессиональный профиль использует одну выбранную модель для сокращения."""

        config = PipelineConfig(
            translation_quality="professional",
            professional_rewrite_provider="neuroapi",
            professional_rewrite_model="gpt-5",
        )
        with patch("translate_video.timing.cloud.load_env_file", lambda: None), \
                patch.dict("os.environ", {"NEUROAPI_API_KEY": "secret"}, clear=True):
            router = CloudFallbackTimingRewriter.from_config(config)

        self.assertEqual([provider.name for provider in router.providers], ["neuroapi"])
        self.assertEqual(router.providers[0].model, "gpt-5")

    def test_professional_profile_does_not_use_rule_based_fallback(self):
        """TVIDEO-081: professional-режим при провале rewriter возвращает оригинал (не падает).

        Старое поведение: raise RewriteProviderError → TimingFitStage.FAILED → pipeline abort.
        Новое поведение: возврат исходного текста + QA-флаг rewrite_provider_no_timing_fit.
        Pipeline продолжается, видео создаётся.
        """

        original_text = "длинный текст который не подогнан"
        router = CloudFallbackTimingRewriter(
            providers=[],
            allow_rule_based_fallback=False,
        )

        # НЕ бросает — возвращает исходный текст
        result = router.rewrite(original_text, source_text="source", max_chars=5, attempt=1)
        self.assertEqual(result, original_text)
        # QA-флаг добавлен
        events = router.consume_events()
        self.assertIn("rewrite_provider_no_timing_fit", events)

    def test_router_falls_back_after_provider_error(self):
        """Ошибка первого провайдера переключает роутер на следующий."""

        router = CloudFallbackTimingRewriter(
            providers=[
                _FailingProvider("gemini"),
                _StaticProvider("openrouter", "короткий ответ"),
            ]
        )

        result = router.rewrite(
            "Очень длинная фраза для озвучки.",
            source_text="Long phrase.",
            max_chars=20,
            attempt=1,
        )

        self.assertEqual(result, "короткий ответ")
        self.assertIn("rewrite_provider_failed", router.consume_events())

    def test_router_puts_quota_limited_provider_into_cooldown(self):
        """429/503/timeout временно ставят провайдера на паузу, а не выключают навсегда."""

        failing = _CountingFailingProvider("gemini", "HTTP 429: quota exceeded")
        clock = _FakeClock()
        router = CloudFallbackTimingRewriter(
            providers=[
                failing,
                _StaticProvider("openrouter", "короткий ответ"),
            ],
            cooldown_seconds=60,
            now_fn=clock.now,
            sleep_fn=clock.sleep,
        )

        first = router.rewrite(
            "Очень длинная фраза для озвучки.",
            source_text="Long phrase.",
            max_chars=20,
            attempt=1,
        )
        first_events = router.consume_events()
        second = router.rewrite(
            "Ещё одна длинная фраза для озвучки.",
            source_text="Another phrase.",
            max_chars=20,
            attempt=1,
        )
        second_events = router.consume_events()

        self.assertEqual(first, "короткий ответ")
        self.assertEqual(second, "короткий ответ")
        self.assertEqual(failing.calls, 1)
        self.assertIn("rewrite_provider_quota_limited", first_events)
        self.assertIn("rewrite_provider_skipped", second_events)

        clock.sleep(61)
        router.rewrite(
            "Третья длинная фраза для озвучки.",
            source_text="Third phrase.",
            max_chars=20,
            attempt=1,
        )

        self.assertEqual(failing.calls, 2)

    def test_router_respects_provider_rpm_before_request(self):
        """RPM-лимит делает паузу до следующего запроса к тому же провайдеру."""

        clock = _FakeClock()
        provider = _StaticProvider("gemini", "короткий ответ")
        router = CloudFallbackTimingRewriter(
            providers=[provider],
            rate_limits_rpm={"gemini": 5},
            now_fn=clock.now,
            sleep_fn=clock.sleep,
        )

        router.rewrite(
            "Очень длинная фраза для озвучки.",
            source_text="Long phrase.",
            max_chars=20,
            attempt=1,
        )
        first_events = router.consume_events()
        router.rewrite(
            "Ещё одна длинная фраза для озвучки.",
            source_text="Another phrase.",
            max_chars=20,
            attempt=1,
        )
        second_events = router.consume_events()

        self.assertNotIn("rewrite_provider_rate_limited", first_events)
        self.assertIn("rewrite_provider_rate_limited", second_events)
        self.assertEqual(clock.current, 12.0)

    def test_router_uses_rule_based_when_no_cloud_candidate(self):
        """Если облако недоступно, остаётся безопасный rule-based fallback."""

        router = CloudFallbackTimingRewriter(providers=[])

        result = router.rewrite(
            "На сегодняшний день это является важным.",
            source_text="source",
            max_chars=20,
            attempt=1,
        )

        self.assertEqual(result, "сейчас это важно.")


class ProviderPayloadTest(unittest.TestCase):
    """Проверяет формат запросов к внешним API без реальной сети."""

    def test_gemini_provider_parses_generate_content_response(self):
        """Gemini-провайдер достаёт текст из candidates[].content.parts[]."""

        calls = []

        def fake_post(url, payload, *, headers, timeout):
            calls.append((url, payload, headers, timeout))
            return {"candidates": [{"content": {"parts": [{"text": "короче"}]}}]}

        provider = GeminiRewriteProvider(
            api_key="secret",
            model="gemini-test",
            http_post=fake_post,
        )

        result = provider.rewrite("длинный текст", source_text="source", max_chars=10, attempt=1)

        self.assertEqual(result, "короче")
        self.assertIn("gemini-test:generateContent", calls[0][0])

        self.assertIn("secret", calls[0][0])

    def test_openai_compatible_provider_parses_chat_completion(self):
        """OpenAI-compatible провайдер отправляет chat/completions и читает choices."""

        calls = []

        def fake_post(url, payload, *, headers, timeout):
            calls.append((url, payload, headers, timeout))
            return {"choices": [{"message": {"content": "короче"}}]}

        provider = OpenAICompatibleRewriteProvider(
            name="openrouter",
            api_key="secret",
            base_url="https://example.test/v1",
            model="free-model",
            http_post=fake_post,
        )

        result = provider.rewrite("длинный текст", source_text="source", max_chars=10, attempt=1)

        self.assertEqual(result, "короче")
        self.assertEqual(calls[0][0], "https://example.test/v1/chat/completions")
        self.assertEqual(calls[0][1]["model"], "free-model")
        self.assertEqual(calls[0][2]["Authorization"], "Bearer secret")

    def test_prompt_contains_character_limit_style_glossary_and_context(self):
        """Промпт professional-rewriter содержит лимит, стиль, глоссарий и соседние сегменты."""

        with tempfile.TemporaryDirectory() as temp_dir:
            glossary = Path(temp_dir) / "glossary.md"
            glossary.write_text("Antigravity = Антигравити", encoding="utf-8")
            config = PipelineConfig(
                source_language="en",
                target_language="ru",
                translation_quality="professional",  # ← стиль только в pro
                translation_style=TranslationStyle.CINEMATIC,
                adaptation_level=AdaptationLevel.SHORTENED_FOR_TIMING,
                profanity_policy="remove",
                glossary_path=glossary,
                do_not_translate=["Codex"],
            )
            prompt = build_rewrite_prompt(
                "длинный перевод",
                "source",
                42,
                segment=Segment(
                    start=1,
                    end=2,
                    source_text="source",
                    translated_text="длинный перевод",
                ),
                context_before=[
                    Segment(start=0, end=1, source_text="before", translated_text="до")
                ],
                context_after=[
                    Segment(start=2, end=3, source_text="after", translated_text="после")
                ],
                config=config,
            )

        self.assertIn("42 символов", prompt)           # лимит упоминается
        self.assertIn("31 до 42", prompt)               # целевой диапазон (75–100%)
        self.assertIn("только готовая фраза", prompt)   # запрет пояснений
        self.assertIn("НЕ обрезай", prompt)             # запрет жёсткой обрезки
        self.assertIn("кинематографичный", prompt)      # стиль cinematic
        self.assertIn("нейтральными эквивалентами", prompt)  # profanity=remove
        self.assertIn("Antigravity = Антигравити", prompt)
        self.assertIn("Codex", prompt)
        self.assertIn("before", prompt)                 # before_context
        self.assertIn("after", prompt)                  # after_context
        self.assertIn("до", prompt)                     # переведённый before_context
        self.assertIn("после", prompt)                  # переведённый after_context

    def test_openrouter_default_model_is_configured(self):
        """OpenRouter по умолчанию использует правильный ID модели с префиксом и суффиксом :free."""

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "secret"}, clear=True):
            provider = OpenAICompatibleRewriteProvider.openrouter_from_env()

        self.assertEqual(provider.model, "openai/gpt-oss-20b:free")
        self.assertEqual(provider.timeout, 8.0)

    def test_provider_timeout_can_be_overridden_globally(self):
        """REWRITE_PROVIDER_TIMEOUT задаёт короткий общий timeout для всей цепочки."""

        env = {
            "OPENROUTER_API_KEY": "secret",
            "REWRITE_PROVIDER_TIMEOUT": "3.5",
        }
        with patch("translate_video.timing.cloud.load_env_file", lambda: None), \
                patch.dict("os.environ", env, clear=True):
            router = CloudFallbackTimingRewriter.from_config(PipelineConfig())

        self.assertEqual(router.providers[0].timeout, 3.5)

    def test_aihubmix_default_model_is_configured(self):
        """AIHubMix по умолчанию использует выбранную пользователем free-модель."""

        with patch.dict("os.environ", {"AIHUBMIX_API_KEY": "secret"}, clear=True):
            provider = OpenAICompatibleRewriteProvider.aihubmix_from_env()

        self.assertEqual(provider.model, "gpt-4.1-nano-free")

    def test_polza_default_model_is_configured(self):
        """Polza.ai по умолчанию использует выбранную пользователем модель."""

        with patch.dict("os.environ", {"POLZA_API_KEY": "secret"}, clear=True):
            provider = OpenAICompatibleRewriteProvider.polza_from_env()

        self.assertEqual(provider.model, "google/gemini-2.5-flash-lite-preview-09-2025")

    def test_neuroapi_default_model_is_configured(self):
        """NeuroAPI использует OpenAI-compatible endpoint и профессиональную модель."""

        with patch.dict("os.environ", {"NEUROAPI_API_KEY": "secret"}, clear=True):
            provider = OpenAICompatibleRewriteProvider.neuroapi_from_env()

        self.assertEqual(provider.base_url, "https://neuroapi.host/v1")
        self.assertEqual(provider.model, "gpt-5-mini")


class _StaticProvider:
    """Тестовый провайдер с фиксированным ответом."""

    def __init__(self, name: str, response: str) -> None:
        self.name = name
        self.response = response

    def rewrite(self, text: str, *, source_text: str, max_chars: int, attempt: int) -> str:
        return self.response


class _FailingProvider:
    """Тестовый провайдер, который имитирует отказ API."""

    def __init__(self, name: str) -> None:
        self.name = name

    def rewrite(self, text: str, *, source_text: str, max_chars: int, attempt: int) -> str:
        raise RewriteProviderError("fail")


class _CountingFailingProvider:
    """Тестовый провайдер, который считает вызовы и всегда падает."""

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        self.calls = 0

    def rewrite(self, text: str, *, source_text: str, max_chars: int, attempt: int) -> str:
        self.calls += 1
        raise RewriteProviderError(self.reason)


class _FakeClock:
    """Управляемые часы для тестов rate-limit и cooldown без реального ожидания."""

    def __init__(self) -> None:
        self.current = 0.0

    def now(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.current += seconds


if __name__ == "__main__":
    unittest.main()
