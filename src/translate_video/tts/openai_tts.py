"""OpenAI-совместимый TTS провайдер (NeuroAPI / Polza).

Реализует профессиональную озвучку через `POST /audio/speech`.
Поддерживает multi-voice: single / two_voices / per_speaker.

API Reference (OpenAI-compatible):
    POST /audio/speech
    {
        "model": "tts-1",     # или tts-1-hd, gpt-4o-mini-tts
        "input": "текст",
        "voice": "nova",      # alloy|echo|fable|onyx|nova|shimmer
        "response_format": "mp3"
    }
    → binary mp3
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from translate_video.core.log import Timer, get_logger
from translate_video.core.schemas import Segment

_log = get_logger(__name__)

# Доступные голоса (OpenAI-совместимые, работают для любого языка)
TTS_VOICES: list[dict] = [
    {"id": "alloy",   "name": "Alloy",   "gender": "neutral", "tone": "Нейтральный, сбалансированный"},
    {"id": "echo",    "name": "Echo",    "gender": "male",    "tone": "Чёткий, уверенный"},
    {"id": "fable",   "name": "Fable",   "gender": "male",    "tone": "Выразительный, артистичный"},
    {"id": "onyx",    "name": "Onyx",    "gender": "male",    "tone": "Глубокий, авторитетный"},
    {"id": "nova",    "name": "Nova",    "gender": "female",  "tone": "Живой, дружелюбный"},
    {"id": "shimmer", "name": "Shimmer", "gender": "female",  "tone": "Мягкий, тёплый"},
]

# Пул голосов для per_speaker: round-robin по всем 6
_VOICE_POOL = [v["id"] for v in TTS_VOICES]


class OpenAITTSProvider:
    """Профессиональный TTS через OpenAI-совместимый /audio/speech.

    Поддерживает:
    - ``single``      → все сегменты voice_1
    - ``two_voices``  → чётные voice_1, нечётные voice_2
    - ``per_speaker`` → каждый speaker_id получает голос из пула (round-robin)
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        voice_1: str,
        voice_2: str,
        timeout: float = 60.0,
        http_post=None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.voice_1 = voice_1
        self.voice_2 = voice_2
        self.timeout = timeout
        self._http_post = http_post or _post_binary

    def synthesize(self, project, segments: list[Segment]) -> list[Segment]:
        """Синтезировать каждый переведённый сегмент через /audio/speech."""
        cfg = project.config
        voice_strategy = getattr(cfg, "voice_strategy", "single")

        # Карта speaker_id → голос для per_speaker
        speaker_voice_map: dict[str, str] = {}

        output_dir: Path = project.work_dir / "tts"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Сбрасываем TTS-специфичные QA-флаги от предыдущего запуска
        for seg in segments:
            seg.qa_flags = [f for f in seg.qa_flags if not f.startswith("tts_")]

        for index, segment in enumerate(segments):
            # Приоритет источника текста:
            # 1. tts_ssml_override — пользовательский текст из SSML-редактора
            #    OpenAI не поддерживает SSML → стриппим теги, оставляем plain text
            # 2. translated_text — стандартный переведённый текст
            ssml_override = (segment.tts_ssml_override or "").strip()
            if ssml_override:
                import re as _re
                text = _re.sub(r"<[^>]+>", "", ssml_override).strip()
                # Убираем SSML-ударения (+), оставляем только текст
                text = text.replace("+", "")
                if not text:
                    text = segment.translated_text.strip()
            else:
                text = segment.translated_text.strip()

            if not text:
                continue

            voice = self._pick_voice(
                index=index,
                speaker_id=segment.speaker_id,
                voice_strategy=voice_strategy,
                speaker_voice_map=speaker_voice_map,
            )

            output = output_dir / f"{segment.id or index}.mp3"
            segment.tts_text = text

            with Timer() as t:
                try:
                    self._synth(text, voice, output)
                except Exception as exc:  # noqa: BLE001
                    _log.error(
                        "tts.openai.error",
                        idx=index,
                        seg_id=segment.id,
                        voice=voice,
                        error=str(exc),
                    )
                    _add_qa_flag(segment, "tts_openai_error")
                    continue

            segment.tts_path = output.relative_to(project.work_dir).as_posix()
            segment.voice = voice
            _add_qa_flag(segment, f"tts_voice_{voice}")

            _log.debug(
                "tts.openai.segment",
                idx=index,
                seg_id=segment.id,
                voice=voice,
                model=self.model,
                text_len=len(text),
                elapsed_s=round(t.elapsed, 2),
            )

        return segments

    def _pick_voice(
        self,
        *,
        index: int,
        speaker_id: str | None,
        voice_strategy: str,
        speaker_voice_map: dict[str, str],
    ) -> str:
        """Выбрать голос по стратегии."""
        if voice_strategy == "single":
            return self.voice_1

        if voice_strategy == "two_voices":
            return self.voice_1 if index % 2 == 0 else self.voice_2

        if voice_strategy == "per_speaker":
            key = speaker_id or str(index)
            if key not in speaker_voice_map:
                # Назначаем следующий голос из пула по round-robin
                pool_idx = len(speaker_voice_map) % len(_VOICE_POOL)
                speaker_voice_map[key] = _VOICE_POOL[pool_idx]
            return speaker_voice_map[key]

        return self.voice_1  # fallback

    def _synth(self, text: str, voice: str, output: Path) -> None:
        """Вызвать /audio/speech и сохранить mp3."""
        payload = {
            "model": self.model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        audio_bytes = self._http_post(
            f"{self.base_url}/audio/speech",
            payload,
            headers=headers,
            timeout=self.timeout,
        )
        output.write_bytes(audio_bytes)


def build_openai_tts_provider(config) -> OpenAITTSProvider | None:
    """Создать OpenAITTSProvider из PipelineConfig.

    Возвращает None если professional_tts_provider не задан или ключ API не найден.
    """
    from translate_video.core.env import load_env_file
    from translate_video.core.provider_catalog import _PROVIDERS, _base_url  # noqa: PLC2701

    provider_id = getattr(config, "professional_tts_provider", "").strip().lower()
    if not provider_id:
        return None

    load_env_file()
    try:
        meta = _PROVIDERS[provider_id]
    except KeyError:
        _log.warning("tts.openai.unknown_provider", provider=provider_id)
        return None

    api_key = os.getenv(meta["key_env"], "")
    if not api_key:
        _log.warning(
            "tts.openai.no_api_key",
            provider=provider_id,
            env_var=meta["key_env"],
        )
        return None

    return OpenAITTSProvider(
        base_url=_base_url(meta),
        api_key=api_key,
        model=getattr(config, "professional_tts_model", "tts-1"),
        voice_1=getattr(config, "professional_tts_voice", "nova"),
        voice_2=getattr(config, "professional_tts_voice_2", "onyx"),
    )


def _add_qa_flag(segment: Segment, flag: str) -> None:
    """Добавить QA-флаг сегменту без дублей."""
    if flag not in segment.qa_flags:
        segment.qa_flags.append(flag)


def _post_binary(
    url: str,
    payload: dict,
    *,
    headers: dict,
    timeout: float,
) -> bytes:
    """Выполнить POST и вернуть бинарный ответ (mp3)."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"TTS API вернул HTTP {exc.code}: {exc.read()[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"TTS сетевая ошибка: {exc.reason}") from exc
    except OSError as exc:
        raise RuntimeError(f"TTS ошибка запроса: {exc}") from exc
