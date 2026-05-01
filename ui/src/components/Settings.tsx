import React, { useState, useEffect } from 'react';
import { Save, CheckCircle2 } from 'lucide-react';
import { PROVIDER_LABELS } from '../i18n';

// ─── localStorage helpers ──────────────────────────────────────────────────

const LS_WEBHOOK  = 'tv_webhook_url';
const LS_PROVIDER = 'tv_default_provider';
const LS_THEME    = 'tv_theme';
const LS_FONTSIZE = 'tv_large_text';

export function getPersistedWebhook(): string  { return localStorage.getItem(LS_WEBHOOK)  ?? ''; }
export function getPersistedProvider(): string  { return localStorage.getItem(LS_PROVIDER) ?? 'legacy'; }
export function getPersistedTheme(): string     { return localStorage.getItem(LS_THEME)    ?? 'dark'; }
export function getPersistedLargeText(): boolean { return localStorage.getItem(LS_FONTSIZE) === 'true'; }

function persistWebhook(v: string)  { if (v) localStorage.setItem(LS_WEBHOOK, v);  else localStorage.removeItem(LS_WEBHOOK); }
function persistProvider(v: string) { localStorage.setItem(LS_PROVIDER, v); }
function persistTheme(v: string)    { localStorage.setItem(LS_THEME, v); }
function persistLargeText(v: boolean) { localStorage.setItem(LS_FONTSIZE, String(v)); }

// ─── Theme application ─────────────────────────────────────────────────────

export function applyTheme(theme: string, largeText: boolean) {
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.classList.toggle('large-text', largeText);
}

// ─── Component ─────────────────────────────────────────────────────────────

export const Settings: React.FC = () => {
  const [webhook,   setWebhook]   = useState(getPersistedWebhook);
  const [provider,  setProvider]  = useState(getPersistedProvider);
  const [theme,     setTheme]     = useState(getPersistedTheme);
  const [largeText, setLargeText] = useState(getPersistedLargeText);
  const [saved,     setSaved]     = useState(false);

  useEffect(() => {
    applyTheme(theme, largeText);
  }, [theme, largeText]);

  const handleSave = () => {
    persistWebhook(webhook);
    persistProvider(provider);
    persistTheme(theme);
    persistLargeText(largeText);
    applyTheme(theme, largeText);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="settings page-container fade-in">
      <header className="page-header">
        <h2>Настройки</h2>
        <p className="subtitle">Параметры приложения, сохраняются в браузере.</p>
      </header>

      <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

        {/* Интеграции */}
        <section>
          <h3 style={{ marginBottom: '16px', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>Интеграции</h3>

          <div className="form-group">
            <label htmlFor="settings-webhook">Webhook URL (n8n)</label>
            <input
              id="settings-webhook"
              className="text-input"
              value={webhook}
              onChange={e => setWebhook(e.target.value)}
              placeholder="https://n8n.bigalexn8n.ru/webhook/..."
            />
            <small className="help-text">
              Этот URL получит уведомление о завершении каждого перевода.
            </small>
          </div>

          <div className="form-group" style={{ marginTop: '12px' }}>
            <label htmlFor="settings-provider">Движок обработки по умолчанию</label>
            <select
              id="settings-provider"
              className="select-input"
              value={provider}
              onChange={e => setProvider(e.target.value)}
            >
              {Object.entries(PROVIDER_LABELS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <small className="help-text">
              Используется при создании нового проекта (можно изменить на шаге 1).
            </small>
          </div>
        </section>

        {/* Внешний вид */}
        <section>
          <h3 style={{ marginBottom: '16px', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>Внешний вид</h3>

          <div className="form-group">
            <label htmlFor="settings-theme">Тема оформления</label>
            <select
              id="settings-theme"
              className="select-input"
              value={theme}
              onChange={e => setTheme(e.target.value)}
            >
              <option value="dark">Тёмная (по умолчанию)</option>
              <option value="light">Светлая</option>
              <option value="system">Системная</option>
            </select>
          </div>

          <div className="form-group" style={{ marginTop: '12px', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <label htmlFor="settings-largefont" style={{ margin: 0 }}>Крупный шрифт (для слабовидящих)</label>
            <button
              id="settings-largefont"
              type="button"
              className={`adv-toggle ${largeText ? 'adv-toggle--on' : ''}`}
              onClick={() => setLargeText(v => !v)}
              aria-pressed={largeText}
            >
              {largeText ? 'Вкл' : 'Выкл'}
            </button>
          </div>
        </section>

        <div className="form-actions">
          <button className="btn-primary" onClick={handleSave}>
            {saved ? <CheckCircle2 size={16} /> : <Save size={16} />}
            {saved ? 'Сохранено!' : 'Сохранить настройки'}
          </button>
        </div>
      </div>
    </div>
  );
};
