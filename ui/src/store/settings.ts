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
const LS_FONTSIZE_LEVEL = 'tv_font_level';  // С1: 'small'|'medium'|'large'
const LS_COMPACT = 'tv_compact_mode';       // С4: компактный режим сегментов
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

/** С1: Уровень шрифта сегментов: small | medium | large */
export function getPersistedFontLevel(): 'small' | 'medium' | 'large' {
  const v = localStorage.getItem(LS_FONTSIZE_LEVEL);
  if (v === 'small' || v === 'large') return v;
  return 'medium';
}

/** С4: Компактный режим — сокращает padding сегментов */
export function getPersistedCompactMode(): boolean {
  return localStorage.getItem(LS_COMPACT) === 'true';
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

/** С1: Сохранить уровень шрифта. */
export function persistFontLevel(value: 'small' | 'medium' | 'large'): void {
  localStorage.setItem(LS_FONTSIZE_LEVEL, value);
}

/** С4: Сохранить compact mode. */
export function persistCompactMode(value: boolean): void {
  localStorage.setItem(LS_COMPACT, String(value));
}

export function persistLocale(value: AppLocale): void {
  localStorage.setItem(LS_LOCALE, value);
}

export function applyTheme(theme: string, largeText: boolean): void {
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.classList.toggle('large-text', largeText);
}

/** С1+С4: Применить уровень шрифта и compact mode к documentElement. */
export function applyFontLevel(level: 'small' | 'medium' | 'large', compact: boolean): void {
  document.documentElement.setAttribute('data-font-level', level);
  document.documentElement.classList.toggle('compact-mode', compact);
}

export function applyLocale(locale: AppLocale): void {
  document.documentElement.lang = locale;
}
