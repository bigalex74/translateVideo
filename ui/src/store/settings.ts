/**
 * Хранилище пользовательских настроек UI.
 *
 * Все ключи localStorage держим в одном месте, чтобы компоненты не расходились
 * в дефолтах для провайдера, webhook и темы оформления.
 */

const LS_WEBHOOK = 'tv_webhook_url';
const LS_PROVIDER = 'tv_default_provider';
const LS_THEME = 'tv_theme';
const LS_FONTSIZE = 'tv_large_text';

export const DEFAULT_PROVIDER = 'legacy';

export function getPersistedWebhook(): string {
  return localStorage.getItem(LS_WEBHOOK) ?? '';
}

export function getPersistedProvider(): string {
  return localStorage.getItem(LS_PROVIDER) ?? DEFAULT_PROVIDER;
}

export function getPersistedTheme(): string {
  return localStorage.getItem(LS_THEME) ?? 'dark';
}

export function getPersistedLargeText(): boolean {
  return localStorage.getItem(LS_FONTSIZE) === 'true';
}

export function persistWebhook(value: string): void {
  const normalized = value.trim();
  if (normalized) {
    localStorage.setItem(LS_WEBHOOK, normalized);
  } else {
    localStorage.removeItem(LS_WEBHOOK);
  }
}

export function persistProvider(value: string): void {
  localStorage.setItem(LS_PROVIDER, value);
}

export function persistTheme(value: string): void {
  localStorage.setItem(LS_THEME, value);
}

export function persistLargeText(value: boolean): void {
  localStorage.setItem(LS_FONTSIZE, String(value));
}

export function applyTheme(theme: string, largeText: boolean): void {
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.classList.toggle('large-text', largeText);
}
