"""Облачный fallback-роутер для сокращения перевода под тайминг.

Роутер идёт от бесплатных/условно бесплатных провайдеров к платным:
Gemini → AIHubMix → OpenRouter → Polza → rule_based.
Реальные ключи читаются только из окружения и не должны попадать в репозиторий.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from translate_video.core.config import PipelineConfig
from translate_video.core.env import load_env_file
from translate_video.core.log import Timer, get_logger
from translate_video.core.prompting import (
    build_context_block,
    build_glossary_block,
    build_project_directives,
    language_label,
)
from translate_video.core.schemas import Segment
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
        rate_limits_rpm: dict[str, float] | None = None,
        cooldown_seconds: float = 75.0,
        wait_for_rate_limit: bool = True,
        allow_rule_based_fallback: bool = True,
        now_fn=None,
        sleep_fn=None,
    ) -> None:
        self.providers = providers
        self.fallback = fallback or RuleBasedTimingRewriter()
        self.disable_on_quota = disable_on_quota
        self.rate_limits_rpm = rate_limits_rpm or {}
        self.cooldown_seconds = cooldown_seconds
        self.wait_for_rate_limit = wait_for_rate_limit
        self.allow_rule_based_fallback = allow_rule_based_fallback
        self._now = now_fn or time.monotonic
        self._sleep = sleep_fn or time.sleep
        self._events: list[str] = []
        self._cooldown_until: dict[str, float] = {}
        self._next_allowed_at: dict[str, float] = {}

    @classmethod
    def from_config(cls, config: PipelineConfig) -> "CloudFallbackTimingRewriter":
        """Собрать роутер из конфигурации и переменных окружения."""

        load_env_file()
        timeout = _env_float("REWRITE_PROVIDER_TIMEOUT", config.rewrite_provider_timeout)
        allow_paid = _env_bool(
            "REWRITE_ALLOW_PAID_FALLBACK",
            config.rewrite_allow_paid_fallback,
        )
        factories = {
            "gemini": GeminiRewriteProvider.from_env,
            "openrouter": OpenAICompatibleRewriteProvider.openrouter_from_env,
            "aihubmix": OpenAICompatibleRewriteProvider.aihubmix_from_env,
            "polza": OpenAICompatibleRewriteProvider.polza_from_env,
            "neuroapi": OpenAICompatibleRewriteProvider.neuroapi_from_env,
        }
        providers: list[TimingRewriter] = []
        if config.translation_quality == "professional":
            provider = _build_professional_rewriter(
                config.professional_rewrite_provider,
                config.professional_rewrite_model,
                factories=factories,
                timeout=timeout,
            )
            if provider is not None:
                providers.append(provider)
        else:
            for raw_name in config.rewrite_provider_order:
                name = raw_name.strip().lower()
                factory = factories.get(name)
                if factory is None:
                    continue
                if name in {"polza", "neuroapi"} and not allow_paid:
                    _log.info("rewriter.paid_provider_skip", provider=name)
                    continue
                provider = factory(timeout=timeout)
                if provider is not None:
                    providers.append(provider)
        return cls(
            providers=providers,
            disable_on_quota=config.rewrite_provider_disable_on_quota,
            rate_limits_rpm=config.rewrite_provider_rpm,
            cooldown_seconds=config.rewrite_provider_cooldown_seconds,
            wait_for_rate_limit=config.rewrite_provider_wait_for_rate_limit,
            allow_rule_based_fallback=config.translation_quality != "professional",
        )

    def rewrite(
        self,
        text: str,
        *,
        source_text: str,
        max_chars: int,
        attempt: int,
        segment: Segment | None = None,
        context_before: list[Segment] | None = None,
        context_after: list[Segment] | None = None,
        config: PipelineConfig | None = None,
    ) -> str:
        """Вернуть лучший короткий вариант, используя fallback-цепочку."""

        self._events = []
        prev_provider: str | None = None

        for provider in self.providers:
            name = getattr(provider, "name", provider.__class__.__name__)
            cooldown_remaining = self._cooldown_remaining(name)
            if cooldown_remaining > 0:
                self._events.extend([
                    "rewrite_provider_cooldown",
                    "rewrite_provider_skipped",
                    "rewrite_fallback_used",
                ])
                _log.warning(
                    "rewriter.provider_skip",
                    provider=name,
                    reason="cooldown_after_quota_or_timeout",
                    wait_s=round(cooldown_remaining, 3),
                )
                prev_provider = name
                continue
            try:
                self._respect_rate_limit(name)
                _log.debug(
                    "rewriter.request",
                    provider=name,
                    max_chars=max_chars,
                    attempt=attempt,
                    in_chars=len(text),
                )
                with Timer() as t:
                    candidate = _clean_candidate(_call_rewriter(
                        provider,
                        text,
                        source_text=source_text,
                        max_chars=max_chars,
                        attempt=attempt,
                        segment=segment,
                        context_before=context_before,
                        context_after=context_after,
                        config=config,
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
                    self._cooldown_until[name] = self._now() + self.cooldown_seconds
                    self._events.append("rewrite_provider_quota_limited")
                    _log.warning(
                        "rewriter.provider_cooldown",
                        provider=name,
                        reason=reason,
                        cooldown_s=self.cooldown_seconds,
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
        if not self.allow_rule_based_fallback:
            raise RewriteProviderError("профессиональный rewriter не вернул полезный результат")
        candidate = _call_rewriter(
            self.fallback,
            text,
            source_text=source_text,
            max_chars=max_chars,
            attempt=attempt,
            segment=segment,
            context_before=context_before,
            context_after=context_after,
            config=config,
        )
        if candidate != text:
            self._events.append("rewrite_provider_rule_based")
        return candidate

    def consume_events(self) -> list[str]:
        """Вернуть и очистить события последней rewrite-попытки."""

        events = list(dict.fromkeys(self._events))
        self._events = []
        return events

    def _cooldown_remaining(self, provider_name: str) -> float:
        """Вернуть остаток cooldown для провайдера в секундах."""

        until = self._cooldown_until.get(provider_name, 0.0)
        return max(0.0, until - self._now())

    def _respect_rate_limit(self, provider_name: str) -> None:
        """Выдержать минимальную паузу между запросами к бесплатной модели."""

        rpm = self.rate_limits_rpm.get(provider_name, 0.0)
        if rpm <= 0:
            return
        interval = 60.0 / rpm
        now = self._now()
        allowed_at = self._next_allowed_at.get(provider_name, now)
        if allowed_at > now:
            wait_s = allowed_at - now
            self._events.append("rewrite_provider_rate_limited")
            _log.info(
                "rewriter.rate_limit_wait",
                provider=provider_name,
                wait_s=round(wait_s, 3),
                rpm=rpm,
            )
            if self.wait_for_rate_limit:
                self._sleep(wait_s)
                now = self._now()
            else:
                raise RewriteProviderError(f"rate limit wait required: {wait_s:.3f}s")
        self._next_allowed_at[provider_name] = max(allowed_at, now) + interval


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
        model: str | None = None,
    ) -> "GeminiRewriteProvider | OpenAICompatibleRewriteProvider | None":
        """Создать провайдер Gemini из окружения.

        Если задан GEMINI_BRIDGE_URL — использует OpenAI-совместимый мост
        (например http://127.0.0.1:5000/v1). Мост авторизуется самостоятельно,
        GEMINI_API_KEY не нужен.

        Иначе — нативный Gemini generateContent API с GEMINI_API_KEY.
        """

        selected_model = model or os.getenv("GEMINI_REWRITE_MODEL", "gemini-3-flash-preview")
        bridge_url = os.getenv("GEMINI_BRIDGE_URL")

        if bridge_url:
            # OpenAI-совместимый мост (127.0.0.1:5000 и др.)
            return OpenAICompatibleRewriteProvider(
                name="gemini",
                api_key=os.getenv("GEMINI_API_KEY", "bridge"),  # мост авторизуется сам
                base_url=bridge_url.rstrip("/"),
                model=selected_model,
                timeout=timeout or _env_float("GEMINI_REWRITE_TIMEOUT", 8.0),
            )

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            model=selected_model,
            timeout=timeout or _env_float("GEMINI_REWRITE_TIMEOUT", 8.0),
        )

    def rewrite(
        self,
        text: str,
        *,
        source_text: str,
        max_chars: int,
        attempt: int,
        segment: Segment | None = None,
        context_before: list[Segment] | None = None,
        context_after: list[Segment] | None = None,
        config: PipelineConfig | None = None,
    ) -> str:
        """Запросить у Gemini короткую версию перевода."""

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{
                "parts": [{
                    "text": build_rewrite_prompt(
                        text,
                        source_text,
                        max_chars,
                        segment=segment,
                        context_before=context_before,
                        context_after=context_after,
                        config=config,
                    )
                }]
            }],
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
        model: str | None = None,
    ) -> "OpenAICompatibleRewriteProvider | None":
        """Создать OpenRouter-провайдер, если ключ есть в окружении."""

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return None
        return cls(
            name="openrouter",
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=model or os.getenv("OPENROUTER_REWRITE_MODEL", "openai/gpt-oss-20b:free"),
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
        model: str | None = None,
    ) -> "OpenAICompatibleRewriteProvider | None":
        """Создать AIHubMix-провайдер, если ключ есть в окружении."""

        api_key = os.getenv("AIHUBMIX_API_KEY")
        if not api_key:
            return None
        return cls(
            name="aihubmix",
            api_key=api_key,
            base_url=os.getenv("AIHUBMIX_BASE_URL", "https://aihubmix.com/v1"),
            model=model or os.getenv("AIHUBMIX_REWRITE_MODEL", "gpt-4.1-nano-free"),
            timeout=timeout or _env_float("AIHUBMIX_REWRITE_TIMEOUT", 8.0),
        )

    @classmethod
    def polza_from_env(
        cls,
        *,
        timeout: float | None = None,
        model: str | None = None,
    ) -> "OpenAICompatibleRewriteProvider | None":
        """Создать Polza.ai-провайдер, если ключ есть в окружении."""

        api_key = os.getenv("POLZA_API_KEY")
        if not api_key:
            return None
        return cls(
            name="polza",
            api_key=api_key,
            base_url=os.getenv("POLZA_BASE_URL", "https://api.polza.ai/api/v1"),
            model=model or os.getenv(
                "POLZA_REWRITE_MODEL",
                "google/gemini-2.5-flash-lite-preview-09-2025",
            ),
            timeout=timeout or _env_float("POLZA_REWRITE_TIMEOUT", 8.0),
        )

    @classmethod
    def neuroapi_from_env(
        cls,
        *,
        timeout: float | None = None,
        model: str | None = None,
    ) -> "OpenAICompatibleRewriteProvider | None":
        """Создать NeuroAPI-провайдер, если ключ есть в окружении."""

        api_key = os.getenv("NEUROAPI_API_KEY")
        if not api_key:
            return None
        return cls(
            name="neuroapi",
            api_key=api_key,
            base_url=os.getenv("NEUROAPI_BASE_URL", "https://neuroapi.host/v1"),
            model=model or os.getenv("NEUROAPI_REWRITE_MODEL", "gpt-5-mini"),
            timeout=timeout or _env_float("NEUROAPI_REWRITE_TIMEOUT", 8.0),
        )

    def rewrite(
        self,
        text: str,
        *,
        source_text: str,
        max_chars: int,
        attempt: int,
        segment: Segment | None = None,
        context_before: list[Segment] | None = None,
        context_after: list[Segment] | None = None,
        config: PipelineConfig | None = None,
    ) -> str:
        """Запросить короткую версию перевода у OpenAI-compatible API."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            **self.extra_headers,
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": build_rewrite_prompt(
                        text,
                        source_text,
                        max_chars,
                        segment=segment,
                        context_before=context_before,
                        context_after=context_after,
                        config=config,
                    ),
                },
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


def build_rewrite_prompt(
    text: str,
    source_text: str,
    max_chars: int,
    *,
    segment: Segment | None = None,
    context_before: list[Segment] | None = None,
    context_after: list[Segment] | None = None,
    config: PipelineConfig | None = None,
) -> str:
    """Сформировать промпт для сокращения текста под тайминг дубляжа."""

    # Целевой диапазон — использовать лимит по максимуму, не обрезать лишнего.
    target_min = max(1, int(max_chars * 0.75))
    source_language = language_label(config.source_language) if config else "исходный язык"
    target_language = language_label(config.target_language) if config else "целевой язык"
    current = segment or Segment(start=0.0, end=0.0, source_text=source_text, translated_text=text)
    context = build_context_block(
        before=context_before,
        current=current,
        after=context_after,
        include_translations=True,
    )
    directives = build_project_directives(config) if config else "Настройки проекта не переданы."
    glossary = build_glossary_block(config) if config else "Глоссарий не задан."
    return (
        f"Ты редактор дубляжа и адаптации текста под естественную озвучку.\n"
        f"Перепиши ТОЛЬКО текущий перевод на {target_language}, чтобы он помещался "
        f"в слот озвучки и не терял смысл оригинала на {source_language}.\n\n"
        f"ТРЕБОВАНИЯ ПРОЕКТА:\n{directives}\n\n"
        f"ГЛОССАРИЙ И ТЕРМИНЫ:\n{glossary}\n\n"
        f"КОНТЕКСТ СЦЕНЫ:\n{context}\n\n"
        f"ПРАВИЛА:\n"
        f"- Длина результата: от {target_min} до {max_chars} символов (стремись к максимуму).\n"
        f"- Сохраняй смысл, факты, имена, термины, метафоры, тон и стиль проекта.\n"
        f"- Используй глоссарий и список do-not-translate строго, без переименований.\n"
        f"- Соседние сегменты нужны только для контекста; не добавляй их смысл в текущую реплику.\n"
        f"- Сокращай длинные обороты, убирай вводные слова, перестраивай фразу естественно.\n"
        f"- НЕ обрезай текст на полуслове и НЕ выбрасывай ключевые идеи.\n"
        f"- Ответ — только готовая фраза, без кавычек, пояснений и комментариев.\n\n"
        f"ОРИГИНАЛ ТЕКУЩЕГО СЕГМЕНТА:\n{source_text}\n\n"
        f"ТЕКУЩИЙ ПЕРЕВОД ({len(text)} симв.):\n{text}\n\n"
        f"Перепиши (≤{max_chars} симв.):"
    )


def _build_professional_rewriter(
    provider_name: str,
    model: str,
    *,
    factories: dict[str, Any],
    timeout: float,
) -> TimingRewriter | None:
    """Собрать единственный профессиональный rewriter с выбранной моделью."""

    name = provider_name.strip().lower()
    factory = factories.get(name)
    if factory is None:
        _log.warning("rewriter.professional_provider_unknown", provider=name)
        return None
    provider = factory(timeout=timeout, model=model.strip() or None)
    if provider is None:
        _log.warning("rewriter.professional_provider_missing_key", provider=name)
    return provider


def _call_rewriter(
    provider: TimingRewriter,
    text: str,
    *,
    source_text: str,
    max_chars: int,
    attempt: int,
    segment: Segment | None,
    context_before: list[Segment] | None,
    context_after: list[Segment] | None,
    config: PipelineConfig | None,
) -> str:
    """Вызвать rewriter с контекстом, сохранив совместимость со старыми тестовыми классами."""

    try:
        return provider.rewrite(
            text,
            source_text=source_text,
            max_chars=max_chars,
            attempt=attempt,
            segment=segment,
            context_before=context_before,
            context_after=context_after,
            config=config,
        )
    except TypeError as exc:
        if "unexpected keyword" not in str(exc):
            raise
        return provider.rewrite(
            text,
            source_text=source_text,
            max_chars=max_chars,
            attempt=attempt,
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
