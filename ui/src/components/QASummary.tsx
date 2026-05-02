import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, XCircle, ChevronDown, ChevronRight, Info } from 'lucide-react';
import { needsReviewCount, t } from '../i18n';
import type { AppLocale } from '../store/settings';
import type { Segment } from '../types/schemas';
import './QASummary.css';

interface QASummaryProps {
  segments: Segment[];
  projectStatus: string;
  locale: AppLocale;
}

// ── Классификация флагов по степени опасности ──────────────────────────────
// critical: контент может быть потерян или видео сломано
// error:    заметная деградация качества, требует ручной правки
// warning:  небольшая деградация, стоит проверить
// info:     информационные, не требуют действий

type Severity = 'critical' | 'error' | 'warning' | 'info';

const FLAG_SEVERITY: Record<string, Severity> = {
  // Критические — потеря контента
  translation_empty:                   'critical',
  tts_invalid_slot:                    'critical',
  timing_fit_invalid_slot:             'critical',
  timeline_audio_extends_video:        'critical',

  // Ошибки — заметная деградация
  translation_fallback_source:         'error',
  tts_overflow_after_rate:             'error',
  timing_fit_failed:                   'error',
  render_audio_trimmed:                'error',
  timeline_shift_limit_reached:        'error',

  // Предупреждения — стоит проверить
  tts_overflow_natural_rate:           'warning',
  render_audio_overflow:               'warning',
  tts_rate_adapted:                    'warning',
  translation_rewritten_for_timing:    'warning',
  rewrite_provider_failed:             'warning',
  render_speed_fallback:               'warning',
  tts_pretrim:                         'warning',
  timeline_shifted:                    'warning',

  // Информационные — норма работы
  rewrite_provider_used:               'info',
  rewrite_fallback_used:               'info',
  rewrite_provider_gemini:             'info',
  rewrite_provider_openrouter:         'info',
  rewrite_provider_aihubmix:           'info',
  rewrite_provider_polza:              'info',
  rewrite_provider_neuroapi:           'info',
  rewrite_provider_rule_based:         'info',
  render_audio_speedup:                'info',
  translation_llm:                     'info',
  translation_provider_used:           'info',
  translation_provider_gemini:         'info',
  translation_provider_openrouter:     'info',
  translation_provider_aihubmix:       'info',
  translation_provider_polza:          'info',
  translation_provider_neuroapi:       'info',
  rewrite_provider_quota_limited:      'warning',
  rewrite_provider_cooldown:           'warning',
  rewrite_provider_skipped:            'info',
};

const SEVERITY_ORDER: Severity[] = ['critical', 'error', 'warning', 'info'];

const SEVERITY_CONFIG: Record<Severity, {
  label: string;
  icon: React.ReactElement;
  color: string;
  bg: string;
  border: string;
}> = {
  critical: {
    label: 'Критично',
    icon: <XCircle size={13} />,
    color: '#f87171',
    bg: 'rgba(239,68,68,0.10)',
    border: 'rgba(239,68,68,0.25)',
  },
  error: {
    label: 'Ошибка',
    icon: <AlertCircle size={13} />,
    color: '#fb923c',
    bg: 'rgba(251,146,60,0.10)',
    border: 'rgba(251,146,60,0.25)',
  },
  warning: {
    label: 'Предупреждение',
    icon: <AlertTriangle size={13} />,
    color: '#fbbf24',
    bg: 'rgba(251,191,36,0.08)',
    border: 'rgba(251,191,36,0.20)',
  },
  info: {
    label: 'Информация',
    icon: <Info size={13} />,
    color: '#60a5fa',
    bg: 'rgba(59,130,246,0.07)',
    border: 'rgba(59,130,246,0.18)',
  },
};

function getSeverity(flag: string): Severity {
  return FLAG_SEVERITY[flag] ?? 'warning';
}

// Группа флагов одного уровня с привязкой к сегментам
interface FlagGroup {
  severity: Severity;
  flag: string;
  label: string;
  segments: Array<{ index: number; seg: Segment }>;
}

export const QASummary: React.FC<QASummaryProps> = ({ segments, projectStatus, locale }) => {
  const [expandedFlags, setExpandedFlags] = useState<Set<string>>(new Set());
  const [showInfo, setShowInfo] = useState(false);

  if (segments.length === 0) return null;

  const total = segments.length;
  const reviewCount = needsReviewCount(segments);
  const translatedCount = total - reviewCount;
  const coveragePercent = Math.round((translatedCount / total) * 100);

  const longSegments = segments.filter(s => (s.translated_text ?? '').length > 200);
  const shortSegments = segments.filter(s => {
    const dur = (s.end ?? 0) - (s.start ?? 0);
    return dur < 0.3 && dur >= 0;
  });

  // Собираем флаги сгруппированные по типу (flag → список сегментов с индексами)
  const flagMap: Record<string, Array<{ index: number; seg: Segment }>> = {};
  segments.forEach((seg, index) => {
    (seg.qa_flags ?? []).forEach(flag => {
      if (!flagMap[flag]) flagMap[flag] = [];
      flagMap[flag].push({ index, seg });
    });
  });

  // Строим FlagGroup[], сортированные по severity
  const flagGroups: FlagGroup[] = Object.entries(flagMap)
    .map(([flag, segs]) => ({
      severity: getSeverity(flag),
      flag,
      label: t(`qa.flag.${flag}`, locale),
      segments: segs,
    }))
    .sort((a, b) =>
      SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
    );

  const nonInfoGroups = flagGroups.filter(g => g.severity !== 'info');
  const infoGroups    = flagGroups.filter(g => g.severity === 'info');

  const criticalCount = flagGroups.filter(g => g.severity === 'critical').reduce((s, g) => s + g.segments.length, 0);
  const errorCount    = flagGroups.filter(g => g.severity === 'error').reduce((s, g) => s + g.segments.length, 0);
  const warningCount  = flagGroups.filter(g => g.severity === 'warning').reduce((s, g) => s + g.segments.length, 0);
  const infoCount     = flagGroups.filter(g => g.severity === 'info').reduce((s, g) => s + g.segments.length, 0);

  const verdict: 'ok' | 'warn' | 'fail' =
    projectStatus !== 'completed' ? 'fail' :
    criticalCount > 0 || errorCount > 0 ? 'fail' :
    reviewCount === 0 && longSegments.length === 0 && warningCount === 0 ? 'ok' :
    'warn';

  const verdictConfig = {
    ok:   { icon: <CheckCircle2 size={18} />, label: t('qa.ready', locale),           className: 'qa-ok' },
    warn: { icon: <AlertTriangle size={18} />, label: t('qa.checkRecommended', locale), className: 'qa-warn' },
    fail: { icon: <XCircle size={18} />,       label: t('qa.needsWork', locale),        className: 'qa-fail' },
  }[verdict];

  const toggleFlag = (flag: string) => {
    setExpandedFlags(prev => {
      const next = new Set(prev);
      next.has(flag) ? next.delete(flag) : next.add(flag);
      return next;
    });
  };

  const renderFlagGroup = (group: FlagGroup) => {
    const cfg = SEVERITY_CONFIG[group.severity];
    const isExpanded = expandedFlags.has(group.flag);
    const canExpand = group.segments.length > 0;

    return (
      <li
        key={group.flag}
        className="qa-flag-group"
        style={{
          background: cfg.bg,
          borderColor: cfg.border,
          color: cfg.color,
        }}
      >
        <div
          className="qa-flag-header"
          onClick={() => canExpand && toggleFlag(group.flag)}
          style={{ cursor: canExpand ? 'pointer' : 'default' }}
        >
          <span className="qa-flag-severity-icon">{cfg.icon}</span>
          <span className="qa-flag-text">{group.label}</span>
          <span className="qa-flag-count" style={{ background: cfg.border }}>
            {group.segments.length}
          </span>
          {canExpand && (
            <span className="qa-flag-expand">
              {isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
            </span>
          )}
        </div>

        {/* Список сегментов */}
        {isExpanded && group.segments.length > 0 && (
          <ul className="qa-flag-segments">
            {group.segments.slice(0, 12).map(({ index, seg }) => {
              const timeStr = `${seg.start?.toFixed(1)}с`;
              const preview = (seg.source_text ?? '').slice(0, 60) + ((seg.source_text ?? '').length > 60 ? '…' : '');
              return (
                <li key={seg.id} className="qa-seg-item">
                  <span className="qa-seg-num">#{index + 1}</span>
                  <span className="qa-seg-time">{timeStr}</span>
                  <span className="qa-seg-text">{preview}</span>
                </li>
              );
            })}
            {group.segments.length > 12 && (
              <li className="qa-seg-more">… ещё {group.segments.length - 12} сегм.</li>
            )}
          </ul>
        )}
      </li>
    );
  };

  return (
    <div className={`qa-summary ${verdictConfig.className}`}>
      {/* Вердикт */}
      <div className="qa-verdict">
        {verdictConfig.icon}
        <strong>{verdictConfig.label}</strong>
      </div>

      {/* Метрики */}
      <div className="qa-metrics">
        <div className="qa-metric">
          <span className="qa-metric-value">{coveragePercent}%</span>
          <span className="qa-metric-label">{t('qa.translated', locale)}</span>
        </div>
        <div className="qa-metric">
          <span className={`qa-metric-value ${reviewCount > 0 ? 'qa-metric--error' : ''}`}>
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
          <span className={`qa-metric-value ${shortSegments.length > 0 ? 'qa-metric--info' : ''}`}>
            {shortSegments.length}
          </span>
          <span className="qa-metric-label">{t('qa.shortPhrases', locale)}</span>
        </div>
      </div>

      {/* Полоска severity summary */}
      {(criticalCount + errorCount + warningCount + infoCount) > 0 && (
        <div className="qa-severity-bar">
          {criticalCount > 0 && (
            <span className="qa-sev-badge qa-sev-critical">
              <XCircle size={10} /> {criticalCount} крит.
            </span>
          )}
          {errorCount > 0 && (
            <span className="qa-sev-badge qa-sev-error">
              <AlertCircle size={10} /> {errorCount} ошиб.
            </span>
          )}
          {warningCount > 0 && (
            <span className="qa-sev-badge qa-sev-warning">
              <AlertTriangle size={10} /> {warningCount} предупр.
            </span>
          )}
          {infoCount > 0 && (
            <span className="qa-sev-badge qa-sev-info">
              <Info size={10} /> {infoCount} инфо
            </span>
          )}
        </div>
      )}

      {/* Структурные проблемы */}
      {(reviewCount > 0 || longSegments.length > 0 || shortSegments.length > 0) && (
        <ul className="qa-issues">
          {reviewCount > 0 && (
            <li className="qa-flag-group" style={{
              background: SEVERITY_CONFIG.critical.bg,
              borderColor: SEVERITY_CONFIG.critical.border,
              color: SEVERITY_CONFIG.critical.color,
            }}>
              <div className="qa-flag-header">
                <span className="qa-flag-severity-icon">{SEVERITY_CONFIG.critical.icon}</span>
                <span className="qa-flag-text">
                  {reviewCount} {t('qa.untranslatedIssue', locale)}
                </span>
              </div>
            </li>
          )}
          {longSegments.length > 0 && (
            <li className="qa-flag-group" style={{
              background: SEVERITY_CONFIG.warning.bg,
              borderColor: SEVERITY_CONFIG.warning.border,
              color: SEVERITY_CONFIG.warning.color,
            }}>
              <div className="qa-flag-header">
                <span className="qa-flag-severity-icon">{SEVERITY_CONFIG.warning.icon}</span>
                <span className="qa-flag-text">
                  {longSegments.length} {t('qa.longIssue', locale)}
                </span>
              </div>
            </li>
          )}
          {shortSegments.length > 0 && (
            <li className="qa-flag-group" style={{
              background: SEVERITY_CONFIG.info.bg,
              borderColor: SEVERITY_CONFIG.info.border,
              color: SEVERITY_CONFIG.info.color,
            }}>
              <div className="qa-flag-header">
                <span className="qa-flag-severity-icon">{SEVERITY_CONFIG.info.icon}</span>
                <span className="qa-flag-text">
                  {shortSegments.length} {t('qa.shortIssue', locale)}
                </span>
              </div>
            </li>
          )}
        </ul>
      )}

      {/* Флаги с раскрытием сегментов */}
      {nonInfoGroups.length > 0 && (
        <ul className="qa-issues">
          {nonInfoGroups.map(renderFlagGroup)}
        </ul>
      )}

      {/* Информационные флаги — скрыты по умолчанию */}
      {infoGroups.length > 0 && (
        <div className="qa-info-section">
          <button className="qa-info-toggle" onClick={() => setShowInfo(v => !v)}>
            <Info size={11} />
            Технические события: {infoGroups.length} типов, {infoCount} сегм.
            {showInfo ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </button>
          {showInfo && (
            <ul className="qa-issues qa-issues--info-block">
              {infoGroups.map(renderFlagGroup)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};
