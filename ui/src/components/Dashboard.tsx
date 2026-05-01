import React, { useState, useEffect, useCallback } from 'react';
import { getProjectStatus, listProjects, runPipeline } from '../api/client';
import type { VideoProject, Segment } from '../types/schemas';
import { stageLabel, statusLabel, STATUS_EMOJI } from '../i18n';
import { ConfirmRunModal } from './ConfirmRunModal';
import {
  Play, FolderOpen, AlertCircle, CheckCircle2, Loader2,
  ArrowRight, RefreshCw, Clock, Search
} from 'lucide-react';
import './Dashboard.css';

interface DashboardProps {
  onOpenProject: (id: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onOpenProject }) => {
  const [project, setProject] = useState<VideoProject | null>(null);
  const [projects, setProjects] = useState<VideoProject[]>([]);
  const [searchInput, setSearchInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [confirm, setConfirm] = useState<{ id: string; force: boolean } | null>(null);

  const refreshProjects = useCallback(async () => {
    try {
      const data = await listProjects();
      setProjects(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadStatus = async (id: string) => {
    if (!id.trim()) return;
    setLoading(true);
    setError('');
    try {
      const data = await getProjectStatus(id.trim());
      setProject(data);
      refreshProjects();
    } catch (e) {
      setProject(null);
      setError(e instanceof Error ? e.message : 'Не удалось загрузить проект');
    } finally {
      setLoading(false);
    }
  };

  const handleRunConfirmed = async (id: string, force: boolean) => {
    setConfirm(null);
    try {
      await runPipeline(id, force, 'fake');
      await loadStatus(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось запустить перевод');
    }
  };

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  // Автопобновление статуса открытого проекта
  useEffect(() => {
    if (!project?.project_id || project.status !== 'running') return;
    const interval = setInterval(() => loadStatus(project.project_id), 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.project_id, project?.status]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle2 size={16} className="text-success" />;
      case 'failed':    return <AlertCircle  size={16} className="text-danger" />;
      case 'running':   return <Loader2      size={16} className="text-warning animate-spin" />;
      default: return null;
    }
  };

  const segments = Array.isArray(project?.segments) ? (project!.segments as Segment[]) : [];

  return (
    <div className="dashboard page-container fade-in">
      <header className="page-header">
        <h2>Мои переводы</h2>
        <p className="subtitle">Загрузите проект по имени или выберите из списка ниже.</p>
      </header>

      <form
        className="search-bar glass-panel"
        onSubmit={e => { e.preventDefault(); loadStatus(searchInput); }}
      >
        <input
          id="project-search-input"
          className="text-input"
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          placeholder="Имя проекта (например: my-video-en-ru)…"
        />
        <button type="submit" className="btn-secondary" disabled={loading}>
          {loading ? <Loader2 className="animate-spin" size={16} /> : <Search size={16} />}
          Найти
        </button>
        <button type="button" className="btn-secondary" onClick={refreshProjects} title="Обновить список">
          <RefreshCw size={16} />
        </button>
      </form>

      {error && <div className="error-banner" role="alert">{error}</div>}

      <main className="dashboard-content">
        {project && (
          <div className="project-card glass-panel" data-testid="project-card">
            <div className="card-header">
              <div className="card-title">
                <h3>{project.project_id}</h3>
                <span className={`badge ${project.status}`}>
                  {getStatusIcon(project.status)}
                  {statusLabel(project.status)}
                </span>
              </div>
              <div className="card-actions">
                {project.status !== 'running' && (
                  <button
                    id="btn-run-pipeline"
                    onClick={() => setConfirm({ id: project.project_id, force: false })}
                    className="btn-secondary"
                  >
                    <Play size={16} /> Запустить перевод
                  </button>
                )}
                {project.status !== 'running' && (
                  <button
                    id="btn-force-run-pipeline"
                    onClick={() => setConfirm({ id: project.project_id, force: true })}
                    className="btn-secondary"
                  >
                    <RefreshCw size={16} /> Перезапустить всё
                  </button>
                )}
                <button
                  id="btn-open-workspace"
                  onClick={() => onOpenProject(project.project_id)}
                  className="btn-primary"
                >
                  <FolderOpen size={16} /> Открыть редактор
                </button>
              </div>
            </div>

            <div className="card-body">
              <div className="meta-info">
                <div className="meta-item">
                  <span className="meta-label">Направление перевода</span>
                  <span className="meta-value">
                    {project.config?.source_language ?? 'Auto'}
                    <ArrowRight size={14} className="inline-icon" />
                    {project.config?.target_language ?? 'RU'}
                  </span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Сегментов распознано</span>
                  <span className="meta-value">
                    {Array.isArray(project.segments) ? project.segments.length : project.segments}
                  </span>
                </div>
              </div>

              <div className="stages">
                <h4>Прогресс обработки</h4>
                <div className="stages-grid">
                  {project.stage_runs?.map(run => (
                    <div key={run.id} className={`stage-pill ${run.status}`}>
                      <div className="stage-header">
                        <strong>{stageLabel(run.stage)}</strong>
                        {getStatusIcon(run.status)}
                      </div>
                      {run.error && <div className="stage-error">{run.error}</div>}
                    </div>
                  ))}
                  {(!project.stage_runs || project.stage_runs.length === 0) && (
                    <p className="text-muted">Обработка ещё не запускалась.</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {!project && (
          <div className="empty-state glass-panel">
            <FolderOpen size={48} className="text-muted mb-4" />
            <h3>Проект не выбран</h3>
            <p className="text-muted">
              Введите имя проекта в строку поиска или выберите из списка ниже.
            </p>
          </div>
        )}

        <section className="projects-section glass-panel">
          <div className="section-header">
            <div>
              <h3>Все проекты</h3>
              <p className="text-muted">Отсортированы по времени последнего изменения.</p>
            </div>
            <span className="text-sm text-muted">Найдено: {projects.length}</span>
          </div>
          <div className="projects-grid" data-testid="project-list">
            {projects.map(item => (
              <article key={item.project_id} className="project-mini-card">
                <div className="mini-card-title">
                  <strong>{item.project_id}</strong>
                  <span className={`badge ${item.status}`}>
                    {STATUS_EMOJI[item.status] ?? ''} {statusLabel(item.status)}
                  </span>
                </div>
                <div className="mini-card-meta">
                  <span>{item.config?.source_language ?? 'auto'}</span>
                  <ArrowRight size={12} />
                  <span>{item.config?.target_language ?? 'ru'}</span>
                  <Clock size={12} />
                  <span>{Array.isArray(item.segments) ? item.segments.length : item.segments} сегм.</span>
                </div>
                <div className="mini-card-actions">
                  <button
                    className="btn-secondary"
                    onClick={() => loadStatus(item.project_id)}
                    aria-label={`Загрузить статус проекта ${item.project_id}`}
                  >
                    <Search size={14} /> Статус
                  </button>
                  <button
                    className="btn-primary"
                    onClick={() => onOpenProject(item.project_id)}
                    aria-label={`Открыть редактор проекта ${item.project_id}`}
                  >
                    <FolderOpen size={14} /> Редактор
                  </button>
                </div>
              </article>
            ))}
            {projects.length === 0 && (
              <p className="empty-text">Проекты пока не найдены. Создайте первый перевод!</p>
            )}
          </div>
        </section>
      </main>

      {confirm && (
        <ConfirmRunModal
          projectId={confirm.id}
          provider="fake"
          isForce={confirm.force}
          segments={segments}
          onConfirm={() => handleRunConfirmed(confirm.id, confirm.force)}
          onCancel={() => setConfirm(null)}
        />
      )}
    </div>
  );
};
