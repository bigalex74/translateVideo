/**
 * Тесты для qa_stage_filter.ts (TVIDEO-098).
 *
 * Проверяет что live-лента QA показывает ТОЛЬКО флаги текущей стадии,
 * а не флаги от предыдущих запусков.
 *
 * Регрессия: при запуске только TTS пользователь видел предупреждения от
 * timing_fit и translate из предыдущих запусков в блоке «QA: обнаружено
 * в процессе».
 */
import { describe, it, expect } from 'vitest';
import {
  flagBelongsToStage,
  filterFlagsByStage,
  STAGE_FLAG_PREFIXES,
} from './qa_stage_filter';

// ── flagBelongsToStage ────────────────────────────────────────────────────────

describe('flagBelongsToStage — TTS stage', () => {
  it('tts_invalid_slot принадлежит tts', () => {
    expect(flagBelongsToStage('tts_invalid_slot', 'tts')).toBe(true);
  });

  it('tts_overflow_natural_rate принадлежит tts', () => {
    expect(flagBelongsToStage('tts_overflow_natural_rate', 'tts')).toBe(true);
  });

  it('tts_speechkit принадлежит tts', () => {
    expect(flagBelongsToStage('tts_speechkit', 'tts')).toBe(true);
  });

  it('tts_voice_alena принадлежит tts', () => {
    expect(flagBelongsToStage('tts_voice_alena', 'tts')).toBe(true);
  });

  it('timing_fit_failed НЕ принадлежит tts', () => {
    expect(flagBelongsToStage('timing_fit_failed', 'tts')).toBe(false);
  });

  it('translation_rewritten_for_timing НЕ принадлежит tts', () => {
    expect(flagBelongsToStage('translation_rewritten_for_timing', 'tts')).toBe(false);
  });

  it('translation_fallback_source НЕ принадлежит tts', () => {
    expect(flagBelongsToStage('translation_fallback_source', 'tts')).toBe(false);
  });

  it('render_audio_trimmed НЕ принадлежит tts', () => {
    expect(flagBelongsToStage('render_audio_trimmed', 'tts')).toBe(false);
  });
});

describe('flagBelongsToStage — timing_fit stage', () => {
  it('timing_fit_failed принадлежит timing_fit', () => {
    expect(flagBelongsToStage('timing_fit_failed', 'timing_fit')).toBe(true);
  });

  it('timing_fit_invalid_slot принадлежит timing_fit', () => {
    expect(flagBelongsToStage('timing_fit_invalid_slot', 'timing_fit')).toBe(true);
  });

  it('translation_rewritten_for_timing принадлежит timing_fit (exact match)', () => {
    expect(flagBelongsToStage('translation_rewritten_for_timing', 'timing_fit')).toBe(true);
  });

  it('rewrite_provider_failed принадлежит timing_fit', () => {
    expect(flagBelongsToStage('rewrite_provider_failed', 'timing_fit')).toBe(true);
  });

  it('tts_invalid_slot НЕ принадлежит timing_fit', () => {
    expect(flagBelongsToStage('tts_invalid_slot', 'timing_fit')).toBe(false);
  });

  it('translation_empty НЕ принадлежит timing_fit', () => {
    // translation_empty → принадлежит translate, не timing_fit
    expect(flagBelongsToStage('translation_empty', 'timing_fit')).toBe(false);
  });
});

describe('flagBelongsToStage — translate stage', () => {
  it('translation_empty принадлежит translate', () => {
    expect(flagBelongsToStage('translation_empty', 'translate')).toBe(true);
  });

  it('translation_fallback_source принадлежит translate', () => {
    expect(flagBelongsToStage('translation_fallback_source', 'translate')).toBe(true);
  });

  it('timing_fit_failed НЕ принадлежит translate', () => {
    expect(flagBelongsToStage('timing_fit_failed', 'translate')).toBe(false);
  });
});

describe('flagBelongsToStage — render stage', () => {
  it('render_audio_trimmed принадлежит render', () => {
    expect(flagBelongsToStage('render_audio_trimmed', 'render')).toBe(true);
  });

  it('timeline_audio_extends_video принадлежит render', () => {
    expect(flagBelongsToStage('timeline_audio_extends_video', 'render')).toBe(true);
  });

  it('tts_invalid_slot НЕ принадлежит render', () => {
    expect(flagBelongsToStage('tts_invalid_slot', 'render')).toBe(false);
  });
});

describe('flagBelongsToStage — unknown stage', () => {
  it('любой флаг НЕ принадлежит несуществующей стадии', () => {
    expect(flagBelongsToStage('tts_invalid_slot', 'unknown_stage')).toBe(false);
  });

  it('пустой список префиксов → всегда false', () => {
    expect(flagBelongsToStage('tts_overflow', 'export')).toBe(false);
  });
});

// ── filterFlagsByStage ────────────────────────────────────────────────────────

describe('filterFlagsByStage — регрессия TVIDEO-098', () => {
  it('При tts: timing_fit_* и translation_* флаги отфильтровываются', () => {
    // Именно эта ситуация была у пользователя: старые флаги видны во время TTS
    const allFlags = [
      'timing_fit_failed',           // от прошлого timing_fit запуска
      'translation_rewritten_for_timing', // от прошлого timing_fit
      'tts_invalid_slot',            // от текущего TTS
      'tts_overflow_natural_rate',   // от текущего TTS
    ];
    const result = filterFlagsByStage(allFlags, 'tts');
    expect(result).toContain('tts_invalid_slot');
    expect(result).toContain('tts_overflow_natural_rate');
    expect(result).not.toContain('timing_fit_failed');
    expect(result).not.toContain('translation_rewritten_for_timing');
  });

  it('При timing_fit: tts_* флаги отфильтровываются', () => {
    const allFlags = [
      'tts_invalid_slot',            // от прошлого TTS
      'timing_fit_failed',           // от текущего timing_fit
      'rewrite_provider_failed',     // от текущего timing_fit
    ];
    const result = filterFlagsByStage(allFlags, 'timing_fit');
    expect(result).toContain('timing_fit_failed');
    expect(result).toContain('rewrite_provider_failed');
    expect(result).not.toContain('tts_invalid_slot');
  });

  it('При activeStage=undefined: возвращаются все флаги', () => {
    const allFlags = ['timing_fit_failed', 'tts_invalid_slot', 'render_audio_trimmed'];
    const result = filterFlagsByStage(allFlags, undefined);
    expect(result).toEqual(allFlags);
  });

  it('Пустой список флагов → пустой результат', () => {
    expect(filterFlagsByStage([], 'tts')).toEqual([]);
  });

  it('Нет флагов принадлежащих текущей стадии → пустой результат', () => {
    const allFlags = ['timing_fit_failed', 'translation_empty'];
    const result = filterFlagsByStage(allFlags, 'tts');
    expect(result).toEqual([]);
  });
});

// ── STAGE_FLAG_PREFIXES — структурные проверки ────────────────────────────────

describe('STAGE_FLAG_PREFIXES — структура', () => {
  it('содержит все основные стадии', () => {
    expect(STAGE_FLAG_PREFIXES).toHaveProperty('translate');
    expect(STAGE_FLAG_PREFIXES).toHaveProperty('timing_fit');
    expect(STAGE_FLAG_PREFIXES).toHaveProperty('tts');
    expect(STAGE_FLAG_PREFIXES).toHaveProperty('render');
    expect(STAGE_FLAG_PREFIXES).toHaveProperty('export');
  });

  it('tts стадия включает только tts_ префикс', () => {
    expect(STAGE_FLAG_PREFIXES['tts']).toContain('tts_');
    expect(STAGE_FLAG_PREFIXES['tts']).not.toContain('timing_fit_');
  });

  it('timing_fit стадия включает rewrite_ (rewrite = часть timing)', () => {
    expect(STAGE_FLAG_PREFIXES['timing_fit']).toContain('rewrite_');
  });
});
