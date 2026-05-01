"""edge-tts адаптер синтеза речи с адаптивным rate (TVIDEO-040b).

Если синтезированная озвучка не укладывается в временной слот:
1. Измеряем длительность через ffprobe
2. Вычисляем нужный rate: base_rate + (duration/slot - 1) * 100
3. Ограничиваем до tts_max_rate (по умолчанию 40%)
4. Если нужный rate > базового — переозвучиваем один раз

Преимущества перед Ollama-сжатием:
- Мгновенно (< 0.1с вычисление)
- Не зависит от внешних сервисов
- Сохраняет 100% смысла перевода
- Тон голоса не изменяется (edge-tts rate ≠ pitch)
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

        Если аудио длиннее слота > tts_rate_slack — ускоряем rate и
        переозвучиваем один раз. Текст не изменяется.
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

            # Первичный синтез с базовым rate
            rate = _fmt_rate(cfg.tts_base_rate)
            self._synth(text, voice, rate, output)

            # Адаптивное ускорение при переполнении
            dur = get_audio_duration(output)
            if dur is not None and dur > slot * cfg.tts_rate_slack:
                needed = _compute_rate(
                    duration=dur,
                    slot=slot,
                    base_rate=cfg.tts_base_rate,
                    max_rate=cfg.tts_max_rate,
                )
                if needed > cfg.tts_base_rate:
                    logger.info(
                        "Сегмент %s: %.2fс > слот %.2fс → rate +%d%%",
                        segment.id, dur, slot, needed,
                    )
                    rate = _fmt_rate(needed)
                    self._synth(text, voice, rate, output)

                    if "tts_rate_adapted" not in segment.qa_flags:
                        segment.qa_flags.append("tts_rate_adapted")

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


def _edge_communicate(*args, **kwargs):
    """Лениво импортировать `edge-tts`."""

    import edge_tts

    return edge_tts.Communicate(*args, **kwargs)
