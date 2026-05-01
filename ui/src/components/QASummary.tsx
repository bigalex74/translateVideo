import React from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, XCircle } from 'lucide-react';
import { needsReviewCount } from '../i18n';
import type { Segment } from '../types/schemas';
import './QASummary.css';

interface QASummaryProps {
  segments: Segment[];
  projectStatus: string;
}

export const QASummary: React.FC<QASummaryProps> = ({ segments, projectStatus }) => {
  if (segments.length === 0) return null;

  const total = segments.length;
  const reviewCount = needsReviewCount(segments);
  const translatedCount = total - reviewCount;
  const coveragePercent = Math.round((translatedCount / total) * 100);

  // Сегменты с очень длинным текстом (>200 символов — риск обрезки в TTS)
  const longSegments = segments.filter(s => (s.translated_text ?? '').length > 200);
  // Сегменты с нулевой или очень короткой длительностью (< 0.3с)
  const shortSegments = segments.filter(s => {
    const dur = (s.end ?? 0) - (s.start ?? 0);
    return dur < 0.3 && dur >= 0;
  });

  const verdict: 'ok' | 'warn' | 'fail' =
    projectStatus !== 'completed' ? 'fail' :
    reviewCount === 0 && longSegments.length === 0 ? 'ok' :
    reviewCount < total * 0.1 ? 'warn' : 'fail';

  const verdictConfig = {
    ok:   { icon: <CheckCircle2 size={18} />, label: 'Готово к публикации',  className: 'qa-ok' },
    warn: { icon: <AlertTriangle size={18} />, label: 'Рекомендуется проверка', className: 'qa-warn' },
    fail: { icon: <XCircle size={18} />,       label: 'Требуется доработка',  className: 'qa-fail' },
  }[verdict];

  return (
    <div className={`qa-summary ${verdictConfig.className}`}>
      <div className="qa-verdict">
        {verdictConfig.icon}
        <strong>{verdictConfig.label}</strong>
      </div>

      <div className="qa-metrics">
        <div className="qa-metric">
          <span className="qa-metric-value">{coveragePercent}%</span>
          <span className="qa-metric-label">Переведено</span>
        </div>
        <div className="qa-metric">
          <span className={`qa-metric-value ${reviewCount > 0 ? 'qa-metric--warn' : ''}`}>
            {reviewCount}
          </span>
          <span className="qa-metric-label">Нужна проверка</span>
        </div>
        <div className="qa-metric">
          <span className={`qa-metric-value ${longSegments.length > 0 ? 'qa-metric--warn' : ''}`}>
            {longSegments.length}
          </span>
          <span className="qa-metric-label">Длинных фраз</span>
        </div>
        <div className="qa-metric">
          <span className={`qa-metric-value ${shortSegments.length > 0 ? 'qa-metric--warn' : ''}`}>
            {shortSegments.length}
          </span>
          <span className="qa-metric-label">{'Коротких (<0.3с)'}</span>
        </div>
      </div>

      {(reviewCount > 0 || longSegments.length > 0 || shortSegments.length > 0) && (
        <ul className="qa-issues">
          {reviewCount > 0 && (
            <li className="qa-issue qa-issue--warn">
              <AlertTriangle size={12} />
              {reviewCount} сегментов без перевода — исправьте вручную перед TTS
            </li>
          )}
          {longSegments.length > 0 && (
            <li className="qa-issue qa-issue--warn">
              <AlertTriangle size={12} />
              {longSegments.length} фраз длиннее 200 символов — возможна обрезка голосовым движком
            </li>
          )}
          {shortSegments.length > 0 && (
            <li className="qa-issue qa-issue--info">
              <AlertCircle size={12} />
              {shortSegments.length} сегментов короче 0.3с — голос может не успеть прочитать
            </li>
          )}
        </ul>
      )}
    </div>
  );
};
