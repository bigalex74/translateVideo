import React, { useState, useEffect, useRef } from 'react';
import { artifactDownloadUrl, getProjectStatus, runPipeline, saveProjectSegments, patchProjectConfig, cancelPipeline } from '../api/client';
import type { ArtifactRecord, VideoProject, Segment, PipelineConfig } from '../types/schemas';
import { stageLabel, statusLabel, t } from '../i18n';
import type { AppLocale } from '../store/settings';
import { stageProgressInfo } from '../progress';
import { QASummary } from './QASummary';
import { ConfirmRunModal } from './ConfirmRunModal';
import { AdvancedSettings } from './AdvancedSettings';
import { ArtifactCard } from './ArtifactCard';
import { StatsPanel } from './StatsPanel';
import { DevLogPanel } from './DevLogPanel';
import { getPersistedProvider } from '../store/settings';
import {
  ArrowLeft, Download, RefreshCw, Save, CheckCircle2,
  Loader2, AlertCircle, Undo2, Redo2, Settings, X,
  Film, AlignLeft, Activity, Play, XCircle, AlertTriangle, Info,
} from 'lucide-react';
import './Workspace.css';

interface WorkspaceProps {
  projectId: string;
  onBack: () => void;
  locale: AppLocale;
}

// Правая панель: вкладки
type RightTab = 'status' | 'qa' | 'artifacts' | 'stats' | 'devlog';

const API_VIDEO = '/api/v1/video';

export const Workspace: React.FC<WorkspaceProps> = ({ projectId, onBack, locale }) => {
  const [project, setProject] = useState<VideoProject | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelConfirm, setCancelConfirm] = useState(false);  // инлайн-подтверждение
  const [videoTab, setVideoTab] = useState<'source' | 'translated'>('source');
  const [rightTab, setRightTab] = useState<RightTab>('status');
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [confirm, setConfirm] = useState<{ force: boolean } | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [configPatch, setConfigPatch] = useState<Partial<PipelineConfig>>({});
  const [savingConfig, setSavingConfig] = useState(false);
  const [activeSegId, setActiveSegId] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  // Ссылки на DOM-узлы карточек сегментов для авто-скролла
  const segRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // Undo/redo история
  const [history, setHistory] = useState<Segment[][]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);

  // Авто-скролл к активному сегменту при воспроизведении
  useEffect(() => {
    if (!activeSegId) return;
    const node = segRefs.current.get(activeSegId);
    if (node) {
      node.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [activeSegId]);

  // Первоначальная загрузка
  useEffect(() => {
    let cancelled = false;
    void getProjectStatus(projectId)
      .then(data => {
        if (cancelled) return;
        setProject(data);
        const loadedSegments = Array.isArray(data.segments) ? data.segments : [];
        // История сбрасывается при смене проекта, чтобы undo не переносил сегменты.
        setHistory(loadedSegments.length > 0 ? [loadedSegments] : []);
        setHistoryIndex(loadedSegments.length > 0 ? 0 : -1);
        setDirty(false);
      })
      .catch(e => console.error(e));
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Поллинг статуса во время работы пайплайна.
  // При cancelling=true ускоряем до 500ms, чтобы overlay закрылся сразу после остановки.
  useEffect(() => {
    if (project?.status !== 'running') return;
    const interval = cancelling ? 500 : 2000;
    const poll = setInterval(async () => {
      try {
        const data = await getProjectStatus(projectId);
        // Во время поллинга не затираем локально отредактированные сегменты.
        setProject(prev => (prev && dirty ? { ...data, segments: prev.segments } : data));
        // Когда перевод завершился — сбрасываем состояние отмены
        if (data.status !== 'running') {
          setCancelling(false);
          setCancelConfirm(false);
        }
      } catch (e) {
        console.error('poll error', e);
      }
    }, interval);
    return () => clearInterval(poll);
  }, [cancelling, dirty, project?.status, projectId]);

  // ─── Live QA feed ─── (ДОЛЖЕН быть ДО любого раннего return — Rules of Hooks)
  const FLAG_SEV: Record<string, 'critical' | 'error' | 'warning' | 'info'> = {
    translation_empty: 'critical', tts_invalid_slot: 'critical',
    timing_fit_invalid_slot: 'critical', timeline_audio_extends_video: 'critical',
    translation_fallback_source: 'error', tts_overflow_after_rate: 'error',
    timing_fit_failed: 'error', render_audio_trimmed: 'error', timeline_shift_limit_reached: 'error',
    tts_overflow_natural_rate: 'warning', render_audio_overflow: 'warning',
    tts_rate_adapted: 'warning', translation_rewritten_for_timing: 'warning',
    rewrite_provider_failed: 'warning', render_speed_fallback: 'warning',
    tts_pretrim: 'warning', timeline_shifted: 'warning',
    rewrite_provider_quota_limited: 'warning', rewrite_provider_cooldown: 'warning',
  };
  type LiveSev = 'critical' | 'error' | 'warning' | 'info';
  interface LiveFlag { flag: string; sev: LiveSev; count: number; }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const liveFlags: LiveFlag[] = React.useMemo(() => {
    const isRunningNow = project?.status === 'running';
    if (!isRunningNow || !project) return [];
    const segs = Array.isArray(project.segments) ? (project.segments as Segment[]) : [];
    const counts: Record<string, number> = {};
    segs.forEach(seg =>
      (seg.qa_flags ?? []).forEach(f => { counts[f] = (counts[f] ?? 0) + 1; })
    );
    const SEV_ORDER: LiveSev[] = ['critical', 'error', 'warning', 'info'];
    return Object.entries(counts)
      .filter(([f]) => FLAG_SEV[f] !== 'info' && FLAG_SEV[f] !== undefined)
      .map(([flag, count]) => ({ flag, sev: FLAG_SEV[flag] ?? 'info' as LiveSev, count }))
      .sort((a, b) => SEV_ORDER.indexOf(a.sev) - SEV_ORDER.indexOf(b.sev));
  }, [project]);

  if (!project) return (
    <div className="workspace-loading">
      <Loader2 className="animate-spin text-accent" size={32} />
      <p>{t('workspace.loading', locale)}</p>
    </div>
  );

  const isRunning = project.status === 'running';
  const segments = Array.isArray(project.segments) ? (project.segments as Segment[]) : [];

  // ─── Running overlay ──────────────────────────────────────────────────────

  const runningStage = project.stage_runs?.find(r => r.status === 'running');
  const completedStages = project.stage_runs?.filter(r => r.status === 'completed') ?? [];
  const totalStages = project.stage_runs?.length ?? 0;
  const progress = totalStages > 0 ? Math.round((completedStages.length / totalStages) * 100) : 0;
  const runningStageProgress = stageProgressInfo(runningStage);


  const pushHistory = (newSegments: Segment[]) => {
    const newHistory = history.slice(0, historyIndex + 1).concat([newSegments]);
    const trimmed = newHistory.slice(-50);
    setHistory(trimmed);
    setHistoryIndex(trimmed.length - 1);
  };

  const handleTextChange = (segId: string, newText: string) => {
    setProject(prev => {
      if (!prev) return prev;
      const newSegments = (prev.segments as Segment[]).map(s =>
        s.id === segId ? { ...s, translated_text: newText } : s
      );
      pushHistory(newSegments);
      return { ...prev, segments: newSegments };
    });
    setDirty(true);
  };

  const undo = () => {
    if (historyIndex <= 0) return;
    const ni = historyIndex - 1;
    setHistoryIndex(ni);
    setProject(prev => prev ? { ...prev, segments: history[ni] } : prev);
    setDirty(true);
  };

  const redo = () => {
    if (historyIndex >= history.length - 1) return;
    const ni = historyIndex + 1;
    setHistoryIndex(ni);
    setProject(prev => prev ? { ...prev, segments: history[ni] } : prev);
    setDirty(true);
  };

  // ─── Save ─────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!dirty) return;
    setSaving(true);
    try {
      await saveProjectSegments(projectId, segments);
      setDirty(false);
      setMessage(t('workspace.segmentsSaved', locale));
      setTimeout(() => setMessage(''), 3000);
    } catch (e) {
      setMessage(`${t('workspace.saveError', locale)}: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSaving(false);
    }
  };

  // ─── Run ──────────────────────────────────────────────────────────────────

  const handleRunConfirmed = async (force: boolean) => {
    setConfirm(null);
    setMessage('');
    setRightTab('status');
    try {
      await runPipeline(projectId, force);
      // Оптимистично переключаем статус — поллинг подхватит реальный
      setProject(prev => prev ? { ...prev, status: 'running' } : prev);
      setCancelling(false);
      setCancelConfirm(false);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : t('workspace.runError', locale));
    }
  };

  // ─── Video URL ────────────────────────────────────────────────────────────

  const getVideoUrl = (): string => {
    // Используем стриминг-роут с поддержкой Range и правильным MIME
    if (videoTab === 'translated' && project.artifacts['output_video']) {
      return `${API_VIDEO}/${projectId}/${project.artifacts['output_video']}`;
    }
    return `${API_VIDEO}/${projectId}/input.mp4`;
  };

  // ─── Helpers ──────────────────────────────────────────────────────────────

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle2 size={16} className="text-success" />;
      case 'failed':    return <AlertCircle  size={16} className="text-danger" />;
      case 'running':   return <Loader2      size={16} className="text-warning animate-spin" />;
      default: return <div className="timeline-marker" />;
    }
  };

  const findArtifact = (kind: string): ArtifactRecord | undefined =>
    project.artifact_records?.find(r => r.kind === kind);

  const downloadableArtifacts = [
    { kind: 'subtitles',            label: '📄 Субтитры' },
    { kind: 'output_video',         label: '🎬 Готовое видео' },
    { kind: 'qa_report',            label: '✅ QA-отчёт' },
    { kind: 'translated_transcript', label: '📝 Перевод (JSON)' },
  ].filter(item => findArtifact(item.kind));

  const canUndo = historyIndex > 0;
  const canRedo = historyIndex < history.length - 1;

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="workspace fade-in">
      {/* ═══ Running Overlay ═══ */}
      {isRunning && (
        <div className="running-overlay" role="status" aria-live="polite">
          <div className="running-card">
            <Loader2 size={40} className="animate-spin running-spinner" />
            <h3>{cancelling ? 'Отмена перевода…' : t('workspace.running', locale)}</h3>
            {runningStage && (
              <p className="running-stage">
                ⚙️ {stageLabel(runningStage.stage, locale)}
              </p>
            )}
            {totalStages > 0 && (
              <div className="running-progress-wrap">
                <div className="running-progress-bar" style={{ width: `${progress}%` }} />
              </div>
            )}
            {runningStageProgress && (
              <div className="running-stage-progress" aria-label={t('workspace.stageProgress', locale)}>
                <div className="running-stage-progress-head">
                  <span>{runningStageProgress.message ?? t('workspace.stageProgress', locale)}</span>
                  <strong>{runningStageProgress.label}</strong>
                </div>
                <div className="running-progress-wrap running-progress-wrap-stage">
                  <div
                    className="running-progress-bar running-progress-bar-stage"
                    style={{ width: `${runningStageProgress.percent}%` }}
                  />
                </div>
              </div>
            )}

            {/* ── Live QA лента ── */}
            {liveFlags.length > 0 && (
              <div className="running-qa-feed">
                <div className="running-qa-feed-title">
                  <AlertTriangle size={11} />
                  QA: обнаружено в процессе
                </div>
                <ul className="running-qa-list">
                  {liveFlags.slice(0, 8).map(({ flag, sev, count }) => {
                    const icon = sev === 'critical' ? <XCircle size={10} />
                               : sev === 'error'    ? <AlertCircle size={10} />
                               : sev === 'warning'  ? <AlertTriangle size={10} />
                               :                      <Info size={10} />;
                    const label = t(`qa.flag.${flag}`, locale);
                    return (
                      <li key={flag} className={`running-qa-item running-qa-item--${sev}`}>
                        {icon}
                        <span className="running-qa-label">{label}</span>
                        <span className="running-qa-count">{count}</span>
                      </li>
                    );
                  })}
                  {liveFlags.length > 8 && (
                    <li className="running-qa-more">
                      … ещё {liveFlags.length - 8} предупреждений
                    </li>
                  )}
                </ul>
              </div>
            )}

            <p className="running-hint">
              {cancelling
                ? `Ожидаем завершения этапа «${runningStage ? stageLabel(runningStage.stage, locale) : '…'}» — после этого перевод остановится.`
                : t('workspace.runningHint', locale)
              }
            </p>

            {/* ── Инлайн-подтверждение / кнопка отмены ── */}
            {!cancelling && !cancelConfirm && (
              <button
                id="cancel-pipeline-btn"
                className="running-cancel-btn"
                onClick={() => setCancelConfirm(true)}
              >
                <X size={13} /> Отменить перевод
              </button>
            )}

            {!cancelling && cancelConfirm && (
              <div className="running-cancel-confirm">
                <p className="running-cancel-confirm-text">
                  <AlertTriangle size={13} />
                  Текущий этап дорабoтает до конца, затем перевод остановится.
                </p>
                <div className="running-cancel-confirm-actions">
                  <button
                    className="btn-secondary running-cancel-confirm-keep"
                    onClick={() => setCancelConfirm(false)}
                  >
                    Продолжить перевод
                  </button>
                  <button
                    id="cancel-pipeline-confirm-btn"
                    className="running-cancel-btn running-cancel-btn--confirm"
                    onClick={async () => {
                      setCancelConfirm(false);
                      setCancelling(true);
                      try {
                        await cancelPipeline(projectId);
                      } catch (e) {
                        console.error('cancel error', e);
                        setCancelling(false);
                      }
                    }}
                  >
                    <X size={13} /> Да, остановить
                  </button>
                </div>
              </div>
            )}

            {cancelling && (
              <div className="running-cancel-waiting">
                <Loader2 size={13} className="animate-spin" />
                Останавливаем перевод …
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══ Header ═══ */}
      <header className="workspace-header">
        {/* Строка 1: название + статус */}
        <div className="header-row header-row-title">
          <button onClick={onBack} className="btn-icon" title={t('workspace.back', locale)}>
            <ArrowLeft size={18} />
          </button>
          <h2 title={projectId}>{projectId}</h2>
          <span className={`badge ${project.status}`}>{statusLabel(project.status, locale)}</span>
        </div>
        {/* Строка 2: кнопки действий */}
        <div className="header-row header-row-actions">
          <div className="undo-redo-group">
            <button className="btn-icon" onClick={undo} disabled={!canUndo || isRunning} title="Отменить" aria-label="Отменить последнее изменение">
              <Undo2 size={15} />
            </button>
            <button className="btn-icon" onClick={redo} disabled={!canRedo || isRunning} title="Повторить" aria-label="Повторить отменённое изменение">
              <Redo2 size={15} />
            </button>
          </div>
          {/* Кнопки зависят от статуса проекта:
               created/completed → [▶ Запустить]
               failed             → [▶ Продолжить] [🔄 Перезапустить]
               completed          → [🔄 Перезапустить]
               running            → (ничего) */}
          {!isRunning && project.status === 'failed' && (
            <button
              className="btn-success btn-sm"
              onClick={() => setConfirm({ force: false })}
              title="Возобновить с проваленного этапа"
            >
              <Play size={14} /> {t('workspace.continue', locale)}
            </button>
          )}
          {!isRunning && (project.status === 'created' || project.status === 'failed' || project.status === 'completed') && (
            <button
              className="btn-secondary btn-sm"
              onClick={() => setConfirm({ force: true })}
              title={project.status === 'completed' ? 'Запустить все этапы заново' : 'Перезапустить всё с начала'}
            >
              <RefreshCw size={14} /> {project.status === 'completed' ? t('workspace.run', locale) : t('workspace.restart', locale)}
            </button>
          )}
          <button
            className="btn-icon"
            title={t('workspace.translationSettings', locale)}
            aria-label={t('workspace.translationSettings', locale)}
            onClick={() => setShowConfig(prev => !prev)}
          >
            <Settings size={15} />
          </button>
          <button
            className="btn-primary btn-sm"
            onClick={handleSave}
            disabled={!dirty || saving || isRunning}
            title={dirty ? t('workspace.saveSegments', locale) : t('workspace.noChanges', locale)}
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {t('workspace.save', locale)}{dirty ? ' *' : ''}
          </button>
        </div>
      </header>

      {/* ═══ Уведомление ═══ */}
      {message && (
        <div className="workspace-message" role="status">{message}</div>
      )}

      {/* ═══ Config Panel ═══ */}
      {showConfig && (
        <div className="workspace-config-panel glass-panel">
          <div className="config-panel-header">
            <h4>{t('workspace.translationSettings', locale)}</h4>
            <div className="config-panel-actions">
              <button
                className="btn-primary btn-sm"
                disabled={savingConfig || Object.keys(configPatch).length === 0}
                onClick={async () => {
                  if (!project || Object.keys(configPatch).length === 0) return;
                  setSavingConfig(true);
                  try {
                    const result = await patchProjectConfig(projectId, configPatch);
                    setProject(prev => prev ? { ...prev, config: result.config } : prev);
                    setConfigPatch({});
                    setMessage(t('workspace.settingsSaved', locale));
                    setTimeout(() => setMessage(''), 3000);
                    setShowConfig(false);  // закрываем панель после сохранения
                  } catch (e) {
                    setMessage(`${t('workspace.error', locale)}: ${e instanceof Error ? e.message : String(e)}`);
                  } finally {
                    setSavingConfig(false);
                  }
                }}
              >
                {savingConfig ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                {t('workspace.save', locale)}
              </button>
              <button
                className="btn-icon config-close-btn"
                title={t('workspace.closeSettings', locale)}
                aria-label={t('workspace.closeSettings', locale)}
                onClick={() => setShowConfig(false)}
              >
                <X size={16} />
              </button>
            </div>
          </div>
          <div className="adv-scroll-wrap">
            <AdvancedSettings
              config={{ ...(project.config ?? {}), ...configPatch }}
              onChange={patch => setConfigPatch(prev => ({ ...prev, ...patch }))}
              disabled={savingConfig}
            />
          </div>
        </div>
      )}

      {/* ═══ Main Layout: 2 колонки (видео + сегменты | статус) ═══ */}
      <div className="workspace-grid">

        {/* ── Левая область: видео + редактор ── */}
        <div className="workspace-left">

          {/* Видеоплеер */}
          <div className="panel video-panel glass-panel">
            <div className="panel-tabs">
              <button
                className={videoTab === 'source' ? 'active' : ''}
                onClick={() => setVideoTab('source')}
              >
                <Film size={14} /> {t('workspace.original', locale)}
              </button>
              <button
                className={videoTab === 'translated' ? 'active' : ''}
                onClick={() => setVideoTab('translated')}
                disabled={!findArtifact('output_video')}
                title={!findArtifact('output_video') ? t('workspace.outputNotReady', locale) : ''}
              >
                <Film size={14} /> {t('workspace.aiTranslation', locale)}
              </button>
            </div>
            <div className="video-container">
              <video
                ref={videoRef}
                controls
                src={getVideoUrl()}
                key={getVideoUrl()}
                onTimeUpdate={() => {
                  const t = videoRef.current?.currentTime ?? 0;
                  const active = segments.find(s => t >= s.start && t < s.end);
                  setActiveSegId(active?.id ?? null);
                }}
              >
                {project.artifacts['subtitles'] && (
                  <track
                    kind="subtitles"
                    src={`${API_VIDEO}/${projectId}/${project.artifacts['subtitles']}`}
                    srcLang="ru"
                    label="Русский"
                    default
                  />
                )}
              </video>
            </div>
          </div>

          {/* Редактор сегментов */}
          <div className="panel segments-panel glass-panel">
            <div className="panel-header">
              <h3><AlignLeft size={16} /> {t('workspace.translationEditor', locale)}</h3>
              <span className="text-sm text-muted">
                {segments.length} сегментов
                {dirty && <span className="dirty-indicator"> · {t('workspace.unsaved', locale)}</span>}
              </span>
            </div>
            <div className="segments-list">
              {segments.map((seg) => (
                <div
                  key={seg.id}
                  ref={(el) => {
                    if (el) segRefs.current.set(seg.id, el);
                    else segRefs.current.delete(seg.id);
                  }}
                  className={`segment-item ${seg.status}${activeSegId === seg.id ? ' segment-active' : ''}`}
                >
                  <div className="seg-header">
                    <span
                      className="seg-timing seg-timing--clickable"
                      title="Перейти к этому моменту в видео"
                      onClick={() => {
                        if (videoRef.current) {
                          videoRef.current.currentTime = seg.start;
                          videoRef.current.play().catch(() => {});
                        }
                      }}
                    >
                      {seg.start.toFixed(1)}с — {seg.end.toFixed(1)}с
                      <span className="seg-duration">({(seg.end - seg.start).toFixed(1)}с)</span>
                    </span>
                    <span className="seg-status">{statusLabel(seg.status ?? '', locale)}</span>
                  </div>
                  <div className="seg-source">{seg.source_text}</div>
                  <textarea
                    className={`seg-translated text-input ${!seg.translated_text?.trim() ? 'seg-empty' : ''}`}
                    value={seg.translated_text ?? ''}
                    onChange={(e) => handleTextChange(seg.id, e.target.value)}
                    placeholder={t('workspace.enterTranslation', locale)}
                    rows={2}
                  />
                </div>
              ))}
              {segments.length === 0 && !isRunning && (
                <div className="editor-empty-state">
                  <span className="editor-empty-icon">🎬</span>
                  <p className="editor-empty-title">{t('workspace.notStartedTitle', locale)}</p>
                  <p className="editor-empty-hint">
                    {t('workspace.notStartedHint', locale)}
                  </p>
                  <button
                    className="btn-primary"
                    onClick={() => setConfirm({ force: false })}
                  >
                    <RefreshCw size={16} /> {t('dashboard.run', locale)}
                  </button>
                </div>
              )}
              {segments.length === 0 && isRunning && (
                <div className="editor-empty-state">
                  <Loader2 size={32} className="animate-spin editor-empty-icon" />
                  <p className="editor-empty-title">{t('workspace.processing', locale)}</p>
                  <p className="editor-empty-hint">{t('workspace.processingHint', locale)}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Правая панель с вкладками ── */}
        <div className="workspace-right panel glass-panel">
          <div className="panel-tabs right-tabs">
            <button
              className={rightTab === 'status' ? 'active' : ''}
              onClick={() => setRightTab('status')}
            >
              <Activity size={14} /> {t('workspace.statusTab', locale)}
            </button>
            <button
              className={rightTab === 'qa' ? 'active' : ''}
              onClick={() => setRightTab('qa')}
              disabled={segments.length === 0}
            >
              QA
            </button>
            <button
              className={rightTab === 'artifacts' ? 'active' : ''}
              onClick={() => setRightTab('artifacts')}
            >
              <Download size={14} /> {t('workspace.filesTab', locale)}
            </button>
            <button
              className={rightTab === 'stats' ? 'active' : ''}
              onClick={() => setRightTab('stats')}
              title="Статистика перевода"
            >
              📊
            </button>
            <button
              className={rightTab === 'devlog' ? 'active' : ''}
              onClick={() => setRightTab('devlog')}
              title={`Режим разработчика${project.config?.dev_mode ? '' : ' (выключен)'}`}
            >
              🔧{project.config?.dev_mode ? '' : '·'}
            </button>
          </div>

          {/* Вкладка: Статус */}
          {rightTab === 'status' && (
            <div className="right-tab-content">
              <ul className="timeline">
                {project.stage_runs?.map(run => {
                  const progressInfo = stageProgressInfo(run);
                  return (
                    <li key={run.id} className={`timeline-item ${run.status}`}>
                      <div className="timeline-icon">{getStatusIcon(run.status)}</div>
                      <div className="timeline-content">
                        <strong>{stageLabel(run.stage, locale)}</strong>
                        <span className="status-text">{statusLabel(run.status, locale)}</span>
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
                            <span className="stage-error-label">{t('workspace.error', locale)}:</span>
                            <code className="stage-error-msg">
                              {run.error
                                .replace(/\/app\/runs\/[^/]+\//g, '')
                                .replace(/runs\/[^/]+\//g, '')
                                .slice(0, 200)}
                            </code>
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
            </div>
          )}

          {/* Вкладка: QA */}
          {rightTab === 'qa' && (
            <div className="right-tab-content">
              {segments.length > 0 ? (
                <QASummary segments={segments} projectStatus={project.status} locale={locale} />
              ) : (
                <p className="empty-text">{t('workspace.noSegments', locale)}</p>
              )}
            </div>
          )}

          {/* Вкладка: Файлы */}
          {rightTab === 'artifacts' && (
            <div className="right-tab-content">
              {project.artifact_records && project.artifact_records.length > 0 ? (
                project.artifact_records
                  .filter(r => r.kind !== 'settings')
                  .map(r => <ArtifactCard key={r.kind} record={r} projectId={projectId} locale={locale} />)
              ) : downloadableArtifacts.length > 0 ? (
                downloadableArtifacts.map(item => (
                  <a key={item.kind} className="artifact-link" href={artifactDownloadUrl(projectId, item.kind)} target="_blank" rel="noreferrer">
                    <Download size={14} /> {item.label}
                  </a>
                ))
              ) : (
                <p className="empty-text">{t('workspace.noResults', locale)}</p>
              )}
            </div>
          )}

          {/* Вкладка: Статистика */}
          {rightTab === 'stats' && (
            <div className="right-tab-content right-tab-content--flush">
              <StatsPanel projectId={projectId} />
            </div>
          )}

          {/* Вкладка: Dev Log */}
          {rightTab === 'devlog' && (
            <div className="right-tab-content right-tab-content--flush right-tab-content--devlog">
              <DevLogPanel
                projectId={projectId}
                devMode={project.config?.dev_mode ?? false}
              />
            </div>
          )}
        </div>
      </div>

      {confirm && (
        <ConfirmRunModal
          projectId={projectId}
          provider={getPersistedProvider()}
          isForce={confirm.force}
          segments={segments}
          locale={locale}
          onConfirm={() => handleRunConfirmed(confirm.force)}
          onCancel={() => setConfirm(null)}
        />
      )}
    </div>
  );
};
