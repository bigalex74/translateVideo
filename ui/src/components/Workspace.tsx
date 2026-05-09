import React, { useState, useEffect, useRef } from 'react';
import { apiHeaders, preflightVideo, artifactDownloadUrl, getProjectDoctor, getProjectSnapshots, getProjectStatus, rebuildSubtitles, runPipeline, runSegmentAction, saveProjectSegments, patchProjectConfig, cancelPipeline, previewTTS, subtitleExportUrl, subtitleExportZipUrl, safariSafeDownload, withApiKeyQuery } from '../api/client';
import type { ArtifactRecord, CostEstimate, ProjectDoctorReport, ProjectSnapshot, VideoProject, Segment, PipelineConfig } from '../types/schemas';
import { stageLabel, statusLabel, t } from '../i18n';
import type { AppLocale } from '../store/settings';
import { stageProgressInfo } from '../progress';
import { flagBelongsToStage } from '../qa_stage_filter';
import { QASummary } from './QASummary';
import { ConfirmRunModal } from './ConfirmRunModal';
import { AdvancedSettings } from './AdvancedSettings';
import { ExportPanel } from './ExportPanel';
import { StatsPanel } from './StatsPanel';
import { DevLogPanel } from './DevLogPanel';
import { VideoPlayerSection } from './workspace/VideoPlayerSection';
import { SegmentEditorHeader } from './workspace/SegmentEditorHeader';
import { SegmentList } from './workspace/SegmentList';
import { getPersistedProvider } from '../store/settings';
import {
  ArrowLeft, Download, RefreshCw, Save, CheckCircle2,
  Loader2, AlertCircle, Undo2, Redo2, Settings, X,
  Film, AlignLeft, Activity, Play, XCircle, AlertTriangle, Info, Share2, ExternalLink
} from 'lucide-react';
import './Workspace.css';
import { useProjectStatus } from '../hooks/useProjectStatus';
import { useVisibilityRefresh, requestCompletionNotification } from '../hooks/useVisibilityRefresh';

declare global {
  interface Window {
    __ttsPreviewAudio?: HTMLAudioElement;
  }
}

interface WorkspaceProps {
  projectId: string;
  onBack: () => void;
  locale: AppLocale;
}

// Правая панель: вкладки
type RightTab = 'status' | 'qa' | 'artifacts' | 'stats' | 'devlog';

const API_VIDEO = '/api/v1/video';

/** R7-И2: Форматирует секунды в HH:MM:SS для темпоральных меток сегментов (Глеб Гчит. 3, Валентина) */
function formatTimecode(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  const pad = (n: number) => String(n).padStart(2, '0');
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}


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
  const [doctorLoading, setDoctorLoading] = useState(false);
  const [doctorReport, setDoctorReport] = useState<ProjectDoctorReport | null>(null);
  const [snapshots, setSnapshots] = useState<ProjectSnapshot[]>([]);
  const [segmentActionLoading, setSegmentActionLoading] = useState<string | null>(null);
  const prevStatusRef = useRef<string | null>(null);
  const [confirm, setConfirm] = useState<{ force: boolean } | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [configPatch, setConfigPatch] = useState<Partial<PipelineConfig>>({});
  const [savingConfig, setSavingConfig] = useState(false);
  const [activeSegId, setActiveSegId] = useState<string | null>(null);
  const [previewingSegId, setPreviewingSegId] = useState<string | null>(null);
  const [isPortraitVideo, setIsPortraitVideo] = useState(false);
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
  const [segReplace, setSegReplace] = React.useState('');
  const [showReplace, setShowReplace] = React.useState(false);
  const [filterEmptyOnly, setFilterEmptyOnly] = React.useState(false);  // Л6: показывать только пустые
  const [qaFlagFilter, setQaFlagFilter] = React.useState('');  // NC8-02
  const [selectedSegIds, setSelectedSegIds] = React.useState<Set<string>>(new Set());  // Z2.15
  // Z4.10: Keyboard shortcuts help modal
  const [showShortcuts, setShowShortcuts] = useState(false);
  // R7-И3: Side-by-side режим (оригинал | перевод в две колонки) (Валентина Вт1, Глеб Гчит.10)
  const [sideBySide, setSideBySide] = useState(false);
  // Z3.11: Quality report state
  const [qualityReport, setQualityReport] = useState<Record<string, unknown> | null>(null);
  const [loadingQR, setLoadingQR] = useState(false);

  const fetchQualityReport = async () => {
    setLoadingQR(true);
    try {
      const resp = await fetch(`/api/v1/projects/${projectId}/quality-report`, { headers: apiHeaders() });
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
        }
      })
      .catch(e => console.error(e));
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Designer R6-iter2: Toast "Перевод готов!" при переходе running→completed
  // TVIDEO-223: + Browser Notification при завершении
  useEffect(() => {
    if (!project) return;
    const prev = prevStatusRef.current;
    if (prev === 'running' && project.status === 'completed') {
      setMessage('✅ Перевод завершён! Скачайте результат.');
      setTimeout(() => setMessage(''), 5000);
      // Browser Notification если вкладка не активна
      void requestCompletionNotification(projectId, 'completed');
    } else if (prev === 'running' && project.status === 'failed') {
      void requestCompletionNotification(projectId, 'failed');
    }
    prevStatusRef.current = project.status;
  }, [project, projectId]);

  // R8-И1: WebSocket + adaptive HTTP fallback через useProjectStatus hook (Глеб Г7)
  // Заменяет инлайн поллинг — больше нет дёргающего setInterval
  useProjectStatus({
    projectId,
    isRunning: project?.status === 'running',
    cancelling,
    onUpdate: (data) => {
      setProject(prev => (prev && dirty ? { ...data, segments: prev.segments } : data));
      if (data.status !== 'running') {
        setCancelling(false);
        setCancelConfirm(false);
        setCancelTimedOut(false);
      }
    },
    onError: (e) => console.error('[status] error', e),
  });

  // TVIDEO-223: Принудительный poll при возврате на вкладку (visibility change)
  // Решает проблему устаревшего статуса когда пользователь переключает вкладки.
  useVisibilityRefresh({
    enabled: project?.status === 'running',
    onVisible: () => {
      void getProjectStatus(projectId).then(data => {
        setProject(prev => (prev && dirty ? { ...data, segments: prev.segments } : data));
        if (data.status === 'completed' || data.status === 'failed') {
          void requestCompletionNotification(projectId, data.status as 'completed' | 'failed');
        }
      }).catch(() => {});
    },
  });
  useEffect(() => {
    if (!cancelling) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCancelTimedOut(false);
      return;
    }
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
  // R7-И2: beforeunload — браузер предупреждает при закрытии с несохранёнными правками (Глеб Г4)
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = 'Есть несохранённые изменения. Уйти?';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (dirty && project && project.status !== 'running') {
          document.getElementById('btn-save-segments')?.click();
        }
      }
      // Л5: Ctrl+H → открыть/закрыть панель замены
      if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
        e.preventDefault();
        setShowReplace(r => !r);
      }
      // D9: Alt+N → следующий непереведённый сегмент
      if (e.altKey && e.key === 'n' && project) {
        e.preventDefault();
        const segs = Array.isArray(project.segments) ? (project.segments as Segment[]) : [];
        const firstUntranslated = segs.find(s => !s.translated_text?.trim());
        if (firstUntranslated) {
          const el = segRefs.current.get(firstUntranslated.id);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            // Фокус на textarea внутри сегмента
            el.querySelector<HTMLTextAreaElement>('textarea')?.focus();
          }
        }
      }
      // Л3: Alt+] → следующий сегмент, Alt+[ → предыдущий
      if (e.altKey && (e.key === ']' || e.key === '[') && project) {
        e.preventDefault();
        const segs = Array.isArray(project.segments) ? (project.segments as Segment[]) : [];
        const active = document.activeElement?.closest('[data-seg-id]') as HTMLElement | null;
        const activeId = active?.dataset.segId;
        const idx = activeId ? segs.findIndex(s => String(s.id) === activeId) : -1;
        const nextIdx = e.key === ']' ? Math.min(idx + 1, segs.length - 1) : Math.max(idx - 1, 0);
        if (nextIdx >= 0) {
          const next = segs[nextIdx];
          const el = segRefs.current.get(next.id);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.querySelector<HTMLTextAreaElement>('textarea')?.focus();
          }
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [dirty, project]);

  // D-012 + О2: Прогресс + ETA в title браузера — '🔄 45% ~3мин | AI Video Translator'
  useEffect(() => {
    if (!project) return;
    const base = 'AI Video Translator';
    if (project.status === 'running') {
      const pct = project.progress_percent ?? 0;
      const eta = project.eta_seconds;
      const etaStr = eta != null && eta > 0
        ? (eta >= 60 ? ` ~${Math.ceil(eta / 60)}мин` : ` ~${eta}с`)
        : '';
      document.title = `🔄 ${pct}%${etaStr} | ${base}`;
    } else if (project.status === 'completed') {
      document.title = `✅ Готово | ${base}`;
    } else if (project.status === 'failed') {
      document.title = `❌ Ошибка | ${base}`;
    } else if (project.status === 'cancelled') {
      document.title = `Остановлено | ${base}`;
    } else {
      document.title = base;
    }
    return () => { document.title = base; };
  }, [project]);

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
  const FLAG_SEV = React.useMemo<Record<string, 'critical' | 'error' | 'warning' | 'info'>>(() => ({
    translation_empty: 'critical', tts_invalid_slot: 'critical',
    timing_fit_invalid_slot: 'critical', timeline_audio_extends_video: 'critical',
    translation_fallback_source: 'error', tts_overflow_after_rate: 'error',
    timing_fit_failed: 'error', render_audio_trimmed: 'error', timeline_shift_limit_reached: 'error',
    tts_overflow_natural_rate: 'warning', render_audio_overflow: 'warning',
    tts_rate_adapted: 'warning', translation_rewritten_for_timing: 'warning',
    rewrite_provider_failed: 'warning', render_speed_fallback: 'warning',
    tts_pretrim: 'warning', timeline_shifted: 'warning',
    rewrite_provider_quota_limited: 'warning', rewrite_provider_cooldown: 'warning',
  }), []);

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
  }, [FLAG_SEV, project]);

  if (!project) return (
    <div className="workspace-loading">
      <Loader2 className="animate-spin text-accent" size={32} />
      <p>{t('workspace.loading', locale)}</p>
    </div>
  );

  const isRunning = project.status === 'running';
  const isDone = project.status === 'completed';
  const segments = Array.isArray(project.segments) ? (project.segments as Segment[]) : [];
  const filteredSegments = segments
    .filter(seg => !segSearch || seg.source_text?.toLowerCase().includes(segSearch.toLowerCase()) ||
      seg.translated_text?.toLowerCase().includes(segSearch.toLowerCase()))
    .filter(seg => !qaFlagFilter || (seg.qa_flags ?? []).includes(qaFlagFilter))
    .filter(seg => !filterEmptyOnly || !seg.translated_text?.trim());
  const hasTranslatedText = segments.some(seg => Boolean((seg.translated_text ?? '').trim()));
  const canPartialRerun = !isRunning && hasTranslatedText;
  const hasVoicePipeline = project.config?.translation_mode !== 'subtitles';

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
        s.id === segId ? {
          ...s,
          [field]: newText,
          // Z2.16: Счётчик правок инкрементируется при изменении перевода
          ...(field === 'translated_text' ? { edit_count: (s.edit_count ?? 0) + 1 } : {}),
        } : s
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

  // ─── Z2.14: Объединение двух соседних сегментов ──────────────────────────────
  const handleMergeSegments = (segId: string) => {
    setProject(prev => {
      if (!prev) return prev;
      const segs = prev.segments as Segment[];
      const idx = segs.findIndex(s => s.id === segId);
      if (idx < 0 || idx >= segs.length - 1) return prev;

      const curr = segs[idx];
      const next = segs[idx + 1];
      const merged: Segment = {
        ...curr,
        end: next.end,
        source_text: [curr.source_text, next.source_text].filter(Boolean).join(' '),
        translated_text: [curr.translated_text, next.translated_text].filter(Boolean).join(' '),
        notes: [curr.notes, next.notes].filter(Boolean).join(' | '),
      };
      const newSegs = [...segs.slice(0, idx), merged, ...segs.slice(idx + 2)];
      return { ...prev, segments: newSegs };
    });
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

  const saveDirtySegments = async (): Promise<boolean> => {
    if (!dirty) return true;
    setSaving(true);
    try {
      await saveProjectSegments(projectId, segments);
      setDirty(false);
      return true;
    } catch (saveErr) {
      setMessage(`${t('workspace.saveError', locale)}: ${saveErr instanceof Error ? saveErr.message : String(saveErr)}`);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const startPartialRerun = async (fromStage: string, label: string) => {
    setMessage('');
    setRightTab('status');
    if (!(await saveDirtySegments())) return;
    try {
      await runPipeline(projectId, false, undefined, undefined, fromStage);
      setProject(prev => prev ? { ...prev, status: 'running' } : prev);
      setMessage(`${label}: запущено`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : t('workspace.runError', locale));
    }
  };

  const rebuildCurrentSubtitles = async () => {
    setMessage('');
    if (!(await saveDirtySegments())) return;
    try {
      await rebuildSubtitles(projectId);
      const data = await getProjectStatus(projectId);
      setProject(prev => (prev && dirty ? { ...data, segments: prev.segments } : data));
      setMessage('Субтитры пересобраны');
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Не удалось пересобрать субтитры');
    }
  };

  const runDoctor = async () => {
    setDoctorLoading(true);
    setMessage('');
    try {
      const [report, snapshotData] = await Promise.all([
        getProjectDoctor(projectId),
        getProjectSnapshots(projectId),
      ]);
      setDoctorReport(report);
      setSnapshots(snapshotData.snapshots);
      setRightTab('status');
      const issueCount = report.issues.length;
      const recommended = report.recommended_from_stage
        ? ` Рекомендуемый старт: ${stageLabel(report.recommended_from_stage, locale)}.`
        : '';
      setMessage(`Проверка проекта: ${issueCount === 0 ? 'проблем не найдено' : `найдено ${issueCount}`}.${recommended}`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Не удалось проверить проект');
    } finally {
      setDoctorLoading(false);
    }
  };

  const continueFromDoctor = async () => {
    const fromStage = doctorReport?.recommended_from_stage ?? null;
    if (!fromStage) {
      setMessage('Project Doctor не нашёл этап для продолжения');
      return;
    }
    await startPartialRerun(fromStage, `Продолжение с этапа ${stageLabel(fromStage, locale)}`);
  };

  const selectSegmentsWhere = (predicate: (segment: Segment) => boolean) => {
    setSelectedSegIds(new Set(segments.filter(predicate).map(segment => segment.id)));
  };

  const runSelectedSegmentAction = async (
    action: 'translate' | 'tts' | 'reset-tts' | 'mark-reviewed',
    label: string,
    force = false,
  ) => {
    const ids = Array.from(selectedSegIds);
    if (ids.length === 0) return;
    setSegmentActionLoading(action);
    setMessage('');
    if (!(await saveDirtySegments())) {
      setSegmentActionLoading(null);
      return;
    }
    try {
      const result = await runSegmentAction(projectId, action, ids, force);
      setProject(result.project);
      setSelectedSegIds(new Set());
      setMessage(`${label}: ${result.changed}`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : `Не удалось выполнить: ${label}`);
    } finally {
      setSegmentActionLoading(null);
    }
  };

  const handleRunConfirmed = async (force: boolean, fromStage: string | null) => {
    setConfirm(null);
    setMessage('');
    setRightTab('status');
    try {
      // Автосохранение несохранённых правок перед запуском пайплайна.
      // Без этого TTS использует старый текст с диска, а не отредактированный.
      if (!(await saveDirtySegments())) return;
      await runPipeline(projectId, force, undefined, undefined, fromStage);
      // TVIDEO-223: Запрашиваем разрешение на уведомления при первом запуске (контекстуально)
      if ('Notification' in window && Notification.permission === 'default') {
        void Notification.requestPermission();
      }
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
      return withApiKeyQuery(`${API_VIDEO}/${projectId}/${project.artifacts['output_video']}`);
    }
    return withApiKeyQuery(`${API_VIDEO}/${projectId}/input.mp4`);
  };

  // ─── Helpers ──────────────────────────────────────────────────────────────

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle2 size={16} className="text-success" />;
      case 'failed':    return <AlertCircle  size={16} className="text-danger" />;
      case 'cancelled': return <XCircle      size={16} className="text-muted" />;
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
    { kind: 'output_video',           label: '🎬 Готовое видео (MP4)',         title: 'Финальный MP4 — видео с переведённой озвучкой и/или субтитрами. Оригинальный файл заменён.' },
    { kind: 'output_video_with_subs', label: '🎬💬 Видео + субтитры (MP4)',   title: 'MP4 с встроенными субтитрами поверх видео.' },
    { kind: 'subtitles',              label: '📄 Субтитры (SRT)',              title: 'Файл субтитров формата SRT — совместим с большинством видеоплееров и YouTube.' },
    { kind: 'subtitles_vtt',          label: '📄 Субтитры (VTT)',              title: 'WebVTT — для использования в браузере и HTML5-видео.' },
    { kind: 'qa_report',              label: '✅ QA-отчёт (JSON)',             title: 'Машинная проверка качества перевода: пустые сегменты, превышения тайминга, несоответствия.' },
    { kind: 'translated_transcript',  label: '📝 Перевод (JSON)',              title: 'Полный JSON с оригинальными и переведёнными сегментами — для дальнейшей обработки.' },
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
                ? `Ожидаем завершения этапа «${runningStage ? stageLabel(runningStage.stage, locale) : '…'}» — после этого перевод остановится.`
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
          {!isRunning && (project.status === 'failed' || project.status === 'cancelled') && (
            <button
              className="btn-success btn-sm"
              onClick={() => setConfirm({ force: false })}
              title="Возобновить с проваленного этапа"
            >
              <Play size={14} /> {t('workspace.continue', locale)}
            </button>
          )}
          {!isRunning && (project.status === 'created' || project.status === 'failed' || project.status === 'completed' || project.status === 'cancelled') && (
            <button
              className="btn-secondary btn-sm"
              onClick={() => setConfirm({ force: true })}
              title={
                project.status === 'completed'
                  ? '🔄 Запустить перевод заново: все этапы будут выполнены повторно — извлечение аудио, распознавание речи, перевод текста, озвучка и монтаж. Старые файлы будут перезаписаны.'
                  : '▶️ Запустить перевод с нуля: последовательно выполнятся все этапы. Это может занять несколько минут в зависимости от длины видео.'
              }
            >
              <RefreshCw size={14} /> {project.status === 'completed' ? t('workspace.run', locale) : t('workspace.restart', locale)}
            </button>
          )}
          {canPartialRerun && (
            <div className="partial-rerun-group" aria-label="Частичная пересборка">
              <button
                className="btn-secondary btn-sm"
                onClick={rebuildCurrentSubtitles}
                title="Пересобрать SRT/VTT из текущего текста без полного пайплайна"
              >
                <AlignLeft size={14} /> Субтитры
              </button>
              {hasVoicePipeline && (
                <>
                  <button
                    className="btn-secondary btn-sm"
                    onClick={() => startPartialRerun('tts', 'Озвучка')}
                    title="Пересинтезировать озвучку и пересобрать видео"
                  >
                    <Activity size={14} /> Озвучка
                  </button>
                  <button
                    className="btn-secondary btn-sm"
                    onClick={() => startPartialRerun('render', 'Видео')}
                    title="Пересобрать видео; если TTS-файлы уже удалены, сервер безопасно начнёт раньше"
                  >
                    <Film size={14} /> Видео
                  </button>
                </>
              )}
            </div>
          )}
          {!isRunning && (
            <button
              className="btn-icon"
              title="Проверить проект и рекомендовать безопасное продолжение"
              aria-label="Проверить проект"
              disabled={doctorLoading}
              onClick={runDoctor}
            >
              {doctorLoading ? <Loader2 size={15} className="animate-spin" /> : <Activity size={15} />}
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
            <button
              className="btn-download-cta"
              title="Скачать готовое видео"
              onClick={() => safariSafeDownload(
                artifactDownloadUrl(projectId, primaryArtifacts[0].kind),
                `${projectId}_translated.mp4`
              )}
            >
              <Download size={14} />
              {locale === 'ru' ? 'Скачать' : 'Download'}
            </button>
          )}
        </div>
      </header>

      {/* ═══ Уведомление ═══ */}
      {message && (
        <div className="workspace-message" role="status">{message}</div>
      )}

      {/* С3: Error Recovery Guide — показывается при status=failed */}
      {!isRunning && project.status === 'failed' && (() => {
        const failedStage = project.stage_runs?.find((r: { status: string }) => r.status === 'failed');
        const stageHints: Record<string, string> = {
          extract_audio: '🔊 Проверьте формат видеофайла (MP4/MKV/AVI). Попробуйте перекодировать видео.',
          transcribe: '🎙️ Возможно аудио слишком тихое или с шумом. Увеличьте громкость или используйте другой файл.',
          translate: '🌐 Проверьте API-ключ провайдера перевода и баланс счёта в настройках.',
          tts: '🔈 Проверьте API-ключ TTS-провайдера и баланс. Попробуйте другого провайдера.',
          timing_fit: '⏱️ Слишком длинный перевод. Попробуйте скорость TTS 1.2× или уменьшить текст сегментов.',
          render: '🎬 Ошибка монтажа. Проверьте что файл не удалён. Нажмите «Продолжить» для повтора.',
          export: '📦 Ошибка экспорта. Убедитесь что есть свободное место на диске. Нажмите «Продолжить».',
        };
        const stageKey = failedStage ? String((failedStage as { stage?: string }).stage ?? '') : '';
        const hint = stageHints[stageKey] || '❓ Нажмите «Продолжить» для повтора с проваленного этапа или «Перезапустить» для полного старта.';
        return (
          <div style={{
            display: 'flex', gap: '10px', alignItems: 'flex-start',
            background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)',
            borderRadius: '10px', padding: '10px 14px', marginBottom: '12px',
            fontSize: '0.84rem', color: '#fca5a5',
          }}>
            <span style={{ fontSize: '1.2rem', flexShrink: 0 }}>🆘</span>
            <div>
              <strong style={{ display: 'block', marginBottom: '2px', color: '#fca5a5' }}>
                Что делать при ошибке{stageKey ? ` (этап: ${stageKey})` : ''}
              </strong>
              {hint}
            </div>
          </div>
        );
      })()}

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
          <VideoPlayerSection
            project={project}
            projectId={projectId}
            locale={locale}
            videoTab={videoTab}
            setVideoTab={setVideoTab}
            isPortraitVideo={isPortraitVideo}
            setIsPortraitVideo={setIsPortraitVideo}
            videoRef={videoRef}
            getVideoUrl={getVideoUrl}
            findArtifact={findArtifact}
            segments={segments}
            activeSegId={activeSegId}
            setActiveSegId={setActiveSegId}
          />

          {/* Редактор сегментов */}
          <div className="panel segments-panel glass-panel">
            <SegmentEditorHeader
              locale={locale}
              project={project}
              setProject={setProject}
              segments={segments}
              filteredSegments={filteredSegments}
              dirty={dirty}
              setDirty={setDirty}
              setMessage={setMessage}
              segSearch={segSearch}
              setSegSearch={setSegSearch}
              segReplace={segReplace}
              setSegReplace={setSegReplace}
              showReplace={showReplace}
              setShowReplace={setShowReplace}
              qaFlagFilter={qaFlagFilter}
              setQaFlagFilter={setQaFlagFilter}
              filterEmptyOnly={filterEmptyOnly}
              setFilterEmptyOnly={setFilterEmptyOnly}
              selectedSegIds={selectedSegIds}
              setSelectedSegIds={setSelectedSegIds}
              sideBySide={sideBySide}
              setSideBySide={setSideBySide}
              selectSegmentsWhere={selectSegmentsWhere}
              segmentActionLoading={segmentActionLoading}
              runSelectedSegmentAction={runSelectedSegmentAction}
            />
            <SegmentList
              project={project!}
              projectId={projectId}
              locale={locale}
              segments={segments}
              filteredSegments={filteredSegments}
              activeSegId={activeSegId}
              selectedSegIds={selectedSegIds}
              setSelectedSegIds={setSelectedSegIds}
              videoRef={videoRef}
              formatTimecode={formatTimecode}
              previewingSegId={previewingSegId}
              setPreviewingSegId={setPreviewingSegId}
              previewTTS={previewTTS}
              handleSsmlChange={handleSsmlChange}
              handleSsmlReset={handleSsmlReset}
              handleTextChange={handleTextChange}
              handleMergeSegments={handleMergeSegments}
              setSegRef={(id, el) => {
                if (el) segRefs.current.set(id, el);
                else segRefs.current.delete(id);
              }}
              setSsmlTextareaRef={(id, el) => {
                if (el) ssmlTextareaRefs.current.set(id, el);
                else ssmlTextareaRefs.current.delete(id);
              }}
              getSsmlTextareaRef={(id) => ssmlTextareaRefs.current.get(id) ?? null}
              sideBySide={sideBySide}
              isRunning={isRunning}
              setConfirm={setConfirm}
            />
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

          {/* Вкладка: Файлы — ExportPanel [R11-И1] */}
          {rightTab === 'artifacts' && (
            <ExportPanel
              projectId={projectId}
              locale={locale}
              segments={segments}
              artifactRecords={project.artifact_records}
              downloadableArtifacts={downloadableArtifacts}
            />
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
