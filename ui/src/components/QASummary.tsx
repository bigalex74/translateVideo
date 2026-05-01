import React from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, XCircle } from 'lucide-react';
import { needsReviewCount, t } from '../i18n';
import type { AppLocale } from '../store/settings';
import type { Segment } from '../types/schemas';
import './QASummary.css';

interface QASummaryProps {
  segments: Segment[];
  projectStatus: string;
  locale: AppLocale;
}

export const QASummary: React.FC<QASummaryProps> = ({ segments, projectStatus, locale }) => {
  if (segments.length === 0) return null;

  const total = segments.length;
  const reviewCount = needsReviewCount(segments);
  const translatedCount = total - reviewCount;
  const coveragePercent = Math.round((translatedCount / total) * 100);

  // Сегменты с очень длинным текстом (>200 символов — риск проблем с естественным таймингом)
  const longSegments = segments.filter(s => (s.translated_text ?? '').length > 200);
  // Сегменты с нулевой или очень короткой длительностью (< 0.3с)
  const shortSegments = segments.filter(s => {
    const dur = (s.end ?? 0) - (s.start ?? 0);
    return dur < 0.3 && dur >= 0;
  });
  const flaggedSegments = segments.filter(s => (s.qa_flags ?? []).length > 0);
  const qaFlags = Array.from(new Set(flaggedSegments.flatMap(s => s.qa_flags ?? [])));

  const verdict: 'ok' | 'warn' | 'fail' =
    projectStatus !== 'completed' ? 'fail' :
    reviewCount === 0 && longSegments.length === 0 ? 'ok' :
    reviewCount < total * 0.1 ? 'warn' : 'fail';

  const verdictConfig = {
    ok:   { icon: <CheckCircle2 size={18} />, label: t('qa.ready', locale),  className: 'qa-ok' },
    warn: { icon: <AlertTriangle size={18} />, label: t('qa.checkRecommended', locale), className: 'qa-warn' },
    fail: { icon: <XCircle size={18} />,       label: t('qa.needsWork', locale),  className: 'qa-fail' },
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
          <span className="qa-metric-label">{t('qa.translated', locale)}</span>
        </div>
        <div className="qa-metric">
          <span className={`qa-metric-value ${reviewCount > 0 ? 'qa-metric--warn' : ''}`}>
            {reviewCount}
          </span>
          <span className="qa-metric-label">{t('qa.needsReview', locale)}</span>
        </div>
        <div className="qa-metric">
          <span className={`qa-metric-value ${longSegments.length > 0 ? 'qa-metric--warn' : ''}`}>
            {longSegments.length}
          </span>
          <span className="qa-metric-label">{t('qa.longPhrases', locale)}</span>
        </div>
        <div className="qa-metric">
          <span className={`qa-metric-value ${shortSegments.length > 0 ? 'qa-metric--warn' : ''}`}>
            {shortSegments.length}
          </span>
          <span className="qa-metric-label">{t('qa.shortPhrases', locale)}</span>
        </div>
        <div className="qa-metric">
          <span className={`qa-metric-value ${flaggedSegments.length > 0 ? 'qa-metric--warn' : ''}`}>
            {flaggedSegments.length}
          </span>
          <span className="qa-metric-label">{t('qa.degradationFlags', locale)}</span>
        </div>
      </div>

      {(reviewCount > 0 || longSegments.length > 0 || shortSegments.length > 0 || qaFlags.length > 0) && (
        <ul className="qa-issues">
          {reviewCount > 0 && (
            <li className="qa-issue qa-issue--warn">
              <AlertTriangle size={12} />
              {reviewCount} {t('qa.untranslatedIssue', locale)}
            </li>
          )}
          {longSegments.length > 0 && (
            <li className="qa-issue qa-issue--warn">
              <AlertTriangle size={12} />
              {longSegments.length} {t('qa.longIssue', locale)}
            </li>
          )}
          {shortSegments.length > 0 && (
            <li className="qa-issue qa-issue--info">
              <AlertCircle size={12} />
              {shortSegments.length} {t('qa.shortIssue', locale)}
            </li>
          )}
          {qaFlags.map(flag => (
            <li key={flag} className="qa-issue qa-issue--warn">
              <AlertTriangle size={12} />
              {t(`qa.flag.${flag}`, locale)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
