"""edge-tts адаптер синтеза речи с LLM-сжатием (TVIDEO-037).

Если синтезированная озвучка не укладывается в временной слот:
1. Измеряем длительность через ffprobe
2. Запрашиваем Ollama сократить перевод (сохранив смысл)
3. Переозвучиваем — до compress_max_retries попыток
4. Pre-trim удалён: не обрезаем текст символьным счётчиком
"""

from __future__ import annotations

import asyncio
import logging

from translate_video.tts.compress import compress_via_llm, get_audio_duration

logger = logging.getLogger(__name__)


class EdgeTTSProvider:
    """Создает TTS-файлы сегментов через `edge-tts`."""

    DEFAULT_VOICES = {
        "ru": "ru-RU-SvetlanaNeural",
        "en": "en-US-AriaNeural",
        "de": "de-DE-KatjaNeural",
        "es": "es-ES-ElviraNeural",
        "fr": "fr-FR-DeniseNeural",
    }

    def __init__(self, communicate_factory=None, async_runner=None, base_rate: int = 15) -> None:
        self.communicate_factory = communicate_factory or _edge_communicate
        self.async_runner = async_runner or asyncio.run
        self.base_rate = base_rate

    def synthesize(self, project, segments):
        """Синтезировать каждый переведенный сегмент в отдельный аудиофайл.

        Если озвучка длиннее слота — сжимаем перевод через Ollama и
        переозвучиваем (до config.compress_max_retries попыток).
        """

        cfg = project.config
        voice = self.DEFAULT_VOICES.get(
            cfg.target_language.lower(),
            self.DEFAULT_VOICES["en"],
        )
        rate = f"+{self.base_rate}%"

        for index, segment in enumerate(segments):
            text = segment.translated_text.strip()
            if not text:
                continue

            slot = segment.end - segment.start
            output = project.work_dir / "tts" / f"{segment.id or index}.mp3"

            # Первичный синтез
            self._synth(text, voice, rate, output)

            # Цикл LLM-сжатия при переполнении
            for attempt in range(cfg.compress_max_retries):
                dur = get_audio_duration(output)
                if dur is None:
                    break  # ffprobe недоступен — идём дальше
                if dur <= slot * cfg.compress_slack:
                    break  # укладывается — всё OK

                logger.info(
                    "Сегмент %s: tts=%.2fs > slot=%.2fs (x%.2f), "
                    "попытка сжатия %d/%d",
                    segment.id, dur, slot, dur / slot,
                    attempt + 1, cfg.compress_max_retries,
                )

                target_sec = slot * 0.92  # целим в 92% от слота
                compressed = compress_via_llm(
                    text=text,
                    current_sec=dur,
                    target_sec=target_sec,
                    model=cfg.compress_llm_model,
                    ollama_url=cfg.compress_llm_url,
                )
                if not compressed:
                    logger.warning(
                        "LLM не помог для сегмента %s — оставляем как есть",
                        segment.id,
                    )
                    break

                text = compressed
                self._synth(text, voice, rate, output)

            # Сохраняем финальный текст если он изменился
            if text != segment.translated_text.strip():
                segment.tts_text = text
                if "tts_llm_compressed" not in segment.qa_flags:
                    segment.qa_flags.append("tts_llm_compressed")

            segment.tts_path = output.relative_to(project.work_dir).as_posix()
            segment.voice = voice

        return segments

    def _synth(self, text: str, voice: str, rate: str, output) -> None:
        """Синтезировать текст и сохранить в файл."""
        communicate = self.communicate_factory(text, voice, rate=rate)
        self.async_runner(communicate.save(str(output)))


def _edge_communicate(*args, **kwargs):
    """Лениво импортировать `edge-tts`."""

    import edge_tts

    return edge_tts.Communicate(*args, **kwargs)
