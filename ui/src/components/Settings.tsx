import React, { useState, useEffect } from 'react';
import { Save, CheckCircle2, KeyRound, Copy, ExternalLink, BookOpen, HelpCircle, RotateCcw, Eye, EyeOff, Trash2 } from 'lucide-react';
import { LOCALE_LABELS, providerLabels, t } from '../i18n';
import {
  applyTheme,
  applyFontLevel,
  type AppLocale,
  getPersistedLargeText,
  getPersistedLocale,
  getPersistedProvider,
  getPersistedTheme,
  getPersistedWebhook,
  getPersistedFontLevel,
  getPersistedCompactMode,
  persistLargeText,
  persistLocale,
  persistProvider,
  persistTheme,
  persistWebhook,
  persistFontLevel,
  persistCompactMode,
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
  const [fontLevel, setFontLevel] = useState<'small' | 'medium' | 'large'>(getPersistedFontLevel);
  const [compactMode, setCompactMode] = useState(getPersistedCompactMode);
  const [selectedLocale, setSelectedLocale] = useState<AppLocale>(getPersistedLocale);
  const [saved,     setSaved]     = useState(false);
  const [apiKey,    setApiKey]    = useState(getPersistedApiKey);
  const [keyCopied, setKeyCopied] = useState(false);
  // TVIDEO-225: показать/скрыть API-ключ
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    applyTheme(theme, largeText);
    applyFontLevel(fontLevel, compactMode);
  }, [theme, largeText, fontLevel, compactMode]);

  const handleSave = () => {
    persistWebhook(webhook);
    persistProvider(provider);
    persistTheme(theme);
    persistLargeText(largeText);
    persistFontLevel(fontLevel);
    persistCompactMode(compactMode);
    persistLocale(selectedLocale);
    localStorage.setItem(API_KEY_STORAGE, apiKey);
    applyTheme(theme, largeText);
    applyFontLevel(fontLevel, compactMode);
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
            {/* K4: Описание выбранного провайдера */}
            {provider && (
              <div className="provider-hint" style={{
                marginTop: '8px',
                padding: '8px 12px',
                background: 'var(--bg-elevated)',
                borderRadius: '6px',
                fontSize: '0.82rem',
                color: 'var(--text-secondary)',
                borderLeft: '3px solid var(--accent-primary)',
              }}>
                {{
                  'polza':    '💎 Polza.ai — высокое качество, русскоязычные голоса, платный сервис. Хорош для контента на русском языке.',
                  'neuroapi': '⚡ NeuroAPI — быстрый и доступный, поддерживает OpenAI-совместимые модели.',
                  'legacy':   '🔧 Legacy (Яндекс/OpenAI) — классический набор провайдеров. Нужны API-ключи OPENAI_API_KEY или YANDEX_API_KEY.',
                  'fake':     '🧪 Fake — только для разработки и тестирования. Реальной озвучки нет.',
                }[provider] || `Провайдер: ${provider}`}
              </div>
            )}
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
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder="Оставьте пустым если API_KEY не настроен на сервере"
                autoComplete="off"
                spellCheck={false}
              />
              <button
                type="button"
                className="btn-secondary api-key-copy-btn"
                onClick={() => setShowKey(v => !v)}
                title={showKey ? 'Скрыть ключ' : 'Показать ключ'}
                aria-label={showKey ? 'Скрыть API-ключ' : 'Показать API-ключ'}
              >
                {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
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

          {/* С1: Размер шрифта сегментов */}
          <div className="form-group" style={{ marginTop: '12px' }}>
            <label htmlFor="settings-font-level">
              {locale === 'ru' ? 'Размер шрифта (Сегменты)' : 'Segment Font Size'}
            </label>
            <select
              id="settings-font-level"
              className="select-input"
              value={fontLevel}
              onChange={e => setFontLevel(e.target.value as 'small' | 'medium' | 'large')}
            >
              <option value="small">{locale === 'ru' ? 'Мелкий' : 'Small'}</option>
              <option value="medium">{locale === 'ru' ? 'Нормальный' : 'Medium'}</option>
              <option value="large">{locale === 'ru' ? 'Крупный' : 'Large'}</option>
            </select>
          </div>

          {/* С4: Компактный режим */}
          <div className="form-group" style={{ marginTop: '12px', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <label htmlFor="settings-compact" style={{ margin: 0 }}>
              {locale === 'ru' ? 'Компактный режим (сегменты)' : 'Compact Mode (Segments)'}
            </label>
            <button
              id="settings-compact"
              type="button"
              className={`adv-toggle ${compactMode ? 'adv-toggle--on' : ''}`}
              onClick={() => setCompactMode(v => !v)}
              aria-pressed={compactMode}
            >
              {compactMode ? t('settings.on', locale) : t('settings.off', locale)}
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

        {/* D2: Шаблоны настроек (пресеты) */}
        <section>
          <h3 style={{ marginBottom: '12px', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
            🗂 Шаблоны настроек
          </h3>
          <p className="help-text" style={{ marginBottom: '12px' }}>
            Быстрые пресеты для типовых задач — нажмите чтобы применить настройки одним кликом.
          </p>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {([
              { id: 'preset-youtube', label: '🎬 YouTube RU→EN', provider: 'legacy', webhook: '' },
              { id: 'preset-anime',   label: '🎌 Аниме JP→RU',   provider: 'legacy', webhook: '' },
              { id: 'preset-course',  label: '📚 Курс EN→RU',    provider: 'polza',  webhook: '' },
              { id: 'preset-auto',    label: '⚡ Авто (быстро)', provider: 'legacy', webhook: '' },
            ] as const).map(preset => (
              <button
                key={preset.id}
                id={preset.id}
                type="button"
                className="btn-secondary"
                style={{ fontSize: '0.85rem', padding: '6px 12px' }}
                onClick={() => {
                  setProvider(preset.provider as string);
                  if (preset.webhook) setWebhook(preset.webhook);
                }}
                title={`Применить пресет: ${preset.label}`}
              >
                {preset.label}
              </button>
            ))}
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
              // TVIDEO-225: Дополнительные FAQ из FBA
              ['Что такое «Retry/Backoff»?', 'Автоматическое повторение запроса при сбое: 3 попытки с нарастающей паузой (2s, 4s, 8s). Данные не теряются при временных ошибках сети.'],
              ['Что означает cost_usd в статусе?', 'Приблизительная стоимость запроса к AI-провайдеру в долларах. Используется для контроля расходов.'],
              ['Почему я не получаю уведомление о завершении?', 'Убедитесь что вы разрешили уведомления браузера при запуске перевода. Уведомление приходит только если вкладка неактивна.'],
              ['Что делать если статус устарел после смены вкладки?', 'Статус обновляется автоматически при возврате на вкладку (Visibility API). Если нет — обновите страницу (F5).'],
            ] as [string, string][]).map(([q, a]) => (
              <details key={q} className="faq-item">
                <summary className="faq-q">{q}</summary>
                <p className="faq-a">{a}</p>
              </details>
            ))}
          </div>
          <div style={{ marginTop: '12px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn-secondary"
              style={{ fontSize: '0.82rem' }}
              onClick={() => {
                // TVIDEO-225: Destructive confirm перед сбросом онбординга
                if (window.confirm('Повторить онбординг? Обучение запустится снова при следующем открытии приложения.')) {
                  localStorage.removeItem('tv_onboarded');
                  window.location.reload();
                }
              }}
              title="Показать пошаговое руководство снова"
            >
              <RotateCcw size={14} /> Повторить онбординг
            </button>
            <button
              id="settings-reset-all"
              type="button"
              className="btn-secondary"
              style={{ fontSize: '0.82rem', color: 'var(--danger)', borderColor: 'rgba(239,68,68,0.4)' }}
              onClick={() => {
                // TVIDEO-225: Destructive confirm — сброс всех настроек
                if (window.confirm('Сбросить все настройки к значениям по умолчанию? Это действие нельзя отменить.')) {
                  const keysToRemove = [
                    'tv_webhook', 'tv_provider', 'tv_theme', 'tv_large_text',
                    'tv_font_level', 'tv_compact_mode', 'tv_locale', API_KEY_STORAGE,
                  ];
                  keysToRemove.forEach(k => localStorage.removeItem(k));
                  window.location.reload();
                }
              }}
              title="Сбросить все настройки к значениям по умолчанию"
            >
              <Trash2 size={14} /> Сбросить всё
            </button>
          </div>
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
