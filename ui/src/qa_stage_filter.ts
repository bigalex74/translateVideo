/**
 * qa_stage_filter.ts — фильтрация QA-флагов по стадии пайплайна.
 *
 * Используется в live-ленте прогресс-оверлея чтобы показывать
 * ТОЛЬКО флаги текущей выполняющейся стадии, а не флаги от
 * предыдущих запусков (timing_fit, translate, и т.д.).
 *
 * TVIDEO-098.
 */

/**
 * Какие flag-префиксы принадлежат каждой стадии пайплайна.
 * - Префикс с '_' на конце: flag.startsWith(prefix)
 * - Без '_': exact match
 */
export const STAGE_FLAG_PREFIXES: Record<string, string[]> = {
  translate:  ['translation_'],
  timing_fit: ['timing_fit_', 'translation_rewritten_for_timing', 'rewrite_'],
  tts:        ['tts_'],
  render:     ['render_', 'timeline_'],
  export:     [],
};

/**
 * Возвращает true если данный qa_flag принадлежит указанной стадии.
 *
 * Правила:
 * - Префикс оканчивающийся на '_' → flag.startsWith(prefix)
 * - Префикс без '_' на конце → flag === prefix (exact match)
 */
export function flagBelongsToStage(flag: string, stage: string): boolean {
  const prefixes = STAGE_FLAG_PREFIXES[stage] ?? [];
  return prefixes.some(p =>
    p.endsWith('_') ? flag.startsWith(p) : flag === p,
  );
}

/**
 * Фильтрует список флагов, оставляя только принадлежащие activeStage.
 * Если activeStage = undefined → возвращает все флаги (без фильтрации).
 */
export function filterFlagsByStage(flags: string[], activeStage: string | undefined): string[] {
  if (!activeStage) return flags;
  return flags.filter(f => flagBelongsToStage(f, activeStage));
}
