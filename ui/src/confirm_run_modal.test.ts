/**
 * TVIDEO-077: тесты логики отображения предупреждения о сегментах в ConfirmRunModal.
 *
 * Проверяет правило:
 * - При isForce=true  — предупреждение «N сегментов не переведены» НЕ показывается.
 * - При isForce=false — показывается, если reviewCount > 0.
 */
import { describe, it, expect } from 'vitest';
import { needsReviewCount } from './i18n';

// Симуляция логики рендера из ConfirmRunModal.tsx:
// {!isForce && reviewCount > 0 && segments.length > 0 && <Warning/>}
function shouldShowReviewWarning(
  isForce: boolean,
  segments: Array<{ translated_text?: string; source_text: string }>,
): boolean {
  const reviewCount = needsReviewCount(segments);
  return !isForce && reviewCount > 0 && segments.length > 0;
}

const draftSegment = (id: number) => ({
  source_text: `Source text ${id}`,
  translated_text: '',
});

const translatedSegment = (id: number) => ({
  source_text: `Source text ${id}`,
  translated_text: `Translated text ${id}`,
});

describe('TVIDEO-077: ConfirmRunModal — reviewCount warning visibility', () => {
  it('force=true + все сегменты draft → предупреждение НЕ показывается', () => {
    const segments = [draftSegment(1), draftSegment(2), draftSegment(3)];
    expect(shouldShowReviewWarning(true, segments)).toBe(false);
  });

  it('force=true + смешанные сегменты → предупреждение НЕ показывается', () => {
    const segments = [translatedSegment(1), draftSegment(2), draftSegment(3)];
    expect(shouldShowReviewWarning(true, segments)).toBe(false);
  });

  it('force=true + все переведены → предупреждение НЕ показывается', () => {
    const segments = [translatedSegment(1), translatedSegment(2)];
    expect(shouldShowReviewWarning(true, segments)).toBe(false);
  });

  it('force=false + есть непереведённые → предупреждение показывается', () => {
    const segments = [draftSegment(1), draftSegment(2), draftSegment(3)];
    expect(shouldShowReviewWarning(false, segments)).toBe(true);
  });

  it('force=false + все переведены → предупреждение НЕ показывается', () => {
    const segments = [translatedSegment(1), translatedSegment(2)];
    expect(shouldShowReviewWarning(false, segments)).toBe(false);
  });

  it('force=false + пустые сегменты → предупреждение НЕ показывается', () => {
    expect(shouldShowReviewWarning(false, [])).toBe(false);
  });

  it('force=false + частично переведены → предупреждение показывается', () => {
    const segments = [translatedSegment(1), draftSegment(2), draftSegment(3)];
    expect(shouldShowReviewWarning(false, segments)).toBe(true);
  });

  it('reviewCount считает только непереведённые сегменты', () => {
    const segments = [
      translatedSegment(1),
      draftSegment(2),
      draftSegment(3),
      translatedSegment(4),
    ];
    expect(needsReviewCount(segments)).toBe(2);
  });
});
