import React, { useState, useRef } from 'react';
import { createProject, preflightVideo, uploadProject } from '../api/client';
import type { PreflightReport } from '../types/schemas';
import { PROVIDER_LABELS, PROVIDER_WARNINGS } from '../i18n';
import {
  Play, UploadCloud, Link as LinkIcon, FileVideo, Loader2, ShieldCheck,
  ChevronDown, ChevronUp, AlertTriangle, Clock
} from 'lucide-react';
import './NewProject.css';

interface NewProjectProps {
  onProjectCreated: (id: string) => void;
}

export const NewProject: React.FC<NewProjectProps> = ({ onProjectCreated }) => {
  const [inputType, setInputType]   = useState<'upload' | 'url'>('upload');
  const [file, setFile]             = useState<File | null>(null);
  const [videoUrl, setVideoUrl]     = useState('');
  const [projectId, setProjectId]   = useState('');
  const [sourceLang, setSourceLang] = useState('auto');
  const [targetLang, setTargetLang] = useState('ru');
  const [mode, setMode]             = useState('voiceover');
  const [provider, setProvider]     = useState('fake');
  const [loading, setLoading]       = useState(false);
  const [checking, setChecking]     = useState(false);
  const [error, setError]           = useState('');
  const [preflight, setPreflight]   = useState<PreflightReport | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const providerWarning = PROVIDER_WARNINGS[provider];

  /* ---- drag & drop ---- */
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files?.[0]) applyFile(e.dataTransfer.files[0]);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) applyFile(e.target.files[0]);
  };

  const applyFile = (f: File) => {
    setFile(f);
    if (!projectId) {
      const name = f.name.replace(/\.[^/.]+$/, '').replace(/[^a-zA-Z0-9_-]/g, '_').toLowerCase();
      setProjectId(name);
    }
    setPreflight(null);
  };

  /* ---- preflight ---- */
  const handlePreflight = async () => {
    if (!videoUrl) {
      setError('Для проверки укажите URL или путь на сервере.');
      return;
    }
    setChecking(true);
    setError('');
    setPreflight(null);
    try {
      const report = await preflightVideo(videoUrl, provider);
      setPreflight(report);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка предварительной проверки');
    } finally {
      setChecking(false);
    }
  };

  /* ---- submit ---- */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (inputType === 'upload' && !file) {
      setError('Пожалуйста, выберите или перетащите видеофайл.');
      return;
    }
    if (inputType === 'url' && !videoUrl) {
      setError('Пожалуйста, введите корректный URL или путь к файлу.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const config = { source_language: sourceLang, target_language: targetLang, translation_mode: mode };
      const project = inputType === 'upload' && file
        ? await uploadProject(file, projectId || undefined, config)
        : await createProject(videoUrl, projectId || undefined, config);
      onProjectCreated(project.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка при создании проекта');
    } finally {
      setLoading(false);
    }
  };

  /* ---- helpers ---- */
  const formatDuration = (secs?: number): string => {
    if (!secs) return '';
    const m = Math.floor(secs / 60);
    const s = Math.round(secs % 60);
    return `${m}м ${s}с`;
  };

  return (
    <div className="new-project page-container fade-in">
      <header className="page-header">
        <h2>Создание нового перевода</h2>
        <p className="subtitle">Загрузите видео или укажите ссылку — ИИ-конвейер сделает всё остальное.</p>
      </header>

      <form onSubmit={handleSubmit} className="glass-panel wizard-form">

        {/* Тип ввода */}
        <div className="input-type-toggle">
          <button type="button" className={inputType === 'upload' ? 'active' : ''} onClick={() => setInputType('upload')}>
            <UploadCloud size={16} /> Загрузить файл
          </button>
          <button type="button" className={inputType === 'url' ? 'active' : ''} onClick={() => setInputType('url')}>
            <LinkIcon size={16} /> URL / путь на сервере
          </button>
        </div>

        {/* Область ввода */}
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
                <span className="change-file">Кликните или перетащите другой файл для замены</span>
              </div>
            ) : (
              <div className="drop-prompt">
                <UploadCloud size={48} className="text-muted" />
                <span>Перетащите ваше видео сюда</span>
                <span className="text-muted text-sm">или кликните для выбора файла</span>
              </div>
            )}
          </div>
        ) : (
          <div className="form-group">
            <label>URL видео или путь на сервере</label>
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

        {/* Preflight report */}
        {preflight && (
          <div className={`preflight-report ${preflight.ok ? 'ok' : 'failed'}`}>
            <div className="preflight-header">
              <strong>{preflight.ok ? '✅ Проверка пройдена' : '⚠️ Обнаружены проблемы'}</strong>
              {/* Показываем оценку времени, если API вернул duration */}
              {(preflight as { duration_seconds?: number }).duration_seconds && (
                <span className="preflight-duration">
                  <Clock size={13} />
                  Длительность: {formatDuration((preflight as { duration_seconds?: number }).duration_seconds)}
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

        {/* Имя проекта */}
        <div className="form-group">
          <label htmlFor="project-id-input">Имя проекта</label>
          <input
            id="project-id-input"
            className="text-input"
            value={projectId}
            onChange={e => setProjectId(e.target.value)}
            placeholder="Оставьте пустым — имя будет сгенерировано из файла"
          />
          <small className="help-text">Используется как идентификатор папки и URL. Только латинские буквы, цифры и дефисы.</small>
        </div>

        {/* Языки и режим */}
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

        <div className="form-group">
          <label>Режим перевода</label>
          <select className="select-input" value={mode} onChange={e => setMode(e.target.value)}>
            <option value="voiceover">🎙️ Закадровый голос (оригинал приглушён)</option>
            <option value="dub">🗣️ Дубляж (полная замена оригинала)</option>
            <option value="subtitles">📄 Только субтитры (без озвучки)</option>
          </select>
        </div>

        {/* Расширенные настройки */}
        <div className="advanced-section">
          <button
            type="button"
            className="advanced-toggle"
            onClick={() => setShowAdvanced(v => !v)}
            aria-expanded={showAdvanced}
          >
            {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            Расширенные настройки
          </button>

          {showAdvanced && (
            <div className="advanced-body">
              <div className="form-group">
                <label>Движок обработки</label>
                <select
                  className="select-input"
                  value={provider}
                  onChange={e => { setProvider(e.target.value); setPreflight(null); }}
                >
                  {Object.entries(PROVIDER_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>{label}</option>
                  ))}
                </select>
                {providerWarning && (
                  <div className="provider-warning">
                    <AlertTriangle size={14} />
                    {providerWarning}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {error && <div className="error-banner" role="alert">{error}</div>}

        <div className="form-actions">
          <button
            id="btn-create-project"
            type="submit"
            disabled={loading || (inputType === 'upload' && !file)}
            className="btn-primary w-full"
            style={{ justifyContent: 'center' }}
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
            {loading ? 'Создание проекта…' : 'Создать проект'}
          </button>
        </div>
      </form>
    </div>
  );
};
