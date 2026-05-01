import React, { useState, useEffect, useCallback, useRef } from 'react';
import { artifactDownloadUrl, getProjectStatus, runPipeline, saveProjectSegments, patchProjectConfig } from '../api/client';
import type { ArtifactRecord, VideoProject, Segment, PipelineConfig } from '../types/schemas';
import { stageLabel, statusLabel } from '../i18n';
import { QASummary } from './QASummary';
import { ConfirmRunModal } from './ConfirmRunModal';
import { AdvancedSettings } from './AdvancedSettings';
import { ArtifactCard } from './ArtifactCard';
import { getPersistedProvider } from './Settings';
import {
  ArrowLeft, Download, RefreshCw, Save, CheckCircle2,
  Loader2, AlertCircle, Undo2, Redo2, Settings,
  Film, AlignLeft, Activity,
} from 'lucide-react';
import './Workspace.css';

interface WorkspaceProps {
  projectId: string;
  onBack: () => void;
}

// Правая панель: вкладки
type RightTab = 'status' | 'qa' | 'artifacts';

const API_VIDEO = '/api/v1/video';

export const Workspace: React.FC<WorkspaceProps> = ({ projectId, onBack }) => {
  const [project, setProject] = useState<VideoProject | null>(null);
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

  // Undo/redo история
  const [history, setHistory] = useState<Segment[][]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);

  const loadProject = useCallback(async (skipIfDirty = true) => {
    if (skipIfDirty && dirty) return;
    try {
      const data = await getProjectStatus(projectId);
      setProject(data);
    } catch (e) {
      console.error(e);
    }
  }, [projectId, dirty]);

  useEffect(() => {
    loadProject(false);
    // Быстрый polling пока running, обычный иначе
    const fast = setInterval(() => loadProject(true), 2000);
    return () => clearInterval(fast);
  }, [loadProject]);

  // Инициализировать историю при первой загрузке сегментов
  useEffect(() => {
    if (!project || !Array.isArray(project.segments) || history.length > 0) return;
    const segs = project.segments as Segment[];
    if (segs.length > 0) {
      setHistory([segs]);
      setHistoryIndex(0);
    }
  }, [project, history.length]);

  if (!project) return (
    <div className="workspace-loading">
      <Loader2 className="animate-spin text-accent" size={32} />
      <p>Загрузка редактора…</p>
    </div>
  );

  const isRunning = project.status === 'running';
  const segments = Array.isArray(project.segments) ? (project.segments as Segment[]) : [];

  // ─── Running overlay ──────────────────────────────────────────────────────

  const runningStage = project.stage_runs?.find(r => r.status === 'running');
  const completedStages = project.stage_runs?.filter(r => r.status === 'completed') ?? [];
  const totalStages = project.stage_runs?.length ?? 0;
  const progress = totalStages > 0 ? Math.round((completedStages.length / totalStages) * 100) : 0;

  // ─── History ──────────────────────────────────────────────────────────────

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
      setMessage('✓ Сегменты сохранены');
      setTimeout(() => setMessage(''), 3000);
    } catch (e) {
      setMessage(`Ошибка сохранения: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSaving(false);
    }
  };

  // ─── Run ──────────────────────────────────────────────────────────────────

  const handleRunConfirmed = async (force: boolean) => {
    setConfirm(null);
    // Оптимистично переключаем статус чтобы лоадер появился немедленно
    setProject(prev => prev ? { ...prev, status: 'running' } : prev);
    setMessage('');
    setRightTab('status');
    try {
      await runPipeline(projectId, force);
      await loadProject(false);
    } catch (e) {
      setProject(prev => prev ? { ...prev, status: 'failed' } : prev);
      setMessage(e instanceof Error ? e.message : 'Не удалось запустить обработку');
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
            <h3>Идёт обработка…</h3>
            {runningStage && (
              <p className="running-stage">
                ⚙️ {stageLabel(runningStage.stage)}
              </p>
            )}
            {totalStages > 0 && (
              <div className="running-progress-wrap">
                <div className="running-progress-bar" style={{ width: `${progress}%` }} />
              </div>
            )}
            <p className="running-hint">
              Страница обновляется автоматически. Можно закрыть вкладку — перевод продолжится на сервере.
            </p>
          </div>
        </div>
      )}

      {/* ═══ Header ═══ */}
      <header className="workspace-header">
        <div className="header-left">
          <button onClick={onBack} className="btn-icon" title="Назад к списку проектов">
            <ArrowLeft size={20} />
          </button>
          <h2 title={projectId}>{projectId}</h2>
          <span className={`badge ${project.status}`}>{statusLabel(project.status)}</span>
        </div>
        <div className="header-right">
          <div className="undo-redo-group">
            <button className="btn-icon" onClick={undo} disabled={!canUndo || isRunning} title="Отменить" aria-label="Отменить последнее изменение">
              <Undo2 size={16} />
            </button>
            <button className="btn-icon" onClick={redo} disabled={!canRedo || isRunning} title="Повторить" aria-label="Повторить отменённое изменение">
              <Redo2 size={16} />
            </button>
          </div>
          {!isRunning && (
            <button className="btn-secondary" onClick={() => setConfirm({ force: false })}>
              <RefreshCw size={16} /> Запустить
            </button>
          )}
          {!isRunning && (
            <button className="btn-secondary" onClick={() => setConfirm({ force: true })}>
              <RefreshCw size={16} /> Перезапустить
            </button>
          )}
          <button
            className="btn-icon"
            title="Настройки перевода"
            aria-label="Настройки перевода"
            onClick={() => setShowConfig(prev => !prev)}
          >
            <Settings size={16} />
          </button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={!dirty || saving || isRunning}
            title={dirty ? 'Сохранить правки сегментов' : 'Нет несохранённых изменений'}
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            Сохранить{dirty ? ' *' : ''}
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
            <h4>Настройки перевода</h4>
            <button
              className="btn-primary"
              disabled={savingConfig || Object.keys(configPatch).length === 0}
              onClick={async () => {
                if (!project || Object.keys(configPatch).length === 0) return;
                setSavingConfig(true);
                try {
                  const result = await patchProjectConfig(projectId, configPatch);
                  setProject(prev => prev ? { ...prev, config: result.config } : prev);
                  setConfigPatch({});
                  setMessage('✓ Настройки сохранены');
                  setTimeout(() => setMessage(''), 3000);
                } catch (e) {
                  setMessage(`Ошибка: ${e instanceof Error ? e.message : String(e)}`);
                } finally {
                  setSavingConfig(false);
                }
              }}
            >
              {savingConfig ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              Сохранить настройки
            </button>
          </div>
          <AdvancedSettings
            config={{ ...(project.config ?? {}), ...configPatch }}
            onChange={patch => setConfigPatch(prev => ({ ...prev, ...patch }))}
            disabled={savingConfig}
          />
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
                <Film size={14} /> Оригинал
              </button>
              <button
                className={videoTab === 'translated' ? 'active' : ''}
                onClick={() => setVideoTab('translated')}
                disabled={!findArtifact('output_video')}
                title={!findArtifact('output_video') ? 'Готовое видео ещё не создано' : ''}
              >
                <Film size={14} /> Перевод ИИ
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
              <h3><AlignLeft size={16} /> Редактор перевода</h3>
              <span className="text-sm text-muted">
                {segments.length} сегментов
                {dirty && <span className="dirty-indicator"> · Несохранённые правки</span>}
              </span>
            </div>
            <div className="segments-list">
              {segments.map((seg) => (
                <div key={seg.id} className={`segment-item ${seg.status}${activeSegId === seg.id ? ' segment-active' : ''}`}>
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
                    <span className="seg-status">{statusLabel(seg.status ?? '')}</span>
                  </div>
                  <div className="seg-source">{seg.source_text}</div>
                  <textarea
                    className={`seg-translated text-input ${!seg.translated_text?.trim() ? 'seg-empty' : ''}`}
                    value={seg.translated_text ?? ''}
                    onChange={(e) => handleTextChange(seg.id, e.target.value)}
                    placeholder="Введите перевод…"
                    rows={2}
                  />
                </div>
              ))}
              {segments.length === 0 && (
                <div className="empty-text">
                  <p>Транскрипт пока недоступен.</p>
                  <small>Дождитесь завершения этапа «Распознавание речи».</small>
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
              <Activity size={14} /> Статус
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
              <Download size={14} /> Файлы
            </button>
          </div>

          {/* Вкладка: Статус */}
          {rightTab === 'status' && (
            <div className="right-tab-content">
              <ul className="timeline">
                {project.stage_runs?.map(run => (
                  <li key={run.id} className={`timeline-item ${run.status}`}>
                    <div className="timeline-icon">{getStatusIcon(run.status)}</div>
                    <div className="timeline-content">
                      <strong>{stageLabel(run.stage)}</strong>
                      <span className="status-text">{statusLabel(run.status)}</span>
                      {run.error && <div className="error-text text-sm">{run.error}</div>}
                    </div>
                  </li>
                ))}
                {(!project.stage_runs || project.stage_runs.length === 0) && (
                  <p className="empty-text">Обработка ещё не запускалась.</p>
                )}
              </ul>
            </div>
          )}

          {/* Вкладка: QA */}
          {rightTab === 'qa' && (
            <div className="right-tab-content">
              {segments.length > 0 ? (
                <QASummary segments={segments} projectStatus={project.status} />
              ) : (
                <p className="empty-text">Нет сегментов для анализа.</p>
              )}
            </div>
          )}

          {/* Вкладка: Файлы */}
          {rightTab === 'artifacts' && (
            <div className="right-tab-content">
              {project.artifact_records && project.artifact_records.length > 0 ? (
                project.artifact_records
                  .filter(r => r.kind !== 'settings')
                  .map(r => <ArtifactCard key={r.kind} record={r} projectId={projectId} />)
              ) : downloadableArtifacts.length > 0 ? (
                downloadableArtifacts.map(item => (
                  <a key={item.kind} className="artifact-link" href={artifactDownloadUrl(projectId, item.kind)} target="_blank" rel="noreferrer">
                    <Download size={14} /> {item.label}
                  </a>
                ))
              ) : (
                <p className="empty-text">Результаты ещё не готовы.</p>
              )}
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
          onConfirm={() => handleRunConfirmed(confirm.force)}
          onCancel={() => setConfirm(null)}
        />
      )}
    </div>
  );
};
