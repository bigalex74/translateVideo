import React, { useRef, useState } from 'react';
import './SSMLToolbar.css';

/**
 * SSMLToolbar — компактная панель Яндекс TTS-разметки.
 * v1.28.0: компактный вид, умный акцент (определяет слово под курсором),
 *           автоскрытие ошибок, без лишних подписей групп.
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

function insertAt(text: string, pos: number, insert: string): string {
  return text.slice(0, pos) + insert + text.slice(pos);
}

function wrapAt(text: string, s: number, e: number, before: string, after: string, fallback = 'слово'): string {
  const inner = s < e ? text.slice(s, e) : fallback;
  return text.slice(0, s < e ? s : s) + before + inner + after + text.slice(s < e ? e : s);
}

/** Определить границы слова в позиции pos */
function wordBounds(text: string, pos: number): [number, number] {
  let s = pos, e = pos;
  // Шаг назад до начала слова
  while (s > 0 && /\S/.test(text[s - 1])) s--;
  // Шаг вперёд до конца слова
  while (e < text.length && /\S/.test(text[e])) e++;
  return [s, e];
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
  const pauseMsRef  = useRef<HTMLSelectElement>(null);
  const pauseCtxRef = useRef<HTMLSelectElement>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewErr, setPreviewErr] = useState('');
  const errTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Сохранённый selection — обновляется через onMouseDown (до потери фокуса).
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

  const showErr = (msg: string) => {
    setPreviewErr(msg);
    if (errTimerRef.current) clearTimeout(errTimerRef.current);
    errTimerRef.current = setTimeout(() => setPreviewErr(''), 5000);
  };

  // ── Обработчики ──────────────────────────────────────────────────────────

  /** Ударение +: вставить «+» в позицию курсора */
  const doStress = () => {
    const { start } = sel.current;
    onChange(insertAt(currentText, start, '+'));
    refocus(start + 1);
  };

  /** Явная пауза sil<[Xms]> */
  const doSilPause = () => {
    const { start } = sel.current;
    const ms  = pauseMsRef.current?.value ?? '300';
    const tag = `sil<[${ms}]>`;
    onChange(insertAt(currentText, start, tag));
    refocus(start + tag.length);
  };

  /** Контекстная пауза <[medium]> */
  const doCtxPause = () => {
    const { start } = sel.current;
    const size = pauseCtxRef.current?.value ?? 'medium';
    const tag  = `<[${size}]>`;
    onChange(insertAt(currentText, start, tag));
    refocus(start + tag.length);
  };

  /**
   * Акцент **слово**:
   * - Если есть выделение → обернуть его
   * - Если курсор внутри слова → определить границы автоматически
   * - Если курсор на пробеле → вставить **слово**
   */
  const doAccent = () => {
    const { start, end } = sel.current;

    let wS = start, wE = end;

    if (start === end) {
      // Нет выделения — определяем слово под курсором
      [wS, wE] = wordBounds(currentText, start);
    }

    if (wS === wE) {
      // Курсор между пробелами — вставляем placeholder
      const tag = '**слово**';
      onChange(insertAt(currentText, start, tag));
      refocus(start + 2, start + 2 + 'слово'.length);
      return;
    }

    const newVal = wrapAt(currentText, wS, wE, '**', '**');
    onChange(newVal);
    refocus(wS + 2, wS + 2 + (wE - wS));
  };

  /** Фонемы [[...]] */
  const doPhoneme = () => {
    const { start, end } = sel.current;

    let wS = start, wE = end;
    if (start === end) [wS, wE] = wordBounds(currentText, start);

    const selected = wS < wE ? currentText.slice(wS, wE) : '';
    const ph = window.prompt('Введите фонемы через пробел (например: v a sʲ ʌ):', selected);
    if (!ph) return;

    // Заменяем слово/выделение обёрткой [[фонемы]]
    const before = '[[';
    const after  = ']]';
    const inner  = ph;
    const newVal = currentText.slice(0, wS < wE ? wS : start)
      + before + inner + after
      + currentText.slice(wS < wE ? wE : start);

    onChange(newVal);
    refocus((wS < wE ? wS : start) + before.length + inner.length + after.length);
  };

  /** Прослушать */
  const doPreview = async () => {
    if (previewing || !currentText.trim()) return;
    setPreviewErr('');
    setPreviewing(true);
    try {
      await onPreview(currentText.trim());
    } catch (e) {
      showErr(e instanceof Error ? e.message.slice(0, 60) : 'Ошибка синтеза');
    } finally {
      setPreviewing(false);
    }
  };

  // ── JSX ──────────────────────────────────────────────────────────────────
  return (
    <div className="ssml-toolbar" role="toolbar" aria-label="TTS-разметка произношения">

      {/* +а́ Ударение */}
      <button
        className="ssml-btn ssml-btn--stress"
        title={"Ударение: вставить «+» перед ударной гласной\nПример: зам+ок, при+вет, во+да"}
        onMouseDown={saveSel}
        onClick={doStress}
        type="button"
      >
        +а́
      </button>

      <div className="ssml-divider" />

      {/* Пауза явная */}
      <select ref={pauseMsRef} className="ssml-select" title="Длина явной паузы (мс)" defaultValue="300"
        onMouseDown={(e) => e.stopPropagation()}>
        <option value="100">100ms</option>
        <option value="200">200ms</option>
        <option value="300">300ms</option>
        <option value="500">500ms</option>
        <option value="700">700ms</option>
        <option value="1000">1s</option>
        <option value="2000">2s</option>
      </select>
      <button
        className="ssml-btn"
        title={"Вставить явную паузу sil<[Xms]>\nПример: Унылая пора! sil<[300]> Очей очарованье!"}
        onMouseDown={saveSel}
        onClick={doSilPause}
        type="button"
      >
        ⏸
      </button>

      <div className="ssml-divider" />

      {/* Пауза контекстная */}
      <select ref={pauseCtxRef} className="ssml-select" title="Размер контекстной паузы" defaultValue="medium"
        onMouseDown={(e) => e.stopPropagation()}>
        <option value="tiny">tiny</option>
        <option value="small">small</option>
        <option value="medium">medium</option>
        <option value="large">large</option>
        <option value="huge">huge</option>
      </select>
      <button
        className="ssml-btn"
        title={"Контекстная пауза — длина подбирается автоматически\nПример: Мороз и солнце; <[medium]> день чудесный!"}
        onMouseDown={saveSel}
        onClick={doCtxPause}
        type="button"
      >
        ⏸~
      </button>

      <div className="ssml-divider" />

      {/* Акцент **слово** */}
      <button
        className="ssml-btn ssml-btn--accent"
        title={"Акцент: выделить слово или поставить курсор внутри\nАвтоматически определяет границы слова\nВставляет: **слово**"}
        onMouseDown={saveSel}
        onClick={doAccent}
        type="button"
      >
        **B**
      </button>

      <div className="ssml-divider" />

      {/* Фонемы [[...]] */}
      <button
        className="ssml-btn ssml-btn--phoneme"
        title={"Фонетическое произношение\nВыделите слово или поставьте курсор внутри\nПример: [[v a sʲ ʌ]] → «Вася»"}
        onMouseDown={saveSel}
        onClick={doPhoneme}
        type="button"
      >
        [[🔤]]
      </button>

      {/* Сброс — только если есть override */}
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

      <div className="ssml-divider" />

      {/* Прослушать */}
      <button
        className={`ssml-btn ssml-btn--preview${previewing ? ' ssml-btn--loading' : ''}`}
        title="Синтезировать и прослушать этот фрагмент"
        onClick={doPreview}
        disabled={previewing || !currentText.trim()}
        type="button"
      >
        {previewing ? '⏳' : '▶'} Прослушать
      </button>

      {/* Badge — только если override задан */}
      {hasOverride && (
        <span className="ssml-override-badge" title="Активна ручная TTS-разметка">✎ TTS</span>
      )}

      {/* Ошибка синтеза — автоскрывается через 5с */}
      {previewErr && (
        <span className="ssml-preview-err" title={previewErr}>⚠ {previewErr}</span>
      )}
    </div>
  );
};
