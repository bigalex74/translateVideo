import React from 'react';
import { CheckCircle2, AlertTriangle, X, Play, Loader2, Activity, AlertCircle, XCircle } from 'lucide-react';
import { t, stageLabel, statusLabel } from '../../i18n';
import type { ProjectDoctorReport, ProjectSnapshot, VideoProject, Segment } from '../../types/schemas';
import type { AppLocale } from '../../store/settings';
import { stageProgressInfo } from '../../progress';
import { subtitleExportUrl, subtitleExportZipUrl } from '../../api/client';

interface StatusPanelProps {
  project: VideoProject;
  projectId: string;
  locale: AppLocale;
  doctorReport: ProjectDoctorReport | null;
  setDoctorReport: React.Dispatch<React.SetStateAction<ProjectDoctorReport | null>>;
  doctorLoading: boolean;
  runDoctor: () => void;
  continueFromDoctor: () => void;
  isRunning: boolean;
  isDone: boolean;
  snapshots: ProjectSnapshot[];
  selectSegmentsWhere: (predicate: (s: Segment) => boolean) => void;
  qualityReport: Record<string, unknown> | null;
  fetchQualityReport: () => void;
  loadingQR: boolean;
}

export const StatusPanel: React.FC<StatusPanelProps> = ({
  project,
  projectId,
  locale,
  doctorReport,
  setDoctorReport,
  doctorLoading,
  runDoctor,
  continueFromDoctor,
  isRunning,
  isDone,
  snapshots,
  selectSegmentsWhere,
  qualityReport,
  fetchQualityReport,
  loadingQR,
}) => {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle2 size={16} className="text-success" />;
      case 'failed':    return <AlertCircle  size={16} className="text-danger" />;
      case 'cancelled': return <XCircle      size={16} className="text-muted" />;
      case 'running':   return <Loader2      size={16} className="text-warning animate-spin" />;
      default: return <div className="timeline-marker" />;
    }
  };

  return (
    <div className="right-tab-content">
      {doctorReport && (
        <div className={`doctor-panel doctor-panel--${doctorReport.ok ? 'ok' : 'warn'}`}>
          <div className="doctor-panel-head">
            <div className="doctor-panel-title">
              {doctorReport.ok
                ? <CheckCircle2 size={16} className="text-success" />
                : <AlertTriangle size={16} className="text-warning" />}
              <strong>Project Doctor</strong>
            </div>
            <button
              className="btn-icon doctor-close"
              title="Скрыть проверку"
              aria-label="Скрыть Project Doctor"
              onClick={() => setDoctorReport(null)}
            >
              <X size={14} />
            </button>
          </div>

          <div className="doctor-summary">
            <span>{doctorReport.ok ? 'Проблем не найдено' : `Найдено: ${doctorReport.issues.length}`}</span>
            {doctorReport.recommended_from_stage && (
              <span>
                Старт: <strong>{stageLabel(doctorReport.recommended_from_stage, locale)}</strong>
              </span>
            )}
          </div>

          {doctorReport.issues.length > 0 && (
            <ul className="doctor-issues">
              {doctorReport.issues.slice(0, 5).map((issue, index) => (
                <li key={`${issue.code}-${index}`} className={`doctor-issue doctor-issue--${issue.severity}`}>
                  <span className="doctor-issue-code">{issue.code.replace(/_/g, ' ')}</span>
                  <span className="doctor-issue-msg">
                    {issue.stage ? `${stageLabel(issue.stage, locale)}: ` : ''}
                    {issue.kind ? `${issue.kind}: ` : ''}
                    {issue.message}
                  </span>
                </li>
              ))}
              {doctorReport.issues.length > 5 && (
                <li className="doctor-issue doctor-issue--more">
                  Ещё {doctorReport.issues.length - 5}
                </li>
              )}
            </ul>
          )}

          {doctorReport.actions.length > 0 && (
            <div className="doctor-actions-list">
              {doctorReport.actions
                .filter(action => action.enabled)
                .slice(0, 4)
                .map(action => (
                  <span key={action.id} className="doctor-action-chip">
                    {action.id}: {action.from_stage ? stageLabel(action.from_stage, locale) : 'auto'}
                  </span>
                ))}
            </div>
          )}

          {doctorReport.segment_summary && (
            <div className="doctor-segment-summary">
              <span>Пустые: {doctorReport.segment_summary.empty_translations ?? 0}</span>
              <span>Без TTS: {doctorReport.segment_summary.missing_tts ?? 0}</span>
              <span>QA: {doctorReport.segment_summary.qa_flagged ?? 0}</span>
              <span>Не проверены: {doctorReport.segment_summary.unreviewed_issues ?? 0}</span>
            </div>
          )}

          {doctorReport.segment_actions && doctorReport.segment_actions.some(action => action.count > 0) && (
            <div className="doctor-panel-actions">
              {doctorReport.segment_actions
                .filter(action => action.count > 0)
                .map(action => (
                  <button
                    key={action.id}
                    className="btn-secondary btn-sm"
                    onClick={() => {
                      if (action.id === 'select-empty') {
                        selectSegmentsWhere(s => !(s.translated_text ?? '').trim());
                      } else if (action.id === 'select-missing-tts') {
                        selectSegmentsWhere(s => Boolean((s.translated_text ?? '').trim()) && !s.tts_path);
                      } else if (action.id === 'select-timing-failed') {
                        selectSegmentsWhere(s => (s.qa_flags ?? []).includes('timing_fit_failed'));
                      } else if (action.id === 'select-unreviewed-qa') {
                        selectSegmentsWhere(s => (s.qa_flags ?? []).length > 0 && !s.reviewed);
                      }
                    }}
                  >
                    {action.count} · {action.id.replace('select-', '')}
                  </button>
                ))}
            </div>
          )}

          <div className="doctor-panel-actions">
            <button
              className="btn-primary btn-sm"
              disabled={!doctorReport.recommended_from_stage || isRunning}
              onClick={continueFromDoctor}
            >
              <Play size={14} /> Продолжить безопасно
            </button>
            <button
              className="btn-secondary btn-sm"
              disabled={doctorLoading}
              onClick={runDoctor}
            >
              {doctorLoading ? <Loader2 size={14} className="animate-spin" /> : <Activity size={14} />}
              Проверить снова
            </button>
          </div>

          {snapshots.length > 0 && (
            <div className="doctor-snapshots">
              <span className="doctor-snapshots-title">Snapshots: {snapshots.length}</span>
              <ul>
                {snapshots.slice(0, 3).map(snapshot => (
                  <li key={snapshot.filename}>
                    <span>{snapshot.reason || snapshot.filename}</span>
                    {snapshot.created_at && (
                      <time dateTime={snapshot.created_at}>
                        {new Date(snapshot.created_at).toLocaleString(locale === 'ru' ? 'ru-RU' : 'en-US')}
                      </time>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Г7/В7: CTA "Скачать всё" после завершения */}
      {isDone && (
        <div className="download-all-cta">
          <span className="cta-label">✅ Перевод готов!</span>
          <a href={subtitleExportZipUrl(projectId)} target="_blank" rel="noreferrer"
            className="btn-primary btn-sm" style={{ textDecoration: 'none' }}>
            📦 Скачать всё (ZIP)
          </a>
          <a href={subtitleExportUrl(projectId, 'srt')} target="_blank" rel="noreferrer"
            className="btn-secondary btn-sm" style={{ textDecoration: 'none' }}>
            📄 SRT
          </a>
        </div>
      )}
      <ul className="timeline">
        {project.stage_runs?.map(run => {
          const progressInfo = stageProgressInfo(run);
          return (
            <li key={run.id} className={`timeline-item ${run.status}`}>
              <div className="timeline-icon">{getStatusIcon(run.status)}</div>
              <div className="timeline-content">
                <strong>{stageLabel(run.stage, locale)}</strong>
                <span className="status-text">{statusLabel(run.status, locale)}</span>
                {/* Z2.7: elapsed time */}
                {run.elapsed != null && run.elapsed > 0 && (
                  <span className="stage-elapsed">
                    {run.elapsed >= 60
                      ? `${Math.floor(run.elapsed / 60)}м ${Math.round(run.elapsed % 60)}с`
                      : `${Math.round(run.elapsed)}с`}
                  </span>
                )}
                {progressInfo && (
                  <div className="timeline-progress">
                    <div className="timeline-progress-head">
                      <span>{progressInfo.message ?? t('workspace.stageProgress', locale)}</span>
                      <strong>{progressInfo.label}</strong>
                    </div>
                    <div className="timeline-progress-track">
                      <div
                        className="timeline-progress-bar"
                        style={{ width: `${progressInfo.percent}%` }}
                      />
                    </div>
                  </div>
                )}
                {run.error && (
                  <div className="stage-error-block">
                    <span className="stage-error-label">⚠️ Произошла ошибка:</span>
                    <span className="stage-error-msg">
                      {run.error
                        .replace(/\/app\/runs\/[^/]+\//g, '')
                        .replace(/runs\/[^/]+\//g, '')
                        .replace(/File "\/[^"]+", line \d+/g, '')
                        .replace(/Traceback \(most recent call last\):/g, '')
                        .replace(/^\s+/gm, '')
                        .trim()
                        .slice(0, 240)}
                    </span>
                    <details className="stage-error-hint">
                      <summary>💡 Что делать?</summary>
                      <ul>
                        <li>Проверьте подключение к интернету</li>
                        <li>Убедитесь что API-ключ настроен в <strong>Настройках</strong></li>
                        <li>Попробуйте запустить перевод заново</li>
                      </ul>
                    </details>
                  </div>
                )}
              </div>
            </li>
          );
        })}
        {(!project.stage_runs || project.stage_runs.length === 0) && (
          <p className="empty-text">{t('dashboard.notStarted', locale)}</p>
        )}
      </ul>

      {/* Z3.11: Quality Report */}
      {project.status === 'completed' && (
        <div className="quality-report-section">
          <button
            className="btn-secondary btn-sm"
            onClick={fetchQualityReport}
            disabled={loadingQR}
          >
            {loadingQR ? '...' : '📊 Оценить качество перевода'}
          </button>
          {qualityReport && (
            <div className="quality-report-card">
              <div className="qr-grade-row">
                <span className={`qr-grade qr-grade--${String(qualityReport.grade).toLowerCase()}`}>
                  {String(qualityReport.grade)}
                </span>
                <span className="qr-grade-label">{String(qualityReport.grade_label)}</span>
                <span className="qr-issues">
                  {Number(qualityReport.segments_with_issues)} / {Number(qualityReport.segments_total)} сегментов с проблемами
                </span>
              </div>
              {Array.isArray(qualityReport.recommendations) && (
                <ul className="qr-recommendations">
                  {(qualityReport.recommendations as string[]).map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
