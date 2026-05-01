import React, { useState, useEffect, useCallback } from 'react';
import { artifactDownloadUrl, getProjectStatus, runPipeline, saveProjectSegments, patchProjectConfig } from '../api/client';
import type { ArtifactRecord, VideoProject, Segment, PipelineConfig } from '../types/schemas';
import { stageLabel, statusLabel } from '../i18n';
import { QASummary } from './QASummary';
import { ConfirmRunModal } from './ConfirmRunModal';
import { AdvancedSettings } from './AdvancedSettings';
import {
  ArrowLeft, Download, RefreshCw, Save, CheckCircle2,
  Loader2, AlertCircle, Undo2, Redo2, Settings
} from 'lucide-react';
import './Workspace.css';

interface WorkspaceProps {
  projectId: string;
  onBack: () => void;
}

export const Workspace: React.FC<WorkspaceProps> = ({ projectId, onBack }) => {
  const [project, setProject] = useState<VideoProject | null>(null);
  const [activeTab, setActiveTab] = useState<'source' | 'translated' | 'subtitles'>('source');
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [confirm, setConfirm] = useState<{ force: boolean } | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [configPatch, setConfigPatch] = useState<Partial<PipelineConfig>>({});
  const [savingConfig, setSavingConfig] = useState(false);

  // Undo/redo история: массив снапшотов segments
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
    const interval = setInterval(() => loadProject(true), 5000);
    return () => clearInterval(interval);
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

  const segments = Array.isArray(project.segments) ? (project.segments as Segment[]) : [];

  const pushHistory = (newSegments: Segment[]) => {
    const newHistory = history.slice(0, historyIndex + 1).concat([newSegments]);
    // Ограничиваем глубину истории 50 шагами
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
    const newIndex = historyIndex - 1;
    setHistoryIndex(newIndex);
    setProject(prev => prev ? { ...prev, segments: history[newIndex] } : prev);
    setDirty(true);
  };

  const redo = () => {
    if (historyIndex >= history.length - 1) return;
    const newIndex = historyIndex + 1;
    setHistoryIndex(newIndex);
    setProject(prev => prev ? { ...prev, segments: history[newIndex] } : prev);
    setDirty(true);
  };

  const handleSave = async () => {
    if (!project || !Array.isArray(project.segments)) return;
    setSaving(true);
    setMessage('');
    try {
      const saved = await saveProjectSegments(projectId, project.segments as Segment[]);
      setProject(saved);
      setDirty(false);
      setMessage('✅ Правки сохранены.');
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Не удалось сохранить сегменты');
    } finally {
      setSaving(false);
    }
  };

  const handleRunConfirmed = async (force: boolean) => {
    setConfirm(null);
    setMessage('');
    try {
      await runPipeline(projectId, force, 'fake');
      await loadProject(false);
      setMessage(force ? '🔄 Полный перезапуск запущен.' : '▶️ Обработка запущена.');
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Не удалось запустить обработку');
    }
  };

  const getVideoUrl = () => {
    const base = `/runs/${projectId}`;
    if (activeTab === 'translated' && project.artifacts['output_video']) {
      return `${base}/${project.artifacts['output_video']}`;
    }
    return `${base}/input.mp4`;
  };

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

  return (
    <div className="workspace fade-in">
      <header className="workspace-header">
        <div className="header-left">
          <button onClick={onBack} className="btn-icon" title="Назад к списку проектов">
            <ArrowLeft size={20} />
          </button>
          <h2>{projectId}</h2>
          <span className={`badge ${project.status}`}>{statusLabel(project.status)}</span>
        </div>
        <div className="header-right">
          <div className="undo-redo-group">
            <button
              className="btn-icon"
              onClick={undo}
              disabled={!canUndo}
              title={`Отменить (${historyIndex} шаг(ов) назад)`}
              aria-label="Отменить последнее изменение"
            >
              <Undo2 size={16} />
            </button>
            <button
              className="btn-icon"
              onClick={redo}
              disabled={!canRedo}
              title="Повторить"
              aria-label="Повторить отменённое изменение"
            >
              <Redo2 size={16} />
            </button>
          </div>
          {project.status !== 'running' && (
            <button className="btn-secondary" onClick={() => setConfirm({ force: false })}>
              <RefreshCw size={16} /> Запустить
            </button>
          )}
          {project.status !== 'running' && (
            <button className="btn-secondary" onClick={() => setConfirm({ force: true })}>
              <RefreshCw size={16} /> Перезапустить всё
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
            disabled={!dirty || saving}
            title={dirty ? 'Сохранить правки сегментов' : 'Нет несохранённых изменений'}
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            Сохранить{dirty ? ' *' : ''}
          </button>
        </div>
      </header>

      {message && (
        <div className="workspace-message" role="status">{message}</div>
      )}

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

      <div className="workspace-grid">
        {/* Left: Видеоплеер */}
        <div className="panel video-panel glass-panel">
          <div className="panel-tabs">
            <button className={activeTab === 'source' ? 'active' : ''} onClick={() => setActiveTab('source')}>
              Оригинал
            </button>
            <button className={activeTab === 'translated' ? 'active' : ''} onClick={() => setActiveTab('translated')}>
              Озвучка ИИ
            </button>
            <button className={activeTab === 'subtitles' ? 'active' : ''} onClick={() => setActiveTab('subtitles')}>
              Субтитры
            </button>
          </div>
          <div className="video-container">
            <video controls src={getVideoUrl()} key={getVideoUrl()}>
              {activeTab === 'subtitles' && project.artifacts['subtitles'] && (
                <track
                  kind="subtitles"
                  src={`/runs/${projectId}/${project.artifacts['subtitles']}`}
                  srcLang="ru"
                  label="Russian"
                  default
                />
              )}
              Ваш браузер не поддерживает элемент video.
            </video>
          </div>
        </div>

        {/* Center: Редактор сегментов */}
        <div className="panel segments-panel glass-panel">
          <div className="panel-header">
            <h3>Редактор перевода</h3>
            <span className="text-sm text-muted">
              {segments.length} сегментов
              {dirty && <span className="dirty-indicator"> · Есть несохранённые правки</span>}
            </span>
          </div>
          <div className="segments-list">
            {segments.map((seg) => (
              <div key={seg.id} className={`segment-item ${seg.status}`}>
                <div className="seg-header">
                  <span className="seg-timing">
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

        {/* Right: Прогресс + QA + Артефакты */}
        <div className="panel progress-panel glass-panel">
          <div className="panel-header">
            <h3>Статус обработки</h3>
          </div>

          {/* QA Summary */}
          {segments.length > 0 && (
            <div className="qa-section">
              <QASummary segments={segments} projectStatus={project.status} />
            </div>
          )}

          {/* Скачиваемые артефакты */}
          <div className="artifact-downloads">
            <h4>Результаты</h4>
            {downloadableArtifacts.map(item => (
              <a
                key={item.kind}
                className="artifact-link"
                href={artifactDownloadUrl(projectId, item.kind)}
                target="_blank"
                rel="noreferrer"
              >
                <Download size={14} /> {item.label}
              </a>
            ))}
            {downloadableArtifacts.length === 0 && (
              <p className="empty-text">Результаты ещё не готовы.</p>
            )}
          </div>

          {/* Timeline этапов */}
          <div className="timeline-container">
            <ul className="timeline">
              {project.stage_runs?.map(run => (
                <li key={run.id} className={`timeline-item ${run.status}`}>
                  <div className="timeline-icon">
                    {getStatusIcon(run.status)}
                  </div>
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
        </div>
      </div>

      {confirm && (
        <ConfirmRunModal
          projectId={projectId}
          provider="fake"
          isForce={confirm.force}
          segments={segments}
          onConfirm={() => handleRunConfirmed(confirm.force)}
          onCancel={() => setConfirm(null)}
        />
      )}
    </div>
  );
};
