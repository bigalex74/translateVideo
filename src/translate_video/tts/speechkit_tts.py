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
from translate_video.tts import stress as _stress
from translate_video.tts.ssml_enhance import EMOTION_OFF, enhance as ssml_enhance

_log = get_logger(__name__)

SPEECHKIT_TTS_URL = "https://tts.api.cloud.yandex.net/tts/v3/utteranceSynthesis"

# Голоса SpeechKit для русского языка — полный список (проверено через API 2026-05-02).
# roles=[] означает что role-хинт отправлять нельзя (вернёт HTTP 400).
# Источник: live API test + Yandex SpeechKit Playground.
SPEECHKIT_VOICES: list[dict] = [
    # ── Стандартные голоса ─────────────────────────────────────────────────────
    {"id": "alena",     "name": "Алёна",     "gender": "female", "tier": "standard", "tone": "Тёплая, дружелюбная",       "roles": ["neutral", "good"]},
    {"id": "jane",      "name": "Джейн",     "gender": "female", "tier": "standard", "tone": "Эмоциональная, живая",       "roles": ["neutral", "good", "evil"]},
    {"id": "omazh",     "name": "Омаж",      "gender": "female", "tier": "standard", "tone": "Нейтральная, офисная",       "roles": ["neutral", "evil"]},
    {"id": "zahar",     "name": "Захар",     "gender": "male",   "tier": "standard", "tone": "Авторитетный, солидный",     "roles": ["neutral", "good"]},
    {"id": "ermil",     "name": "Ермил",     "gender": "male",   "tier": "standard", "tone": "Дикторский, чёткий",         "roles": ["neutral", "good"]},
    {"id": "filipp",    "name": "Филипп",    "gender": "male",   "tier": "standard", "tone": "Деловой, уверенный",         "roles": []},
    {"id": "madirus",   "name": "Мадирус",   "gender": "male",   "tier": "standard", "tone": "Молодой, энергичный",        "roles": []},
    {"id": "amira",     "name": "Амира",     "gender": "female", "tier": "standard", "tone": "Мягкая, приятная",           "roles": []},
    {"id": "john",      "name": "Джон",      "gender": "male",   "tier": "standard", "tone": "Нейтральный, универсальный", "roles": []},
    # ── Премиум голоса (новое поколение) ───────────────────────────────────────
    {"id": "julia",     "name": "Юлия",      "gender": "female", "tier": "premium",  "tone": "Чёткая, деловая",            "roles": ["neutral", "strict"]},
    {"id": "lera",      "name": "Лера",      "gender": "female", "tier": "premium",  "tone": "Молодая, живая",             "roles": ["neutral"]},
    {"id": "marina",    "name": "Марина",    "gender": "female", "tier": "premium",  "tone": "Мягкая, выразительная",      "roles": ["neutral", "whisper"]},
    {"id": "alexander", "name": "Александр", "gender": "male",   "tier": "premium",  "tone": "Уверенный, солидный",        "roles": ["neutral", "good"]},
    {"id": "kirill",    "name": "Кирилл",    "gender": "male",   "tier": "premium",  "tone": "Строгий, профессиональный",  "roles": ["neutral", "good", "strict"]},
    {"id": "anton",     "name": "Антон",     "gender": "male",   "tier": "premium",  "tone": "Нейтральный, чёткий",        "roles": ["neutral", "good"]},
    {"id": "masha",     "name": "Маша",      "gender": "female", "tier": "premium",  "tone": "Лёгкая, дружелюбная",        "roles": ["neutral", "good", "strict"]},
    {"id": "zhanar",    "name": "Жанар",     "gender": "female", "tier": "premium",  "tone": "Нейтральная, ровная",        "roles": ["neutral"]},
    {"id": "saule",     "name": "Сауле",     "gender": "female", "tier": "premium",  "tone": "Строгая, чёткая",            "roles": ["neutral", "strict"]},
    {"id": "yulduz",    "name": "Юлдуз",     "gender": "female", "tier": "premium",  "tone": "Мягкая, шёпот",              "roles": ["neutral", "strict", "whisper"]},
    {"id": "zamira",    "name": "Замира",     "gender": "female", "tier": "premium",  "tone": "Строгая, уверенная",         "roles": ["neutral", "strict"]},
]

# Пул голосов для per_speaker (round-robin) — предпочитаем premium
_VOICE_POOL = [v["id"] for v in SPEECHKIT_VOICES if v.get("tier") == "premium"] + \
              [v["id"] for v in SPEECHKIT_VOICES if v.get("tier") == "standard"]


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
        speed_1: float = 1.0,
        speed_2: float = 1.0,
        pitch_1: int = 0,
        pitch_2: int = 0,
        emotion_level: int = 0,   # 0=off 1=subtle 2=medium 3=expressive
        timeout: float = 60.0,
        use_stress: bool = True,
        folder_id: str = "",       # x-folder-id для premium голосов (zamira, etc.)
        http_post=None,
    ) -> None:
        self.api_key = api_key
        self.voice_1 = voice_1
        self.voice_2 = voice_2
        self.role_1 = role_1
        self.role_2 = role_2
        self.speed_1 = speed_1
        self.speed_2 = speed_2
        self.pitch_1 = pitch_1
        self.pitch_2 = pitch_2
        self.emotion_level = max(0, min(3, int(emotion_level)))
        self.timeout = timeout
        self.use_stress = use_stress
        self.folder_id = folder_id.strip()
        self._http_post = http_post or _post_streaming

    def synthesize(self, project, segments: list[Segment]) -> list[Segment]:
        """Синтезировать каждый переведённый сегмент через SpeechKit v3."""
        cfg = project.config
        voice_strategy = getattr(cfg, "voice_strategy", "single")
        output_dir = project.work_dir / "tts"
        output_dir.mkdir(parents=True, exist_ok=True)
        speaker_voice_map: dict[str, tuple[str, str]] = {}

        # Сбрасываем TTS-специфичные QA-флаги и tts_path от предыдущего запуска.
        # ВАЖНО: tts_path должен быть None чтобы рендер не использовал СТАРЫЕ
        # mp3-файлы от предыдущей озвучки если текущий синтез провалится.
        # Флаги тайминга (timing_fit_*) сохраняются — они остаются актуальными.
        for seg in segments:
            seg.tts_path = None  # защита от использования старого mp3 при ошибке
            seg.qa_flags = [
                f for f in seg.qa_flags if not f.startswith("tts_")
            ]

        for index, segment in enumerate(segments):
            # Приоритет источника текста:
            # 1. tts_ssml_override — TTS-разметка введённая пользователем вручную
            #    (содержит Яндекс TTS-markup: +ударения, sil<[300]>, **акцент**, [[фонемы]])
            #    Отправляется в поле "text" — ssml_enhance и ruaccent НЕ применяются.
            # 2. translated_text — стандартный переведённый текст
            tts_override = (segment.tts_ssml_override or "").strip()
            if tts_override:
                # **слово** → слово: Яндекс TTS v3 не поддерживает **bold**,
                # asterisks игнорируются или озвучиваются как мусор.
                # + ударения внутри сохраняются: **б+олван** → б+олван
                import re as _re_tts
                text = _re_tts.sub(r'\*\*([^*]+)\*\*', r'\1', tts_override)
                _log.debug(
                    "tts.speechkit.tts_markup_override",
                    idx=index,
                    seg_id=segment.id,
                    length=len(text),
                )
            else:
                text = segment.translated_text.strip()

            if not text:
                continue

            voice, role, speed, pitch = self._pick_voice_role(
                index=index,
                speaker_id=segment.speaker_id,
                voice_strategy=voice_strategy,
                speaker_voice_map=speaker_voice_map,
            )

            output = output_dir / f"{segment.id or index}.mp3"
            segment.tts_text = text

            # Автоматическая расстановка ударений (ruaccent) — только если НЕТ
            # пользовательского override (там ударения ставит сам пользователь через +).
            if self.use_stress and not tts_override:
                text = _stress.process(text)

            with Timer() as t:
                try:
                    self._synth(text, voice, role, speed, pitch, output)
                except Exception as exc:  # noqa: BLE001
                    # SSML fallback: если SSML вызвал "Empty Utterance" (HTTP 400)
                    # → повторяем с plain text. SSML-тег удаляется из payload,
                    # заменяется полем "text". Это гарантирует что синтез пройдёт.
                    err_str = str(exc)
                    if (
                        self.emotion_level > EMOTION_OFF
                        and "Empty" in err_str
                        and ("400" in err_str or "Utterance" in err_str)
                    ):
                        _log.warning(
                            "tts.speechkit.ssml_fallback",
                            idx=index,
                            seg_id=segment.id,
                            reason="Empty Utterance — retry with plain text",
                        )
                        try:
                            self._synth_plain(text, voice, role, speed, pitch, output)
                        except Exception as exc2:  # noqa: BLE001
                            _log.error(
                                "tts.speechkit.error",
                                idx=index,
                                seg_id=segment.id,
                                voice=voice,
                                error=str(exc2),
                            )
                            _add_qa_flag(segment, "tts_speechkit_error")
                            continue
                    else:
                        _log.error(
                            "tts.speechkit.error",
                            idx=index,
                            seg_id=segment.id,
                            voice=voice,
                            error=err_str,
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
        speaker_voice_map: dict[str, tuple[str, str, float, int]],
    ) -> tuple[str, str, float, int]:
        """Выбрать (voice, role, speed, pitch) по стратегии."""
        if voice_strategy == "single":
            return self.voice_1, self.role_1, self.speed_1, self.pitch_1

        if voice_strategy == "two_voices":
            if index % 2 == 0:
                return self.voice_1, self.role_1, self.speed_1, self.pitch_1
            return self.voice_2, self.role_2, self.speed_2, self.pitch_2

        if voice_strategy == "per_speaker":
            key = speaker_id or str(index)
            if key not in speaker_voice_map:
                pool_idx = len(speaker_voice_map) % len(_VOICE_POOL)
                voice = _VOICE_POOL[pool_idx]
                speaker_voice_map[key] = (voice, "neutral", self.speed_1, self.pitch_1)
            return speaker_voice_map[key]

        return self.voice_1, self.role_1, self.speed_1, self.pitch_1

    def _synth(
        self,
        text: str,
        voice: str,
        role: str,
        speed: float,
        pitch: int,
        output,
    ) -> None:
        """Вызвать SpeechKit v3 и сохранить mp3.

        Хинт ``role`` отправляется ТОЛЬКО если голос поддерживает роли.
        Хинт ``pitchShift`` отправляется только если pitch != 0 (диапазон -1000..1000).
        """
        voice_meta = next((v for v in SPEECHKIT_VOICES if v["id"] == voice), None)
        supports_role = bool(voice_meta and voice_meta.get("roles"))

        hints: list[dict] = [{"voice": voice}]
        if supports_role:
            hints.append({"role": role})
        hints.append({"speed": max(0.1, min(10.0, speed))})
        if pitch != 0:
            hints.append({"pitchShift": max(-1000, min(1000, pitch))})

        # SSML-эмоции: если emotion_level > 0 — конвертируем текст в SSML
        # и отправляем в поле "ssml" вместо "text".
        # TTS-разметка пользователя (tts_ssml_override) идёт в "text" — не в "ssml".
        if self.emotion_level > EMOTION_OFF:
            enhanced = ssml_enhance(text, self.emotion_level)
            text_payload = {"ssml": enhanced}
        else:
            text_payload = {"text": text}

        payload = {
            **text_payload,
            "hints": hints,
            "outputAudioSpec": {
                "containerAudio": {"containerAudioType": "MP3"},
            },
            "unsafeMode": True,
        }
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.folder_id:
            headers["x-folder-id"] = self.folder_id
        audio_bytes = self._http_post(
            SPEECHKIT_TTS_URL,
            payload,
            headers=headers,
            timeout=self.timeout,
        )
        output.write_bytes(audio_bytes)

    def _synth_plain(
        self,
        text: str,
        voice: str,
        role: str,
        speed: float,
        pitch: int,
        output,
    ) -> None:
        """Синтез с plain text (без SSML) — используется как fallback при ошибках SSML.

        Идентичен _synth, но всегда использует поле ``"text"`` вместо ``"ssml"``.
        """
        voice_meta = next((v for v in SPEECHKIT_VOICES if v["id"] == voice), None)
        supports_role = bool(voice_meta and voice_meta.get("roles"))

        hints: list[dict] = [{"voice": voice}]
        if supports_role:
            hints.append({"role": role})
        hints.append({"speed": max(0.1, min(10.0, speed))})
        if pitch != 0:
            hints.append({"pitchShift": max(-1000, min(1000, pitch))})

        payload = {
            "text": text,  # всегда plain text, независимо от emotion_level
            "hints": hints,
            "outputAudioSpec": {
                "containerAudio": {"containerAudioType": "MP3"},
            },
            "unsafeMode": True,
        }
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.folder_id:
            headers["x-folder-id"] = self.folder_id
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
        voice_1=getattr(config, "professional_tts_voice",    "alena"),
        voice_2=getattr(config, "professional_tts_voice_2",  "filipp"),
        role_1=getattr(config, "professional_tts_role",      "neutral"),
        role_2=getattr(config, "professional_tts_role_2",    "neutral"),
        speed_1=float(getattr(config, "professional_tts_speed",   1.0)),
        speed_2=float(getattr(config, "professional_tts_speed_2", 1.0)),
        pitch_1=int(getattr(config, "professional_tts_pitch",     0)),
        pitch_2=int(getattr(config, "professional_tts_pitch_2",   0)),
        emotion_level=int(getattr(config, "professional_tts_emotion", 0)),
        use_stress=bool(getattr(config, "professional_tts_stress", True)),
        folder_id=os.getenv("YANDEX_FOLDER_ID", ""),
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
    """POST к SpeechKit v3 — собирает NDJSON-ответ в один mp3.

    ВАЖНО: Яндекс SpeechKit v3 отдаёт один длинный JSON-объект без переносов
    строк (~30-50 KB на фразу). Итерация ``for line in response`` разбивает
    ответ по буферу urllib (~8 KB), а не по '\\n' — каждый кусок невалидный
    JSON, все пропускаются, результат — пустой или усечённый аудио (1 буква).

    Исправление: читаем весь ответ через ``response.read()`` и разбиваем
    по b'\\n', чтобы получить полные JSON-строки.
    """
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        chunks: list[bytes] = []
        with urllib.request.urlopen(request, timeout=timeout) as response:
            # Читаем ВЕСЬ ответ сразу — не итерируем построчно.
            # urllib итерирует по буферам ~8KB, а не по \n,
            # что разрывает длинные JSON-объекты Яндекса на невалидные куски.
            raw = response.read()

        for line in raw.split(b"\n"):
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
