import type { StageRun } from './types/schemas';

export interface StageProgressInfo {
  current: number;
  total: number;
  percent: number;
  label: string;
  message?: string;
}

export function stageProgressInfo(run?: StageRun | null): StageProgressInfo | null {
  // Сервер заполняет эти поля только для долгих этапов с внутренним прогрессом.
  const total = run?.progress_total;
  if (typeof total !== 'number' || total <= 0) {
    return null;
  }

  const rawCurrent = typeof run?.progress_current === 'number' ? run.progress_current : 0;
  const current = Math.min(Math.max(0, rawCurrent), total);
  const percent = Math.round((current / total) * 100);

  return {
    current,
    total,
    percent,
    label: `${current}/${total}`,
    message: run?.progress_message ?? undefined,
  };
}
