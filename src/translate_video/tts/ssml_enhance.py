"""SSML-усиление эмоций для Yandex SpeechKit.

Конвертирует плоский текст в разметку с настраиваемым уровнем
эмоциональности (0–3). Уровни:

  0 — отключён, передаётся plain text (без изменений)
  1 — Минимум: паузы на знаках препинания
  2 — Средний: паузы + просодия
  3 — Экспрессивный: паузы + просодия + ударения

ВАЖНО — два формата:
  enhance()        → SSML <speak>...</speak>  — только для API v1
  enhance_tts_v3() → TTS-разметка sil<[ms]>  — только для API v3

API v3 (utteranceSynthesis) НЕ принимает поле "ssml" — возвращает HTTP 400.
В v3 используется поле "text" с TTS-разметкой Яндекс.
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


# ── API v3: TTS-разметка вместо SSML ─────────────────────────────────────────

def enhance_tts_v3(text: str, emotion_level: int) -> tuple[str, float]:
    """Вернуть (tts_text, speed_factor) с TTS-разметкой Яндекс для API v3.

    В отличие от enhance(), возвращает НЕ SSML, а текст с TTS-разметкой:
      - Паузы: sil<[ms]> вместо <break time="ms"/>
      - Просодия: возвращается speed_factor (1.0 = норм, 1.08 = быстрее)
        для передачи через hints[{"speed": base_speed * speed_factor}]
      - <emphasis> и <prosody pitch> — нет эквивалента, игнорируются

    Args:
        text:          Plain text.
        emotion_level: 0–3.

    Returns:
        (tts_text, speed_factor) — строка с TTS-разметкой и множитель скорости.
    """
    level = max(0, min(3, int(emotion_level)))
    if level == 0:
        return text, 1.0

    sentences = _split_sentences(text)
    parts: list[str] = []
    # Для уровня 2-3: усредняем скорость по типам предложений
    speed_votes: list[float] = []

    for sent in sentences:
        raw = sent["text"]
        end_punct = sent["end_punct"]
        is_exclaim = end_punct == "!"
        is_question = end_punct == "?"
        is_ellipsis = end_punct in ("…", "...")

        word = raw.strip()
        if not word:
            continue

        # Паузы → TTS-разметка
        if level == 1:
            pause_ms = _pause_ms(end_punct, factor=_PAUSE_SUBTLE_FACTOR)
        else:
            pause_ms = _pause_ms(end_punct)

        part = word
        if pause_ms:
            part += f" sil<[{pause_ms}]>"
        parts.append(part)

        # Собираем голоса для speed_factor (level 2+)
        if level >= 2:
            if is_exclaim:
                speed_votes.append(1.08)
            elif is_question:
                speed_votes.append(0.95)
            elif is_ellipsis:
                speed_votes.append(0.90)
            else:
                speed_votes.append(1.0)

    tts_text = " ".join(p for p in parts if p.strip()) or text
    speed_factor = (sum(speed_votes) / len(speed_votes)) if speed_votes else 1.0
    return tts_text, round(speed_factor, 3)
