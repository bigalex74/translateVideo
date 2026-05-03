"""SSML-усиление эмоций для Yandex SpeechKit v3.

Конвертирует плоский текст в SSML-разметку с настраиваемым уровнем
эмоциональности (0–3). Уровни:

  0 — SSML отключён, передаётся plain text (без изменений)
  1 — Минимум: паузы на знаках препинания, естественные ударения
  2 — Средний: паузы + ускорение/замедление по типу предложений
  3 — Экспрессивный: просодия, акцент на эмоциональных фразах

Все теги соответствуют подмножеству Yandex SpeechKit SSML (W3C SSML 1.1):
  https://yandex.cloud/ru/docs/speechkit/tts/markup/ssml
"""

from __future__ import annotations

import re
import xml.sax.saxutils as sax


# ── Уровни эмоций ─────────────────────────────────────────────────────────────

EMOTION_OFF      = 0  # plain text
EMOTION_SUBTLE   = 1  # паузы
EMOTION_MEDIUM   = 2  # паузы + просодия
EMOTION_EXPRESSIVE = 3  # паузы + просодия + ударения


# ── Паузы по знакам препинания (ms) ───────────────────────────────────────────

_PAUSE_AFTER: dict[str, int] = {
    ".":  350,
    "!":  450,
    "?":  400,
    "…":  400,
    ";":  200,
    ",":  130,
    ":":  150,
    "—":  120,
    "-":  80,
}

# Для уровня 1 используем умеренные паузы (60%)
_PAUSE_SUBTLE_FACTOR = 0.6


def enhance(text: str, emotion_level: int) -> str:
    """Вернуть SSML-строку (или plain text при emotion_level=0).

    Args:
        text:          Исходный текст (plain text).
        emotion_level: 0–3, уровень эмоциональности.

    Returns:
        При emotion_level=0 возвращает text без изменений.
        Иначе возвращает строку вида ``<speak>...</speak>``.
    """
    level = max(0, min(3, int(emotion_level)))
    if level == 0:
        return text

    sentences = _split_sentences(text)
    parts: list[str] = []

    for sent in sentences:
        raw = sent["text"]
        end_punct = sent["end_punct"]
        is_exclaim = end_punct == "!"
        is_question = end_punct == "?"
        is_ellipsis = end_punct in ("…", "...")

        escaped = sax.escape(raw.strip())
        if not escaped:   # пустой сегмент — пропускаем, чтобы не слать <speak></speak>
            continue

        if level == 1:
            # Только пауза после предложения
            pause_ms = _pause_ms(end_punct, factor=_PAUSE_SUBTLE_FACTOR)
            part = escaped
            if pause_ms:
                part += f'<break time="{pause_ms}ms"/>'
            parts.append(part)

        elif level == 2:
            # Пауза + небольшая просодия по типу предложения
            pause_ms = _pause_ms(end_punct)
            if is_exclaim:
                # Восклицание: чуть быстрее и громче
                content = f'<prosody rate="108%" volume="+2dB">{escaped}</prosody>'
            elif is_question:
                # Вопрос: чуть медленнее
                content = f'<prosody rate="95%">{escaped}</prosody>'
            elif is_ellipsis:
                # Многоточие: медленнее
                content = f'<prosody rate="90%">{escaped}</prosody>'
            else:
                content = escaped
            part = content
            if pause_ms:
                part += f'<break time="{pause_ms}ms"/>'
            parts.append(part)

        else:
            # level == 3: полная экспрессия
            pause_ms = _pause_ms(end_punct)
            if is_exclaim:
                content = f'<prosody rate="112%" pitch="+1st" volume="+3dB">{escaped}</prosody>'
            elif is_question:
                content = f'<prosody rate="93%" pitch="+0.5st">{escaped}</prosody>'
            elif is_ellipsis:
                content = f'<prosody rate="87%" pitch="-0.5st">{escaped}</prosody>'
            else:
                content = escaped

            # Добавляем ударение на вводные фразы (в начале предложения)
            content = _emphasize_intros(content)
            part = content
            if pause_ms:
                part += f'<break time="{pause_ms}ms"/>'
            parts.append(part)

    inner = " ".join(p for p in parts if p.strip())  # фильтруем пустые части
    # Защита: если inner пустой — Яндекс вернёт HTTP 400 "Empty Utterance".
    # Возвращаем plain text как fallback.
    if not inner.strip():
        return text
    return f"<speak>{inner}</speak>"


# ── Вспомогательные функции ───────────────────────────────────────────────────

# Разделяем на предложения по терминаторам (. ! ? … ; — с учётом многоточий)
_SENT_RE = re.compile(
    r'([^.!?…;]+(?:[.!?…](?!\s*[a-zа-яё])[.!?…]*|;|$))',
    re.UNICODE | re.IGNORECASE,
)

# Терминаторы (конечная пунктуация предложений)
_TERMINATORS_RE = re.compile(r'([.!?…;]+)\s*$')

# Ударные вводные слова (в начале фразы)
_INTRO_PHRASES = (
    r'\bобратите внимание\b',
    r'\bвнимание\b',
    r'\bважно\b',
    r'\bпомните\b',
    r'\bнапример\b',
    r'\bчтобы\b',
    r'\bитак\b',
)
_INTRO_RE = re.compile(
    '|'.join(_INTRO_PHRASES),
    re.IGNORECASE | re.UNICODE,
)


def _split_sentences(text: str) -> list[dict]:
    """Разбить текст на предложения, сохраняя завершающий пунктуатор."""
    result: list[dict] = []
    # Простая стратегия: разбить по . ! ? … с учётом сокращений
    raw_sents = re.split(r'(?<=[.!?…])\s+', text.strip())
    for s in raw_sents:
        s = s.strip()
        if not s:
            continue
        m = _TERMINATORS_RE.search(s)
        end_punct = m.group(1)[-1] if m else ""
        # Убираем финальный знак из текста (он добавится как пауза)
        clean = _TERMINATORS_RE.sub("", s).strip()
        result.append({"text": clean or s, "end_punct": end_punct})
    return result or [{"text": text, "end_punct": ""}]


def _pause_ms(punct: str, factor: float = 1.0) -> int:
    """Вернуть длительность паузы в мс для заданного знака препинания."""
    ms = _PAUSE_AFTER.get(punct, 0)
    return int(ms * factor)


def _emphasize_intros(ssml_text: str) -> str:
    """Обернуть вводные слова тегом emphasis (moderate) если нет тегов вокруг."""
    def repl(m: re.Match) -> str:
        word = m.group(0)
        return f'<emphasis level="moderate">{sax.escape(word)}</emphasis>'
    return _INTRO_RE.sub(repl, ssml_text)
