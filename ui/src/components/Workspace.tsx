import React, { useState, useEffect, useRef } from 'react';
import { artifactDownloadUrl, getProjectStatus, runPipeline, saveProjectSegments, patchProjectConfig, cancelPipeline, previewTTS } from '../api/client';
import type { ArtifactRecord, CostEstimate, VideoProject, Segment, PipelineConfig } from '../types/schemas';
import { stageLabel, statusLabel, t } from '../i18n';
import type { AppLocale } from '../store/settings';
import { stageProgressInfo } from '../progress';
import { flagBelongsToStage } from '../qa_stage_filter';
import { QASummary } from './QASummary';
import { ConfirmRunModal } from './ConfirmRunModal';
import { AdvancedSettings } from './AdvancedSettings';
import { ArtifactCard } from './ArtifactCard';
import { StatsPanel } from './StatsPanel';
import { DevLogPanel } from './DevLogPanel';
import { SSMLToolbar, renderTtsMarkup } from './SSMLToolbar';
import { getPersistedProvider } from '../store/settings';
import {
  ArrowLeft, Download, RefreshCw, Save, CheckCircle2,
  Loader2, AlertCircle, Undo2, Redo2, Settings, X,
  Film, AlignLeft, Activity, Play, XCircle, AlertTriangle, Info, Share2, ExternalLink,
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
  const [cancelTimedOut, setCancelTimedOut] = useState(false); // zombie-режим
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
  const [previewingSegId, setPreviewingSegId] = useState<string | null>(null);
  // Модальное предупреждение: откат Яндекс-разметки при смене провайдера
  const [yandexRevertModal, setYandexRevertModal] = useState<{
    pendingPatch: Partial<PipelineConfig>;
    affectedCount: number;
  } | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  // Ссылки на DOM-узлы карточек сегментов для авто-скролла
  const segRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  // Ref на textarea активного SSML-редактора. Нужен SSMLToolbar для работы с selection.
  // ВАЖНО: должен быть ДО любого раннего return (Rules of Hooks).
  const ssmlTextareaRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map());

  const [history, setHistory] = useState<Segment[][]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  // Z2.12: Segment search/filter
  const [segSearch, setSegSearch] = React.useState('');
  // Z4.10: Keyboard shortcuts help modal
  const [showShortcuts, setShowShortcuts] = useState(false);
  // Z3.11: Quality report state
  const [qualityReport, setQualityReport] = useState<Record<string, unknown> | null>(null);
  const [loadingQR, setLoadingQR] = useState(false);

  const fetchQualityReport = async () => {
    setLoadingQR(true);
    try {
      const resp = await fetch(`${window.location.pathname.includes('localhost') ? '' : ''}/api/v1/projects/${projectId}/quality-report`);
      if (resp.ok) setQualityReport(await resp.json());
    } catch {/* ignore */}
    finally { setLoadingQR(false); }
  };
  // Оценка стоимости из последнего preflight (для ConfirmRunModal)
  const [preflightCost, setPreflightCost] = useState<{
    cost?: CostEstimate | null;
    eta?: number | null;
  }>({});

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

        // Запрашиваем preflight для получения cost_estimate / ETA
        // Ошибки — некритичны, просто не показываем оценку
        if (data.input_video && data.config?.professional_translation_provider) {
          import('../api/client').then(({ preflightVideo }) => {
            preflightVideo(data.input_video, data.config!.professional_translation_provider || 'fake')
              .then(report => {
                if (!cancelled) {
                  setPreflightCost({
                    cost: report.cost_estimate,
                    eta: report.duration_estimate_seconds,
                  });
                }
              })
              .catch(() => {/* silent */});
          });
        }
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
          setCancelTimedOut(false);
        }
      } catch (e) {
        console.error('poll error', e);
      }
    }, interval);
    return () => clearInterval(poll);
  }, [cancelling, dirty, project?.status, projectId]);

  // Zombie-timeout: если через 8с после отмены статус не изменился — показываем Force Stop.
  useEffect(() => {
    if (!cancelling) { setCancelTimedOut(false); return; }
    const t = setTimeout(() => setCancelTimedOut(true), 8000);
    return () => clearTimeout(t);
  }, [cancelling]);

  // ─── Autosave субтитров каждые 30с (C-07) ───────────────────────────────────
  // Автосохранение: если есть несохранённые правки и проект не запущен — сохраняем тихо.
  const [autosaveAt, setAutosaveAt] = useState<string | null>(null);
  useEffect(() => {
    if (!dirty || !project || project.status === 'running') return;
    const timer = setInterval(async () => {
      try {
        const segs = Array.isArray(project.segments) ? project.segments : [];
        if (segs.length === 0) return;
        await saveProjectSegments(project.project_id, segs);
        setDirty(false);
        const now = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
        setAutosaveAt(now);
        setTimeout(() => setAutosaveAt(null), 3000);
      } catch {
        // silent — не мешаем пользователю ошибкой autosave
      }
    }, 30_000);
    return () => clearInterval(timer);
  }, [dirty, project]);

  // ─── Ctrl+S keyboard shortcut (UX агент — предложение iter 1) ───────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (dirty && project && project.status !== 'running') {
          // Симулируем нажатие кнопки Save
          document.getElementById('btn-save-segments')?.click();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [dirty, project]);

  // ─── Z4.12: Alt+↑/↓ навигация по сегментам в редакторе ──────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!e.altKey || !['ArrowUp', 'ArrowDown'].includes(e.key)) return;
      const segs = (project?.segments ?? []) as Segment[];
      if (!segs.length) return;
      e.preventDefault();
      setActiveSegId(prev => {
        const idx = prev ? segs.findIndex(s => s.id === prev) : -1;
        if (e.key === 'ArrowDown') {
          return segs[Math.min(idx + 1, segs.length - 1)]?.id ?? prev;
        } else {
          return segs[Math.max(idx - 1, 0)]?.id ?? prev;
        }
      });
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [project]);

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

  // Z2.5: Подсказки "что делать" для каждого QA-флага
  const QA_FLAG_ACTIONS: Record<string, string> = {
    translation_empty: 'Откройте сегмент и введите перевод вручную.',
    translation_fallback_source: 'Перевод совпал с оригиналом — проверьте язык перевода в настройках.',
    timing_fit_failed: 'Озвучка не помещается в слот. Сократите перевод в редакторе или уменьшите скорость.',
    render_audio_trimmed: 'Аудио обрезано — попробуйте уменьшить текст перевода или увеличить скорость речи.',
    tts_overflow_after_rate: 'Даже на максимальной скорости не помещается. Сократите текст перевода.',
    timeline_shift_limit_reached: 'Субтитр выходит за рамки. Скорректируйте тайминг вручную.',
    timeline_audio_extends_video: 'Озвучка длиннее видео — сократите последний сегмент.',
    tts_rate_adapted: 'TTS ускорен — при необходимости сократите текст перевода.',
    tts_pretrim: 'Текст обрезан перед отправкой в TTS — проверьте перевод.',
    translation_rewritten_for_timing: 'Перевод был автоматически сокращён — проверьте качество.',
  };

  // Какие флаги принадлежат каждой стадии пайплайна (импортировано из qa_stage_filter.ts).
  // Используется чтобы в live-ленте показывать ТОЛЬКО флаги текущей стадии,
  // а не флаги от предыдущих запусков (timing_fit, translate и т.д.).

  type LiveSev = 'critical' | 'error' | 'warning' | 'info';
  interface LiveFlag { flag: string; sev: LiveSev; count: number; }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const liveFlags: LiveFlag[] = React.useMemo(() => {
    const isRunningNow = project?.status === 'running';
    if (!isRunningNow || !project) return [];

    // Стадия, которая выполняется СЕЙЧАС
    const activeStage = (project.stage_runs ?? []).find(r => r.status === 'running')?.stage;

    const segs = Array.isArray(project.segments) ? (project.segments as Segment[]) : [];
    const counts: Record<string, number> = {};
    segs.forEach(seg =>
      (seg.qa_flags ?? []).forEach(f => { counts[f] = (counts[f] ?? 0) + 1; }),
    );

    const SEV_ORDER: LiveSev[] = ['critical', 'error', 'warning', 'info'];
    return Object.entries(counts)
      .filter(([f]) => {
        // Показываем только известные (не info) флаги
        if (FLAG_SEV[f] === 'info' || FLAG_SEV[f] === undefined) return false;
        // Если известна активная стадия — показываем ТОЛЬКО её флаги.
        // Флаги других стадий (даже если они есть в сегментах) — скрываем.
        if (activeStage) return flagBelongsToStage(f, activeStage);
        return true; // активная стадия неизвестна → показываем всё
      })
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

  const handleTextChange = (segId: string, newText: string, field: 'translated_text' | 'notes' = 'translated_text') => {
    setProject(prev => {
      if (!prev) return prev;
      const newSegments = (prev.segments as Segment[]).map(s =>
        s.id === segId ? { ...s, [field]: newText } : s
      );
      pushHistory(newSegments);
      return { ...prev, segments: newSegments };
    });
    setDirty(true);
  };

  /** Изменить SSML-override для сегмента (поле tts_ssml_override). */
  const handleSsmlChange = (segId: string, newSsml: string) => {
    setProject(prev => {
      if (!prev) return prev;
      const newSegments = (prev.segments as Segment[]).map(s =>
        s.id === segId ? { ...s, tts_ssml_override: newSsml } : s,
      );
      return { ...prev, segments: newSegments };
    });
    setDirty(true);
  };

  /** Сбросить SSML-override — TTS вернётся к translated_text. */
  const handleSsmlReset = (segId: string) => {
    setProject(prev => {
      if (!prev) return prev;
      const newSegments = (prev.segments as Segment[]).map(s =>
        s.id === segId ? { ...s, tts_ssml_override: '' } : s,
      );
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

  const handleRunConfirmed = async (force: boolean, fromStage: string | null) => {
    setConfirm(null);
    setMessage('');
    setRightTab('status');
    try {
      // Автосохранение несохранённых правок перед запуском пайплайна.
      // Без этого TTS использует старый текст с диска, а не отредактированный.
      if (dirty) {
        setSaving(true);
        try {
          await saveProjectSegments(projectId, segments);
          setDirty(false);
        } catch (saveErr) {
          setMessage(`${t('workspace.saveError', locale)}: ${saveErr instanceof Error ? saveErr.message : String(saveErr)}`);
          setSaving(false);
          return; // не запускать пайплайн если не удалось сохранить
        } finally {
          setSaving(false);
        }
      }
      await runPipeline(projectId, force, undefined, undefined, fromStage);
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

  // Z1.6: Приоритетные артефакты — видео первым, затем аудио и субтитры
  const primaryArtifacts = [
    { kind: 'output_video',           label: '🎬 Готовое видео',           primary: true },
    { kind: 'output_video_with_subs', label: '🎬💬 Видео с субтитрами',    primary: true },
  ].filter(item => findArtifact(item.kind));

  const downloadableArtifacts = [
    { kind: 'output_video',           label: '🎬 Готовое видео' },
    { kind: 'output_video_with_subs', label: '🎬💬 Видео с субтитрами' },
    { kind: 'subtitles',              label: '📄 Субтитры (SRT)' },
    { kind: 'subtitles_vtt',          label: '📄 Субтитры (VTT)' },
    { kind: 'qa_report',              label: '✅ QA-отчёт' },
    { kind: 'translated_transcript',  label: '📝 Перевод (JSON)' },
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
            {/* ETA из бэкенда */}
            {project?.eta_seconds != null && project.eta_seconds > 0 && (
              <p className="running-eta">
                ⏱ {project.eta_seconds >= 60
                  ? `~${Math.ceil(project.eta_seconds / 60)} мин`
                  : `~${project.eta_seconds} сек`}
              </p>
            )}
            {runningStage && (
              <p className="running-stage">
                ⚙️ {stageLabel(runningStage.stage, locale)}
              </p>
            )}
            {/* Основной прогресс-бар: используем project.progress_percent если есть */}
            {(project?.progress_percent != null || totalStages > 0) && (
              <div className="running-progress-wrap">
                <div
                  className="running-progress-bar"
                  style={{ width: `${project?.progress_percent ?? progress}%` }}
                />
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
                    const action = QA_FLAG_ACTIONS[flag];
                    return (
                      <li
                        key={flag}
                        className={`running-qa-item running-qa-item--${sev}`}
                        title={action || label}
                      >
                        {icon}
                        <span className="running-qa-label">{label}</span>
                        {action && <span className="running-qa-hint" title={action}>💡</span>}
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
                {cancelTimedOut
                  ? 'Пайплайн не отвечает — контейнер мог перезапуститься'
                  : 'Останавливаем перевод …'}
              </div>
            )}

            {cancelling && cancelTimedOut && (
              <button
                id="cancel-pipeline-force-btn"
                className="running-cancel-btn running-cancel-btn--force"
                onClick={async () => {
                  try { await cancelPipeline(projectId); } catch { /* zombie */ }
                  try {
                    const data = await getProjectStatus(projectId);
                    setProject(prev => (prev && dirty ? { ...data, segments: prev.segments } : data));
                  } catch { /* ignore */ }
                  setCancelling(false);
                  setCancelTimedOut(false);
                }}
              >
                <XCircle size={13} /> Принудительно остановить
              </button>
            )}
          </div>
        </div>
      )}

      {/* ═══ Header ═══ */}
      <header className="workspace-header">
        {/* Строка 1: название + статус */}
        <div className="header-row header-row-title">
          <button
            onClick={onBack}
            className="btn-back-projects"
            aria-label={t('workspace.back', locale)}
            title={t('workspace.back', locale)}
          >
            <ArrowLeft size={16} />
            <span>{t('workspace.back', locale) || '← К проектам'}</span>
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
          {/* Z4.10: Keyboard shortcuts help */}
          <button
            className="btn-icon"
            title="Горячие клавиши (Keyboard shortcuts)"
            aria-label="Справка по горячим клавишам"
            onClick={() => setShowShortcuts(true)}
          >
            ?
          </button>
          {/* Z1.8: Share link button */}
          <button
            className="btn-icon"
            title={locale === 'ru' ? 'Скопировать ссылку на проект' : 'Copy project link'}
            aria-label={locale === 'ru' ? 'Поделиться' : 'Share'}
            onClick={() => {
              const url = `${window.location.origin}${window.location.pathname}?project=${projectId}`;
              navigator.clipboard.writeText(url).then(() => {
                setMessage(locale === 'ru' ? '🔗 Ссылка скопирована!' : '🔗 Link copied!');
                setTimeout(() => setMessage(''), 3000);
              });
            }}
          >
            <Share2 size={15} />
          </button>
          {/* Z1.13: Открыть исходное видео */}
          {project?.input_video && (
            <a
              className="btn-icon btn-icon--labeled"
              href={`/api/v1/projects/${projectId}/video`}
              target="_blank"
              rel="noopener noreferrer"
              title={locale === 'ru' ? 'Открыть видео в новой вкладке' : 'Open video in new tab'}
            >
              <ExternalLink size={15} />
            </a>
          )}
          <button
            className="btn-icon btn-icon--labeled"
            title={t('workspace.translationSettings', locale)}
            aria-label={t('workspace.translationSettings', locale)}
            onClick={() => setShowConfig(prev => !prev)}
          >
            <Settings size={15} />
            <span className="btn-icon-label">{locale === 'ru' ? 'Настройки' : 'Settings'}</span>
          </button>
          <button
            id="btn-save-segments"
            className="btn-primary btn-sm"
            onClick={handleSave}
            disabled={!dirty || saving || isRunning}
            title={dirty ? `${t('workspace.saveSegments', locale)} (Ctrl+S)` : t('workspace.noChanges', locale)}
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {t('workspace.save', locale)}{dirty ? ' *' : ''}
          </button>
          {/* Autosave indicator (C-07) */}
          {autosaveAt && (
            <span className="autosave-badge" title="Изменения автоматически сохранены">
              <CheckCircle2 size={12} />
              {locale === 'ru' ? `Сохранено ${autosaveAt}` : `Saved ${autosaveAt}`}
            </span>
          )}
          {/* Z1.6: CTA кнопка скачивания готового видео */}
          {primaryArtifacts.length > 0 && (
            <a
              href={artifactDownloadUrl(projectId, primaryArtifacts[0].kind)}
              className="btn-download-cta"
              target="_blank"
              rel="noreferrer"
              title="Скачать готовое видео"
            >
              <Download size={14} />
              {locale === 'ru' ? 'Скачать' : 'Download'}
            </a>
          )}
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
              onChange={patch => {
                // Обнаруживаем смену провайдера С Yandex НА что-то другое
                const currentProvider = configPatch.professional_tts_provider
                  ?? project?.config?.professional_tts_provider ?? '';
                const nextProvider = patch.professional_tts_provider;

                if (
                  nextProvider !== undefined
                  && nextProvider !== 'yandex'
                  && currentProvider === 'yandex'
                ) {
                  // Считаем сегменты с Яндекс-разметкой в tts_ssml_override
                  const YANDEX_MARKUP_RE = /\*\*|sil<\[|<\[(tiny|small|medium|large|huge)\]>|\[\[|\+[аеёиоуыэюяАЕЁИОУЫЭЮЯaeiouAEIOU]/i;
                  const affectedSegs = segments.filter(s => {
                    const ov = (s as Segment & { tts_ssml_override?: string }).tts_ssml_override || '';
                    return ov && YANDEX_MARKUP_RE.test(ov);
                  });
                  if (affectedSegs.length > 0) {
                    // Показываем модалку — не применяем patch сразу
                    setYandexRevertModal({ pendingPatch: patch, affectedCount: affectedSegs.length });
                    return;
                  }
                }
                setConfigPatch(prev => ({ ...prev, ...patch }));
              }}
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
            <div className={`video-container${videoRef.current && videoRef.current.videoWidth && videoRef.current.videoHeight && videoRef.current.videoWidth < videoRef.current.videoHeight ? ' is-portrait' : ''}`}>
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
                {/* WebVTT-субтитры — браузер понимает только VTT, не SRT */}
                {project.artifacts['subtitles_vtt'] && (
                  <track
                    kind="subtitles"
                    src={`${API_VIDEO}/${projectId}/${project.artifacts['subtitles_vtt']}`}
                    srcLang={project.config?.target_language ?? 'ru'}
                    label="Субтитры"
                    default
                  />
                )}
              </video>
            </div>
          </div>

          {/* Редактор сегментов */}
          <div className="panel segments-panel glass-panel">
            <div className="panel-header">
              <h3 style={{minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}><AlignLeft size={16} /> {t('workspace.translationEditor', locale)}</h3>
              <span className="panel-header-meta">
                {segments.length} {t('workspace.segments', locale) || 'сегм.'}
                {dirty && <span className="dirty-indicator"> · {t('workspace.unsaved', locale)}</span>}
              </span>
            </div>
            {/* Z2.12: Поиск по сегментам */}
            <div className="seg-search-bar">
              <input
                id="seg-search-input"
                className="seg-search-input"
                type="text"
                placeholder={locale === 'ru' ? '🔍 Поиск по тексту...' : '🔍 Search segments...'}
                value={segSearch}
                onChange={e => setSegSearch(e.target.value)}
              />
              {segSearch && (
                <button className="seg-search-clear" onClick={() => setSegSearch('')} aria-label="Очистить">×</button>
              )}
            </div>
            <div className="segments-list">
              {segments
                .filter(seg => !segSearch || seg.source_text?.toLowerCase().includes(segSearch.toLowerCase()) ||
                  seg.translated_text?.toLowerCase().includes(segSearch.toLowerCase()))
                .map((seg) => (
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
                    {/* Z2.10: copy translated text */}
                    {seg.translated_text && (
                      <button
                        className="seg-copy-btn"
                        title={locale === 'ru' ? 'Скопировать перевод' : 'Copy translation'}
                        onClick={() => navigator.clipboard.writeText(seg.translated_text).catch(() => {})}
                        aria-label="Скопировать перевод"
                      >
                        📋
                      </button>
                    )}
                  </div>
                  <div className="seg-source-row">
                    <div className="seg-source">{seg.source_text}</div>
                    {/* Z4.11: diff — кол-во символов до/после */}
                    {seg.translated_text && seg.source_text && (
                      <span className={`seg-diff-badge ${
                        seg.translated_text.length > seg.source_text.length * 1.3 ? 'seg-diff--long' :
                        seg.translated_text.length < seg.source_text.length * 0.7 ? 'seg-diff--short' :
                        'seg-diff--ok'}`}
                        title={`Оригинал: ${seg.source_text.length} символов → Перевод: ${seg.translated_text.length} символов`}
                      >
                        {seg.source_text.length} → {seg.translated_text.length}
                      </span>
                    )}
                  </div>

                  {/* TTS-тулбар — показывается только при Яндекс TTS */}
                  {project.config?.professional_tts_provider === 'yandex' && (() => {
                    const ssmlOverride = (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override || '';
                    const currentText = ssmlOverride || seg.translated_text || '';
                    return (
                      <SSMLToolbar
                        getTextarea={() => ssmlTextareaRefs.current.get(seg.id) ?? null}
                        currentText={currentText}
                        hasOverride={!!ssmlOverride}
                        onChange={(v) => handleSsmlChange(seg.id, v)}
                        onReset={() => handleSsmlReset(seg.id)}
                        onPreview={async (text) => {
                          const url = await previewTTS(projectId, text, false);
                          const audio = new Audio();
                          // Сохраняем ссылку на window чтобы GC не убил объект во время воспроизведения
                          (window as any).__ttsPreviewAudio = audio;
                          audio.onended = () => { URL.revokeObjectURL(url); delete (window as any).__ttsPreviewAudio; };
                          audio.onerror = (e) => { console.error('[preview] audio error', e); URL.revokeObjectURL(url); delete (window as any).__ttsPreviewAudio; };
                          audio.src = url;
                          audio.load();
                          try { await audio.play(); } catch(e) { console.error('[preview] play error', e); }
                        }}
                      />
                    );
                  })()}

                  {/* Превью TTS — для OpenAI-совместимых провайдеров (Polza, NeuroAPI) */}
                  {(() => {
                    const prov = project.config?.professional_tts_provider ?? '';
                    if (!prov || prov === 'yandex') return null;
                    const segText = (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override
                      || seg.translated_text || '';
                    const isPreviewing = previewingSegId === seg.id;
                    return (
                      <div className="seg-preview-bar">
                        <button
                          className={`seg-preview-btn${isPreviewing ? ' seg-preview-btn--loading' : ''}`}
                          title="Прослушать синтез голоса для этого сегмента"
                          disabled={isPreviewing || !segText.trim()}
                          onClick={async () => {
                            if (isPreviewing) return;
                            setPreviewingSegId(seg.id);
                            try {
                              const url = await previewTTS(projectId, segText, false);
                              const audio = new Audio();
                              (window as any).__ttsPreviewAudio = audio;
                              audio.onended = () => { URL.revokeObjectURL(url); delete (window as any).__ttsPreviewAudio; setPreviewingSegId(null); };
                              audio.onerror = () => { URL.revokeObjectURL(url); delete (window as any).__ttsPreviewAudio; setPreviewingSegId(null); };
                              audio.src = url;
                              audio.load();
                              await audio.play();
                            } catch {
                              setPreviewingSegId(null);
                            }
                          }}
                        >
                          {isPreviewing
                            ? <Loader2 size={13} className="seg-preview-spinner" />
                            : <Play size={13} />}
                          {isPreviewing ? 'Синтез…' : 'Превью'}
                        </button>
                      </div>
                    );
                  })()}

                  <textarea
                    ref={(el) => {
                      if (el) ssmlTextareaRefs.current.set(seg.id, el);
                      else ssmlTextareaRefs.current.delete(seg.id);
                    }}
                    className={`seg-translated text-input ${
                      !seg.translated_text?.trim() ? 'seg-empty' : ''
                    }${
                      (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override ? ' seg-has-ssml' : ''
                    }`}
                    value={
                      (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override
                        || (seg.translated_text ?? '')
                    }
                    onChange={(e) => {
                      const hasOverride = !!(seg as Segment & { tts_ssml_override?: string }).tts_ssml_override;
                      if (hasOverride) {
                        handleSsmlChange(seg.id, e.target.value);
                      } else {
                        handleTextChange(seg.id, e.target.value);
                      }
                    }}
                    placeholder={
                      (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override
                        ? 'SSML / текст с тегами Яндекс SpeechKit'
                        : t('workspace.enterTranslation', locale)
                    }
                    rows={2}
                  />
                  {/* TTS Rich Preview — визуализация разметки */}
                  {(() => {
                    const ov = (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override;
                    if (!ov) return null;
                    const hasTtsMarkup = /\*\*|sil<\[|<\[(tiny|small|medium|large|huge)\]>|\[\[|\+[аеёиоуыэюяАЕЁИОУЫЭЮЯaeiouAEIOU]/i.test(ov);
                    if (!hasTtsMarkup) return null;
                    return (
                      <div className="tts-rich-preview" title="Предпросмотр TTS-разметки">
                        {renderTtsMarkup(ov)}
                      </div>
                    );
                  })()}
                  {/* Z2.11: Notes — комментарий редактора */}
                  <input
                    type="text"
                    className="seg-notes-input"
                    placeholder={locale === 'ru' ? '💬 Заметка редактора...' : '💬 Note...'}
                    value={seg.notes ?? ''}
                    onChange={(e) => handleTextChange(seg.id, e.target.value, 'notes')}
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
            <div className="right-tab-content right-tab-content--flush right-tab-content--stats">
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
          stageRuns={project.stage_runs ?? []}
          costEstimate={preflightCost.cost}
          durationEstimateSec={preflightCost.eta}
          speedChanged={(() => {
            // Находим последний успешный timing_fit с metadata скорости
            const timingRun = [...(project.stage_runs ?? [])]
              .reverse()
              .find(r => r.stage === 'timing_fit' && r.status === 'completed' && r.metadata);
            const cfg = project.config as unknown as Record<string, unknown> | undefined;
            const currentSpeed1 = cfg?.professional_tts_speed ?? 1.0;
            const currentSpeed2 = cfg?.professional_tts_speed_2 ?? 1.0;
            if (timingRun?.metadata) {
              const savedSpeed1 = timingRun.metadata['tts_speed_1'] ?? 1.0;
              const savedSpeed2 = timingRun.metadata['tts_speed_2'] ?? 1.0;
              return Math.abs(Number(currentSpeed1) - Number(savedSpeed1)) > 0.001
                  || Math.abs(Number(currentSpeed2) - Number(savedSpeed2)) > 0.001;
            }
            // Fallback: проверяем несохранённый configPatch
            const patch = configPatch as Record<string, unknown>;
            const saved = (project.config ?? {}) as Record<string, unknown>;
            return ['professional_tts_speed', 'professional_tts_speed_2'].some(k =>
              k in patch && patch[k] !== saved[k]
            );
          })()}
          onConfirm={(fromStage) => handleRunConfirmed(confirm.force, fromStage)}
          onCancel={() => setConfirm(null)}
        />
      )}

      {/* Модалка: Яндекс-разметка несовместима с выбранным провайдером */}
      {yandexRevertModal && (
        <div className="workspace-overlay" role="dialog" aria-modal="true">
          <div className="yandex-revert-card glass-panel">
            <div className="yandex-revert-icon">⚠️</div>
            <h3 className="yandex-revert-title">Несовместимые правки</h3>
            <p className="yandex-revert-body">
              У <strong>{yandexRevertModal.affectedCount}</strong> сегм.{' '}
              есть Яндекс-разметка (ударения <code>+</code>, паузы{' '}
              <code>{'sil<[…]>'}</code>, логическое ударение <code>{'**…**'}</code>).
            </p>
            <p className="yandex-revert-body">
              Провайдер <strong>{yandexRevertModal.pendingPatch.professional_tts_provider}</strong>{' '}
              её не поддерживает. Сбросить эти правки до оригинального перевода?
            </p>
            <div className="yandex-revert-actions">
              <button
                className="btn-secondary yandex-revert-btn-keep"
                onClick={() => {
                  // Применяем patch без сброса — разметка стриппируется при синтезе автоматически
                  setConfigPatch(prev => ({ ...prev, ...yandexRevertModal.pendingPatch }));
                  setYandexRevertModal(null);
                }}
              >
                Оставить как есть
              </button>
              <button
                className="btn-danger yandex-revert-btn-reset"
                onClick={() => {
                  const YANDEX_MARKUP_RE = /\*\*|sil<\[|<\[(tiny|small|medium|large|huge)\]>|\[\[|\+[аеёиоуыэюяАЕЁИОУЫЭЮЯaeiouAEIOU]/i;
                  const nextSegs = segments.map(s => {
                    const ov = (s as Segment & { tts_ssml_override?: string }).tts_ssml_override || '';
                    if (ov && YANDEX_MARKUP_RE.test(ov)) {
                      return { ...s, tts_ssml_override: '' };
                    }
                    return s;
                  });
                  pushHistory(nextSegs);
                  setProject(prev => prev ? { ...prev, segments: nextSegs } : prev);
                  setDirty(true);
                  setConfigPatch(prev => ({ ...prev, ...yandexRevertModal.pendingPatch }));
                  setYandexRevertModal(null);
                }}
              >
                Сбросить правки
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Z4.10: Keyboard shortcuts modal */}
      {showShortcuts && (
        <div className="modal-overlay" role="dialog" aria-modal="true" onClick={() => setShowShortcuts(false)}>
          <div className="modal-box shortcuts-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>⌨️ Горячие клавиши</h3>
              <button className="btn-icon" onClick={() => setShowShortcuts(false)} aria-label="Закрыть"><X size={18} /></button>
            </div>
            <div className="shortcuts-grid">
              <div className="shortcut-row"><kbd>Ctrl+S</kbd><span>Сохранить изменения</span></div>
              <div className="shortcut-row"><kbd>Ctrl+Z</kbd><span>Отменить последнее изменение</span></div>
              <div className="shortcut-row"><kbd>Ctrl+Y</kbd><span>Повторить</span></div>
              <div className="shortcut-row"><kbd>Ctrl+Enter</kbd><span>Запустить / продолжить перевод</span></div>
              <div className="shortcut-row"><kbd>Esc</kbd><span>Закрыть панель настроек</span></div>
              <div className="shortcut-row"><kbd>Space</kbd><span>Пауза / воспроизведение видео</span></div>
              <div className="shortcut-row"><kbd>←</kbd> / <kbd>→</kbd><span>Перемотка ±5 сек</span></div>
              <div className="shortcut-row"><kbd>Tab</kbd><span>Следующий сегмент</span></div>
              <div className="shortcut-row"><kbd>Alt+↑</kbd> / <kbd>Alt+↓</kbd><span>Навигация по сегментам (Z4.12)</span></div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
