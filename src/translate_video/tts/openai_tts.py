"""OpenAI-совместимый TTS провайдер (NeuroAPI / Polza).

Поддерживает два формата ответа:
  - binary mp3 (NeuroAPI, прямой OpenAI)
  - JSON {"audio": "<base64_mp3>"} (Polza)

Модели через Polza:
  openai/gpt-4o-mini-tts   — быстрый, живой
  openai/tts-1-hd          — классический HD
  elevenlabs/text-to-speech-turbo-2-5      — эмоциональный (~30с)
  elevenlabs/text-to-speech-multilingual-v2 — многоязычный
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from translate_video.core.log import Timer, get_logger
from translate_video.core.schemas import Segment

_log = get_logger(__name__)

# ── OpenAI голоса ─────────────────────────────────────────────────────────────
TTS_VOICES: list[dict] = [
    {"id": "alloy",   "name": "Alloy",   "gender": "neutral", "tone": "Нейтральный, сбалансированный"},
    {"id": "echo",    "name": "Echo",    "gender": "male",    "tone": "Чёткий, уверенный"},
    {"id": "fable",   "name": "Fable",   "gender": "male",    "tone": "Выразительный, артистичный"},
    {"id": "onyx",    "name": "Onyx",    "gender": "male",    "tone": "Глубокий, авторитетный"},
    {"id": "nova",    "name": "Nova",    "gender": "female",  "tone": "Живой, дружелюбный"},
    {"id": "shimmer", "name": "Shimmer", "gender": "female",  "tone": "Мягкий, тёплый"},
]

# ── ElevenLabs голоса (21 голос, актуальный список из Polza API) ─────────────
ELEVENLABS_VOICES: list[dict] = [
    {"id": "Rachel",   "name": "Rachel",   "gender": "female",  "tone": "Спокойный, профессиональный"},
    {"id": "Aria",     "name": "Aria",     "gender": "female",  "tone": "Выразительный, живой"},
    {"id": "Roger",    "name": "Roger",    "gender": "male",    "tone": "Уверенный, авторитетный"},
    {"id": "Sarah",    "name": "Sarah",    "gender": "female",  "tone": "Мягкий, дружелюбный"},
    {"id": "Laura",    "name": "Laura",    "gender": "female",  "tone": "Чёткий, информационный"},
    {"id": "Charlie",  "name": "Charlie",  "gender": "male",    "tone": "Разговорный, непринуждённый"},
    {"id": "George",   "name": "George",   "gender": "male",    "tone": "Зрелый, солидный"},
    {"id": "Callum",   "name": "Callum",   "gender": "male",    "tone": "Молодой, динамичный"},
    {"id": "River",    "name": "River",    "gender": "neutral", "tone": "Нейтральный, спокойный"},
    {"id": "Liam",     "name": "Liam",     "gender": "male",    "tone": "Живой, энергичный"},
    {"id": "Charlotte","name": "Charlotte","gender": "female",  "tone": "Тёплый, эмоциональный"},
    {"id": "Alice",    "name": "Alice",    "gender": "female",  "tone": "Чёткий, профессиональный"},
    {"id": "Matilda",  "name": "Matilda",  "gender": "female",  "tone": "Мягкий, дружелюбный"},
    {"id": "Will",     "name": "Will",     "gender": "male",    "tone": "Непринуждённый, разговорный"},
    {"id": "Jessica",  "name": "Jessica",  "gender": "female",  "tone": "Живой, выразительный"},
    {"id": "Eric",     "name": "Eric",     "gender": "male",    "tone": "Глубокий, авторитетный"},
    {"id": "Chris",    "name": "Chris",    "gender": "male",    "tone": "Разговорный, естественный"},
    {"id": "Brian",    "name": "Brian",    "gender": "male",    "tone": "Уверенный, профессиональный"},
    {"id": "Daniel",   "name": "Daniel",   "gender": "male",    "tone": "Чёткий, дикторский"},
    {"id": "Lily",     "name": "Lily",     "gender": "female",  "tone": "Молодой, яркий"},
    {"id": "Bill",     "name": "Bill",     "gender": "male",    "tone": "Зрелый, спокойный"},
]

# ── Модели с их голосами ──────────────────────────────────────────────────────
POLZA_TTS_MODELS: list[dict] = [
    {
        "id": "openai/gpt-4o-mini-tts",
        "name": "GPT-4o Mini TTS (быстрый)",
        "provider": "openai",
        "voices": TTS_VOICES,
        "timeout": 60.0,
    },
    {
        "id": "openai/tts-1-hd",
        "name": "OpenAI TTS-1 HD",
        "provider": "openai",
        "voices": TTS_VOICES,
        "timeout": 60.0,
    },
    {
        "id": "openai/tts-1",
        "name": "OpenAI TTS-1",
        "provider": "openai",
        "voices": TTS_VOICES,
        "timeout": 60.0,
    },
    {
        "id": "elevenlabs/text-to-speech-turbo-2-5",
        "name": "ElevenLabs Turbo 2.5 (эмоциональный)",
        "provider": "elevenlabs",
        "voices": ELEVENLABS_VOICES,
        "timeout": 120.0,
    },
    {
        "id": "elevenlabs/text-to-speech-multilingual-v2",
        "name": "ElevenLabs Multilingual v2",
        "provider": "elevenlabs",
        "voices": ELEVENLABS_VOICES,
        "timeout": 120.0,
    },
]

# Пул голосов для per_speaker (OpenAI)
_VOICE_POOL = [v["id"] for v in TTS_VOICES]
_ELEVEN_VOICE_POOL = [v["id"] for v in ELEVENLABS_VOICES]


def voices_for_model(model_id: str) -> list[dict]:
    """Вернуть список голосов для указанной модели."""
    for m in POLZA_TTS_MODELS:
        if m["id"] == model_id:
            return m["voices"]
    return TTS_VOICES  # fallback OpenAI


def timeout_for_model(model_id: str) -> float:
    """Вернуть рекомендуемый timeout (сек) для модели."""
    for m in POLZA_TTS_MODELS:
        if m["id"] == model_id:
            return m["timeout"]
    return 60.0


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
        # OpenAI: скорость речи (0.25–4.0)
        openai_speed: float = 1.0,
        # ElevenLabs-специфичные параметры
        el_stability: float = 0.5,
        el_similarity_boost: float = 0.75,
        el_style: float = 0.0,
        el_speed: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.voice_1 = voice_1
        self.voice_2 = voice_2
        self.timeout = timeout or timeout_for_model(model)
        self._http_post = http_post or _post_audio
        # Выбираем пул голосов в зависимости от движка модели
        self.is_elevenlabs = model.startswith("elevenlabs/")
        self._voice_pool = _ELEVEN_VOICE_POOL if self.is_elevenlabs else _VOICE_POOL
        # OpenAI: speed 0.25–4.0 (default 1.0)
        self.openai_speed = max(0.25, min(4.0, openai_speed))
        # ElevenLabs параметры
        self.el_stability = max(0.0, min(1.0, el_stability))
        self.el_similarity_boost = max(0.0, min(1.0, el_similarity_boost))
        self.el_style = max(0.0, min(1.0, el_style))
        self.el_speed = max(0.7, min(1.2, el_speed))

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
            #    OpenAI не поддерживает SSML/Яндекс-разметку → стриппим всё
            # 2. translated_text — стандартный переведённый текст
            ssml_override = (segment.tts_ssml_override or "").strip()
            if ssml_override:
                text = _strip_tts_markup(ssml_override)
                if not text:
                    text = _strip_tts_markup(segment.translated_text)
            else:
                text = _strip_tts_markup(segment.translated_text)

            if not text:
                continue

            voice = self._pick_voice(
                index=index,
                speaker_id=segment.speaker_id,
                voice_strategy=voice_strategy,
                speaker_voice_map=speaker_voice_map,
            )

            output = output_dir / f"{segment.id or index}.wav"  # WAV — MoviePy читает 24kHz MP3 неверно
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

            segment.tts_path = output.relative_to(project.work_dir).as_posix()  # .wav
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
                pool_idx = len(speaker_voice_map) % len(self._voice_pool)
                speaker_voice_map[key] = self._voice_pool[pool_idx]
            return speaker_voice_map[key]

        return self.voice_1  # fallback

    def _synth(self, text: str, voice: str, output: Path) -> None:
        """Вызвать /audio/speech и сохранить mp3."""
        payload: dict = {
            "model": self.model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }
        # ElevenLabs-специфичные параметры (только для elevenlabs/* моделей)
        if self.is_elevenlabs:
            payload["speed"] = self.el_speed
            payload["stability"] = self.el_stability
            payload["similarity_boost"] = self.el_similarity_boost
            payload["style"] = self.el_style
        else:
            # OpenAI /audio/speech поддерживает speed=0.25..4.0
            # speed != 1.0 — передаём явно
            if abs(self.openai_speed - 1.0) > 0.01:
                payload["speed"] = self.openai_speed
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
        # MoviePy (AudioFileClip) некорректно читает 24kHz MP3 от OpenAI TTS:
        # определяет fps=44100 вместо 24000 → аудио воспроизводится в 1.84× ускорении → кряк.
        # Решение: конвертируем через ffmpeg в WAV 44100Hz до сохранения.
        # Выходной файл сохраняется с расширением .wav (меняем .mp3 на .wav).
        wav_output = output.with_suffix(".wav")
        _mp3_to_wav(audio_bytes, wav_output)


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

    model = getattr(config, "professional_tts_model", "tts-1")
    return OpenAITTSProvider(
        base_url=_base_url(meta),
        api_key=api_key,
        model=model,
        voice_1=getattr(config, "professional_tts_voice", "nova"),
        voice_2=getattr(config, "professional_tts_voice_2", "onyx"),
        timeout=timeout_for_model(model),
        openai_speed=getattr(config, "professional_tts_speed", 1.0),
        el_stability=getattr(config, "el_stability", 0.5),
        el_similarity_boost=getattr(config, "el_similarity_boost", 0.75),
        el_style=getattr(config, "el_style", 0.0),
        el_speed=getattr(config, "el_speed", 1.0),
    )


def _mp3_to_wav(mp3_bytes: bytes, wav_path: Path) -> None:
    """Конвертировать MP3-байты в WAV 44100Hz через ffmpeg.

    MoviePy v1.x некорректно определяет sample rate 24kHz MP3 от OpenAI TTS —
    читает как 44100Hz → аудио воспроизводится в 1.84× ускорении (кряк).
    WAV с явным sample_rate=44100 решает эту проблему раз и навсегда.
    """
    import subprocess  # noqa: PLC0415
    import tempfile    # noqa: PLC0415
    import os          # noqa: PLC0415

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3_bytes)
        tmp_mp3 = f.name
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", tmp_mp3,
                "-ar", "44100",   # resample → стандарт MoviePy
                "-ac", "1",        # моно — TTS не нуждается в стерео
                "-f", "wav",
                str(wav_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg конвертация mp3→wav не удалась: {exc}") from exc
    finally:
        if os.path.exists(tmp_mp3):
            os.unlink(tmp_mp3)


def _strip_tts_markup(text: str) -> str:
    """Очистить текст от разметки Яндекс TTS и SSML перед отправкой в OpenAI/ElevenLabs.

    OpenAI и ElevenLabs не понимают:
    - **слово** — логическое ударение (Яндекс TTS API v3)
    - +гласная — ударение на гласную (Яндекс TTS)
    - sil<[200ms]> — пауза (Яндекс TTS)
    - [[phonemes]] — фонемы (Яндекс TTS)
    - <speak>...</speak>, <break/> и другие SSML-теги

    Эти символы либо произносятся буквально (звёздочки, плюс),
    либо заставляют OpenAI TTS генерировать артефакты/кряки.
    """
    import re as _re

    # 1. Убрать Яндекс sil<[ms]> паузы (должно быть до общего <...>)
    text = _re.sub(r"\bsil\s*<\[[^\]]*\]>", "", text)      # sil<[200ms]>

    # 2. Убрать SSML-теги
    text = _re.sub(r"<[^>]+>", "", text)                    # <speak>, <break/>

    # 3. Убрать Яндекс [[phonemes]]
    text = _re.sub(r"\[\[[^\]]*\]\]", "", text)

    # 4. Убрать Яндекс логическое ударение **слово** → слово
    text = _re.sub(r"\*\*([^*]+)\*\*", r"\1", text)

    # 5. Убрать ударение на гласную (+а → а)
    text = text.replace("+", "")

    # 6. Схлопнуть пробелы
    text = _re.sub(r" {2,}", " ", text)

    return text.strip()


def _add_qa_flag(segment: Segment, flag: str) -> None:
    """Добавить QA-флаг сегменту без дублей."""
    if flag not in segment.qa_flags:
        segment.qa_flags.append(flag)


def _post_audio(
    url: str,
    payload: dict,
    *,
    headers: dict,
    timeout: float,
) -> bytes:
    """POST /audio/speech → bytes (mp3).

    Обрабатывает два формата ответа:
    - binary mp3 (NeuroAPI, прямой OpenAI)
    - JSON {"audio": "<base64_mp3>"} (Polza)
    """
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"TTS API вернул HTTP {exc.code}: {exc.read()[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"TTS сетевая ошибка: {exc.reason}") from exc
    except OSError as exc:
        raise RuntimeError(f"TTS ошибка запроса: {exc}") from exc

    # Определяем формат: JSON или бинарный
    if raw[:1] == b"{":
        try:
            obj = json.loads(raw)
            b64 = obj.get("audio") or obj.get("data") or ""
            if b64:
                return base64.b64decode(b64 + "==")
            raise RuntimeError(f"Polza вернул JSON без поля audio: {list(obj.keys())}")
        except (json.JSONDecodeError, Exception) as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(f"Не удалось разобрать JSON-ответ TTS: {exc}") from exc

    return raw  # бинарный mp3


# Обратная совместимость
_post_binary = _post_audio
