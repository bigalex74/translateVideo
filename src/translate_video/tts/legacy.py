"""edge-tts адаптер синтеза речи.

Дефолтная политика TVIDEO-042 — естественная скорость речи без ускорения.
Адаптивный rate оставлен только как явный fast-режим через
``allow_tts_rate_adaptation=True``.
"""

from __future__ import annotations

import asyncio
import logging
import math

from translate_video.tts.compress import get_audio_duration

logger = logging.getLogger(__name__)


class EdgeTTSProvider:
    """Создает TTS-файлы сегментов через `edge-tts` с адаптивным rate."""

    DEFAULT_VOICES = {
        "ru": "ru-RU-SvetlanaNeural",
        "en": "en-US-AriaNeural",
        "de": "de-DE-KatjaNeural",
        "es": "es-ES-ElviraNeural",
        "fr": "fr-FR-DeniseNeural",
    }

    def __init__(self, communicate_factory=None, async_runner=None) -> None:
        self.communicate_factory = communicate_factory or _edge_communicate
        self.async_runner = async_runner or asyncio.run

    def synthesize(self, project, segments):
        """Синтезировать каждый переведённый сегмент.

        По умолчанию синтез идет с `+0%`, чтобы сохранить естественное
        восприятие. Если пользователь явно разрешил fast-режим, то при
        переполнении слота выполняется одна повторная генерация с повышенным
        rate.
        """
        cfg = project.config
        voice = self.DEFAULT_VOICES.get(
            cfg.target_language.lower(),
            self.DEFAULT_VOICES["en"],
        )

        for index, segment in enumerate(segments):
            text = segment.translated_text.strip()
            if not text:
                continue

            slot = segment.end - segment.start
            output = project.work_dir / "tts" / f"{segment.id or index}.mp3"
            segment.tts_text = text

            # Первичный синтез на естественной скорости, если fast-режим не включён.
            base_rate = cfg.tts_base_rate if cfg.allow_tts_rate_adaptation else 0
            rate = _fmt_rate(base_rate)
            self._synth(text, voice, rate, output)

            if slot <= 0:
                _add_qa_flag(segment, "tts_invalid_slot")
                segment.tts_path = output.relative_to(project.work_dir).as_posix()
                segment.voice = voice
                continue

            # Адаптивное ускорение при переполнении
            dur = get_audio_duration(output)
            if (
                cfg.allow_tts_rate_adaptation
                and cfg.tts_max_rate > base_rate
                and dur is not None
                and dur > slot * cfg.tts_rate_slack
            ):
                needed = _compute_rate(
                    duration=dur,
                    slot=slot,
                    base_rate=base_rate,
                    max_rate=cfg.tts_max_rate,
                )
                if needed > base_rate:
                    logger.info(
                        "Сегмент %s: %.2fс > слот %.2fс → rate +%d%%",
                        segment.id, dur, slot, needed,
                    )
                    rate = _fmt_rate(needed)
                    self._synth(text, voice, rate, output)

                    _add_qa_flag(segment, "tts_rate_adapted")
                    dur = get_audio_duration(output)

            if dur is not None and dur > slot * cfg.tts_rate_slack:
                flag = (
                    "tts_overflow_after_rate"
                    if cfg.allow_tts_rate_adaptation
                    else "tts_overflow_natural_rate"
                )
                _add_qa_flag(segment, flag)

            segment.tts_path = output.relative_to(project.work_dir).as_posix()
            segment.voice = voice

        return segments

    def _synth(self, text: str, voice: str, rate: str, output) -> None:
        """Синтезировать текст и сохранить в файл."""
        communicate = self.communicate_factory(text, voice, rate=rate)
        self.async_runner(communicate.save(str(output)))


def _compute_rate(
    duration: float,
    slot: float,
    base_rate: int,
    max_rate: int,
) -> int:
    """Вычислить нужный rate чтобы аудио уложилось в слот.

    Формула: нужно ускорить пропорционально превышению.
    duration / slot = коэффициент → нужный rate = base + (коэфф - 1) * 100.
    Округляем вверх и ограничиваем до max_rate.
    """
    ratio = duration / slot
    # Сколько % нужно добавить к скорости
    extra = math.ceil((ratio - 1.0) * 100)
    return min(base_rate + extra, max_rate)


def _fmt_rate(rate: int) -> str:
    """Форматировать rate в строку для edge-tts: +15%, -5%, +0%."""
    if rate >= 0:
        return f"+{rate}%"
    return f"{rate}%"


def _add_qa_flag(segment, flag: str) -> None:
    """Добавить QA-флаг сегменту без дублей."""

    if flag not in segment.qa_flags:
        segment.qa_flags.append(flag)


def _edge_communicate(*args, **kwargs):
    """Лениво импортировать `edge-tts`."""

    import edge_tts

    return edge_tts.Communicate(*args, **kwargs)
