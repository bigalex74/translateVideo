"""edge-tts адаптер синтеза речи.

Pre-trim стратегия (TVIDEO-030c):
Перед синтезом оцениваем сколько символов уместится в слот.
Текст укорачивается на естественных границах (предложение → слово),
чтобы голос не обрывался на полуслове.
"""

from __future__ import annotations

import asyncio
import re

# Символов в секунду для edge-tts на русском при rate=+15%.
# Реалистичная оценка: 18-22 chars/sec. Берём 20 как середину.
# При 14 текст обрезался почти везде — слишком консервативно (TVIDEO-036).
_CHARS_PER_SECOND = 20.0

# Pre-trim срабатывает только при экстремальном превышении (2x слот).
# Небольшие превышения (до 2x) обрабатывает atempo в рендерере.
# Старый порог 1.15 обрезал почти каждый сегмент (TVIDEO-036 hotfix).
_OVERFLOW_THRESHOLD = 2.0

# Знаки конца предложения
_SENTENCE_END_RE = re.compile(r'[.!?…]')


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

            # Pre-trim: укорачиваем текст если он не уложится в слот
            slot_duration = segment.end - segment.start
            tts_text = _compute_tts_text(text, slot_duration)
            if tts_text != text and "tts_pretrim" not in segment.qa_flags:
                segment.qa_flags.append("tts_pretrim")

            output = project.work_dir / "tts" / f"{segment.id or index}.mp3"
            communicate = self.communicate_factory(tts_text, voice, rate=rate)
            self.async_runner(communicate.save(str(output)))
            segment.tts_path = output.relative_to(project.work_dir).as_posix()
            segment.voice = voice
        return segments


# ─── Pre-trim логика ──────────────────────────────────────────────────────────

def _compute_tts_text(text: str, slot_duration: float) -> str:
    """Вычислить текст для TTS-синтеза с учётом временного слота.

    Если текст превышает ёмкость слота на OVERFLOW_THRESHOLD — укорачиваем
    на естественной границе (конец предложения или слово), чтобы голос
    не обрывался посреди слова.

    `text` — полный переведённый текст (для UI).
    Возвращает текст для TTS (может быть короче).
    """
    if slot_duration <= 0:
        return text

    max_chars = slot_duration * _CHARS_PER_SECOND
    if len(text) <= max_chars * _OVERFLOW_THRESHOLD:
        # Текст укладывается — не трогаем
        return text

    # Текст слишком длинный — ищем место обрезки
    target = int(max_chars)
    return _trim_at_natural_boundary(text, target)


def _trim_at_natural_boundary(text: str, max_chars: int) -> str:
    """Обрезать текст на ближайшей естественной границе ≤ max_chars.

    Приоритет обрезки:
    1. Конец предложения (.!?…) — идеально
    2. Конец слова (пробел)    — приемлемо
    3. Жёсткая обрезка         — крайний случай (должно быть редким)
    """
    if max_chars >= len(text):
        return text

    # Окно поиска: от max_chars назад до 60% от max_chars
    search_start = max(0, int(max_chars * 0.6))
    window = text[search_start:max_chars + 1]

    # 1. Последний конец предложения в окне
    for match in reversed(list(_SENTENCE_END_RE.finditer(window))):
        cut = search_start + match.end()
        if cut > 0:
            return text[:cut].strip()

    # 2. Последний пробел в окне
    last_space = window.rfind(' ')
    if last_space > 0:
        cut = search_start + last_space
        return text[:cut].strip()

    # 3. Жёсткая обрезка
    return text[:max_chars].strip()


def _edge_communicate(*args, **kwargs):
    """Лениво импортировать `edge-tts`."""

    import edge_tts

    return edge_tts.Communicate(*args, **kwargs)
