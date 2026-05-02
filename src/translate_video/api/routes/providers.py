"""API для внешних AI-провайдеров: модели и баланс."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from translate_video.core.provider_catalog import (
    get_provider_balance,
    list_provider_models,
    supported_model_providers,
)

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


@router.get("")
def list_providers():
    """Вернуть список провайдеров, поддерживающих загрузку моделей."""

    return {"providers": supported_model_providers()}


@router.get("/{provider}/models")
def provider_models(provider: str):
    """Вернуть актуальные модели провайдера через его API."""

    try:
        models = list_provider_models(provider)
        return {"provider": provider, "models": [model.to_dict() for model in models]}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{provider}/balance")
def provider_balance(provider: str):
    """Вернуть баланс/расход провайдера, если такой endpoint поддержан."""

    try:
        return get_provider_balance(provider).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
