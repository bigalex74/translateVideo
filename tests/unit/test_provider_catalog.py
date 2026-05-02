"""Тесты каталога моделей и баланса AI-провайдеров."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from translate_video.core import provider_catalog
from translate_video.core.provider_catalog import get_provider_balance, list_provider_models


class ProviderCatalogTest(unittest.TestCase):
    """Проверяет загрузку моделей и финансовой сводки без реальной сети."""

    def test_list_provider_models_parses_openai_compatible_response(self):
        """OpenAI-compatible `/models` превращается в список id/name."""

        def fake_get_json(url, *, headers, timeout):
            self.assertEqual(url, "https://neuroapi.host/v1/models")
            self.assertEqual(headers["Authorization"], "Bearer secret")
            return {"data": [{"id": "gpt-5-mini"}, {"id": "claude-sonnet", "name": "Claude"}]}

        with patch("translate_video.core.provider_catalog.load_env_file", lambda: None), \
                patch.dict("os.environ", {"NEUROAPI_API_KEY": "secret"}, clear=True), \
                patch.object(provider_catalog, "_get_json", fake_get_json):
            models = list_provider_models("neuroapi")

        self.assertEqual([model.id for model in models], ["claude-sonnet", "gpt-5-mini"])
        self.assertEqual(models[0].name, "Claude")

    def test_neuroapi_balance_returns_usage_and_remaining(self):
        """NeuroAPI: баланс = hard_limit_usd - total_usage/100."""

        def fake_get_json(url, *, headers, timeout):
            self.assertEqual(headers["Authorization"], "Bearer secret")
            if url.endswith("/dashboard/billing/usage"):
                return {"object": "list", "total_usage": 50600}   # 506.00$
            if url.endswith("/dashboard/billing/subscription"):
                return {"object": "billing_subscription", "hard_limit_usd": 600.0}
            self.fail(f"Неожиданный URL: {url}")

        with patch("translate_video.core.provider_catalog.load_env_file", lambda: None), \
                patch.dict("os.environ", {"NEUROAPI_API_KEY": "secret"}, clear=True), \
                patch.object(provider_catalog, "_get_json", fake_get_json):
            balance = get_provider_balance("neuroapi")

        self.assertTrue(balance.configured)
        self.assertAlmostEqual(balance.used, 506.0, places=2)
        self.assertAlmostEqual(balance.balance, 94.0, places=2)   # 600 - 506
        self.assertEqual(balance.currency, "USD")

    def test_missing_key_returns_configured_false_for_balance(self):
        """Если ключа нет, API баланса возвращает понятный статус без утечки секретов."""

        with patch("translate_video.core.provider_catalog.load_env_file", lambda: None), \
                patch.dict("os.environ", {}, clear=True):
            balance = get_provider_balance("neuroapi")

        self.assertFalse(balance.configured)
        self.assertIn("NEUROAPI_API_KEY", balance.message)

    def test_openrouter_balance_computes_remaining_credits(self):
        """OpenRouter credits endpoint превращается в остаток и расход."""

        def fake_get_json(url, *, headers, timeout):
            self.assertEqual(url, "https://openrouter.ai/api/v1/credits")
            return {"data": {"total_credits": 10.0, "total_usage": 2.5}}

        with patch("translate_video.core.provider_catalog.load_env_file", lambda: None), \
                patch.dict("os.environ", {"OPENROUTER_API_KEY": "secret"}, clear=True), \
                patch.object(provider_catalog, "_get_json", fake_get_json):
            balance = get_provider_balance("openrouter")

        self.assertEqual(balance.balance, 7.5)
        self.assertEqual(balance.used, 2.5)


if __name__ == "__main__":
    unittest.main()
