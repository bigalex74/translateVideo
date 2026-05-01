"""Тесты облачного fallback-роутера для timing_fit."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from translate_video.core.config import PipelineConfig
from translate_video.timing.cloud import (
    CloudFallbackTimingRewriter,
    GeminiRewriteProvider,
    OpenAICompatibleRewriteProvider,
    RewriteProviderError,
    build_rewrite_prompt,
)


class CloudFallbackTimingRewriterTest(unittest.TestCase):
    """Проверяет рейтинг провайдеров и fallback-поведение."""

    def test_from_config_orders_polza_after_free_providers(self):
        """Polza.ai должен быть последним облачным fallback, потому что он платный."""

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
        self.assertEqual(names, ["gemini", "openrouter", "aihubmix", "polza"])

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

    def test_prompt_contains_character_limit(self):
        """Промпт явно содержит лимит символов и запрет пояснений."""

        prompt = build_rewrite_prompt("перевод", "source", 42)

        self.assertIn("не больше 42 символов", prompt)
        self.assertIn("только новая фраза", prompt)

    def test_openrouter_default_model_is_configured(self):
        """OpenRouter по умолчанию использует правильный ID модели с префиксом и суффиксом :free."""

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "secret"}, clear=True):
            provider = OpenAICompatibleRewriteProvider.openrouter_from_env()

        self.assertEqual(provider.model, "openai/gpt-oss-120b:free")

    def test_aihubmix_default_model_is_configured(self):
        """AIHubMix по умолчанию использует выбранную пользователем free-модель."""

        with patch.dict("os.environ", {"AIHUBMIX_API_KEY": "secret"}, clear=True):
            provider = OpenAICompatibleRewriteProvider.aihubmix_from_env()

        self.assertEqual(provider.model, "gemini-3-flash-preview-free")

    def test_polza_default_model_is_configured(self):
        """Polza.ai по умолчанию использует выбранную пользователем модель."""

        with patch.dict("os.environ", {"POLZA_API_KEY": "secret"}, clear=True):
            provider = OpenAICompatibleRewriteProvider.polza_from_env()

        self.assertEqual(provider.model, "google/gemini-2.5-flash-lite-preview-09-2025")


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


if __name__ == "__main__":
    unittest.main()
