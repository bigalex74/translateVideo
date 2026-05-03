import React, { useRef, useState } from 'react';
import './SSMLToolbar.css';

/**
 * SSMLToolbar — панель инструментов для ручного управления произношением.
 *
 * КЛЮЧЕВЫЕ ИСПРАВЛЕНИЯ v1.26.0:
 * - getTextarea() — callback вместо RefObject: всегда читает Map из родителя
 *   при вызове (не при рендере), ref всегда актуален.
 * - Выделение сохраняется: перед кликом кнопки сохраняем selectionStart/End
 *   через onMouseDown (т.к. клик по кнопке снимает фокус с textarea).
 * - Кнопка ▶ Прослушать: синтез через backend и воспроизведение в браузере.
 *
 * TVIDEO-100 / TVIDEO-102.
 */

interface SSMLToolbarProps {
  /** Callback для получения textarea (читает Map при каждом вызове — не snapshot) */
  getTextarea: () => HTMLTextAreaElement | null;
  /** Текущий текст в редакторе (tts_ssml_override или translated_text) */
  currentText: string;
  /** Вызывается при каждом изменении — обновляет tts_ssml_override */
  onChange: (newValue: string) => void;
  /** Вызывается при нажатии «Сброс» — очищает tts_ssml_override */
  onReset: () => void;
  /** true если tts_ssml_override задан */
  hasOverride: boolean;
  /** Callback для превью синтеза */
  onPreview: (text: string, isSsml: boolean) => Promise<void>;
}

// ── Вспомогательные функции ─────────────────────────────────────────────────

/**
 * Обернуть СОХРАНЁННОЕ выделение в тег.
 * Принимает saved selection (start/end) вместо чтения из DOM,
 * потому что к моменту клика фокус уже мог уйти с textarea.
 */
function wrapAtSavedSelection(
  currentText: string,
  savedStart: number,
  savedEnd: number,
  before: string,
  after: string,
  fallback: string = 'слово',
): string {
  const selected = currentText.slice(savedStart, savedEnd);
  const insert = selected
    ? `${before}${selected}${after}`
    : `${before}${fallback}${after}`;
  return currentText.slice(0, savedStart) + insert + currentText.slice(savedEnd);
}

/** Вставить строку в сохранённую позицию курсора. */
function insertAtSaved(currentText: string, savedStart: number, insert: string): string {
  return currentText.slice(0, savedStart) + insert + currentText.slice(savedStart);
}

// ── Компонент ────────────────────────────────────────────────────────────────

export const SSMLToolbar: React.FC<SSMLToolbarProps> = ({
  getTextarea,
  currentText,
  onChange,
  onReset,
  hasOverride,
  onPreview,
}) => {
  const pauseSelectRef = useRef<HTMLSelectElement>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewErr, setPreviewErr] = useState('');

  // Сохранённая позиция курсора/выделения на момент НАЖАТИЯ кнопки.
  // Нужно потому что клик на кнопку снимает фокус с textarea и сбрасывает selection.
  const savedSel = useRef<{ start: number; end: number }>({ start: 0, end: 0 });

  /** Сохранить выделение из textarea перед тем как фокус уйдёт (onMouseDown кнопок). */
  const saveSelection = () => {
    const ta = getTextarea();
    if (ta) {
      savedSel.current = { start: ta.selectionStart, end: ta.selectionEnd };
    }
  };

  /** Восстановить фокус и курсор в textarea после вставки. */
  const restoreFocus = (newStart: number, newEnd?: number) => {
    requestAnimationFrame(() => {
      const ta = getTextarea();
      if (ta) {
        ta.focus();
        ta.setSelectionRange(newStart, newEnd ?? newStart);
      }
    });
  };

  // ── Обработчики кнопок ────────────────────────────────────────────────────

  const handleStress = () => {
    const { start } = savedSel.current;
    const newVal = insertAtSaved(currentText, start, '+');
    onChange(newVal);
    restoreFocus(start + 1);
  };

  const handleBreak = () => {
    const { start } = savedSel.current;
    const ms = pauseSelectRef.current?.value ?? '350';
    const tag = `<break time="${ms}ms"/>`;
    const newVal = insertAtSaved(currentText, start, tag);
    onChange(newVal);
    restoreFocus(start + tag.length);
  };

  const handleEmphasis = (level: 'reduced' | 'moderate' | 'strong') => {
    const { start, end } = savedSel.current;
    const before = `<emphasis level="${level}">`;
    const after = '</emphasis>';
    const newVal = wrapAtSavedSelection(currentText, start, end, before, after);
    onChange(newVal);
    // Выделяем вставленный текст
    const selStart = start + before.length;
    const selEnd   = end > start ? start + before.length + (end - start) : selStart + 'слово'.length;
    restoreFocus(selStart, selEnd);
  };

  const handleProsody = (rate: string) => {
    const { start, end } = savedSel.current;
    const before = `<prosody rate="${rate}">`;
    const after = '</prosody>';
    const newVal = wrapAtSavedSelection(currentText, start, end, before, after, 'текст');
    onChange(newVal);
    const selStart = start + before.length;
    const selEnd   = end > start ? start + before.length + (end - start) : selStart + 'текст'.length;
    restoreFocus(selStart, selEnd);
  };

  const handlePhoneme = () => {
    const { start, end } = savedSel.current;
    const ipa = window.prompt('Введите IPA-транскрипцию:');
    if (!ipa) return;
    const before = `<phoneme alphabet="ipa" ph="${ipa}">`;
    const after = '</phoneme>';
    const newVal = wrapAtSavedSelection(currentText, start, end, before, after);
    onChange(newVal);
    restoreFocus(start + before.length);
  };

  const handlePreview = async () => {
    if (previewing) return;
    const text = currentText.trim();
    if (!text) return;
    setPreviewErr('');
    setPreviewing(true);
    try {
      const isSsml = text.includes('<') || text.startsWith('<speak>');
      await onPreview(text, isSsml);
    } catch (e) {
      setPreviewErr(e instanceof Error ? e.message : 'Ошибка синтеза');
    } finally {
      setPreviewing(false);
    }
  };

  // ── JSX ──────────────────────────────────────────────────────────────────

  return (
    <div className="ssml-toolbar" role="toolbar" aria-label="Инструменты произношения">

      {/* Подсказка для новичка */}
      {!hasOverride && (
        <span className="ssml-hint">
          Поставьте курсор в текст ниже, затем нажмите кнопку
        </span>
      )}

      {/* Группа: Ударение */}
      <div className="ssml-group">
        <span className="ssml-group-label">Ударение</span>
        <button
          className="ssml-btn ssml-btn--stress"
          title="Вставить «+» перед ударной гласной: во+да, при+вет"
          onMouseDown={saveSelection}
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
          title="Длина паузы"
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
          onMouseDown={saveSelection}
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
          title="Выделите слово и нажмите — приглушить (reduced)"
          onMouseDown={saveSelection}
          onClick={() => handleEmphasis('reduced')}
          type="button"
        >
          ▾
        </button>
        <button
          className="ssml-btn ssml-btn--moderate"
          title="Выделите слово и нажмите — акцент (moderate)"
          onMouseDown={saveSelection}
          onClick={() => handleEmphasis('moderate')}
          type="button"
        >
          ❗
        </button>
        <button
          className="ssml-btn ssml-btn--strong"
          title="Выделите слово и нажмите — сильный акцент (strong)"
          onMouseDown={saveSelection}
          onClick={() => handleEmphasis('strong')}
          type="button"
        >
          ‼
        </button>
      </div>

      <div className="ssml-divider" />

      {/* Группа: Темп */}
      <div className="ssml-group">
        <span className="ssml-group-label">Темп</span>
        <button
          className="ssml-btn"
          title="Выделите фрагмент — замедлить на 20%"
          onMouseDown={saveSelection}
          onClick={() => handleProsody('80%')}
          type="button"
        >
          🐢
        </button>
        <button
          className="ssml-btn"
          title="Выделите фрагмент — ускорить на 20%"
          onMouseDown={saveSelection}
          onClick={() => handleProsody('120%')}
          type="button"
        >
          🐇
        </button>
      </div>

      <div className="ssml-divider" />

      {/* Группа: IPA */}
      <div className="ssml-group">
        <span className="ssml-group-label">IPA</span>
        <button
          className="ssml-btn ssml-btn--phoneme"
          title="Выделите слово — задать произношение в IPA"
          onMouseDown={saveSelection}
          onClick={handlePhoneme}
          type="button"
        >
          🔤
        </button>
      </div>

      {/* Сброс */}
      {hasOverride && (
        <>
          <div className="ssml-divider" />
          <div className="ssml-group">
            <button
              className="ssml-btn ssml-btn--reset"
              title="Убрать ручные правки — вернуть автоматический текст"
              onClick={onReset}
              type="button"
            >
              🔄 Сброс
            </button>
          </div>
        </>
      )}

      {/* ▶ Прослушать */}
      <div className="ssml-divider" />
      <div className="ssml-group">
        <button
          className={`ssml-btn ssml-btn--preview${previewing ? ' ssml-btn--loading' : ''}`}
          title="Синтезировать и прослушать этот отрывок"
          onClick={handlePreview}
          disabled={previewing || !currentText.trim()}
          type="button"
        >
          {previewing ? '⏳' : '▶'} Прослушать
        </button>
      </div>

      {/* Индикатор override */}
      {hasOverride && (
        <span className="ssml-override-badge" title="Используется ручной SSML">
          ✎ ред.
        </span>
      )}

      {/* Ошибка синтеза */}
      {previewErr && (
        <span className="ssml-preview-err" title={previewErr}>
          ⚠ {previewErr.slice(0, 40)}
        </span>
      )}
    </div>
  );
};
