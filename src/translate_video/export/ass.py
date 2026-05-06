"""Генерация ASS (Advanced SubStation Alpha) субтитров (NC5-01).

Формат ASS поддерживается Aegisub, Kdenlive, MPlayer, FFmpeg.
Используется профессиональными переводчиками и субтитровщиками.
"""

from __future__ import annotations

from translate_video.core.schemas import Segment


def _ass_time(seconds: float) -> str:
    """Преобразовать секунды в формат H:MM:SS.cc (сотые секунды)."""
    total_cs = int(round(seconds * 100))
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# Стандартный заголовок ASS с предустановленным стилем субтитров
_ASS_HEADER = """\
[Script Info]
; NC5-01: Экспорт из AI Video Translator
Title: Translated Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def segments_to_ass(
    segments: list[Segment],
    style: str = "Default",
) -> str:
    """Сгенерировать строку ASS-субтитров из сегментов.

    Args:
        segments: список сегментов с переводом
        style: имя стиля из секции V4+ Styles (по умолчанию "Default")

    Returns:
        str: готовый ASS-контент для записи в .ass файл
    """
    lines: list[str] = [_ASS_HEADER]
    for seg in segments:
        text = (seg.translated_text or seg.source_text or "").strip()
        if not text:
            continue
        # Заменяем переносы строк на \N (soft line break в ASS)
        text_ass = text.replace("\n", "\\N")
        start = _ass_time(seg.start)
        end = _ass_time(seg.end)
        lines.append(f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text_ass}")
    return "\n".join(lines) + "\n"
