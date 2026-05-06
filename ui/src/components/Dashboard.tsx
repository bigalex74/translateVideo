import React, { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { getProjectStatus, listProjects, runPipeline, artifactDownloadUrl, renameProject, deleteProject } from '../api/client';
import type { VideoProject, Segment } from '../types/schemas';
import { stageLabel, statusLabel, STATUS_EMOJI, t } from '../i18n';
import type { AppLocale } from '../store/settings';
import { ConfirmRunModal } from './ConfirmRunModal';
import { CompletionToast } from './CompletionToast';
import { DashboardStats } from './DashboardStats';
import { InstallPWABanner } from './InstallPWABanner';
import { DiskUsageWarning } from './DiskUsageWarning';
import { getPersistedProvider } from '../store/settings';
import {
  Play, FolderOpen, AlertCircle, CheckCircle2, Loader2, Filter,
  ArrowRight, RefreshCw, Clock, Search, BookOpen, Download, Pencil, Check, X, Trash2
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
  // О1: Inline rename состояние
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef<HTMLInputElement>(null);

  const refreshProjects = useCallback(async () => {
    try {
      const data = await listProjects({ search: projectSearch || undefined, sort_by: sortBy, sort_dir: sortDir });
      setProjects(data);
    } catch (e) {
      console.error(e);
    }
  }, [projectSearch, sortBy, sortDir]);

  // А9: Persist sort preferences
  const handleSortBy = (v: 'created_at'|'name'|'status') => {
    setSortBy(v);
    localStorage.setItem('tv_sort_by', v);
  };
  const handleSortDir = (v: 'asc'|'desc') => {
    setSortDir(v);
    localStorage.setItem('tv_sort_dir', v);
  };

  // О1: Переименование проекта
  const handleRenameStart = (id: string, current: string) => {
    setRenamingId(id);
    setRenameValue(current);
    setTimeout(() => renameInputRef.current?.focus(), 50);
  };
  const handleRenameSubmit = async (id: string) => {
    if (!renameValue.trim()) { setRenamingId(null); return; }
    try {
      await renameProject(id, renameValue.trim());
      setRenamingId(null);
      refreshProjects();
    } catch (e) { console.error(e); setRenamingId(null); }
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
      .then(data => {
        if (!cancelled) {
          setProjects(data);
          setInitialLoading(false); // R8-И3: скрываем skeleton
        }
      })
      .catch(e => { console.error(e); setInitialLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // Автопобновление статуса открытого проекта
  useEffect(() => {
    if (!project?.project_id || project.status !== 'running') return;
    const interval = setInterval(() => loadStatus(project.project_id), 3000);
    return () => clearInterval(interval);
  }, [loadStatus, project?.project_id, project?.status]);

  // C-13/C-19: Stale detection — если >5 мин работает без завершения → предупреждение
  const [staleWarning, setStaleWarning] = useState(false);
  useEffect(() => {
    if (project?.status !== 'running') { setStaleWarning(false); return; }
    const timer = setTimeout(() => setStaleWarning(true), 5 * 60 * 1000); // 5 мин
    return () => clearTimeout(timer);
  }, [project?.status, project?.project_id]);

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
    <>
    <div
      className={`dashboard page-container fade-in${dragOver ? ' dashboard-drag-over' : ''}`}
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={async e => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (!file || !file.type.startsWith('video/')) {
          setError(locale === 'ru' ? 'Только видеофайлы' : 'Only video files allowed');
          return;
        }
        setLoading(true);
        try {
          const { uploadProject, runPipeline } = await import('../api/client');
          const created = await uploadProject(file);
          if (autoRun) {
            // R8-И5: «Один клик» — сразу запустить перевод
            await runPipeline(created.project_id, false, getPersistedProvider());
          }
          onOpenProject(created.project_id);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Upload failed');
        } finally { setLoading(false); setAutoRun(false); }
      }}
    >
      {/* Z4.15 + R8-И5: Drag-and-drop overlay «Один клик» */}
      {dragOver && (
        <div className="dashboard-dnd-overlay">
          <span>📽 Перетащите видео</span>
          <div className="dnd-options">
            <button
              className="dnd-option-btn"
              onClick={() => { setAutoRun(false); }}
              onDragEnter={() => setAutoRun(false)}
            >
              📁 Создать проект
            </button>
            <button
              className="dnd-option-btn dnd-option-run"
              onClick={() => { setAutoRun(true); }}
              onDragEnter={() => setAutoRun(true)}
              title="Загрузить видео и сразу запустить перевод без дополнительных шагов"
            >
              ⚡ Создать и перевести
            </button>
          </div>
        </div>
      )}
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
        <button type="submit" className="btn-secondary" disabled={loading}>
          {loading ? <Loader2 className="animate-spin" size={16} /> : <Search size={16} />}
          {t('dashboard.find', locale)}
        </button>
        <button type="button" className="btn-secondary" onClick={refreshProjects} title={t('dashboard.refreshList', locale)}>
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
              {/* K7: Progress bar для running проектов */}
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
                    {project.progress_percent ? `${project.progress_percent}%` : 'Обработка…'}
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
              {/* C-17: человекочитаемые ошибки */}
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

        {!project && (
          <div className="empty-state glass-panel">
            <div className="onboarding-hero">
              <div className="onboarding-icon">🎬</div>
              <h3>{t('dashboard.noProjectTitle', locale)}</h3>
              <p className="text-muted">{t('dashboard.noProjectText', locale)}</p>
            </div>
            <div className="onboarding-steps">
              <div className="onboarding-step">
                <div className="step-num">1</div>
                <div>
                  <strong>Создайте проект</strong>
                  <p>Нажмите «+ Новый проект», загрузите видео или вставьте ссылку</p>
                </div>
              </div>
              <div className="onboarding-step">
                <div className="step-num">2</div>
                <div>
                  <strong>Выберите язык и провайдера</strong>
                  <p>Настройте параметры перевода и озвучки в мастере</p>
                </div>
              </div>
              <div className="onboarding-step">
                <div className="step-num">3</div>
                <div>
                  <strong>Запустите перевод</strong>
                  <p>Нажмите «Запустить» — всё остальное сделает ИИ автоматически</p>
                </div>
              </div>
              <div className="onboarding-step">
                <div className="step-num">4</div>
                <div>
                  <strong>Скачайте результат</strong>
                  <p>Готовое видео с переводом появится в редакторе</p>
                </div>
              </div>
            </div>
            <div className="onboarding-actions">
              <a href="/docs" target="_blank" className="btn-secondary onboarding-docs-link">
                <BookOpen size={15} /> API документация
              </a>
            </div>
          </div>
        )}

        <section className="projects-section glass-panel">
          <div className="section-header">
            <div>
              <h3>{t('dashboard.allProjects', locale)}</h3>
              <p className="text-muted">{t('dashboard.sortedByUpdate', locale)}</p>
            </div>
            <div className="section-header-right">
              {/* K3: Поиск по проектам */}
              <div className="project-list-search">
                <Search size={14} style={{color: 'var(--text-muted)'}} />
                <input
                  id="project-list-search-input"
                  className="text-input"
                  value={projectSearch}
                  onChange={e => { setProjectSearch(e.target.value); }}
                  placeholder="Поиск проектов…"
                  style={{ padding: '6px 10px', fontSize: '0.85rem', width: '160px' }}
                />
              </div>
              {/* K3 + А9: Сортировка с persist */}
              <select
                id="project-sort-select"
                className="select-input"
                value={`${sortBy}_${sortDir}`}
                onChange={e => {
                  const [by, dir] = e.target.value.split('_');
                  handleSortBy(by as 'created_at'|'name'|'status');
                  handleSortDir(dir as 'asc'|'desc');
                }}
                style={{ padding: '6px 10px', fontSize: '0.85rem' }}
                title="Сортировка запоминается между сессиями (А9)"
              >
                <option value="created_at_desc">🕐 Новые первые</option>
                <option value="created_at_asc">🕐 Старые первые</option>
                <option value="name_asc">🔤 По имени (А→Я)</option>
                <option value="name_desc">🔤 По имени (Я→А)</option>
                <option value="status_asc">📊 По статусу</option>
              </select>
              {/* Фильтр по статусу */}
              <div className="status-filter">
                <Filter size={13} />
                {['all', 'created', 'running', 'completed', 'failed'].map(s => (
                  <button
                    key={s}
                    className={`filter-pill ${statusFilter === s ? 'active' : ''}`}
                    onClick={() => setStatusFilter(s)}
                  >
                    {s === 'all' ? 'Все' : STATUS_EMOJI[s as keyof typeof STATUS_EMOJI] ?? ''}{' '}
                    {s === 'all' ? '' : statusLabel(s as 'created'|'running'|'completed'|'failed', locale)}
                  </button>
                ))}
              </div>
              <span className="text-sm text-muted">{t('dashboard.found', locale)}: {projects.filter(p => statusFilter === 'all' || p.status === statusFilter).length}</span>
            </div>
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
                  <article key={item.project_id} className="project-mini-card">
                    <div className="mini-card-title">
                      {/* О1: Переименование проекта */}
                      {renamingId === item.project_id ? (
                        <div style={{ display: 'flex', gap: '4px', flex: 1, minWidth: 0 }}>
                          <input
                            ref={renameInputRef}
                            className="select-input"
                            style={{ flex: 1, padding: '2px 6px', fontSize: '0.85rem' }}
                            value={renameValue}
                            onChange={e => setRenameValue(e.target.value)}
                            onKeyDown={e => {
                              if (e.key === 'Enter') handleRenameSubmit(item.project_id);
                              if (e.key === 'Escape') setRenamingId(null);
                            }}
                            placeholder="Название проекта…"
                            maxLength={120}
                          />
                          <button onClick={() => handleRenameSubmit(item.project_id)} title="Сохранить" style={{ padding: '2px 6px', cursor: 'pointer' }}><Check size={13} /></button>
                          <button onClick={() => setRenamingId(null)} title="Отмена" style={{ padding: '2px 6px', cursor: 'pointer' }}><X size={13} /></button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flex: 1, minWidth: 0, overflow: 'hidden' }}>
                          <strong style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={item.project_id}>
                            {(item as VideoProject & { display_name?: string }).display_name || item.project_id}
                          </strong>
                          <button
                            onClick={() => handleRenameStart(item.project_id,
                              (item as VideoProject & { display_name?: string }).display_name || '')}
                            title="Переименовать проект (О1)"
                            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', color: 'var(--text-muted)', flexShrink: 0 }}
                          ><Pencil size={11} /></button>
                        </div>
                      )}
                      <span
                        className={`badge ${item.status}`}
                        title={
                          item.status === 'created'   ? '⏳ Проект создан, ещё не запущен' :
                          item.status === 'running'   ? '🔄 Перевод выполняется прямо сейчас' :
                          item.status === 'completed' ? '✅ Перевод успешно завершён — файлы готовы к скачиванию' :
                          item.status === 'failed'    ? '❌ Ошибка при переводе — нажмите для деталей' :
                          item.status
                        }
                      >
                        {STATUS_EMOJI[item.status] ?? ''} {statusLabel(item.status, locale)}
                      </span>
                    </div>
                    <div className="mini-card-meta">
                      <span>{item.config?.source_language ?? 'auto'}</span>
                      <ArrowRight size={12} />
                      <span>{item.config?.target_language ?? 'ru'}</span>
                      <Clock size={12} />
                      <span>{Array.isArray(item.segments) ? item.segments.length : item.segments} {t('dashboard.segmentShort', locale)}</span>
                    </div>
                    <div className="mini-card-actions">
                      <button
                        className="btn-secondary"
                        onClick={() => loadStatus(item.project_id)}
                        aria-label={`${t('dashboard.status', locale)} ${item.project_id}`}
                      >
                        <Search size={14} /> {t('dashboard.status', locale)}
                      </button>
                      <button
                        className="btn-primary"
                        onClick={() => onOpenProject(item.project_id)}
                        aria-label={`${t('dashboard.openEditor', locale)} ${item.project_id}`}
                      >
                        <FolderOpen size={14} /> {t('dashboard.editor', locale)}
                      </button>
                    </div>
                  </article>
                ))}
                {projects.filter(item => statusFilter === 'all' || item.status === statusFilter).length === 0 && (
                  <p className="empty-text">{t('dashboard.empty', locale)}</p>
                )}
              </>
            )}
          </div>
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
    {/* R7-И1: Диалог подтверждения удаления проекта */}
    {confirmDelete && createPortal(
      <div className="modal-overlay" onClick={() => setConfirmDelete(null)}>
        <div className="modal-box delete-confirm-modal" onClick={e => e.stopPropagation()}>
          <h3>🗑 Удалить проект?</h3>
          <p>Проект <b>{confirmDelete}</b> и все его файлы будут удалены безвозвратно.</p>
          <div className="modal-actions">
            <button className="btn-secondary" onClick={() => setConfirmDelete(null)}>
              <X size={16} /> Отмена
            </button>
            <button className="btn-danger" onClick={() => handleDeleteProject(confirmDelete)}>
              <Trash2 size={16} /> Удалить
            </button>
          </div>
        </div>
      </div>
    , document.body)}
    <CompletionToast
      projectId={project?.project_id ?? null}
      status={project?.status}
    />
    </>
  );
};
