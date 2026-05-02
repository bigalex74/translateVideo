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

export const QUALITY_LABELS: Record<string, string> = {
  amateur: 'Любительский: бесплатные модели + дешёвый fallback',
  professional: 'Профессиональный: выбранная платная топ-модель',
};

export const MODEL_PROVIDER_LABELS: Record<string, string> = {
  neuroapi: 'NeuroAPI',
  polza: 'Polza.ai',
};

export const PROFESSIONAL_MODEL_OPTIONS: Record<string, string[]> = {
  neuroapi: ['gpt-5-mini', 'gpt-4.1-mini', 'gpt-4.1', 'claude-3-7-sonnet-20250219'],
  polza: ['google/gemini-2.5-flash-lite-preview-09-2025', 'google/gemini-2.5-flash', 'gpt-4o-mini'],
};

export const DEFAULT_CONFIG: Partial<PipelineConfig> = {
  translation_quality: 'amateur',
  translation_style: 'neutral',
  adaptation_level: 'natural',
  voice_strategy: 'single',
  do_not_translate: [],
  profanity_policy: 'keep',
  preserve_names: true,
  professional_translation_provider: 'neuroapi',
  professional_translation_model: 'gpt-5-mini',
  professional_rewrite_provider: 'neuroapi',
  professional_rewrite_model: 'gpt-5-mini',
  professional_tts_provider: '',
  professional_tts_model: 'tts-1',
  professional_tts_voice: 'nova',
  professional_tts_voice_2: 'onyx',
  professional_tts_role: 'neutral',
  professional_tts_role_2: 'neutral',
  professional_tts_speed: 1.0,
  professional_tts_speed_2: 1.0,
  professional_tts_pitch: 0,
  professional_tts_pitch_2: 0,
};
