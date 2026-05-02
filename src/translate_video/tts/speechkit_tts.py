"""Yandex SpeechKit TTS v3 провайдер.

REST API:
    POST https://tts.api.cloud.yandex.net/tts/v3/utteranceSynthesis
    Authorization: Api-Key <key>
    Content-Type: application/json

    {
        "text": "Привет!",
        "hints": [
            {"voice": "alena"},
            {"role":  "good"},
            {"speed": 1.0}
        ],
        "outputAudioSpec": {
            "containerAudio": {"containerAudioType": "MP3"}
        },
        "unsafeMode": true
    }

Ответ — NDJSON-стрим:
    {"audioChunk": {"data": "<base64_mp3>"}, "textChunk": ..., "startMs": ..., "lengthMs": ...}
    {"audioChunk": {"data": "<base64_mp3>"}, ...}
    ...

Голоса (RU): alena, filipp, ermil, jane, omazh, zahar, madirus, amira, john
Роли:
    alena  → neutral, good
    filipp → neutral
    ermil  → neutral, good
    jane   → neutral, good, evil
    omazh  → neutral, evil
    zahar  → neutral, good
    прочие → neutral
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

from translate_video.core.log import Timer, get_logger
from translate_video.core.schemas import Segment

_log = get_logger(__name__)

SPEECHKIT_TTS_URL = "https://tts.api.cloud.yandex.net/tts/v3/utteranceSynthesis"

# Голоса SpeechKit для русского языка с метаданными
SPEECHKIT_VOICES: list[dict] = [
    {"id": "alena",   "name": "Алёна",   "gender": "female", "tone": "Тёплая, дружелюбная",   "roles": ["neutral", "good"]},
    {"id": "jane",    "name": "Джейн",   "gender": "female", "tone": "Эмоциональная, живая",   "roles": ["neutral", "good", "evil"]},
    {"id": "omazh",   "name": "Омаж",    "gender": "female", "tone": "Нейтральная, офисная",   "roles": ["neutral", "evil"]},
    {"id": "madirus", "name": "Мадирус", "gender": "male",   "tone": "Молодой, энергичный",    "roles": ["neutral"]},
    {"id": "zahar",   "name": "Захар",   "gender": "male",   "tone": "Авторитетный, солидный", "roles": ["neutral", "good"]},
    {"id": "ermil",   "name": "Ермил",   "gender": "male",   "tone": "Дикторский, чёткий",     "roles": ["neutral", "good"]},
    {"id": "filipp",  "name": "Филипп",  "gender": "male",   "tone": "Деловой, уверенный",     "roles": ["neutral"]},
    {"id": "amira",   "name": "Амира",   "gender": "female", "tone": "Мягкая, приятная",       "roles": ["neutral"]},
    {"id": "john",    "name": "Джон",    "gender": "male",   "tone": "Нейтральный, универсальный", "roles": ["neutral"]},
]

# Пул голосов для per_speaker (round-robin)
_VOICE_POOL = [v["id"] for v in SPEECHKIT_VOICES]


class YandexSpeechKitTTSProvider:
    """Профессиональный TTS через Yandex SpeechKit v3.

    Поддерживает:
    - ``single``      → все сегменты voice_1 + role_1
    - ``two_voices``  → чётные voice_1, нечётные voice_2
    - ``per_speaker`` → каждый speaker_id получает голос из пула (round-robin)

    Аутентификация: Api-Key (YANDEX_SPEECHKIT_API_KEY из .env).
    """

    def __init__(
        self,
        api_key: str,
        voice_1: str,
        voice_2: str,
        role_1: str = "neutral",
        role_2: str = "neutral",
        speed: float = 1.0,
        timeout: float = 60.0,
        http_post=None,
    ) -> None:
        self.api_key = api_key
        self.voice_1 = voice_1
        self.voice_2 = voice_2
        self.role_1 = role_1
        self.role_2 = role_2
        self.speed = speed
        self.timeout = timeout
        self._http_post = http_post or _post_streaming

    def synthesize(self, project, segments: list[Segment]) -> list[Segment]:
        """Синтезировать каждый переведённый сегмент через SpeechKit v3."""
        cfg = project.config
        voice_strategy = getattr(cfg, "voice_strategy", "single")
        output_dir = project.work_dir / "tts"
        output_dir.mkdir(parents=True, exist_ok=True)
        speaker_voice_map: dict[str, tuple[str, str]] = {}

        for index, segment in enumerate(segments):
            text = segment.translated_text.strip()
            if not text:
                continue

            voice, role = self._pick_voice_role(
                index=index,
                speaker_id=segment.speaker_id,
                voice_strategy=voice_strategy,
                speaker_voice_map=speaker_voice_map,
            )

            output = output_dir / f"{segment.id or index}.mp3"
            segment.tts_text = text

            with Timer() as t:
                try:
                    self._synth(text, voice, role, output)
                except Exception as exc:  # noqa: BLE001
                    _log.error(
                        "tts.speechkit.error",
                        idx=index,
                        seg_id=segment.id,
                        voice=voice,
                        error=str(exc),
                    )
                    _add_qa_flag(segment, "tts_speechkit_error")
                    continue

            segment.tts_path = output.relative_to(project.work_dir).as_posix()
            segment.voice = f"{voice}:{role}"
            _add_qa_flag(segment, f"tts_voice_{voice}")
            _add_qa_flag(segment, "tts_speechkit")

            _log.debug(
                "tts.speechkit.segment",
                idx=index,
                seg_id=segment.id,
                voice=voice,
                role=role,
                text_len=len(text),
                elapsed_s=round(t.elapsed, 2),
            )

        return segments

    def _pick_voice_role(
        self,
        *,
        index: int,
        speaker_id: str | None,
        voice_strategy: str,
        speaker_voice_map: dict[str, tuple[str, str]],
    ) -> tuple[str, str]:
        """Выбрать (voice, role) по стратегии."""
        if voice_strategy == "single":
            return self.voice_1, self.role_1

        if voice_strategy == "two_voices":
            if index % 2 == 0:
                return self.voice_1, self.role_1
            return self.voice_2, self.role_2

        if voice_strategy == "per_speaker":
            key = speaker_id or str(index)
            if key not in speaker_voice_map:
                pool_idx = len(speaker_voice_map) % len(_VOICE_POOL)
                voice = _VOICE_POOL[pool_idx]
                speaker_voice_map[key] = (voice, "neutral")
            return speaker_voice_map[key]

        return self.voice_1, self.role_1

    def _synth(self, text: str, voice: str, role: str, output) -> None:
        """Вызвать SpeechKit v3 и сохранить mp3."""
        payload = {
            "text": text,
            "hints": [
                {"voice": voice},
                {"role": role},
                {"speed": self.speed},
            ],
            "outputAudioSpec": {
                "containerAudio": {"containerAudioType": "MP3"},
            },
            "unsafeMode": True,
        }
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        audio_bytes = self._http_post(
            SPEECHKIT_TTS_URL,
            payload,
            headers=headers,
            timeout=self.timeout,
        )
        output.write_bytes(audio_bytes)


def build_speechkit_tts_provider(config) -> YandexSpeechKitTTSProvider | None:
    """Создать YandexSpeechKitTTSProvider из PipelineConfig.

    Возвращает None если professional_tts_provider != 'yandex' или нет ключа.
    """
    import os

    from translate_video.core.env import load_env_file

    provider_id = getattr(config, "professional_tts_provider", "").strip().lower()
    if provider_id != "yandex":
        return None

    load_env_file()
    api_key = os.getenv("YANDEX_SPEECHKIT_API_KEY", "").strip()
    if not api_key:
        _log.warning("tts.speechkit.no_api_key", env_var="YANDEX_SPEECHKIT_API_KEY")
        return None

    return YandexSpeechKitTTSProvider(
        api_key=api_key,
        voice_1=getattr(config, "professional_tts_voice", "alena"),
        voice_2=getattr(config, "professional_tts_voice_2", "filipp"),
        role_1=getattr(config, "professional_tts_role", "neutral"),
        role_2=getattr(config, "professional_tts_role_2", "neutral"),
        speed=float(getattr(config, "professional_tts_speed", 1.0)),
    )


def _add_qa_flag(segment: Segment, flag: str) -> None:
    if flag not in segment.qa_flags:
        segment.qa_flags.append(flag)


def _post_streaming(
    url: str,
    payload: dict,
    *,
    headers: dict,
    timeout: float,
) -> bytes:
    """POST к SpeechKit v3 — собирает streaming NDJSON-ответ в один mp3."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        chunks: list[bytes] = []
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for line in response:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    b64 = (
                        obj.get("audioChunk", {}).get("data")
                        or obj.get("result", {}).get("audioChunk", {}).get("data")
                    )
                    if b64:
                        chunks.append(base64.b64decode(b64))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        if not chunks:
            raise RuntimeError("SpeechKit вернул пустой аудио-ответ")
        return b"".join(chunks)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"SpeechKit HTTP {exc.code}: {exc.read()[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"SpeechKit сетевая ошибка: {exc.reason}") from exc
    except OSError as exc:
        raise RuntimeError(f"SpeechKit ошибка запроса: {exc}") from exc
