"""LLM-перевод сегментов с fallback на Google Translate.

Модуль не заменяет контракт `Translator`: для пайплайна это обычный переводчик,
который сначала пробует облачные модели по рейтингу, а затем безопасно падает
на legacy Google Translate.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from translate_video.core.config import PipelineConfig
from translate_video.core.env import load_env_file
from translate_video.core.log import Timer, get_logger
from translate_video.core.prompting import (
    build_context_block,
    build_glossary_block,
    build_project_directives,
    context_window,
    language_label,
)
from translate_video.core.schemas import Segment
from translate_video.translation.base import Translator
from translate_video.translation.legacy import GoogleSegmentTranslator

_log = get_logger(__name__)


class TranslationProviderError(RuntimeError):
    """Ошибка одного облачного провайдера перевода."""


class SegmentTranslationProvider(Protocol):
    """Контракт одного LLM-провайдера перевода."""

    name: str

    def translate_segment(
        self,
        segment: Segment,
        *,
        config: PipelineConfig,
        context_before: list[Segment],
        context_after: list[Segment],
    ) -> str:
        """Перевести один сегмент с учетом соседнего контекста."""


@dataclass(slots=True)
class TranslationProviderResult:
    """Результат успешного ответа одного провайдера."""

    provider: str
    text: str


class CloudFallbackSegmentTranslator:
    """Переводит сегменты через LLM-рейтинг и fallback на Google Translate."""

    def __init__(
        self,
        providers: list[SegmentTranslationProvider] | None = None,
        fallback: Translator | None = None,
        *,
        disable_on_quota: bool = True,
        rate_limits_rpm: dict[str, float] | None = None,
        cooldown_seconds: float = 75.0,
        wait_for_rate_limit: bool = True,
        now_fn=None,
        sleep_fn=None,
    ) -> None:
        self.providers = providers
        self.fallback = fallback or GoogleSegmentTranslator()
        self.disable_on_quota = disable_on_quota
        self.rate_limits_rpm = rate_limits_rpm or {}
        self.cooldown_seconds = cooldown_seconds
        self.wait_for_rate_limit = wait_for_rate_limit
        self._now = now_fn or time.monotonic
        self._sleep = sleep_fn or time.sleep
        self._cooldown_until: dict[str, float] = {}
        self._next_allowed_at: dict[str, float] = {}

    @classmethod
    def from_config(
        cls,
        config: PipelineConfig,
        *,
        fallback: Translator | None = None,
    ) -> "CloudFallbackSegmentTranslator":
        """Собрать переводчик из конфигурации и переменных окружения."""

        load_env_file()
        timeout = _env_float("TRANSLATION_PROVIDER_TIMEOUT", config.translation_provider_timeout)
        allow_paid = _env_bool(
            "TRANSLATION_ALLOW_PAID_FALLBACK",
            config.translation_allow_paid_fallback,
        )
        factories = {
            "gemini": GeminiTranslationProvider.from_env,
            "openrouter": OpenAICompatibleTranslationProvider.openrouter_from_env,
            "aihubmix": OpenAICompatibleTranslationProvider.aihubmix_from_env,
            "polza": OpenAICompatibleTranslationProvider.polza_from_env,
        }
        providers: list[SegmentTranslationProvider] = []
        if config.use_cloud_translation:
            for raw_name in config.translation_provider_order:
                name = raw_name.strip().lower()
                if name == "google":
                    continue
                factory = factories.get(name)
                if factory is None:
                    continue
                if name == "polza" and not allow_paid:
                    _log.info("translation.paid_provider_skip", provider=name)
                    continue
                provider = factory(timeout=timeout)
                if provider is not None:
                    providers.append(provider)
        return cls(
            providers=providers,
            fallback=fallback,
            disable_on_quota=config.translation_provider_disable_on_quota,
            rate_limits_rpm=config.translation_provider_rpm,
            cooldown_seconds=config.translation_provider_cooldown_seconds,
            wait_for_rate_limit=config.translation_provider_wait_for_rate_limit,
        )

    def translate(self, segments: list[Segment], config: PipelineConfig) -> list[Segment]:
        """Перевести список сегментов через LLM или fallback-переводчик."""

        if self.providers is None:
            return self.from_config(config, fallback=self.fallback).translate(segments, config)
        if not segments:
            return []
        if not self.providers:
            _log.warning("translation.cloud_unavailable", fallback="google", segments=len(segments))
            return self.fallback.translate(segments, config)

        translated: list[Segment] = []
        with Timer() as timer:
            for index, segment in enumerate(segments):
                before, after = context_window(segments, index, size=2)
                result = self._translate_one(
                    segment,
                    config=config,
                    context_before=before,
                    context_after=after,
                )
                if result is None:
                    translated.append(self._fallback_one(segment, config))
                else:
                    translated.append(_apply_translation(segment, result.text, result.provider))

        _log.info(
            "translation.cloud_done",
            segments=len(segments),
            elapsed_s=timer.elapsed,
            providers=[provider.name for provider in self.providers],
        )
        return translated

    def _translate_one(
        self,
        segment: Segment,
        *,
        config: PipelineConfig,
        context_before: list[Segment],
        context_after: list[Segment],
    ) -> TranslationProviderResult | None:
        """Перевести один сегмент через первый успешный LLM-провайдер."""

        previous_provider: str | None = None
        for provider in self.providers or []:
            name = provider.name
            cooldown_remaining = self._cooldown_remaining(name)
            if cooldown_remaining > 0:
                _log.warning(
                    "translation.provider_skip",
                    provider=name,
                    reason="cooldown_after_quota_or_timeout",
                    wait_s=round(cooldown_remaining, 3),
                )
                previous_provider = name
                continue
            try:
                self._respect_rate_limit(name)
                with Timer() as timer:
                    candidate = _clean_candidate(
                        provider.translate_segment(
                            segment,
                            config=config,
                            context_before=context_before,
                            context_after=context_after,
                        )
                    )
            except TranslationProviderError as exc:
                reason = str(exc)[:120]
                _log.warning("translation.provider_fail", provider=name, reason=reason)
                if self.disable_on_quota and _is_quota_or_overload(reason):
                    self._cooldown_until[name] = self._now() + self.cooldown_seconds
                    _log.warning(
                        "translation.provider_cooldown",
                        provider=name,
                        reason=reason,
                        cooldown_s=self.cooldown_seconds,
                    )
                previous_provider = name
                continue

            _log.info(
                "translation.provider_response",
                provider=name,
                elapsed_s=timer.elapsed,
                source_chars=len(segment.source_text),
                out_chars=len(candidate),
            )
            if _is_useful_translation(candidate):
                if previous_provider is not None:
                    _log.warning(
                        "translation.fallback",
                        from_provider=previous_provider,
                        to_provider=name,
                    )
                return TranslationProviderResult(provider=name, text=candidate)

            _log.warning("translation.candidate_rejected", provider=name, out_chars=len(candidate))
            previous_provider = name

        _log.warning("translation.all_failed", fallback="google", segment=segment.id)
        return None

    def _fallback_one(self, segment: Segment, config: PipelineConfig) -> Segment:
        """Перевести один сегмент через Google Translate и отметить fallback."""

        result = self.fallback.translate([segment], config)
        translated = result[0] if result else _apply_translation(segment, segment.source_text, "google")
        _add_qa_flag(translated, "translation_google_fallback")
        return translated

    def _cooldown_remaining(self, provider_name: str) -> float:
        """Вернуть остаток cooldown для провайдера в секундах."""

        until = self._cooldown_until.get(provider_name, 0.0)
        return max(0.0, until - self._now())

    def _respect_rate_limit(self, provider_name: str) -> None:
        """Выдержать минимальную паузу между запросами к провайдеру."""

        rpm = self.rate_limits_rpm.get(provider_name, 0.0)
        if rpm <= 0:
            return
        interval = 60.0 / rpm
        now = self._now()
        allowed_at = self._next_allowed_at.get(provider_name, now)
        if allowed_at > now:
            wait_s = allowed_at - now
            _log.info(
                "translation.rate_limit_wait",
                provider=provider_name,
                wait_s=round(wait_s, 3),
                rpm=rpm,
            )
            if self.wait_for_rate_limit:
                self._sleep(wait_s)
                now = self._now()
            else:
                raise TranslationProviderError(f"rate limit wait required: {wait_s:.3f}s")
        self._next_allowed_at[provider_name] = max(allowed_at, now) + interval


class GeminiTranslationProvider:
    """LLM-переводчик Gemini через официальный generateContent API."""

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-lite",
        timeout: float = 15.0,
        http_post=None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.http_post = http_post or _post_json

    @classmethod
    def from_env(cls, *, timeout: float | None = None) -> "GeminiTranslationProvider | None":
        """Создать Gemini-провайдер из окружения, если ключ доступен."""

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        model = os.getenv(
            "GEMINI_TRANSLATION_MODEL",
            os.getenv("GEMINI_REWRITE_MODEL", "gemini-2.5-flash-lite"),
        )
        return cls(api_key=api_key, model=model, timeout=timeout or 15.0)

    def translate_segment(
        self,
        segment: Segment,
        *,
        config: PipelineConfig,
        context_before: list[Segment],
        context_after: list[Segment],
    ) -> str:
        """Запросить перевод сегмента у Gemini."""

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{
                "parts": [{
                    "text": build_translation_prompt(
                        segment,
                        config=config,
                        context_before=context_before,
                        context_after=context_after,
                    )
                }]
            }],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 512},
        }
        data = self.http_post(url, payload, headers={}, timeout=self.timeout)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationProviderError("Gemini вернул неожиданный формат") from exc


class OpenAICompatibleTranslationProvider:
    """LLM-переводчик для OpenAI-compatible агрегаторов."""

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 15.0,
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
    ) -> "OpenAICompatibleTranslationProvider | None":
        """Создать OpenRouter-провайдер перевода из окружения."""

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return None
        return cls(
            name="openrouter",
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=os.getenv(
                "OPENROUTER_TRANSLATION_MODEL",
                os.getenv("OPENROUTER_REWRITE_MODEL", "openai/gpt-oss-20b:free"),
            ),
            timeout=timeout or 15.0,
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
    ) -> "OpenAICompatibleTranslationProvider | None":
        """Создать AIHubMix-провайдер перевода из окружения."""

        api_key = os.getenv("AIHUBMIX_API_KEY")
        if not api_key:
            return None
        return cls(
            name="aihubmix",
            api_key=api_key,
            base_url=os.getenv("AIHUBMIX_BASE_URL", "https://aihubmix.com/v1"),
            model=os.getenv("AIHUBMIX_TRANSLATION_MODEL", "gemini-3-flash-preview-free"),
            timeout=timeout or 15.0,
        )

    @classmethod
    def polza_from_env(
        cls,
        *,
        timeout: float | None = None,
    ) -> "OpenAICompatibleTranslationProvider | None":
        """Создать Polza.ai-провайдер перевода из окружения."""

        api_key = os.getenv("POLZA_API_KEY")
        if not api_key:
            return None
        return cls(
            name="polza",
            api_key=api_key,
            base_url=os.getenv("POLZA_BASE_URL", "https://api.polza.ai/api/v1"),
            model=os.getenv(
                "POLZA_TRANSLATION_MODEL",
                os.getenv("POLZA_REWRITE_MODEL", "google/gemini-2.5-flash-lite-preview-09-2025"),
            ),
            timeout=timeout or 15.0,
        )

    def translate_segment(
        self,
        segment: Segment,
        *,
        config: PipelineConfig,
        context_before: list[Segment],
        context_after: list[Segment],
    ) -> str:
        """Запросить перевод сегмента у OpenAI-compatible API."""

        headers = {"Authorization": f"Bearer {self.api_key}", **self.extra_headers}
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": build_translation_prompt(
                        segment,
                        config=config,
                        context_before=context_before,
                        context_after=context_after,
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 768,
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
            raise TranslationProviderError(f"{self.name} вернул неожиданный формат") from exc


def build_translation_prompt(
    segment: Segment,
    *,
    config: PipelineConfig,
    context_before: list[Segment] | None = None,
    context_after: list[Segment] | None = None,
) -> str:
    """Сформировать промпт для перевода одного сегмента с контекстом."""

    target_language = language_label(config.target_language)
    context = build_context_block(
        before=context_before,
        current=segment,
        after=context_after,
        include_translations=False,
    )
    return (
        f"Ты профессиональный переводчик и редактор видео-дубляжа.\n"
        f"Переведи ТОЛЬКО текущий сегмент на {target_language}.\n\n"
        f"ТРЕБОВАНИЯ ПРОЕКТА:\n{build_project_directives(config)}\n\n"
        f"ГЛОССАРИЙ И ТЕРМИНЫ:\n{build_glossary_block(config)}\n\n"
        f"КОНТЕКСТ СЦЕНЫ:\n{context}\n\n"
        f"ПРАВИЛА:\n"
        f"- Переводи только текущий сегмент, соседние сегменты нужны только для контекста.\n"
        f"- Сохраняй смысл, причинно-следственные связи, имена, факты и тон.\n"
        f"- Не добавляй объяснения, markdown, кавычки, варианты перевода или комментарии.\n"
        f"- Не объединяй текущий сегмент с соседними и не переносись на другую реплику.\n"
        f"- Если термин есть в глоссарии или списке do-not-translate, используй его строго.\n\n"
        f"ТЕКУЩИЙ СЕГМЕНТ ДЛЯ ПЕРЕВОДА:\n{segment.source_text.strip()}\n\n"
        f"ОТВЕТ:"
    )


def _apply_translation(segment: Segment, translated_text: str, provider: str) -> Segment:
    """Создать новый сегмент с переводом и QA-флагами провайдера."""

    qa_flags = list(segment.qa_flags)
    translated = translated_text.strip()
    if not translated:
        qa_flags.append("translation_empty")
    elif segment.source_text.strip() and translated == segment.source_text.strip():
        qa_flags.append("translation_fallback_source")
    qa_flags.extend(["translation_llm", "translation_provider_used", f"translation_provider_{provider}"])
    return Segment(
        id=segment.id,
        start=segment.start,
        end=segment.end,
        source_text=segment.source_text,
        translated_text=translated,
        speaker_id=segment.speaker_id,
        confidence=segment.confidence,
        qa_flags=list(dict.fromkeys(qa_flags)),
    )


def _add_qa_flag(segment: Segment, flag: str) -> None:
    """Добавить QA-флаг без дублей."""

    if flag not in segment.qa_flags:
        segment.qa_flags.append(flag)


def _clean_candidate(candidate: str) -> str:
    """Очистить ответ модели от служебных обёрток."""

    import re

    candidate = re.sub(r"<think>.*?</think>", "", candidate or "", flags=re.DOTALL)
    return candidate.strip().strip('"«»').strip()


def _is_useful_translation(candidate: str) -> bool:
    """Проверить, можно ли принять перевод модели."""

    return bool(candidate and candidate.strip())


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    """Выполнить JSON POST для cloud translation API."""

    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    proxy_url = os.getenv("TRANSLATION_PROXY") or os.getenv("REWRITER_PROXY")
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
        raise TranslationProviderError(f"HTTP {exc.code}: translation provider rejected request") from exc
    except TimeoutError as exc:
        raise TranslationProviderError("timeout: translation provider did not respond in time") from exc
    except urllib.error.URLError as exc:
        raise TranslationProviderError(f"network: {exc.reason}") from exc
    except OSError as exc:
        raise TranslationProviderError(f"os: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TranslationProviderError("translation provider returned invalid JSON") from exc


def _env_float(name: str, default: float) -> float:
    """Прочитать float из окружения, не падая на ошибочных значениях."""

    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    """Прочитать bool из окружения с привычными значениями yes/no."""

    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "да"}


def _is_quota_or_overload(reason: str) -> bool:
    """Определить ошибки, после которых провайдера лучше отправить в cooldown."""

    normalized = reason.lower()
    return any(marker in normalized for marker in ("429", "503", "quota", "rate", "timeout"))
