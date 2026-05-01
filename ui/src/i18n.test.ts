/**
 * Тесты для ui/src/i18n.ts
 *
 * Правила, которые проверяем:
 * 1. Пользовательские строки не содержат технических зависимостей/библиотек.
 * 2. stageLabel() и statusLabel() возвращают читаемые строки.
 * 3. needsReviewCount() корректно считает непереведённые сегменты.
 */

import { describe, it, expect } from 'vitest';
import {
  PROVIDER_LABELS,
  PROVIDER_WARNINGS,
  stageLabel,
  statusLabel,
  needsReviewCount,
} from './i18n';

// ─── Запрещённые технические термины в пользовательских строках ────────────
const FORBIDDEN_TECH_TERMS = [
  'moviepy', 'faster-whisper', 'edge-tts', 'ffmpeg',
  'pip install', 'apt-get', 'npm install',
  'python', 'node_modules',
];

describe('i18n — пользовательские строки без технических терминов', () => {
  it('PROVIDER_LABELS не содержит технических зависимостей', () => {
    for (const [key, label] of Object.entries(PROVIDER_LABELS)) {
      for (const term of FORBIDDEN_TECH_TERMS) {
        expect(label.toLowerCase(), `PROVIDER_LABELS['${key}'] содержит '${term}'`)
          .not.toContain(term.toLowerCase());
      }
    }
  });

  it('PROVIDER_WARNINGS не содержит технических зависимостей', () => {
    for (const [key, warning] of Object.entries(PROVIDER_WARNINGS)) {
      if (!warning) continue;
      for (const term of FORBIDDEN_TECH_TERMS) {
        expect(warning.toLowerCase(), `PROVIDER_WARNINGS['${key}'] содержит '${term}'`)
          .not.toContain(term.toLowerCase());
      }
    }
  });

  it('все провайдеры имеют метку', () => {
    expect(PROVIDER_LABELS['fake']).toBeTruthy();
    expect(PROVIDER_LABELS['legacy']).toBeTruthy();
  });

  it('PROVIDER_LABELS — не пустые строки', () => {
    for (const [key, label] of Object.entries(PROVIDER_LABELS)) {
      expect(label.trim(), `PROVIDER_LABELS['${key}'] пустой`).not.toBe('');
    }
  });
});

// ─── stageLabel ───────────────────────────────────────────────────────────
describe('stageLabel()', () => {
  it('возвращает человекочитаемую метку для известных этапов', () => {
    expect(stageLabel('transcribe')).toContain('Распознавание');
    expect(stageLabel('translate')).toContain('Перевод');
    expect(stageLabel('tts')).toContain('озвучки');
    expect(stageLabel('render')).toContain('Сборка');
  });

  it('для неизвестного этапа форматирует подчёркивания в пробелы', () => {
    expect(stageLabel('some_new_stage')).toBe('some new stage');
  });

  it('не возвращает пустую строку', () => {
    for (const stage of ['extract_audio', 'transcribe', 'translate', 'tts', 'render', 'qa', 'export']) {
      expect(stageLabel(stage).trim()).not.toBe('');
    }
  });
});

// ─── statusLabel ──────────────────────────────────────────────────────────
describe('statusLabel()', () => {
  it('возвращает русские статусы для известных значений', () => {
    expect(statusLabel('completed')).toBe('Завершён');
    expect(statusLabel('running')).toBe('Выполняется');
    expect(statusLabel('failed')).toBe('Ошибка');
    expect(statusLabel('pending')).toBe('Ожидает');
    expect(statusLabel('created')).toBe('Создан');
    expect(statusLabel('skipped')).toBe('Пропущен');
  });

  it('для неизвестного статуса возвращает оригинал', () => {
    expect(statusLabel('unknown_status')).toBe('unknown_status');
  });
});

// ─── needsReviewCount ─────────────────────────────────────────────────────
describe('needsReviewCount()', () => {
  const seg = (source: string, translated?: string) => ({
    source_text: source,
    translated_text: translated,
  });

  it('возвращает 0 если все сегменты переведены', () => {
    const segs = [
      seg('Hello', 'Привет'),
      seg('World', 'Мир'),
    ];
    expect(needsReviewCount(segs)).toBe(0);
  });

  it('считает сегмент без перевода', () => {
    const segs = [seg('Hello', ''), seg('World', 'Мир')];
    expect(needsReviewCount(segs)).toBe(1);
  });

  it('считает сегмент с undefined переводом', () => {
    const segs = [seg('Hello', undefined), seg('World', 'Мир')];
    expect(needsReviewCount(segs)).toBe(1);
  });

  it('считает сегмент где перевод совпадает с оригиналом', () => {
    const segs = [seg('Hello', 'Hello'), seg('World', 'Мир')];
    expect(needsReviewCount(segs)).toBe(1);
  });

  it('считает только пробельный перевод как пустой', () => {
    const segs = [seg('Hello', '   '), seg('World', 'Мир')];
    expect(needsReviewCount(segs)).toBe(1);
  });

  it('возвращает 0 для пустого массива', () => {
    expect(needsReviewCount([])).toBe(0);
  });

  it('считает все непереведённые если ни один не переведён', () => {
    const segs = [seg('A'), seg('B', ''), seg('C', 'C')];
    expect(needsReviewCount(segs)).toBe(3);
  });
});
