import React, { useState, useEffect, useCallback } from 'react';
import { getProjectStatus, listProjects, runPipeline, uploadProject, artifactDownloadUrl, renameProject, deleteProject } from '../api/client';
import type { VideoProject, Segment } from '../types/schemas';
import { stageLabel, statusLabel, t } from '../i18n';
import type { AppLocale } from '../store/settings';
import { useProjectWebSocket } from '../hooks/useProjectWebSocket';
import { ConfirmRunModal } from './ConfirmRunModal';
import { CompletionToast } from './CompletionToast';
import { DashboardStats } from './DashboardStats';
import { InstallPWABanner } from './InstallPWABanner';
import { DiskUsageWarning } from './DiskUsageWarning';
import { getPersistedProvider } from '../store/settings';
import { BatchQueue } from './dashboard/BatchQueue';
import type { BatchItem } from './dashboard/BatchQueue';
import { EmptyState } from './dashboard/EmptyState';
import { DashboardFilters } from './dashboard/DashboardFilters';
import { ProjectCard } from './dashboard/ProjectCard';
import { ConfirmDeleteModal } from './dashboard/ConfirmDeleteModal';
import {
  Play, FolderOpen, AlertCircle, CheckCircle2, Loader2,
  ArrowRight, RefreshCw, Clock, Search, Download, Trash2, XCircle
} from 'lucide-react';
import './Dashboard.css';

// Человекочитаемые сообщения ошибок этапа
// Ошибка = технические сообщения заменяются понятным пользователю текстом
const STAGE_ERROR_HINTS: Record<string, string> = {
  'extract_audio': 'Не удалось извлечь аудио — проверьте формат видеофайла',
  'transcribe': 'Ошибка распознавания речи — возможно аудио слишком тихое или нечёткое',
  'translate': 'Не удалось перевести — проверьте API-ключи провайдера перевода',
  'tts': 'Ошибка озвучки — проверьте API-ключ TTS-провайдера и баланс счёта',
  'timing_fit': 'Не удалось подстроить тайминги — попробуйте резким перезапуском',
  'render': 'Ошибка монтажа — возможно файл повреждён, попробуйте перезапустить',
  'export': 'Ошибка экспорта — повторите запуск или обратитесь в суппорт',
};

function humanStageError(stage: string, rawError: string | undefined): string {
  if (!rawError) return '';
  const hint = STAGE_ERROR_HINTS[stage];
  return hint ? `${hint}. (Подробно: ${rawError.slice(0, 120)})` : rawError;
}

interface DashboardProps {
  onOpenProject: (id: string) => void;
  locale: AppLocale;
}

export const Dashboard: React.FC<DashboardProps> = ({ onOpenProject, locale }) => {
  const [project, setProject] = useState<VideoProject | null>(null);
  const [projects, setProjects] = useState<VideoProject[]>([]);
  const [initialLoading, setInitialLoading] = useState(true); // R8-И3: skeleton loader
  // R15-И1: Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState<{ page: number; page_size: number; total: number; pages: number } | null>(null);
  const PAGE_SIZE = 20;
  const [searchInput, setSearchInput] = useState('');
  const [projectSearch, setProjectSearch] = useState('');  // K3: поиск по списку проектов
  // А9: Сортировка с persist через localStorage
  const [sortBy, setSortBy] = useState<'created_at'|'name'|'status'>(
    () => (localStorage.getItem('tv_sort_by') as 'created_at'|'name'|'status') || 'created_at'
  );
  const [sortDir, setSortDir] = useState<'asc'|'desc'>(
    () => (localStorage.getItem('tv_sort_dir') as 'asc'|'desc') || 'desc'
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [confirm, setConfirm] = useState<{ id: string; force: boolean } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null); // R7-И1: id проекта для удаления
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [dragOver, setDragOver] = useState(false);  // Z4.15: DnD upload
  const [autoRun, setAutoRun] = useState(false);    // R8-И5: «Один клик» — запуск сразу после загрузки
  // R10-ИГГ (Batch): Очередь загрузки нескольких файлов
  const [batchQueue, setBatchQueue] = useState<BatchItem[]>([]);
  const [batchActive, setBatchActive] = useState(false);

  const refreshProjects = useCallback(async () => {
    try {
      const result = await listProjects({ search: projectSearch || undefined, sort_by: sortBy, sort_dir: sortDir, page: currentPage, page_size: PAGE_SIZE });
      setProjects(result.projects);
      setPagination(result.pagination);
    } catch (e) {
      console.error(e);
    }
  }, [projectSearch, sortBy, sortDir, currentPage]);

  // А9: Persist sort preferences
  const handleSortBy = (v: 'created_at'|'name'|'status') => {
    setSortBy(v);
    setCurrentPage(1);
    localStorage.setItem('tv_sort_by', v);
  };
  const handleSortDir = (v: 'asc'|'desc') => {
    setSortDir(v);
    setCurrentPage(1);
    localStorage.setItem('tv_sort_dir', v);
  };

  const loadStatus = useCallback(async (id: string) => {
    if (!id.trim()) return;
    setLoading(true);
    setError('');
    try {
      const data = await getProjectStatus(id.trim());
      setProject(data);
      refreshProjects();
    } catch (e) {
      setProject(null);
      setError(e instanceof Error ? e.message : t('dashboard.loadError', locale));
    } finally {
      setLoading(false);
    }
  }, [locale, refreshProjects]);

  const handleRunConfirmed = async (id: string, force: boolean) => {
    setConfirm(null);
    try {
      await runPipeline(id, force, getPersistedProvider());
      await loadStatus(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('dashboard.runError', locale));
    }
  };

  // R7-И1: Удаление проекта
  const handleDeleteProject = useCallback(async (id: string) => {
    try {
      await deleteProject(id);
      setProjects(prev => prev.filter(p => p.project_id !== id));
      if (project?.project_id === id) setProject(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка удаления');
    } finally {
      setConfirmDelete(null);
    }
  }, [project]);


  useEffect(() => {
    let cancelled = false;
    void listProjects()
      .then(result => {
        if (!cancelled) {
          setProjects(result.projects);
          setPagination(result.pagination);
          setInitialLoading(false); // R8-И3: скрываем skeleton
        }
      })
      .catch(e => { console.error(e); setInitialLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // WS-FE R12-И1: WebSocket вместо polling для статуса проекта во время обработки.
  // setInterval(3000) заменён на WS-соединение к /api/v1/projects/{id}/ws.
  useProjectWebSocket({
    projectId: project?.project_id,
    enabled: project?.status === 'running' || project?.status === 'queued',
    onUpdate: (data) => {
      if (data.error) return;
      setProject(prev => prev ? ({
        ...prev,
        status: data.status as VideoProject['status'],
        progress_percent: data.progress_percent,
        eta_seconds: data.eta_seconds,
      }) : prev);
    },
    onDone: () => {
      // WS закрылся (перевод завершён/упал) — обновляем полный статус
      if (project?.project_id) loadStatus(project.project_id);
    },
  });

  // C-13/C-19: Stale detection — если >5 мин работает без завершения → предупреждение
  const [staleWarning, setStaleWarning] = useState(false);
  useEffect(() => {
    if (project?.status !== 'running') {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStaleWarning(false);
      return;
    }
    const timer = setTimeout(() => setStaleWarning(true), 5 * 60 * 1000); // 5 мин
    return () => clearTimeout(timer);
  }, [project?.status, project?.project_id]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle2 size={16} className="text-success" />;
      case 'failed':    return <AlertCircle  size={16} className="text-danger" />;
      case 'cancelled': return <XCircle      size={16} className="text-muted" />;
      case 'running':   return <Loader2      size={16} className="text-warning animate-spin" />;
      case 'queued':    return <Clock        size={16} className="text-muted" />; // API-STATES R12-И2
      default: return null;
    }
  };

  const segments = Array.isArray(project?.segments) ? (project!.segments as Segment[]) : [];

  return (
    <>
    <div
      className={`dashboard page-container fade-in${dragOver ? ' dashboard-drag-over' : ''}`}
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={async e => {
        e.preventDefault();
        setDragOver(false);
        const files = Array.from(e.dataTransfer.files).filter(f =>
          f.type.startsWith('video/') || f.type.startsWith('audio/')
        );
        if (files.length === 0) {
          setError(locale === 'ru' ? 'Только видео- или аудиофайлы' : 'Only video or audio files allowed');
          return;
        }
        if (files.length === 1) {
          setLoading(true);
          try {
            const created = await uploadProject(files[0]);
            if (autoRun) await runPipeline(created.project_id, false, getPersistedProvider());
            onOpenProject(created.project_id);
          } catch (err) {
            setError(err instanceof Error ? err.message : 'Upload failed');
          } finally { setLoading(false); setAutoRun(false); }
          return;
        }
        // Много файлов — batch режим
        const queue = files.map(f => ({ name: f.name, status: 'pending' as const }));
        setBatchQueue(queue);
        setBatchActive(true);
        // uploadProject и runPipeline импортированы статически (QA-001 fix)
        for (let i = 0; i < files.length; i++) {
          setBatchQueue(prev => prev.map((item, idx) => idx === i ? { ...item, status: 'uploading' } : item));
          try {
            const created = await uploadProject(files[i]);
            if (autoRun) { try { await runPipeline(created.project_id, false, getPersistedProvider()); } catch {/* continue */} }
            setBatchQueue(prev => prev.map((item, idx) => idx === i ? { ...item, status: 'done', projectId: created.project_id } : item));
          } catch (err) {
            setBatchQueue(prev => prev.map((item, idx) => idx === i ? { ...item, status: 'error', error: err instanceof Error ? err.message : String(err) } : item));
          }
        }
        setBatchActive(false);
        setAutoRun(false);
        refreshProjects();
      }}
    >
      {/* Z4.15 + R8-И5 + R10-ИГГ: DnD overlay (batch) */}
      {dragOver && (
        <div className="dashboard-dnd-overlay">
          <span>🎬 Перетащите видео (можно несколько)</span>
          <div className="dnd-options">
            <button className="dnd-option-btn" onClick={() => { setAutoRun(false); }} onDragEnter={() => setAutoRun(false)}>
              📁 Создать проект(ы)
            </button>
            <button className="dnd-option-btn dnd-option-run" onClick={() => { setAutoRun(true); }} onDragEnter={() => setAutoRun(true)}
              title="Загрузить видео и сразу запустить перевод">
              ⚡ Создать и перевести
            </button>
          </div>
        </div>
      )}
      {/* R10-ИГГ: Batch очередь загрузки нескольких файлов */}
      <BatchQueue
        queue={batchQueue}
        active={batchActive}
        onHide={() => setBatchQueue([])}
        onOpenProject={onOpenProject}
      />
      <header className="page-header">
        <h2>{t('dashboard.title', locale)}</h2>
        <p className="subtitle">{t('dashboard.subtitle', locale)}</p>
      </header>

      {/* NM2-07: PWA Install Banner */}
      <InstallPWABanner />

      {/* NC4-03: Disk Usage Warning */}
      <DiskUsageWarning />

      {/* NM2-05: Dashboard Stats */}
      <DashboardStats projects={projects} />

      <form
        className="search-bar glass-panel"
        onSubmit={e => { e.preventDefault(); loadStatus(searchInput); }}
      >
        <input
          id="project-search-input"
          className="text-input"
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          placeholder={t('dashboard.searchPlaceholder', locale)}
        />
        <div className="search-bar-actions">
          <button type="submit" className="btn-secondary" disabled={loading}>
            {loading ? <Loader2 className="animate-spin" size={16} /> : <Search size={16} />}
            {t('dashboard.find', locale)}
          </button>
          <button type="button" className="btn-secondary" onClick={refreshProjects} title={t('dashboard.refreshList', locale)}>
            <RefreshCw size={16} />
          </button>
        </div>
      </form>

      {error && <div className="error-banner" role="alert">{error}</div>}

      <main className="dashboard-content">
        {project && (
          <div className="project-card glass-panel" data-testid="project-card">
            <div className="card-header">
              <div className="card-title">
                <h3>{project.project_id}</h3>
                {/* FILE-PREVIEW R12-И4: имя исходного файла */}
                {project.input_video && (
                  <span className="card-filename" title={project.input_video}>
                    📎 {project.input_video.split('/').pop()?.split('\\').pop()}
                  </span>
                )}
                <span className={`badge ${project.status}`}>
                  {getStatusIcon(project.status)}
                    {statusLabel(project.status, locale)}
                </span>
                {/* Z5.16: Теги проекта */}
                {((project as unknown as {tags?: string[]}).tags ?? []).length > 0 && (
                  <div className="project-tags">
                    {((project as unknown as {tags?: string[]}).tags ?? []).map(tag => (
                      <span key={tag} className="project-tag">{tag}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="card-actions">
                {project.status !== 'running' && project.status !== 'completed' && (
                  <button
                    id="btn-run-pipeline"
                    onClick={() => setConfirm({ id: project.project_id, force: false })}
                    className="btn-primary"
                    disabled={loading} // DOUBLE-CLICK R12-И4
                    title="Продолжить или начать перевод с первого незавершённого этапа"
                  >
                    <Play size={16} />
                    {project.status === 'created'
                      ? (locale === 'ru' ? '▶ Запустить перевод' : '▶ Start Translation')
                      : (locale === 'ru' ? '▶ Продолжить' : '▶ Continue')}
                  </button>
                )}
                {project.status !== 'running' && (
                  <button
                    id="btn-force-run-pipeline"
                    onClick={() => setConfirm({ id: project.project_id, force: true })}
                    className="btn-secondary"
                    title="Запустить все этапы заново, включая уже выполненные"
                  >
                    <RefreshCw size={16} />
                    {locale === 'ru' ? '↺ Начать заново' : '↺ Restart All'}
                  </button>
                )}
                {/* R7-И1: Удаление проекта с подтверждением */}
                {project.status !== 'running' && (
                  <button
                    id="btn-delete-project"
                    onClick={() => setConfirmDelete(project.project_id)}
                    className="btn-secondary btn-delete-project"
                    title="Удалить проект"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
                {/* R14-И3: Download CTA (Дмитрий FBA — DOWNLOAD-CTA P1) */}
                {project.status === 'completed' && (
                  <a
                    href={`/api/v1/projects/${project.project_id}/export/zip`}
                    className="btn-success btn-download-cta"
                    id={`btn-card-download-zip-${project.project_id}`}
                    download
                    title="Скачать всё: субтитры (SRT/VTT/ASS), скрипт, project.json"
                  >
                    <Download size={16} /> ⬇️ Скачать результат
                  </a>
                )}
                <button
                  id="btn-open-workspace"
                  onClick={() => onOpenProject(project.project_id)}
                  className="btn-primary"
                >
                  <FolderOpen size={16} /> {t('dashboard.openEditor', locale)}
                </button>
                {/* C-12: быстрое скачивание готовых артефактов */}
                {project.status === 'completed' &&
                  Array.isArray(project.artifact_records) &&
                  project.artifact_records.length > 0 && (
                    <div className="quick-downloads">
                      {(project.artifact_records as Array<{kind: string; path: string}>)
                        .filter(r => ['translated_video', 'subtitles_srt', 'subtitles_vtt'].includes(r.kind))
                        .slice(0, 3)
                        .map(r => (
                          <a
                            key={r.kind}
                            href={artifactDownloadUrl(project.project_id, r.kind)}
                            className="btn-secondary btn-xs"
                            download
                            title={`Скачать ${r.kind}`}
                          >
                            <Download size={13} />
                            {r.kind === 'translated_video' ? 'MP4' :
                             r.kind === 'subtitles_srt' ? 'SRT' : 'VTT'}
                          </a>
                        ))}
                        {/* I7: Экспорт MP3 (аудио дубляжа без видео) */}
                        <a
                          href={`/api/v1/projects/${project.project_id}/export-audio?format=mp3`}
                          className="btn-secondary btn-xs"
                          download
                          title="Скачать аудиодорожку дубляжа (MP3)"
                        >
                          <Download size={13} />
                          🎧 MP3
                        </a>
                    </div>
                  )}
              </div>
            </div>

            <div className="card-body" aria-live="polite" aria-atomic="false">
              {/* K7 + R13-И1: Progress bar с ETA для running проектов */}
              {project.status === 'running' && (
                <div className="card-progress-bar" role="progressbar"
                  aria-valuenow={project.progress_percent ?? 0}
                  aria-valuemin={0} aria-valuemax={100}
                  title={`Прогресс: ${project.progress_percent ?? 0}%`}
                >
                  <div
                    className="card-progress-fill"
                    style={{ width: `${project.progress_percent ?? 5}%` }}
                  />
                  <span className="card-progress-label">
                    {project.progress_percent ? `${project.progress_percent}%` : 'Переводится…'}
                    {project.eta_seconds != null && project.eta_seconds > 0 && (
                      <span className="card-progress-eta">
                        {' · '}
                        {project.eta_seconds >= 60
                          ? `осталось ~${Math.ceil(project.eta_seconds / 60)} мин`
                          : `осталось ~${project.eta_seconds} сек`}
                      </span>
                    )}
                  </span>
                </div>
              )}
              {/* C-13/C-19: Stale warning */}
              {staleWarning && project.status === 'running' && (
                <div className="stale-warning" role="alert">
                  <AlertCircle size={16} />
                  <span>
                    <b>Процесс идёт более 5 минут.</b> Это нормально для длинных видео.
                    Если прогресс не изменился — попробуйте перезапустить.
                  </span>
                  <button
                    className="btn-secondary btn-xs"
                    onClick={() => setConfirm({ id: project.project_id, force: true })}
                  >
                    <RefreshCw size={13} /> Перезапустить
                  </button>
                </div>
              )}
              {/* C-17 + RETRY-BTN R12-И4: человекочитаемые ошибки + кнопка повтора */}
              {project.status === 'failed' && project.error && (
                <div className="error-human" role="alert">
                  <AlertCircle size={16} />
                  <div>
                    <b>Что пошло не так:</b><br />
                    <span className="error-human-msg">
                      {project.error.includes('StageError') ? '⚠️ Один из этапов обработки завершился с ошибкой.' :
                       project.error.includes('ffmpeg') ? '🎬 Ошибка обработки видеофайла. Проверьте формат.' :
                       project.error.includes('TimeoutError') ? '⏱ Превышено время ожидания сервиса.' :
                       project.error.includes('quota') ? '💳 Исчерпан лимит API. Проверьте настройки.' :
                       project.error.slice(0, 120)}
                    </span>
                  </div>
                  {/* RETRY-BTN: кнопка повтора прямо под ошибкой */}
                  <button
                    className="btn-primary btn-xs"
                    style={{ marginTop: 8 }}
                    disabled={loading}
                    onClick={() => handleRunConfirmed(project.project_id, false)}
                  >
                    <RefreshCw size={13} /> Попробовать снова
                  </button>
                </div>
              )}
              <div className="meta-info">
                <div className="meta-item">
                  <span className="meta-label">{t('dashboard.translationDirection', locale)}</span>
                  <span className="meta-value">
                    {project.config?.source_language ?? 'Auto'}
                    <ArrowRight size={14} className="inline-icon" />
                    {project.config?.target_language ?? 'RU'}
                  </span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">{t('dashboard.segmentsRecognized', locale)}</span>
                  <span className="meta-value">
                    {Array.isArray(project.segments) ? project.segments.length : project.segments}
                  </span>
                </div>
                {/* И5: Стоимость запуска [Виктор#4] */}
                {project.billing_snapshots && Object.keys(project.billing_snapshots).length > 0 && (() => {
                  const total = Object.values(project.billing_snapshots).reduce((a, b) => a + b, 0);
                  return total > 0 ? (
                    <div className="meta-item">
                      <span className="meta-label">💰 Стоимость</span>
                      <span className="meta-value meta-value--cost" title={Object.entries(project.billing_snapshots).map(([k,v]) => `${k}: $${v.toFixed(4)}`).join('\n')}>
                        ${total.toFixed(3)}
                      </span>
                    </div>
                  ) : null;
                })()}
              </div>

              <div className="stages">
                <h4>{t('dashboard.progress', locale)}</h4>
                <div className="stages-grid">
                  {project.stage_runs?.map(run => (
                    <div key={run.id} className={`stage-pill ${run.status}`}>
                      <div className="stage-header">
                        <strong>{stageLabel(run.stage, locale)}</strong>
                        {getStatusIcon(run.status)}
                      </div>
                      {run.error && (
                        <div className="stage-error" title={run.error}>
                          {humanStageError(run.stage, run.error)}
                        </div>
                      )}
                    </div>
                  ))}
                  {(!project.stage_runs || project.stage_runs.length === 0) && (
                    <p className="text-muted">{t('dashboard.notStarted', locale)}</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {!project && <EmptyState locale={locale} />}

        <section className="projects-section glass-panel">
          <div className="section-header">
            <div className="section-header-left">
              <h3>{t('dashboard.allProjects', locale)}</h3>
              <span className="section-count">{projects.filter(p => statusFilter === 'all' || p.status === statusFilter).length} {locale === 'ru' ? 'проектов' : 'projects'}</span>
            </div>
            <DashboardFilters
              locale={locale}
              projectSearch={projectSearch}
              setProjectSearch={setProjectSearch}
              sortBy={sortBy}
              sortDir={sortDir}
              handleSortBy={handleSortBy}
              handleSortDir={handleSortDir}
              statusFilter={statusFilter}
              setStatusFilter={setStatusFilter}
            />
          </div>
          <div className="projects-grid" data-testid="project-list">
            {/* R8-И3: Skeleton loader при первой загрузке */}
            {initialLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <article key={i} className="project-mini-card skeleton-card" aria-hidden="true">
                  <div className="skeleton-line skeleton-title" />
                  <div className="skeleton-line skeleton-meta" />
                  <div className="skeleton-line skeleton-actions" />
                </article>
              ))
            ) : (
              <>
                {projects.filter(item => statusFilter === 'all' || item.status === statusFilter).map(item => (
                  <ProjectCard
                    key={item.project_id}
                    project={item}
                    locale={locale}
                    onOpenProject={onOpenProject}
                    onDelete={setConfirmDelete}
                    onRename={async (id, newName) => {
                      await renameProject(id, newName);
                      refreshProjects();
                    }}
                  />
                ))}
                {projects.filter(item => statusFilter === 'all' || item.status === statusFilter).length === 0 && (
                  <p className="empty-text">{t('dashboard.empty', locale)}</p>
                )}
              </>
            )}
          </div>
          {/* R15-И1: Pagination controls */}
          {pagination && pagination.pages > 1 && (
            <div className="pagination-controls" aria-label="Навигация по страницам">
              <span className="pagination-info">
                Показано {projects.length} из {pagination.total}
              </span>
              <div className="pagination-buttons">
                <button
                  id="btn-pagination-prev"
                  className="btn-sm btn-outline"
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  aria-label="Предыдущая страница"
                >← Назад</button>
                <span className="pagination-page">
                  {currentPage} / {pagination.pages}
                </span>
                <button
                  id="btn-pagination-next"
                  className="btn-sm btn-outline"
                  disabled={currentPage >= pagination.pages}
                  onClick={() => setCurrentPage(p => Math.min(pagination.pages, p + 1))}
                  aria-label="Следующая страница"
                >Вперёд →</button>
              </div>
            </div>
          )}
          {pagination && pagination.total > 0 && pagination.pages === 1 && (
            <p className="pagination-info" style={{textAlign:'center', marginTop:'8px'}}>
              Всего проектов: {pagination.total}
            </p>
          )}
        </section>
      </main>

      {confirm && (
        <ConfirmRunModal
          projectId={confirm.id}
          provider={getPersistedProvider()}
          isForce={confirm.force}
          segments={segments}
          locale={locale}
          onConfirm={() => handleRunConfirmed(confirm.id, confirm.force)}
          onCancel={() => setConfirm(null)}
        />
      )}
    </div>
    {confirmDelete && (
      <ConfirmDeleteModal
        projectId={confirmDelete}
        onConfirm={handleDeleteProject}
        onCancel={() => setConfirmDelete(null)}
      />
    )}
    <CompletionToast
      projectId={project?.project_id ?? null}
      status={project?.status}
    />
    </>
  );
};
