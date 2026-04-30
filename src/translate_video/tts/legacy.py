"""edge-tts адаптер синтеза речи."""

from __future__ import annotations

import asyncio


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
        """Синтезировать каждый переведенный сегмент в отдельный аудиофайл."""

        voice = self.DEFAULT_VOICES.get(
            project.config.target_language.lower(),
            self.DEFAULT_VOICES["en"],
        )
        rate = f"+{self.base_rate}%"
        for index, segment in enumerate(segments):
            text = segment.translated_text.strip()
            if not text:
                continue
            output = project.work_dir / "tts" / f"{segment.id or index}.mp3"
            communicate = self.communicate_factory(text, voice, rate=rate)
            self.async_runner(communicate.save(str(output)))
            segment.tts_path = output.relative_to(project.work_dir).as_posix()
            segment.voice = voice
        return segments


def _edge_communicate(*args, **kwargs):
    """Лениво импортировать `edge-tts`."""

    import edge_tts

    return edge_tts.Communicate(*args, **kwargs)
