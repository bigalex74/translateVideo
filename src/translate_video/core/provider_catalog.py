"""Каталог моделей и баланса внешних AI-провайдеров."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from translate_video.core.env import load_env_file


@dataclass(slots=True)
class ProviderModel:
    """Модель, доступная у внешнего провайдера."""

    id: str
    name: str

    def to_dict(self) -> dict[str, str]:
        """Вернуть JSON-представление модели для API."""

        return {"id": self.id, "name": self.name}


@dataclass(slots=True)
class ProviderBalance:
    """Сводка по деньгам/расходам провайдера."""

    provider: str
    configured: bool
    balance: float | None = None
    currency: str | None = None
    used: float | None = None
    source: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Вернуть JSON-представление баланса для UI."""

        return {
            "provider": self.provider,
            "configured": self.configured,
            "balance": self.balance,
            "currency": self.currency,
            "used": self.used,
            "source": self.source,
            "message": self.message,
        }


_PROVIDERS = {
    "openrouter": {
        "base_url_env": "OPENROUTER_BASE_URL",
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
    },
    "aihubmix": {
        "base_url_env": "AIHUBMIX_BASE_URL",
        "base_url": "https://aihubmix.com/v1",
        "key_env": "AIHUBMIX_API_KEY",
    },
    "polza": {
        "base_url_env": "POLZA_BASE_URL",
        "base_url": "https://api.polza.ai/api/v1",
        "key_env": "POLZA_API_KEY",
    },
    "neuroapi": {
        "base_url_env": "NEUROAPI_BASE_URL",
        "base_url": "https://neuroapi.host/v1",
        "key_env": "NEUROAPI_API_KEY",
    },
}


def list_provider_models(provider: str, *, timeout: float = 10.0) -> list[ProviderModel]:
    """Получить список моделей провайдера через OpenAI-compatible `/models`."""

    load_env_file()
    normalized = _normalize_provider(provider)
    meta = _provider_meta(normalized)
    api_key = os.getenv(meta["key_env"], "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    data = _get_json(f"{_base_url(meta)}/models", headers=headers, timeout=timeout)
    raw_models = data.get("data", data if isinstance(data, list) else [])
    models: list[ProviderModel] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or item.get("name") or "").strip()
        if not model_id:
            continue
        models.append(ProviderModel(id=model_id, name=str(item.get("name") or model_id)))
    return sorted(models, key=lambda model: model.id)


def get_provider_balance(provider: str, *, timeout: float = 10.0) -> ProviderBalance:
    """Получить баланс или расход провайдера, если endpoint известен."""

    load_env_file()
    normalized = _normalize_provider(provider)
    meta = _provider_meta(normalized)
    api_key = os.getenv(meta["key_env"], "")
    if not api_key:
        return ProviderBalance(
            provider=normalized,
            configured=False,
            message=f"Ключ {meta['key_env']} не задан.",
        )

    if normalized == "neuroapi":
        data = _get_json(
            f"{_base_url(meta)}/dashboard/billing/usage",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        total_usage_cents = data.get("total_usage")
        used = float(total_usage_cents) / 100 if total_usage_cents is not None else None
        return ProviderBalance(
            provider=normalized,
            configured=True,
            balance=None,
            currency="USD",
            used=used,
            source="dashboard/billing/usage",
            message="NeuroAPI отдаёт расход; endpoint остатка баланса в публичной документации не указан.",
        )

    if normalized == "openrouter":
        data = _get_json(
            f"{_base_url(meta)}/credits",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        payload = data.get("data", data)
        total = _optional_float(payload.get("total_credits"))
        used = _optional_float(payload.get("total_usage"))
        balance = total - used if total is not None and used is not None else None
        return ProviderBalance(
            provider=normalized,
            configured=True,
            balance=balance,
            currency="USD",
            used=used,
            source="credits",
        )

    return ProviderBalance(
        provider=normalized,
        configured=True,
        message="Endpoint баланса для этого провайдера пока не настроен.",
    )


def supported_model_providers() -> list[str]:
    """Вернуть провайдеры, для которых доступна загрузка моделей."""

    return sorted(_PROVIDERS)


def _provider_meta(provider: str) -> dict[str, str]:
    """Вернуть метаданные провайдера или упасть с понятной ошибкой."""

    try:
        return _PROVIDERS[provider]
    except KeyError as exc:
        raise ValueError(f"неподдерживаемый провайдер моделей: {provider}") from exc


def _normalize_provider(provider: str) -> str:
    """Нормализовать id провайдера из UI/API."""

    return provider.strip().lower()


def _base_url(meta: dict[str, str]) -> str:
    """Вернуть base URL провайдера без завершающего слеша."""

    return os.getenv(meta["base_url_env"], meta["base_url"]).rstrip("/")


def _get_json(url: str, *, headers: dict[str, str], timeout: float) -> Any:
    """Выполнить GET и распарсить JSON-ответ."""

    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ValueError(f"провайдер вернул HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"ошибка сети провайдера: {exc.reason}") from exc
    except OSError as exc:
        raise ValueError(f"ошибка запроса к провайдеру: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("провайдер вернул невалидный JSON") from exc


def _optional_float(value: Any) -> float | None:
    """Безопасно привести значение к float."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
