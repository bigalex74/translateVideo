/**
 * Человекочитаемые названия для технических терминов пайплайна.
 * Используется во всех компонентах UI вместо сырых enum-значений.
 */

export const STAGE_LABELS: Record<string, string> = {
  extract_audio:   '🎙️ Извлечение аудио',
  transcribe:      '📝 Распознавание речи',
  translate:       '🌐 Перевод текста',
  tts:             '🔊 Создание озвучки',
  render:          '🎬 Сборка видео',
  qa:              '✅ Проверка качества',
  export:          '📤 Экспорт субтитров',
  normalize_audio: '🎚️ Нормализация звука',
  align:           '🔗 Выравнивание',
  diarize:         '👥 Разделение спикеров',
  glossary:        '📖 Применение глоссария',
  review:          '🔍 Ревью',
  postprocess:     '⚙️ Постобработка',
};

export const STATUS_LABELS: Record<string, string> = {
  created:    'Создан',
  running:    'Выполняется',
  completed:  'Завершён',
  failed:     'Ошибка',
  skipped:    'Пропущен',
  pending:    'Ожидает',
};

export const STATUS_EMOJI: Record<string, string> = {
  created:   '🕐',
  running:   '⚙️',
  completed: '✅',
  failed:    '❌',
  skipped:   '⏭️',
  pending:   '⏳',
};

export const PROVIDER_LABELS: Record<string, string> = {
  fake:   '🧪 Тестовый (без реальной обработки)',
  legacy: '⚙️ Полный пайплайн (moviepy + whisper + edge-tts)',
};

export const PROVIDER_WARNINGS: Record<string, string | undefined> = {
  legacy: 'Требует установленных зависимостей: moviepy, faster-whisper, edge-tts, ffmpeg. Обработка займёт несколько минут.',
  fake:   undefined,
};

/** Вернуть название этапа, если не найдено — форматировать raw. */
export function stageLabel(raw: string): string {
  return STAGE_LABELS[raw] ?? raw.replace(/_/g, ' ');
}

/** Вернуть человеческий статус. */
export function statusLabel(raw: string): string {
  return STATUS_LABELS[raw] ?? raw;
}

/** QA: нужна ли ручная проверка сегментов? */
export function needsReviewCount(segments: Array<{ translated_text?: string; source_text: string }>): number {
  return segments.filter(s => {
    const t = (s.translated_text ?? '').trim();
    const src = s.source_text.trim();
    return !t || t === src;
  }).length;
}
