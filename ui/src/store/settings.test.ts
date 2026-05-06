// @vitest-environment jsdom
/**
 * Unit-тесты хранилища пользовательских настроек UI (store/settings.ts).
 * Покрывает все get/persist/apply функции.
 */

import { beforeEach, describe, expect, it } from 'vitest';
import {
  DEFAULT_LOCALE,
  DEFAULT_PROVIDER,
  applyLocale,
  applyTheme,
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
} from './settings';

beforeEach(() => {
  localStorage.clear();
  // Сброс data-theme и classList перед каждым тестом
  document.documentElement.removeAttribute('data-theme');
  document.documentElement.classList.remove('large-text');
  document.documentElement.lang = '';
});

// ── getPersistedWebhook ───────────────────────────────────────────────────────

describe('getPersistedWebhook', () => {
  it('возвращает пустую строку если ключ не задан', () => {
    expect(getPersistedWebhook()).toBe('');
  });

  it('возвращает сохранённый webhook', () => {
    localStorage.setItem('tv_webhook_url', 'https://hook.example.com');
    expect(getPersistedWebhook()).toBe('https://hook.example.com');
  });
});

// ── getPersistedProvider ──────────────────────────────────────────────────────

describe('getPersistedProvider', () => {
  it('возвращает DEFAULT_PROVIDER если ключ не задан', () => {
    expect(getPersistedProvider()).toBe(DEFAULT_PROVIDER);
  });

  it('возвращает сохранённый провайдер', () => {
    localStorage.setItem('tv_default_provider', 'deepseek');
    expect(getPersistedProvider()).toBe('deepseek');
  });
});

// ── getPersistedTheme ─────────────────────────────────────────────────────────

describe('getPersistedTheme', () => {
  it('возвращает "dark" если ключ не задан', () => {
    expect(getPersistedTheme()).toBe('dark');
  });

  it('возвращает сохранённую тему', () => {
    localStorage.setItem('tv_theme', 'light');
    expect(getPersistedTheme()).toBe('light');
  });
});

// ── getPersistedLargeText ─────────────────────────────────────────────────────

describe('getPersistedLargeText', () => {
  it('возвращает false если ключ не задан', () => {
    expect(getPersistedLargeText()).toBe(false);
  });

  it('возвращает true если значение "true"', () => {
    localStorage.setItem('tv_large_text', 'true');
    expect(getPersistedLargeText()).toBe(true);
  });

  it('возвращает false если значение "false"', () => {
    localStorage.setItem('tv_large_text', 'false');
    expect(getPersistedLargeText()).toBe(false);
  });
});

// ── getPersistedLocale ────────────────────────────────────────────────────────

describe('getPersistedLocale', () => {
  it('возвращает DEFAULT_LOCALE ("ru") если ключ не задан', () => {
    expect(getPersistedLocale()).toBe(DEFAULT_LOCALE);
  });

  it('возвращает "en" если locale="en"', () => {
    localStorage.setItem('tv_locale', 'en');
    expect(getPersistedLocale()).toBe('en');
  });

  it('возвращает "ru" для неизвестных значений', () => {
    localStorage.setItem('tv_locale', 'fr');
    expect(getPersistedLocale()).toBe('ru');
  });
});

// ── persistWebhook ────────────────────────────────────────────────────────────

describe('persistWebhook', () => {
  it('сохраняет webhook в localStorage', () => {
    persistWebhook('https://n8n.example.com');
    expect(localStorage.getItem('tv_webhook_url')).toBe('https://n8n.example.com');
  });

  it('обрезает пробелы', () => {
    persistWebhook('  https://n8n.example.com  ');
    expect(localStorage.getItem('tv_webhook_url')).toBe('https://n8n.example.com');
  });

  it('удаляет ключ если строка пустая', () => {
    localStorage.setItem('tv_webhook_url', 'old');
    persistWebhook('');
    expect(localStorage.getItem('tv_webhook_url')).toBeNull();
  });

  it('удаляет ключ если строка из пробелов', () => {
    localStorage.setItem('tv_webhook_url', 'old');
    persistWebhook('   ');
    expect(localStorage.getItem('tv_webhook_url')).toBeNull();
  });
});

// ── persistProvider ───────────────────────────────────────────────────────────

describe('persistProvider', () => {
  it('сохраняет провайдер', () => {
    persistProvider('neuroapi');
    expect(localStorage.getItem('tv_default_provider')).toBe('neuroapi');
  });
});

// ── persistTheme ──────────────────────────────────────────────────────────────

describe('persistTheme', () => {
  it('сохраняет тему', () => {
    persistTheme('light');
    expect(localStorage.getItem('tv_theme')).toBe('light');
  });
});

// ── persistLargeText ──────────────────────────────────────────────────────────

describe('persistLargeText', () => {
  it('сохраняет true как "true"', () => {
    persistLargeText(true);
    expect(localStorage.getItem('tv_large_text')).toBe('true');
  });

  it('сохраняет false как "false"', () => {
    persistLargeText(false);
    expect(localStorage.getItem('tv_large_text')).toBe('false');
  });
});

// ── persistLocale ─────────────────────────────────────────────────────────────

describe('persistLocale', () => {
  it('сохраняет locale "en"', () => {
    persistLocale('en');
    expect(localStorage.getItem('tv_locale')).toBe('en');
  });

  it('сохраняет locale "ru"', () => {
    persistLocale('ru');
    expect(localStorage.getItem('tv_locale')).toBe('ru');
  });
});

// ── applyTheme ────────────────────────────────────────────────────────────────

describe('applyTheme', () => {
  it('устанавливает data-theme атрибут', () => {
    applyTheme('light', false);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('добавляет класс large-text если largeText=true', () => {
    applyTheme('dark', true);
    expect(document.documentElement.classList.contains('large-text')).toBe(true);
  });

  it('убирает класс large-text если largeText=false', () => {
    document.documentElement.classList.add('large-text');
    applyTheme('dark', false);
    expect(document.documentElement.classList.contains('large-text')).toBe(false);
  });
});

// ── applyLocale ───────────────────────────────────────────────────────────────

describe('applyLocale', () => {
  it('устанавливает lang атрибут на documentElement', () => {
    applyLocale('en');
    expect(document.documentElement.lang).toBe('en');
  });

  it('устанавливает "ru"', () => {
    applyLocale('ru');
    expect(document.documentElement.lang).toBe('ru');
  });
});
