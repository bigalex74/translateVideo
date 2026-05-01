/**
 * Тесты i18n-утилит и UI-регрессий (TVIDEO-023).
 * Покрывает: statusLabel, stageLabel, PROVIDER_LABELS, отсутствие технических терминов.
 */
import { describe, it, expect } from 'vitest';
import { providerLabel, stageLabel, statusLabel, t, PROVIDER_LABELS, PROVIDER_WARNINGS } from './i18n';

// ─── TVIDEO-023 регрессии ─────────────────────────────────────────────────────

describe('TVIDEO-023: statusLabel возвращает читаемые строки', () => {
  it('failed отображается как "Ошибка", не как "failed"', () => {
    expect(statusLabel('failed')).not.toBe('failed');
    expect(statusLabel('failed')).toBeTruthy();
  });

  it('running отображается как "Выполняется" или аналог', () => {
    expect(statusLabel('running')).not.toBe('running');
    expect(statusLabel('running')).toBeTruthy();
  });

  it('completed отображается корректно', () => {
    expect(statusLabel('completed')).not.toBe('completed');
    expect(statusLabel('completed')).toBeTruthy();
  });
});

describe('TVIDEO-023: провайдер legacy — метки без технических терминов', () => {
  it('PROVIDER_LABELS["legacy"] не содержит технических имён пакетов', () => {
    const label = PROVIDER_LABELS['legacy'] ?? '';
    const forbidden = ['moviepy', 'faster-whisper', 'edge-tts', 'ffmpeg'];
    for (const term of forbidden) {
      expect(label.toLowerCase()).not.toContain(term);
    }
  });

  it('PROVIDER_LABELS["fake"] не содержит технических имён пакетов', () => {
    const label = PROVIDER_LABELS['fake'] ?? '';
    const forbidden = ['moviepy', 'faster-whisper', 'edge-tts', 'ffmpeg'];
    for (const term of forbidden) {
      expect(label.toLowerCase()).not.toContain(term);
    }
  });

  it('PROVIDER_WARNINGS не содержат технических имён пакетов', () => {
    const forbidden = ['moviepy', 'faster-whisper', 'edge-tts', 'ffmpeg'];
    for (const [, warning] of Object.entries(PROVIDER_WARNINGS)) {
      if (!warning) continue;
      for (const term of forbidden) {
        expect((warning as string).toLowerCase()).not.toContain(term);
      }
    }
  });
});

describe('TVIDEO-019/020: дефолтный провайдер legacy', () => {
  it('PROVIDER_LABELS содержит ключ "legacy"', () => {
    expect('legacy' in PROVIDER_LABELS).toBe(true);
  });

  it('PROVIDER_LABELS["legacy"] не пустой', () => {
    expect(PROVIDER_LABELS['legacy']).toBeTruthy();
  });
});

// ─── Базовые тесты (были до TVIDEO-023) ─────────────────────────────────────

describe('stageLabel', () => {
  it('возвращает строку для известных этапов', () => {
    const stages = ['extract_audio', 'transcribe', 'translate', 'timing_fit', 'tts', 'render'];
    for (const stage of stages) {
      const label = stageLabel(stage);
      expect(typeof label).toBe('string');
      expect(label.length).toBeGreaterThan(0);
    }
  });

  it('не возвращает технических идентификаторов как есть', () => {
    expect(stageLabel('extract_audio')).not.toBe('extract_audio');
    expect(stageLabel('transcribe')).not.toBe('transcribe');
    expect(stageLabel('translate')).not.toBe('translate');
    expect(stageLabel('timing_fit')).not.toBe('timing_fit');
  });
});

describe('TVIDEO-032: переключение локали RU/EN', () => {
  it('русский язык остается дефолтным', () => {
    expect(t('nav.dashboard', 'ru')).toBe('Мои переводы');
    expect(statusLabel('completed', 'ru')).toBe('Завершён');
  });

  it('английская локаль возвращает английские UI-строки', () => {
    expect(t('nav.dashboard', 'en')).toBe('My translations');
    expect(t('settings.languageLabel', 'en')).toBe('Interface language');
    expect(statusLabel('running', 'en')).toBe('Running');
    expect(stageLabel('translate', 'en')).toContain('Text translation');
    expect(providerLabel('legacy', 'en')).toContain('Full translation');
  });
});
