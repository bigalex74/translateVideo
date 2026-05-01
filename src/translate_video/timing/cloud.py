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
from translate_video.core.log import Timer, get_logger
from translate_video.timing.base import TimingRewriter
from translate_video.timing.natural import RuleBasedTimingRewriter

_log = get_logger(__name__)


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
        *,
        disable_on_quota: bool = True,
    ) -> None:
        self.providers = providers
        self.fallback = fallback or RuleBasedTimingRewriter()
        self.disable_on_quota = disable_on_quota
        self._events: list[str] = []
        self._disabled_providers: set[str] = set()

    @classmethod
    def from_config(cls, config: PipelineConfig) -> "CloudFallbackTimingRewriter":
        """Собрать роутер из конфигурации и переменных окружения."""

        load_env_file()
        timeout = _env_float("REWRITE_PROVIDER_TIMEOUT", config.rewrite_provider_timeout)
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
            provider = factory(timeout=timeout)
            if provider is not None:
                providers.append(provider)
        return cls(
            providers=providers,
            disable_on_quota=config.rewrite_provider_disable_on_quota,
        )

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
        prev_provider: str | None = None

        for provider in self.providers:
            name = getattr(provider, "name", provider.__class__.__name__)
            if name in self._disabled_providers:
                self._events.extend(["rewrite_provider_skipped", "rewrite_fallback_used"])
                _log.warning(
                    "rewriter.provider_skip",
                    provider=name,
                    reason="disabled_after_quota_or_timeout",
                )
                prev_provider = name
                continue
            try:
                _log.debug(
                    "rewriter.request",
                    provider=name,
                    max_chars=max_chars,
                    attempt=attempt,
                    in_chars=len(text),
                )
                with Timer() as t:
                    candidate = _clean_candidate(provider.rewrite(
                        text,
                        source_text=source_text,
                        max_chars=max_chars,
                        attempt=attempt,
                    ))
            except RewriteProviderError as exc:
                reason = str(exc)[:120]
                _log.warning(
                    "rewriter.provider_fail",
                    provider=name,
                    reason=reason,
                )
                self._events.extend(["rewrite_provider_failed", "rewrite_fallback_used"])
                if self.disable_on_quota and _is_quota_or_overload(reason):
                    self._disabled_providers.add(name)
                    self._events.append("rewrite_provider_quota_limited")
                    _log.warning(
                        "rewriter.provider_disable",
                        provider=name,
                        reason=reason,
                    )
                prev_provider = name
                continue

            _log.info(
                "rewriter.response",
                provider=name,
                elapsed_s=t.elapsed,
                in_chars=len(text),
                out_chars=len(candidate),
                max_chars=max_chars,
                fits=len(candidate) <= max_chars,
            )

            if _is_useful_candidate(candidate, original=text, max_chars=max_chars):
                if prev_provider is not None:
                    _log.warning(
                        "rewriter.fallback",
                        from_provider=prev_provider,
                        to_provider=name,
                    )
                self._events.append("rewrite_provider_used")
                if name != "gemini":
                    self._events.append("rewrite_fallback_used")
                self._events.append(f"rewrite_provider_{name}")
                return candidate

            _log.warning(
                "rewriter.candidate_rejected",
                provider=name,
                out_chars=len(candidate),
                max_chars=max_chars,
            )
            self._events.extend(["rewrite_provider_failed", "rewrite_fallback_used"])
            prev_provider = name

        _log.warning(
            "rewriter.all_failed",
            providers=[getattr(p, "name", p.__class__.__name__) for p in self.providers],
            fallback="rule_based",
            in_chars=len(text),
            max_chars=max_chars,
        )
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
        model: str = "gemini-2.5-flash-lite",
        timeout: float = 20.0,
        http_post=None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.http_post = http_post or _post_json

    @classmethod
    def from_env(
        cls,
        *,
        timeout: float | None = None,
    ) -> "GeminiRewriteProvider | OpenAICompatibleRewriteProvider | None":
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
                timeout=timeout or _env_float("GEMINI_REWRITE_TIMEOUT", 8.0),
            )

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            model=model,
            timeout=timeout or _env_float("GEMINI_REWRITE_TIMEOUT", 8.0),
        )

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
    def openrouter_from_env(
        cls,
        *,
        timeout: float | None = None,
    ) -> "OpenAICompatibleRewriteProvider | None":
        """Создать OpenRouter-провайдер, если ключ есть в окружении."""

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return None
        return cls(
            name="openrouter",
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=os.getenv("OPENROUTER_REWRITE_MODEL", "openai/gpt-oss-120b:free"),
            timeout=timeout or _env_float("OPENROUTER_REWRITE_TIMEOUT", 8.0),
            extra_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:8002"),
                "X-Title": os.getenv("OPENROUTER_APP_NAME", "translateVideo"),
            },
        )

    @classmethod
    def aihubmix_from_env(
        cls,
        *,
        timeout: float | None = None,
    ) -> "OpenAICompatibleRewriteProvider | None":
        """Создать AIHubMix-провайдер, если ключ есть в окружении."""

        api_key = os.getenv("AIHUBMIX_API_KEY")
        if not api_key:
            return None
        return cls(
            name="aihubmix",
            api_key=api_key,
            base_url=os.getenv("AIHUBMIX_BASE_URL", "https://aihubmix.com/v1"),
            model=os.getenv("AIHUBMIX_REWRITE_MODEL", "gpt-4.1-nano-free"),
            timeout=timeout or _env_float("AIHUBMIX_REWRITE_TIMEOUT", 8.0),
        )

    @classmethod
    def polza_from_env(
        cls,
        *,
        timeout: float | None = None,
    ) -> "OpenAICompatibleRewriteProvider | None":
        """Создать Polza.ai-провайдер, если ключ есть в окружении."""

        api_key = os.getenv("POLZA_API_KEY")
        if not api_key:
            return None
        return cls(
            name="polza",
            api_key=api_key,
            base_url=os.getenv("POLZA_BASE_URL", "https://api.polza.ai/api/v1"),
            model=os.getenv("POLZA_REWRITE_MODEL", "google/gemini-2.5-flash-lite-preview-09-2025"),
            timeout=timeout or _env_float("POLZA_REWRITE_TIMEOUT", 8.0),
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
                {"role": "user", "content": build_rewrite_prompt(text, source_text, max_chars)},
            ],
            "temperature": 0.1,
            "max_tokens": max(64, min(512, max_chars * 3)),
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
    """Сформировать промпт для сокращения текста под тайминг дубляжа."""

    # Целевой диапазон — использовать лимит по максимуму, не обрезать лишнего.
    target_min = max(1, int(max_chars * 0.75))
    return (
        f"Ты редактор русского дубляжа. Перепиши перевод так, чтобы он умещался "
        f"в {max_chars} символов, сохраняя смысл максимально полно.\n\n"
        f"ПРАВИЛА:\n"
        f"- Длина результата: от {target_min} до {max_chars} символов (стремись к максимуму).\n"
        f"- Сохраняй смысл, факты, имена, термины, метафоры и тон оригинала.\n"
        f"- Сокращай длинные обороты, убирай вводные слова, используй синонимы.\n"
        f"- НЕ обрезай текст на полуслове и НЕ выбрасывай ключевые идеи.\n"
        f"- Ответ — только готовая фраза, без кавычек, пояснений и комментариев.\n\n"
        f"Оригинал (EN):\n{source_text}\n\n"
        f"Перевод (RU, {len(text)} симв.):\n{text}\n\n"
        f"Перепиши (≤{max_chars} симв.):"
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
    except urllib.error.HTTPError as exc:
        raise RewriteProviderError(f"HTTP {exc.code}: rewrite provider rejected request") from exc
    except TimeoutError as exc:
        raise RewriteProviderError("timeout: rewrite provider did not respond in time") from exc
    except urllib.error.URLError as exc:
        raise RewriteProviderError(f"network: {exc.reason}") from exc
    except OSError as exc:
        raise RewriteProviderError(f"os: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RewriteProviderError("rewrite provider returned invalid JSON") from exc


def _env_float(name: str, default: float) -> float:
    """Прочитать float из окружения, не падая на ошибочных значениях."""

    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _is_quota_or_overload(reason: str) -> bool:
    """Определить ошибки, после которых провайдера лучше пропустить до конца запуска."""

    normalized = reason.lower()
    return any(marker in normalized for marker in ("429", "503", "quota", "rate", "timeout"))
