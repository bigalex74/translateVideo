import React, { useRef } from 'react';
import './SSMLToolbar.css';

/**
 * SSMLToolbar — панель инструментов для ручного управления произношением.
 *
 * Работает с textarea сегмента. Пользователь выделяет текст → нажимает кнопку
 * → тег вставляется вокруг выделения. Результат записывается в tts_ssml_override.
 *
 * Поддерживаемые операции:
 * - Ударение:    во+да  (ruaccent / Яндекс SpeechKit)
 * - Пауза:       <break time="Xms"/>
 * - Акцент:      <emphasis level="moderate">слово</emphasis>
 * - Просодия:    <prosody rate="X%">текст</prosody>
 * - Фонема:      <phoneme alphabet="ipa" ph="...">слово</phoneme>
 * - Сброс:       очистить tts_ssml_override → вернуть к translated_text
 *
 * TVIDEO-100.
 */

interface SSMLToolbarProps {
  /** Вызывается при каждом изменении — обновляет tts_ssml_override */
  onChange: (newValue: string) => void;
  /** Вызывается при нажатии «Сброс» — очищает tts_ssml_override */
  onReset: () => void;
  /** true если tts_ssml_override задан (показываем индикатор) */
  hasOverride: boolean;
  /** Ссылка на textarea для работы с выделением */
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}

// ── Вспомогательные функции ─────────────────────────────────────────────────

/** Обернуть выделенный фрагмент в тег, или вставить в позицию курсора */
function wrapSelection(
  textarea: HTMLTextAreaElement,
  before: string,
  after: string,
  fallback: string = '',
  cursorOffset: number = 0,
): string {
  const start = textarea.selectionStart;
  const end   = textarea.selectionEnd;
  const text  = textarea.value;
  const selected = text.slice(start, end);
  const insert = selected
    ? `${before}${selected}${after}`
    : `${before}${fallback}${after}`;
  const newValue = text.slice(0, start) + insert + text.slice(end);

  // Восстановить курсор/выделение
  const newCursor = start + before.length + (selected ? selected.length : fallback.length) + cursorOffset;
  requestAnimationFrame(() => {
    textarea.focus();
    textarea.setSelectionRange(
      selected ? start + before.length : newCursor,
      selected ? start + before.length + selected.length : newCursor,
    );
  });

  return newValue;
}

/** Вставить строку в позицию курсора без обёртки */
function insertAt(textarea: HTMLTextAreaElement, insert: string): string {
  const start = textarea.selectionStart;
  const text  = textarea.value;
  const newValue = text.slice(0, start) + insert + text.slice(start);
  const newCursor = start + insert.length;
  requestAnimationFrame(() => {
    textarea.focus();
    textarea.setSelectionRange(newCursor, newCursor);
  });
  return newValue;
}

// ── Компонент ────────────────────────────────────────────────────────────────

export const SSMLToolbar: React.FC<SSMLToolbarProps> = ({
  onChange,
  onReset,
  hasOverride,
  textareaRef,
}) => {
  const pauseSelectRef = useRef<HTMLSelectElement>(null);

  const getTextarea = () => textareaRef.current;

  /** Кнопка: вставить ударение «+» перед следующей гласной (или в позицию курсора) */
  const handleStress = () => {
    const ta = getTextarea();
    if (!ta) return;
    // Вставляем '+' после текущей позиции курсора — пользователь ставит сам перед гласной
    onChange(insertAt(ta, '+'));
  };

  /** Кнопка: вставить паузу <break time="Xms"/> */
  const handleBreak = () => {
    const ta = getTextarea();
    if (!ta) return;
    const ms = pauseSelectRef.current?.value ?? '350';
    onChange(insertAt(ta, `<break time="${ms}ms"/>`));
  };

  /** Кнопка: обернуть выделение в <emphasis> */
  const handleEmphasis = (level: 'reduced' | 'moderate' | 'strong') => {
    const ta = getTextarea();
    if (!ta) return;
    onChange(wrapSelection(ta, `<emphasis level="${level}">`, '</emphasis>', 'слово'));
  };

  /** Кнопка: обернуть выделение в <prosody rate="X%"> */
  const handleProsody = (rate: string) => {
    const ta = getTextarea();
    if (!ta) return;
    onChange(wrapSelection(ta, `<prosody rate="${rate}">`, '</prosody>', 'текст'));
  };

  /** Кнопка: обернуть выделение в <phoneme> */
  const handlePhoneme = () => {
    const ta = getTextarea();
    if (!ta) return;
    const ipa = window.prompt('Введите IPA-транскрипцию:');
    if (!ipa) return;
    onChange(wrapSelection(ta, `<phoneme alphabet="ipa" ph="${ipa}">`, '</phoneme>', 'слово'));
  };

  return (
    <div className="ssml-toolbar" role="toolbar" aria-label="SSML-инструменты произношения">
      {/* Группа: Ударение */}
      <div className="ssml-group">
        <span className="ssml-group-label">Ударение</span>
        <button
          className="ssml-btn ssml-btn--stress"
          title="Поставить ударение: вставить «+» перед ударной гласной (во+да)"
          onClick={handleStress}
          type="button"
        >
          +а́
        </button>
      </div>

      <div className="ssml-divider" />

      {/* Группа: Пауза */}
      <div className="ssml-group">
        <span className="ssml-group-label">Пауза</span>
        <select
          ref={pauseSelectRef}
          className="ssml-select"
          title="Длительность паузы"
          defaultValue="350"
        >
          <option value="150">150ms</option>
          <option value="350">350ms</option>
          <option value="500">500ms</option>
          <option value="700">700ms</option>
          <option value="1000">1с</option>
        </select>
        <button
          className="ssml-btn"
          title="Вставить паузу в позицию курсора"
          onClick={handleBreak}
          type="button"
        >
          ⏸
        </button>
      </div>

      <div className="ssml-divider" />

      {/* Группа: Акцент */}
      <div className="ssml-group">
        <span className="ssml-group-label">Акцент</span>
        <button
          className="ssml-btn ssml-btn--reduced"
          title="Приглушить выделенное слово (reduced)"
          onClick={() => handleEmphasis('reduced')}
          type="button"
        >
          ▾
        </button>
        <button
          className="ssml-btn ssml-btn--moderate"
          title="Умеренный акцент (moderate)"
          onClick={() => handleEmphasis('moderate')}
          type="button"
        >
          ❗
        </button>
        <button
          className="ssml-btn ssml-btn--strong"
          title="Сильный акцент (strong)"
          onClick={() => handleEmphasis('strong')}
          type="button"
        >
          ‼️
        </button>
      </div>

      <div className="ssml-divider" />

      {/* Группа: Скорость */}
      <div className="ssml-group">
        <span className="ssml-group-label">Темп</span>
        <button
          className="ssml-btn"
          title="Медленнее (-20%)"
          onClick={() => handleProsody('80%')}
          type="button"
        >
          🐢
        </button>
        <button
          className="ssml-btn"
          title="Быстрее (+20%)"
          onClick={() => handleProsody('120%')}
          type="button"
        >
          🐇
        </button>
      </div>

      <div className="ssml-divider" />

      {/* Группа: Фонема */}
      <div className="ssml-group">
        <span className="ssml-group-label">IPA</span>
        <button
          className="ssml-btn ssml-btn--phoneme"
          title="Задать IPA-транскрипцию для выделенного слова"
          onClick={handlePhoneme}
          type="button"
        >
          🔤
        </button>
      </div>

      {/* Сброс — только если есть override */}
      {hasOverride && (
        <>
          <div className="ssml-divider" />
          <div className="ssml-group">
            <button
              className="ssml-btn ssml-btn--reset"
              title="Сбросить ручные изменения SSML — вернуть к автоматическому тексту"
              onClick={onReset}
              type="button"
            >
              🔄 Сброс
            </button>
          </div>
        </>
      )}

      {/* Индикатор override */}
      {hasOverride && (
        <span className="ssml-override-badge" title="Используется ручной SSML">
          SSML ✎
        </span>
      )}
    </div>
  );
};
