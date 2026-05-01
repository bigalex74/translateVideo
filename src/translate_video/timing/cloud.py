"""Облачный fallback-роутер для сокращения перевода под тайминг.

Роутер идёт от бесплатных/условно бесплатных провайдеров к платным:
Gemini → OpenRouter → AIHubMix → Polza → rule_based.
Реальные ключи читаются только из окружения и не должны попадать в репозиторий.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from translate_video.core.config import PipelineConfig
from translate_video.core.env import load_env_file
from translate_video.timing.base import TimingRewriter
from translate_video.timing.natural import RuleBasedTimingRewriter


class RewriteProviderError(RuntimeError):
    """Ошибка одного облачного провайдера rewrite-задачи."""


@dataclass(slots=True)
class RewriteProviderResult:
    """Результат попытки одного провайдера."""

    provider: str
    text: str


class CloudFallbackTimingRewriter:
    """Пробует облачные модели по рейтингу и падает в rule-based fallback."""

    def __init__(
        self,
        providers: list[TimingRewriter],
        fallback: TimingRewriter | None = None,
    ) -> None:
        self.providers = providers
        self.fallback = fallback or RuleBasedTimingRewriter()
        self._events: list[str] = []

    @classmethod
    def from_config(cls, config: PipelineConfig) -> "CloudFallbackTimingRewriter":
        """Собрать роутер из конфигурации и переменных окружения."""

        load_env_file()
        factories = {
            "gemini": GeminiRewriteProvider.from_env,
            "openrouter": OpenAICompatibleRewriteProvider.openrouter_from_env,
            "aihubmix": OpenAICompatibleRewriteProvider.aihubmix_from_env,
            "polza": OpenAICompatibleRewriteProvider.polza_from_env,
        }
        providers: list[TimingRewriter] = []
        for raw_name in config.rewrite_provider_order:
            name = raw_name.strip().lower()
            factory = factories.get(name)
            if factory is None:
                continue
            provider = factory()
            if provider is not None:
                providers.append(provider)
        return cls(providers=providers)

    def rewrite(
        self,
        text: str,
        *,
        source_text: str,
        max_chars: int,
        attempt: int,
    ) -> str:
        """Вернуть лучший короткий вариант, используя fallback-цепочку."""

        self._events = []
        for provider in self.providers:
            name = getattr(provider, "name", provider.__class__.__name__)
            try:
                candidate = _clean_candidate(provider.rewrite(
                    text,
                    source_text=source_text,
                    max_chars=max_chars,
                    attempt=attempt,
                ))
            except RewriteProviderError:
                self._events.extend(["rewrite_provider_failed", "rewrite_fallback_used"])
                continue
            if _is_useful_candidate(candidate, original=text, max_chars=max_chars):
                self._events.append("rewrite_provider_used")
                if name != "gemini":
                    self._events.append("rewrite_fallback_used")
                self._events.append(f"rewrite_provider_{name}")
                return candidate
            self._events.extend(["rewrite_provider_failed", "rewrite_fallback_used"])

        candidate = self.fallback.rewrite(
            text,
            source_text=source_text,
            max_chars=max_chars,
            attempt=attempt,
        )
        if candidate != text:
            self._events.append("rewrite_provider_rule_based")
        return candidate

    def consume_events(self) -> list[str]:
        """Вернуть и очистить события последней rewrite-попытки."""

        events = list(dict.fromkeys(self._events))
        self._events = []
        return events


class GeminiRewriteProvider:
    """Rewrite-провайдер Gemini через официальный generateContent API."""

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3-flash-preview",
        timeout: float = 20.0,
        http_post=None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.http_post = http_post or _post_json

    @classmethod
    def from_env(cls) -> "GeminiRewriteProvider | OpenAICompatibleRewriteProvider | None":
        """Создать провайдер Gemini из окружения.

        Если задан GEMINI_BRIDGE_URL — использует OpenAI-совместимый мост
        (например http://127.0.0.1:5000/v1). Мост авторизуется самостоятельно,
        GEMINI_API_KEY не нужен.

        Иначе — нативный Gemini generateContent API с GEMINI_API_KEY.
        """

        model = os.getenv("GEMINI_REWRITE_MODEL", "gemini-3-flash-preview")
        bridge_url = os.getenv("GEMINI_BRIDGE_URL")

        if bridge_url:
            # OpenAI-совместимый мост (127.0.0.1:5000 и др.)
            return OpenAICompatibleRewriteProvider(
                name="gemini",
                api_key=os.getenv("GEMINI_API_KEY", "bridge"),  # мост авторизуется сам
                base_url=bridge_url.rstrip("/"),
                model=model,
            )

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        return cls(api_key=api_key, model=model)

    def rewrite(
        self,
        text: str,
        *,
        source_text: str,
        max_chars: int,
        attempt: int,
    ) -> str:
        """Запросить у Gemini короткую версию перевода."""

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": build_rewrite_prompt(text, source_text, max_chars)}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": max(32, min(256, max_chars * 2)),
            },
        }
        data = self.http_post(url, payload, headers={}, timeout=self.timeout)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RewriteProviderError("Gemini вернул неожиданный формат") from exc


class OpenAICompatibleRewriteProvider:
    """Rewrite-провайдер для OpenAI-compatible агрегаторов."""

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 20.0,
        extra_headers: dict[str, str] | None = None,
        http_post=None,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self.http_post = http_post or _post_json

    @classmethod
    def openrouter_from_env(cls) -> "OpenAICompatibleRewriteProvider | None":
        """Создать OpenRouter-провайдер, если ключ есть в окружении."""

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return None
        return cls(
            name="openrouter",
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=os.getenv("OPENROUTER_REWRITE_MODEL", "openai/gpt-oss-120b:free"),
            extra_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:8002"),
                "X-Title": os.getenv("OPENROUTER_APP_NAME", "translateVideo"),
            },
        )

    @classmethod
    def aihubmix_from_env(cls) -> "OpenAICompatibleRewriteProvider | None":
        """Создать AIHubMix-провайдер, если ключ есть в окружении."""

        api_key = os.getenv("AIHUBMIX_API_KEY")
        if not api_key:
            return None
        return cls(
            name="aihubmix",
            api_key=api_key,
            base_url=os.getenv("AIHUBMIX_BASE_URL", "https://aihubmix.com/v1"),
            model=os.getenv("AIHUBMIX_REWRITE_MODEL", "gpt-4.1-nano-free"),
        )

    @classmethod
    def polza_from_env(cls) -> "OpenAICompatibleRewriteProvider | None":
        """Создать Polza.ai-провайдер, если ключ есть в окружении."""

        api_key = os.getenv("POLZA_API_KEY")
        if not api_key:
            return None
        return cls(
            name="polza",
            api_key=api_key,
            base_url=os.getenv("POLZA_BASE_URL", "https://api.polza.ai/api/v1"),
            model=os.getenv("POLZA_REWRITE_MODEL", "google/gemini-2.5-flash-lite-preview-09-2025"),
        )

    def rewrite(
        self,
        text: str,
        *,
        source_text: str,
        max_chars: int,
        attempt: int,
    ) -> str:
        """Запросить короткую версию перевода у OpenAI-compatible API."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            **self.extra_headers,
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Ты редактор дубляжа. Отвечай только готовой фразой."},
                {"role": "user", "content": build_rewrite_prompt(text, source_text, max_chars)},
            ],
            "temperature": 0.2,
            "max_tokens": max(32, min(256, max_chars * 2)),
        }
        data = self.http_post(
            f"{self.base_url}/chat/completions",
            payload,
            headers=headers,
            timeout=self.timeout,
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RewriteProviderError(f"{self.name} вернул неожиданный формат") from exc


def build_rewrite_prompt(text: str, source_text: str, max_chars: int) -> str:
    """Сформировать строгий промпт для сокращения под тайминг."""

    return (
        "Сократи русский перевод для естественной озвучки.\n"
        f"Лимит: не больше {max_chars} символов.\n"
        "Сохрани смысл, факты, имена, термины и тон. Не добавляй пояснения.\n"
        "Если смысл нельзя сохранить в лимите, верни максимально короткую естественную фразу.\n\n"
        f"Оригинал:\n{source_text}\n\n"
        f"Перевод:\n{text}\n\n"
        "Ответ: только новая фраза без кавычек."
    )


def _clean_candidate(candidate: str) -> str:
    """Убрать кавычки и thinking-блоки вокруг ответа модели.

    Reasoning-модели (minimax, DeepSeek-R1, Qwen) оборачивают рассуждения в
    <think>...</think>. Нам нужен только итоговый текст после закрывающего тега.
    """

    import re
    # Убираем <think>...</think> блоки reasoning-моделей
    candidate = re.sub(r"<think>.*?</think>", "", candidate, flags=re.DOTALL)
    return candidate.strip().strip('"«»').strip()


def _is_useful_candidate(candidate: str, *, original: str, max_chars: int) -> bool:
    """Проверить, стоит ли принимать ответ провайдера."""

    if not candidate:
        return False
    if candidate == original.strip():
        return False
    return len(candidate) <= max_chars or len(candidate) < len(original)


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    """Выполнить JSON POST через стандартную библиотеку.

    Если задан HTTPS_PROXY или HTTP_PROXY — использует их.
    Это позволяет обойти региональные блокировки (например, для Gemini API).
    """

    all_headers = {"Content-Type": "application/json", **headers}

    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=all_headers,
        method="POST",
    )

    # Прокси: REWRITER_PROXY (кастомный, только для cloud rewriter).
    # НЕ используем системные HTTPS_PROXY/HTTP_PROXY — они ломают Docker
    # (Whisper, HuggingFace и другие соединения тоже пойдут через прокси).
    proxy_url = os.getenv("REWRITER_PROXY")
    if proxy_url:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
        open_fn = opener.open
    else:
        open_fn = urllib.request.urlopen

    try:
        with open_fn(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RewriteProviderError("rewrite provider unavailable") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RewriteProviderError("rewrite provider returned invalid JSON") from exc
