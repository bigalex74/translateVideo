import React, { useState, useEffect, useCallback } from 'react';
import { getProjectStatus, listProjects, runPipeline, artifactDownloadUrl } from '../api/client';
import type { VideoProject, Segment } from '../types/schemas';
import { stageLabel, statusLabel, STATUS_EMOJI, t } from '../i18n';
import type { AppLocale } from '../store/settings';
import { ConfirmRunModal } from './ConfirmRunModal';
import { CompletionToast } from './CompletionToast';
import { DashboardStats } from './DashboardStats';
import { InstallPWABanner } from './InstallPWABanner';
import { getPersistedProvider } from '../store/settings';
import {
  Play, FolderOpen, AlertCircle, CheckCircle2, Loader2, Filter,
  ArrowRight, RefreshCw, Clock, Search, BookOpen, Download
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
  const [searchInput, setSearchInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [confirm, setConfirm] = useState<{ id: string; force: boolean } | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const refreshProjects = useCallback(async () => {
    try {
      const data = await listProjects();
      setProjects(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

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

  useEffect(() => {
    let cancelled = false;
    void listProjects()
      .then(data => {
        if (!cancelled) setProjects(data);
      })
      .catch(e => console.error(e));
    return () => {
      cancelled = true;
    };
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
    <div className="dashboard page-container fade-in">
      <header className="page-header">
        <h2>{t('dashboard.title', locale)}</h2>
        <p className="subtitle">{t('dashboard.subtitle', locale)}</p>
      </header>

      {/* NM2-07: PWA Install Banner */}
      <InstallPWABanner />

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
              </div>
              <div className="card-actions">
                {project.status !== 'running' && (
                  <button
                    id="btn-run-pipeline"
                    onClick={() => setConfirm({ id: project.project_id, force: false })}
                    className="btn-secondary"
                  >
                    <Play size={16} /> {t('dashboard.run', locale)}
                  </button>
                )}
                {project.status !== 'running' && (
                  <button
                    id="btn-force-run-pipeline"
                    onClick={() => setConfirm({ id: project.project_id, force: true })}
                    className="btn-secondary"
                  >
                    <RefreshCw size={16} /> {t('dashboard.restart', locale)}
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
                    </div>
                  )}
              </div>
            </div>

            <div className="card-body" aria-live="polite" aria-atomic="false">
              {/* C-13/C-19: Stale warning — если работает >5 мин */}
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
            {projects.filter(item => statusFilter === 'all' || item.status === statusFilter).map(item => (
              <article key={item.project_id} className="project-mini-card">
                <div className="mini-card-title">
                  <strong>{item.project_id}</strong>
                  <span className={`badge ${item.status}`}>
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
    <CompletionToast
      projectId={project?.project_id ?? null}
      status={project?.status}
    />
    </>
  );
};
