import React, { useState, useRef } from 'react';
import { URLDownloadStatus } from './URLDownloadStatus';
import { createProject, preflightVideo } from '../api/client';
import type { PipelineConfigDraft, PreflightReport } from '../types/schemas';
import { providerLabels, providerWarning, t } from '../i18n';
import { AdvancedSettings } from './AdvancedSettings';
import { DEFAULT_CONFIG } from './advancedSettingsConfig';
import { getPersistedProvider, persistProvider, type AppLocale } from '../store/settings';
import type { PipelineConfig } from '../types/schemas';
import {
  Play, UploadCloud, Link as LinkIcon, FileVideo, Loader2, ShieldCheck,
  Info, Clock, ArrowRight, ArrowLeft, Zap, HelpCircle,
  GraduationCap, Users, Monitor, FileText, Settings
} from 'lucide-react';
import './NewProject.css';

// ─── Tooltip для технических терминов (C-03) ───────────────────────────────
const TERM_GLOSSARY: Record<string, string> = {
  'TTS': 'Text-to-Speech — синтез речи. Технология, которая превращает текст перевода в голос.',
  'Провайдер': 'Сервис, который выполняет озвучку (например, OpenAI или Яндекс). Каждый провайдер имеет свои голоса и стоимость.',
  'Движок обработки': 'Сервис AI, который озвучивает переведённый текст. OpenAI — высокое качество, Яндекс — оптимально для русского.',
  'Дубляж': 'Режим, при котором оригинальная речь заменяется озвученным переводом.',
  'Preflight': 'Предварительная проверка файла: формат, длина, наличие звука. Помогает убедиться что файл подходит до запуска.',
  'Пресет': 'Готовый набор настроек для типичного сценария (Shorts, Лекция, Интервью). Выбери пресет — и не нужно настраивать вручную.',
};

const Tooltip: React.FC<{ term: string; children: React.ReactNode }> = ({ term, children }) => {
  const [show, setShow] = useState(false);
  const tip = TERM_GLOSSARY[term];
  if (!tip) return <>{children}</>;
  return (
    <span className="term-tooltip-wrap">
      {children}
      <button
        type="button"
        className="term-help-btn"
        aria-label={`Что такое ${term}?`}
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onFocus={() => setShow(true)}
        onBlur={() => setShow(false)}
      >
        <HelpCircle size={13} />
      </button>
      {show && <div className="term-tooltip" role="tooltip">{tip}</div>}
    </span>
  );
};

interface NewProjectProps {
  onProjectCreated: (id: string) => void;
  locale: AppLocale;
}

// ─── Пресеты сценариев ────────────────────────────────────────────────────

const PRESETS = [
  {
    id: 'default',
    label: 'Без пресета',
    icon: <Settings size={20} />,
    description: 'Настройки по умолчанию',
    config: {},
  },
  {
    id: 'shorts',
    label: 'Shorts / TikTok',
    icon: <Zap size={20} />,
    description: 'Короткое видео, укороченный перевод под тайминг',
    config: { adaptation_level: 'shortened_for_timing', voice_strategy: 'single', translation_style: 'casual' },
  },
  {
    id: 'lecture',
    label: 'Лекция / Курс',
    icon: <GraduationCap size={20} />,
    description: 'Образовательный стиль, строгое QA',
    config: { translation_style: 'educational', adaptation_level: 'natural', quality_gate: 'strict' },
  },
  {
    id: 'interview',
    label: 'Интервью',
    icon: <Users size={20} />,
    description: 'Два голоса, нейтральный стиль',
    config: { voice_strategy: 'two_voices', translation_style: 'neutral' },
  },
  {
    id: 'webinar',
    label: 'Вебинар / Презентация',
    icon: <Monitor size={20} />,
    description: 'Деловой стиль, естественная адаптация',
    config: { translation_style: 'business', adaptation_level: 'natural' },
  },
  {
    id: 'subtitles',
    label: 'Только субтитры',
    icon: <FileText size={20} />,
    description: 'Без озвучки — только файл субтитров',
    config: { translation_mode: 'subtitles' },
  },
] as const;

// ─── Режимы пайплайна ─────────────────────────────────────────────────────

const PIPELINE_MODES = [
  {
    id: 'voiceover',
    icon: '🎙️',
    label: 'Дубляж',
    description: 'Перевод + озвучка. Оригинальный звук приглушён.',
  },
  {
    id: 'subtitles',
    icon: '💬',
    label: 'Субтитры',
    description: 'Только SRT/VTT файлы. Без TTS и рендера — быстро и бесплатно.',
  },
  {
    id: 'voiceover_and_subtitles',
    icon: '🎙️💬',
    label: 'Дубляж + субтитры',
    description: 'Озвучка вшивается в видео, и дополнительно генерируются SRT/VTT.',
  },
] as const;

// ─── Компонент ────────────────────────────────────────────────────────────

export const NewProject: React.FC<NewProjectProps> = ({ onProjectCreated, locale }) => {
  // Шаги wizard: 0=Файл, 1=Параметры+Пресет, 2=Расширенные
  const [step, setStep] = useState(0);

  // Шаг 0
  const [inputType, setInputType]   = useState<'upload' | 'url'>('upload');
  const [file, setFile]             = useState<File | null>(null);
  const [videoUrl, setVideoUrl]     = useState('');
  const [projectId, setProjectId]   = useState('');
  const [checking, setChecking]     = useState(false);
  const [preflight, setPreflight]   = useState<PreflightReport | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Шаг 1
  const [sourceLang, setSourceLang] = useState('auto');
  const [targetLang, setTargetLang] = useState('ru');
  const [mode, setMode]             = useState('voiceover');
  const [provider, setProvider]     = useState(getPersistedProvider);
  const [selectedPreset, setSelectedPreset] = useState('default');

  // Шаг 2
  const [advConfig, setAdvConfig]   = useState<Partial<PipelineConfig>>(DEFAULT_CONFIG);

  // Общее
  const [loading, setLoading]       = useState(false);
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [urlDownloading, setUrlDownloading] = useState(false);  // NC-01 yt-dlp
  const [error, setError]           = useState('');

  const currentProviderWarning = providerWarning(provider, locale);

  /* ─── Helpers ─────────────────────────────────────────────────────────── */

  const formatDuration = (secs?: number | null): string => {
    if (!secs) return '';
    const m = Math.floor(secs / 60);
    const s = Math.round(secs % 60);
    return `${m}м ${s}с`;
  };

  const estimatedTime = (secs?: number | null): string => {
    if (!secs) return '';
    const factor = provider === 'fake' ? 0.05 : 3;
    const est = Math.ceil(secs * factor / 60);
    return est < 1 ? '< 1 мин' : `~${est} мин`;
  };

  /* ─── Drag & Drop ─────────────────────────────────────────────────────── */

  const applyFile = (f: File) => {
    setFile(f);
    if (!projectId) {
      const name = f.name.replace(/\.[^/.]+$/, '').replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
      setProjectId(name);
    }
    setPreflight(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files?.[0]) applyFile(e.dataTransfer.files[0]);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) applyFile(e.target.files[0]);
  };

  /* ─── Preflight ────────────────────────────────────────────────────────── */

  const handlePreflight = async () => {
    if (!videoUrl) { setError(t('newProject.needUrl', locale)); return; }
    setChecking(true);
    setError('');
    try {
      const report = await preflightVideo(videoUrl, provider);
      setPreflight(report);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('newProject.preflightError', locale));
    } finally {
      setChecking(false);
    }
  };

  /* ─── Preset ───────────────────────────────────────────────────────────── */

  const applyPreset = (presetId: string) => {
    setSelectedPreset(presetId);
    const preset = PRESETS.find(p => p.id === presetId);
    if (preset) {
      setAdvConfig(prev => ({ ...DEFAULT_CONFIG, ...prev, ...preset.config }));
      if ('translation_mode' in preset.config && preset.config.translation_mode) {
        setMode(preset.config.translation_mode as string);
      }
    }
  };

  /* ─── Submit ───────────────────────────────────────────────────────────── */

  const handleSubmit = async () => {
    if (inputType === 'upload' && !file) {
      setError(t('newProject.needFile', locale));
      return;
    }
    if (inputType === 'url' && !videoUrl) {
      setError(t('newProject.needUrl', locale));
      return;
    }
    setLoading(true);
    setUploadPercent(inputType === 'upload' ? 0 : null);
    setError('');
    try {
      const config: PipelineConfigDraft = {
        source_language: sourceLang,
        target_language: targetLang,
        translation_mode: mode,
        ...advConfig,
      };
      let project;
      if (inputType === 'upload' && file) {
        // XHR с progress tracking (C-04)
        project = await new Promise<{ project_id: string }>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) setUploadPercent(Math.round(e.loaded / e.total * 100));
          };
          xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve(JSON.parse(xhr.responseText));
            } else {
              reject(new Error(xhr.responseText || `HTTP ${xhr.status}`));
            }
          };
          xhr.onerror = () => reject(new Error('Network error'));
          const fd = new FormData();
          fd.append('file', file);
          if (projectId) fd.append('project_id', projectId);
          fd.append('config', JSON.stringify(config));
          xhr.open('POST', '/api/v1/projects/upload');
          const apiKey = localStorage.getItem('api_key');
          if (apiKey) xhr.setRequestHeader('X-API-Key', apiKey);
          xhr.send(fd);
        });
      } else {
        // NC-01: показываем индикатор скачивания yt-dlp
        if (videoUrl.startsWith('http://') || videoUrl.startsWith('https://')) {
          setUrlDownloading(true);
        }
        project = await createProject(videoUrl, projectId || undefined, config);
      }
      persistProvider(provider);
      onProjectCreated(project.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('newProject.createError', locale));
    } finally {
      setLoading(false);
      setUploadPercent(null);
      setUrlDownloading(false);
    }
  };

  /* ─── Navigation ────────────────────────────────────────────────────────── */

  const canGoStep1 = inputType === 'upload' ? !!file : !!videoUrl;

  const stepTitles = [t('newProject.stepFile', locale), t('newProject.stepParams', locale), t('newProject.stepSettings', locale)];

  /* ─── Render ────────────────────────────────────────────────────────────── */

  return (
    <div className="new-project page-container fade-in">
      <header className="page-header">
        <h2>{t('newProject.title', locale)}</h2>
        <p className="subtitle">{t('newProject.subtitle', locale)}</p>
      </header>

      {/* Индикатор шагов */}
      <div className="wizard-steps">
        {stepTitles.map((title, i) => (
          <div
            key={i}
            className={`wizard-step ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`}
            onClick={() => i < step && setStep(i)}
          >
            <span className="wizard-step-num">{i < step ? '✓' : i + 1}</span>
            <span className="wizard-step-label">{title}</span>
          </div>
        ))}
      </div>

      <div className="glass-panel wizard-form">

        {/* ═══ Шаг 0: Файл ═══ */}
        {step === 0 && (
          <>
            <div className="input-type-toggle">
              <button type="button" className={inputType === 'upload' ? 'active' : ''} onClick={() => setInputType('upload')}>
                <UploadCloud size={16} /> {t('newProject.uploadFile', locale)}
              </button>
              <button type="button" className={inputType === 'url' ? 'active' : ''} onClick={() => setInputType('url')}>
                <LinkIcon size={16} /> {t('newProject.urlPath', locale)}
              </button>
            </div>

            {inputType === 'upload' ? (
              <div
                className={`drop-zone ${file ? 'has-file' : ''}`}
                onDragOver={e => e.preventDefault()}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input type="file" accept="video/*,audio/*" ref={fileInputRef} onChange={handleFileSelect} style={{ display: 'none' }} />
                {file ? (
                  <div className="file-info">
                    <FileVideo size={48} className="text-accent" />
                    <span className="file-name">{file.name}</span>
                    <span className="file-size">{(file.size / (1024 * 1024)).toFixed(2)} МБ</span>
                    <span className="change-file">{t('newProject.changeFile', locale)}</span>
                  </div>
                ) : (
                  <div className="drop-prompt">
                    <UploadCloud size={64} className="text-muted" />
                    <span className="drop-prompt-title">{t('newProject.dropVideo', locale)}</span>
                    <span className="text-muted text-sm">{t('newProject.clickToChoose', locale)}</span>
                    <span className="drop-prompt-formats">MP4, MKV, MOV, AVI, YouTube</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="form-group">
                <label>{t('newProject.urlPath', locale)}</label>
                <input
                  className="text-input"
                  value={videoUrl}
                  onChange={e => setVideoUrl(e.target.value)}
                  placeholder="https://example.com/video.mp4 или /app/data/video.mp4"
                />
                <button type="button" className="btn-secondary preflight-button" onClick={handlePreflight} disabled={checking}>
                  {checking ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                  Проверить файл
                </button>
              </div>
            )}

            {preflight && (
              <div className={`preflight-report ${preflight.ok ? 'ok' : 'failed'}`}>
                <div className="preflight-header">
                  <strong>{preflight.ok ? '✅ Проверка пройдена' : '⚠️ Обнаружены проблемы'}</strong>
                  {preflight.duration_seconds && (
                    <span className="preflight-duration">
                      <Clock size={13} />
                      {formatDuration(preflight.duration_seconds)} → оценка: {estimatedTime(preflight.duration_seconds)}
                    </span>
                  )}
                </div>
                <ul>
                  {preflight.checks.map(check => (
                    <li key={check.name} className={check.ok ? 'ok' : 'failed'}>
                      <span>{check.ok ? 'OK' : 'FAIL'}</span>
                      {check.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="project-id-input">{t('newProject.projectName', locale)}</label>
              <input
                id="project-id-input"
                className="text-input"
                value={projectId}
                onChange={e => setProjectId(e.target.value)}
                placeholder={t('newProject.projectNamePlaceholder', locale)}
              />
            </div>
          </>
        )}

        {/* ═══ Шаг 1: Язык + Пресет ═══ */}
        {step === 1 && (
          <>
            {/* Языки */}
            <div className="form-row">
              <div className="form-group">
                <label>Исходный язык</label>
                <select className="select-input" value={sourceLang} onChange={e => setSourceLang(e.target.value)}>
                  <option value="auto">🔍 Автоопределение</option>
                  <option value="en">🇬🇧 Английский</option>
                  <option value="ko">🇰🇷 Корейский</option>
                  <option value="ja">🇯🇵 Японский</option>
                  <option value="zh">🇨🇳 Китайский</option>
                  <option value="ru">🇷🇺 Русский</option>
                  <option value="de">🇩🇪 Немецкий</option>
                  <option value="fr">🇫🇷 Французский</option>
                  <option value="es">🇪🇸 Испанский</option>
                </select>
              </div>
              <div className="form-group">
                <label>Язык перевода</label>
                <select className="select-input" value={targetLang} onChange={e => setTargetLang(e.target.value)}>
                  <option value="ru">🇷🇺 Русский</option>
                  <option value="en">🇬🇧 Английский</option>
                  <option value="de">🇩🇪 Немецкий</option>
                  <option value="fr">🇫🇷 Французский</option>
                  <option value="es">🇪🇸 Испанский</option>
                  <option value="zh">🇨🇳 Китайский</option>
                  <option value="ja">🇯🇵 Японский</option>
                </select>
              </div>
            </div>

            {/* Пресеты */}
            <div className="form-group">
              <label>Сценарий использования</label>
              <div className="preset-grid">
                {PRESETS.map(preset => (
                  <button
                    key={preset.id}
                    type="button"
                    className={`preset-card ${selectedPreset === preset.id ? 'active' : ''}`}
                    onClick={() => applyPreset(preset.id)}
                  >
                    <span className="preset-icon">{preset.icon}</span>
                    <span className="preset-label">{preset.label}</span>
                    <span className="preset-desc">{preset.description}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Режим пайплайна — карточки */}
            <div className="form-group">
              <label>Что делать с видео?</label>
              <div className="mode-cards">
                {PIPELINE_MODES.map(m => (
                  <button
                    key={m.id}
                    type="button"
                    className={`mode-card ${mode === m.id ? 'mode-card--active' : ''}`}
                    onClick={() => setMode(m.id)}
                  >
                    <span className="mode-card__icon">{m.icon}</span>
                    <span className="mode-card__label">{m.label}</span>
                    <span className="mode-card__desc">{m.description}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Движок */}
            <div className="form-group">
              <label>
                <Tooltip term="Движок обработки">Движок обработки</Tooltip>
              </label>
              <select
                className="select-input"
                value={provider}
                onChange={e => { setProvider(e.target.value); setPreflight(null); }}
              >
                {Object.entries(providerLabels(locale)).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
              {currentProviderWarning && (
                <div className="provider-info">
                  <Info size={14} />
                  {currentProviderWarning}
                </div>
              )}
            </div>
          </>
        )}

        {/* ═══ Шаг 2: Расширенные настройки ═══ */}
        {step === 2 && (
          <div className="adv-scroll-wrap">
            <AdvancedSettings
              config={advConfig}
              onChange={patch => setAdvConfig(prev => ({ ...prev, ...patch }))}
            />
          </div>
        )}

        {error && <div className="error-banner" role="alert">{error}</div>}

        {/* Upload progress bar (C-04) */}
        {uploadPercent !== null && (
          <div className="upload-progress-wrap" aria-label={`Загрузка файла: ${uploadPercent}%`}>
            <div className="upload-progress-label">
              <UploadCloud size={14} />
              <span>Загрузка файла… {uploadPercent}%</span>
            </div>
            <div className="upload-progress-bar">
              <div className="upload-progress-fill" style={{ width: `${uploadPercent}%` }} />
            </div>
          </div>
        )}

        {/* NC-01: yt-dlp URL download indicator */}
        <URLDownloadStatus isVisible={urlDownloading} url={videoUrl} />

        {/* ─── Навигация ─── */}
        <div className="wizard-nav">
          {step > 0 && (
            <button type="button" className="btn-secondary" onClick={() => setStep(s => s - 1)}>
              <ArrowLeft size={16} /> {t('newProject.back', locale)}
            </button>
          )}
          <div style={{ flex: 1 }} />
          {step < 2 && (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setStep(s => s + 1)}
              disabled={step === 0 && !canGoStep1}
            >
              {t('newProject.next', locale)} <ArrowRight size={16} />
            </button>
          )}
          {step === 2 && (
            <button
              id="btn-create-project"
              type="button"
              className="btn-primary"
              onClick={handleSubmit}
              disabled={loading || (inputType === 'upload' && !file)}
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
              {loading
                ? (uploadPercent !== null ? `Загрузка ${uploadPercent}%…` : t('newProject.creatingProject', locale))
                : t('newProject.createProject', locale)}
            </button>
          )}
          {step < 2 && step > 0 && (
            <button
              id="btn-create-project"
              type="button"
              className="btn-primary"
              onClick={handleSubmit}
              disabled={loading || (inputType === 'upload' && !file)}
              style={{ marginLeft: 8 }}
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
              {loading ? t('newProject.creating', locale) : t('newProject.create', locale)}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
