import React, { useState, useEffect } from 'react';
import { Save, CheckCircle2, KeyRound, Copy, ExternalLink, BookOpen, HelpCircle, RotateCcw } from 'lucide-react';
import { LOCALE_LABELS, providerLabels, t } from '../i18n';
import {
  applyTheme,
  type AppLocale,
  getPersistedLargeText,
  getPersistedLocale,
  getPersistedProvider,
  getPersistedTheme,
  getPersistedWebhook,
  persistLargeText,
  persistLocale,
  persistProvider,
  persistTheme,
  persistWebhook,
} from '../store/settings';

// ─── Component ─────────────────────────────────────────────────────────────

interface SettingsProps {
  locale: AppLocale;
  onLocaleChange: (locale: AppLocale) => void;
}

const API_KEY_STORAGE = 'tv_api_key';

function getPersistedApiKey(): string {
  return localStorage.getItem(API_KEY_STORAGE) ?? '';
}

export const Settings: React.FC<SettingsProps> = ({ locale, onLocaleChange }) => {
  const [webhook,   setWebhook]   = useState(getPersistedWebhook);
  const [provider,  setProvider]  = useState(getPersistedProvider);
  const [theme,     setTheme]     = useState(getPersistedTheme);
  const [largeText, setLargeText] = useState(getPersistedLargeText);
  const [selectedLocale, setSelectedLocale] = useState<AppLocale>(getPersistedLocale);
  const [saved,     setSaved]     = useState(false);
  const [apiKey,    setApiKey]    = useState(getPersistedApiKey);
  const [keyCopied, setKeyCopied] = useState(false);

  useEffect(() => {
    applyTheme(theme, largeText);
  }, [theme, largeText]);

  const handleSave = () => {
    persistWebhook(webhook);
    persistProvider(provider);
    persistTheme(theme);
    persistLargeText(largeText);
    persistLocale(selectedLocale);
    localStorage.setItem(API_KEY_STORAGE, apiKey);
    applyTheme(theme, largeText);
    onLocaleChange(selectedLocale);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const handleCopyKey = () => {
    navigator.clipboard.writeText(apiKey).then(() => {
      setKeyCopied(true);
      setTimeout(() => setKeyCopied(false), 1500);
    });
  };

  return (
    <div className="settings page-container fade-in">
      <header className="page-header">
        <h2>{t('settings.title', locale)}</h2>
        <p className="subtitle">{t('settings.subtitle', locale)}</p>
      </header>

      <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

        {/* Интеграции */}
        <section>
          <h3 style={{ marginBottom: '16px', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>{t('settings.integrations', locale)}</h3>

          <div className="form-group">
            <label htmlFor="settings-webhook">{t('settings.webhookLabel', locale)}</label>
            <input
              id="settings-webhook"
              className="text-input"
              value={webhook}
              onChange={e => setWebhook(e.target.value)}
              placeholder="https://n8n.bigalexn8n.ru/webhook/..."
            />
            <small className="help-text">
              {t('settings.webhookHelp', locale)}
            </small>
          </div>

          <div className="form-group" style={{ marginTop: '12px' }}>
            <label htmlFor="settings-provider">{t('settings.providerLabel', locale)}</label>
            <select
              id="settings-provider"
              className="select-input"
              value={provider}
              onChange={e => setProvider(e.target.value)}
            >
              {Object.entries(providerLabels(locale)).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <small className="help-text">
              {t('settings.providerHelp', locale)}
            </small>
          </div>

          {/* API Key */}
          <div className="form-group" style={{ marginTop: '16px' }}>
            <label htmlFor="settings-apikey">
              <KeyRound size={14} style={{ display: 'inline', marginRight: 5 }} />
              API Key (X-API-Key)
            </label>
            <div className="api-key-row">
              <input
                id="settings-apikey"
                className="text-input api-key-input"
                type="password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder="Оставьте пустым если API_KEY не настроен на сервере"
              />
              <button
                type="button"
                className="btn-secondary api-key-copy-btn"
                onClick={handleCopyKey}
                title="Копировать ключ"
                disabled={!apiKey}
              >
                {keyCopied ? <CheckCircle2 size={14} /> : <Copy size={14} />}
              </button>
            </div>
            <small className="help-text">
              Если на сервере задана переменная <code>API_KEY</code> — введите её здесь.
              Ключ сохраняется локально и добавляется в заголовок <code>X-API-Key</code>.
            </small>
          </div>
        </section>

        {/* Внешний вид */}
        <section>
          <h3 style={{ marginBottom: '16px', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>{t('settings.appearance', locale)}</h3>

          <div className="form-group">
            <label htmlFor="settings-theme">{t('settings.themeLabel', locale)}</label>
            <select
              id="settings-theme"
              className="select-input"
              value={theme}
              onChange={e => setTheme(e.target.value)}
            >
              <option value="dark">{t('settings.themeDark', locale)}</option>
              <option value="light">{t('settings.themeLight', locale)}</option>
              <option value="system">{t('settings.themeSystem', locale)}</option>
            </select>
          </div>

          <div className="form-group" style={{ marginTop: '12px', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <label htmlFor="settings-largefont" style={{ margin: 0 }}>{t('settings.largeText', locale)}</label>
            <button
              id="settings-largefont"
              type="button"
              className={`adv-toggle ${largeText ? 'adv-toggle--on' : ''}`}
              onClick={() => setLargeText(v => !v)}
              aria-pressed={largeText}
            >
              {largeText ? t('settings.on', locale) : t('settings.off', locale)}
            </button>
          </div>

          <div className="form-group" style={{ marginTop: '12px' }}>
            <label htmlFor="settings-locale">{t('settings.languageLabel', locale)}</label>
            <select
              id="settings-locale"
              className="select-input"
              value={selectedLocale}
              onChange={e => setSelectedLocale(e.target.value === 'en' ? 'en' : 'ru')}
            >
              {Object.entries(LOCALE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <small className="help-text">{t('settings.languageHelp', locale)}</small>
          </div>
        </section>

        {/* Разработчик / API */}
        <section>
          <h3 style={{ marginBottom: '12px', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
            Для разработчиков
          </h3>
          <div className="dev-links">
            <a href="/docs" target="_blank" rel="noopener" className="dev-link">
              <BookOpen size={15} /> Swagger API Docs
            </a>
            <a href="/redoc" target="_blank" rel="noopener" className="dev-link">
              <ExternalLink size={15} /> ReDoc
            </a>
            <a href="/openapi.json" target="_blank" rel="noopener" className="dev-link">
              <ExternalLink size={15} /> openapi.json
            </a>
          </div>
        </section>

        {/* FAQ секция (C-21, C-22) */}
        <section>
          <h3 style={{ marginBottom: '12px', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
            <HelpCircle size={15} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6 }} />
            FAQ — Частые вопросы
          </h3>
          <div className="faq-list">
            {([
              ['Что такое TTS?', 'Text-to-Speech — синтез речи. Технология превращает переведённый текст в аудио с голосом.'],
              ['Что такое «Провайдер»?', 'Сервис синтеза речи: OpenAI, Яндекс, ElevenLabs. У каждого свои голоса и стоимость.'],
              ['Что такое «Пайплайн»?', 'Последовательность шагов: транскрипция → перевод → озвучка → рендер видео.'],
              ['Как долго длится перевод?', 'Зависит от длины видео и провайдера. Обычно 2–10 мин на 10 мин видео.'],
              ['Где найти переведённое видео?', 'Откройте проект → вкладка «Артефакты» → скачайте MP4, SRT или VTT.'],
              ['Нужны ли мне API-ключи?', 'Если приложение развёрнуто администратором — нет. Иначе введите ключи в разделе выше.'],
              ['Что делать если перевод завис?', 'Подождите 5 минут. Если прогресс не меняется — нажмите «Перезапустить» на карточке проекта.'],
              ['Можно ли отредактировать субтитры?', 'Да! Откройте проект → редактируйте текст в каждом сегменте → Сохранить (или Ctrl+S).'],
            ] as [string, string][]).map(([q, a]) => (
              <details key={q} className="faq-item">
                <summary className="faq-q">{q}</summary>
                <p className="faq-a">{a}</p>
              </details>
            ))}
          </div>
          <button
            type="button"
            className="btn-secondary"
            style={{ marginTop: '12px', fontSize: '0.82rem' }}
            onClick={() => {
              localStorage.removeItem('tv_onboarded');
              window.location.reload();
            }}
            title="Показать пошаговое руководство снова"
          >
            <RotateCcw size={14} /> Повторить онбординг
          </button>
        </section>

        {/* Z5.15: О проекте */}
        <section>
          <h3 style={{ marginBottom: '12px', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
            ℹ️ О проекте
          </h3>
          <div style={{ fontSize: '0.85rem', lineHeight: '1.7', color: 'var(--text-secondary)' }}>
            <p><strong>translateVideo</strong> — ИИ-движок перевода видео с сохранением голоса и тайминга.</p>
            <ul style={{ paddingLeft: '1.2rem', marginTop: '8px' }}>
              <li>🐍 Python 3.11+ · FastAPI · Pydantic v2</li>
              <li>⚛️ React 18 · TypeScript · Vite</li>
              <li>🎞️ FFmpeg · ffprobe</li>
              <li>🤖 OpenAI · Yandex TTS · ElevenLabs</li>
            </ul>
            <div style={{ marginTop: '12px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <a href="/api/health" target="_blank" rel="noopener" className="dev-link">
                🟢 API Health
              </a>
              <a href="/docs" target="_blank" rel="noopener" className="dev-link">
                📖 API Docs
              </a>
              <a href="https://github.com/bigalex74/translateVideo" target="_blank" rel="noopener" className="dev-link">
                🐙 GitHub
              </a>
            </div>
          </div>
        </section>

        <div className="form-actions">
          <button className="btn-primary" onClick={handleSave}>
            {saved ? <CheckCircle2 size={16} /> : <Save size={16} />}
            {saved ? t('settings.saved', locale) : t('settings.save', locale)}
          </button>
        </div>
      </div>
    </div>
  );
};
