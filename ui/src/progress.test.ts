import { describe, expect, it } from 'vitest';
import { stageProgressInfo } from './progress';
import type { StageRun } from './types/schemas';

const baseRun: StageRun = {
  id: 'stage_1',
  stage: 'timing_fit',
  status: 'running',
  inputs: [],
  outputs: [],
  attempt: 1,
};

describe('stageProgressInfo', () => {
  it('возвращает null для этапа без внутреннего прогресса', () => {
    expect(stageProgressInfo(baseRun)).toBeNull();
  });

  it('считает процент и подпись для прогресса этапа', () => {
    const result = stageProgressInfo({
      ...baseRun,
      progress_current: 7,
      progress_total: 10,
      progress_message: 'Сегмент 8/10',
    });

    expect(result).toEqual({
      current: 7,
      total: 10,
      percent: 70,
      label: '7/10',
      message: 'Сегмент 8/10',
    });
  });

  it('ограничивает current диапазоном total', () => {
    const result = stageProgressInfo({
      ...baseRun,
      progress_current: 15,
      progress_total: 10,
    });

    expect(result?.current).toBe(10);
    expect(result?.percent).toBe(100);
  });
});
