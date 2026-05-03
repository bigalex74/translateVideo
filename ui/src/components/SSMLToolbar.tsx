import React, { useRef, useState } from 'react';
import './SSMLToolbar.css';

/**
 * SSMLToolbar — панель инструментов Яндекс TTS-разметки.
 *
 * Использует нативную TTS-разметку Яндекс SpeechKit (поле "text", не "ssml"):
 *   +     — ударение перед ударной гласной: во+да, зам+ок
 *   sil<[300]>  — пауза указанной длины (мс)
 *   <[medium]>  — контекстная пауза (tiny/small/medium/large/huge)
 *   **слово**   — акцент на слово/фразу
 *   [[фонемы]]  — фонетическое произношение через русские фонемы SpeechKit
 *
 * Ключевые фиксы v1.26.0:
 *   - getTextarea() callback (не RefObject) — всегда актуален
 *   - onMouseDown сохраняет selection ДО потери фокуса
 *
 * TVIDEO-100 / TVIDEO-102 / TVIDEO-103.
 */

interface SSMLToolbarProps {
  getTextarea: () => HTMLTextAreaElement | null;
  currentText: string;
  onChange: (newValue: string) => void;
  onReset: () => void;
  hasOverride: boolean;
  onPreview: (text: string) => Promise<void>;
}

// ── Вспомогательные функции ─────────────────────────────────────────────────

function insertAtSaved(text: string, pos: number, insert: string): string {
  return text.slice(0, pos) + insert + text.slice(pos);
}

function wrapSaved(
  text: string,
  start: number,
  end: number,
  before: string,
  after: string,
  fallback = 'слово',
): string {
  const sel = text.slice(start, end);
  const inner = sel || fallback;
  return text.slice(0, start) + before + inner + after + text.slice(end);
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
  const pauseMsRef   = useRef<HTMLSelectElement>(null);
  const pauseCtxRef  = useRef<HTMLSelectElement>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewErr, setPreviewErr] = useState('');

  // Сохранённый selection (курсор) — обновляется через onMouseDown на каждой кнопке.
  // Нужно т.к. клик на кнопку снимает фокус с textarea и браузер сбрасывает selection.
  const sel = useRef({ start: 0, end: 0 });

  const saveSel = () => {
    const ta = getTextarea();
    if (ta) sel.current = { start: ta.selectionStart, end: ta.selectionEnd };
  };

  const refocus = (newStart: number, newEnd = newStart) => {
    requestAnimationFrame(() => {
      const ta = getTextarea();
      if (ta) { ta.focus(); ta.setSelectionRange(newStart, newEnd); }
    });
  };

  // ── Кнопки ──────────────────────────────────────────────────────────────

  /** Ударение: вставить «+» в позицию курсора — ставить ПЕРЕД ударной гласной */
  const doStress = () => {
    const { start } = sel.current;
    onChange(insertAtSaved(currentText, start, '+'));
    refocus(start + 1);
  };

  /** Явная пауза sil<[300]> */
  const doSilPause = () => {
    const { start } = sel.current;
    const ms  = pauseMsRef.current?.value ?? '300';
    const tag = `sil<[${ms}]>`;
    onChange(insertAtSaved(currentText, start, tag));
    refocus(start + tag.length);
  };

  /** Контекстная пауза <[medium]> */
  const doCtxPause = () => {
    const { start } = sel.current;
    const size = pauseCtxRef.current?.value ?? 'medium';
    const tag  = `<[${size}]>`;
    onChange(insertAtSaved(currentText, start, tag));
    refocus(start + tag.length);
  };

  /** Акцент **слово** */
  const doAccent = () => {
    const { start, end } = sel.current;
    const newVal = wrapSaved(currentText, start, end, '**', '**');
    onChange(newVal);
    // Выделяем вставленное
    const sel2start = start + 2;
    const sel2end   = end > start ? sel2start + (end - start) : sel2start + 'слово'.length;
    refocus(sel2start, sel2end);
  };

  /** Фонетическое произношение [[фонемы]] */
  const doPhoneme = () => {
    const { start, end } = sel.current;
    const ph = window.prompt(
      'Введите фонемы через пробел (пример: v a sʲ ʌ):',
      currentText.slice(start, end) || '',
    );
    if (!ph) return;
    // Заменяем выделение обёрткой [[фонемы]]
    const newVal = wrapSaved(currentText, start, end, '[[', ']]', ph);
    onChange(newVal);
    refocus(start + 2 + ph.length);
  };

  /** Прослушать */
  const doPreview = async () => {
    if (previewing || !currentText.trim()) return;
    setPreviewErr('');
    setPreviewing(true);
    try {
      await onPreview(currentText.trim());
    } catch (e) {
      setPreviewErr(e instanceof Error ? e.message.slice(0, 50) : 'Ошибка');
    } finally {
      setPreviewing(false);
    }
  };

  // ── JSX ──────────────────────────────────────────────────────────────────
  return (
    <div className="ssml-toolbar" role="toolbar" aria-label="TTS-разметка произношения">

      {!hasOverride && (
        <span className="ssml-hint">Поставьте курсор в текст ниже → нажмите кнопку</span>
      )}

      {/* Ударение */}
      <div className="ssml-group">
        <span className="ssml-group-label">Ударение</span>
        <button
          className="ssml-btn ssml-btn--stress"
          title="Вставить «+» перед ударной гласной&#10;Пример: во+да, зам+ок, при+вет"
          onMouseDown={saveSel}
          onClick={doStress}
          type="button"
        >
          +а́
        </button>
      </div>

      <div className="ssml-divider" />

      {/* Явная пауза */}
      <div className="ssml-group">
        <span className="ssml-group-label">Пауза (мс)</span>
        <select ref={pauseMsRef} className="ssml-select" title="Длина паузы" defaultValue="300">
          <option value="100">100</option>
          <option value="200">200</option>
          <option value="300">300</option>
          <option value="500">500</option>
          <option value="700">700</option>
          <option value="1000">1000</option>
          <option value="2000">2000</option>
        </select>
        <button
          className="ssml-btn"
          title="Вставить явную паузу sil<[Xms]>&#10;Пример: Унылая пора! sil<[300]> Очей очарованье!"
          onMouseDown={saveSel}
          onClick={doSilPause}
          type="button"
        >
          ⏸ms
        </button>
      </div>

      <div className="ssml-divider" />

      {/* Контекстная пауза */}
      <div className="ssml-group">
        <span className="ssml-group-label">Пауза (контекст)</span>
        <select ref={pauseCtxRef} className="ssml-select" title="Размер контекстной паузы" defaultValue="medium">
          <option value="tiny">tiny</option>
          <option value="small">small</option>
          <option value="medium">medium</option>
          <option value="large">large</option>
          <option value="huge">huge</option>
        </select>
        <button
          className="ssml-btn"
          title="Контекстная пауза — длина подбирается автоматически&#10;Пример: Мороз и солнце; <[medium]> день чудесный!"
          onMouseDown={saveSel}
          onClick={doCtxPause}
          type="button"
        >
          ⏸~
        </button>
      </div>

      <div className="ssml-divider" />

      {/* Акцент */}
      <div className="ssml-group">
        <span className="ssml-group-label">Акцент</span>
        <button
          className="ssml-btn ssml-btn--accent"
          title="Выделите слово — обернуть в **акцент**&#10;Пример: Мы **всегда** будем в ответе"
          onMouseDown={saveSel}
          onClick={doAccent}
          type="button"
        >
          **B**
        </button>
      </div>

      <div className="ssml-divider" />

      {/* Фонемы */}
      <div className="ssml-group">
        <span className="ssml-group-label">Фонемы</span>
        <button
          className="ssml-btn ssml-btn--phoneme"
          title="Выделите слово — задать произношение фонемами&#10;Пример: [[v a sʲ ʌ]] → «Вася»"
          onMouseDown={saveSel}
          onClick={doPhoneme}
          type="button"
        >
          [[🔤]]
        </button>
      </div>

      {/* Сброс */}
      {hasOverride && (
        <>
          <div className="ssml-divider" />
          <button
            className="ssml-btn ssml-btn--reset"
            title="Убрать ручные правки — вернуть автоматический текст"
            onClick={onReset}
            type="button"
          >
            🔄 Сброс
          </button>
        </>
      )}

      {/* Прослушать */}
      <div className="ssml-divider" />
      <button
        className={`ssml-btn ssml-btn--preview${previewing ? ' ssml-btn--loading' : ''}`}
        title="Синтезировать и прослушать этот фрагмент"
        onClick={doPreview}
        disabled={previewing || !currentText.trim()}
        type="button"
      >
        {previewing ? '⏳' : '▶'} Прослушать
      </button>

      {hasOverride && (
        <span className="ssml-override-badge" title="Активна ручная разметка TTS">✎ TTS</span>
      )}

      {previewErr && (
        <span className="ssml-preview-err" title={previewErr}>⚠ {previewErr}</span>
      )}
    </div>
  );
};
