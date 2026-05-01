import React, { useState, useEffect } from 'react';
import { Save, CheckCircle2 } from 'lucide-react';
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

export const Settings: React.FC<SettingsProps> = ({ locale, onLocaleChange }) => {
  const [webhook,   setWebhook]   = useState(getPersistedWebhook);
  const [provider,  setProvider]  = useState(getPersistedProvider);
  const [theme,     setTheme]     = useState(getPersistedTheme);
  const [largeText, setLargeText] = useState(getPersistedLargeText);
  const [selectedLocale, setSelectedLocale] = useState<AppLocale>(getPersistedLocale);
  const [saved,     setSaved]     = useState(false);

  useEffect(() => {
    applyTheme(theme, largeText);
  }, [theme, largeText]);

  const handleSave = () => {
    persistWebhook(webhook);
    persistProvider(provider);
    persistTheme(theme);
    persistLargeText(largeText);
    persistLocale(selectedLocale);
    applyTheme(theme, largeText);
    onLocaleChange(selectedLocale);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
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
