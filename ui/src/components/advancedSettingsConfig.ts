import type { PipelineConfig } from '../types/schemas';

/**
 * Словари и дефолты расширенных настроек перевода.
 *
 * Файл отделен от React-компонента, чтобы fast refresh видел в компонентных
 * файлах только компоненты и не ломал lint release gate.
 */

export const STYLE_LABELS: Record<string, string> = {
  neutral: 'Нейтральный',
  business: 'Деловой',
  casual: 'Разговорный',
  humorous: 'Юмористический',
  educational: 'Образовательный',
  cinematic: 'Кинематографический',
  child_friendly: 'Для детей',
};

export const ADAPTATION_LABELS: Record<string, string> = {
  literal: 'Дословно (точный перевод)',
  natural: 'Естественно (рекомендуется)',
  localized: 'Локализовано (культурная адаптация)',
  shortened_for_timing: 'Укорочено (под тайминг)',
};

export const VOICE_LABELS: Record<string, string> = {
  single: 'Один голос',
  by_gender: 'По полу (муж./жен.)',
  two_voices: 'Два голоса',
  per_speaker: 'Каждому спикеру свой',
};

export const PROFANITY_LABELS: Record<string, string> = {
  keep: 'Сохранить',
  soften: 'Смягчить',
  remove: 'Удалить',
};

export const DEFAULT_CONFIG: Partial<PipelineConfig> = {
  translation_style: 'neutral',
  adaptation_level: 'natural',
  voice_strategy: 'single',
  do_not_translate: [],
  profanity_policy: 'keep',
  preserve_names: true,
};
