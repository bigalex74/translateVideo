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
const LS_LOCALE = 'tv_locale';

export const DEFAULT_PROVIDER = 'legacy';
export const DEFAULT_LOCALE = 'ru';
export type AppLocale = 'ru' | 'en';

export function getPersistedWebhook(): string {
  return localStorage.getItem(LS_WEBHOOK) ?? '';
}

export function getPersistedProvider(): string {
  return localStorage.getItem(LS_PROVIDER) ?? DEFAULT_PROVIDER;
}

export function getPersistedTheme(): string {
  const saved = localStorage.getItem(LS_THEME);
  if (saved) return saved;
  // Z4.3: для новых пользователей — светлая тема по умолчанию (удобнее для пожилых).
  // Системная преференция в приоритете если пользователь явно настроил dark mode.
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function getPersistedLargeText(): boolean {
  return localStorage.getItem(LS_FONTSIZE) === 'true';
}

export function getPersistedLocale(): AppLocale {
  if (typeof localStorage === 'undefined') {
    return DEFAULT_LOCALE;
  }
  const raw = localStorage.getItem(LS_LOCALE);
  return raw === 'en' ? 'en' : DEFAULT_LOCALE;
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

export function persistLocale(value: AppLocale): void {
  localStorage.setItem(LS_LOCALE, value);
}

export function applyTheme(theme: string, largeText: boolean): void {
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.classList.toggle('large-text', largeText);
}

export function applyLocale(locale: AppLocale): void {
  document.documentElement.lang = locale;
}
