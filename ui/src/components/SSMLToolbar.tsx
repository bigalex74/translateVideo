import React, { useRef, useState } from 'react';
import './SSMLToolbar.css';

/**
 * SSMLToolbar — компактная панель Яндекс TTS-разметки.
 *
 * FIX v1.28.0: doPreview читает getTextarea().value (живое значение),
 * а не проп currentText (может быть устаревшим между рендерами).
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

/** Определить границы слова в позиции pos */
function wordBounds(text: string, pos: number): [number, number] {
  let s = pos, e = pos;
  while (s > 0 && /\S/.test(text[s - 1])) s--;
  while (e < text.length && /\S/.test(text[e])) e++;
  return [s, e];
}

// ── TTS-preview визуализация ─────────────────────────────────────────────────

/**
 * Рендерит TTS-разметку как читаемый HTML.
 * **слово** → <b>слово</b> (оранжевый)
 * sil<[300]> → ⏸ 300ms
 * <[medium]> → ⏸~medium
 * [[ph]] → 🔤ph
 * + (перед гласной) → <sup>+</sup> (жёлтый)
 */
export function renderTtsMarkup(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  // Паттерны обработки (порядок важен)
  const patterns: Array<{ re: RegExp; render: (m: RegExpExecArray) => React.ReactNode }> = [
    {
      // sil<[300]>
      re: /sil<\[(\d+)\]>/,
      render: (m) => <span key={key++} className="tts-sil" title={`Пауза ${m[1]}мс`}>⏸{m[1]}мс</span>,
    },
    {
      // <[medium]> контекстная пауза
      re: /<\[(tiny|small|medium|large|huge)\]>/,
      render: (m) => <span key={key++} className="tts-ctx-pause" title={`Контекстная пауза: ${m[1]}`}>⏸~{m[1]}</span>,
    },
    {
      // [[фонемы]]
      re: /\[\[(.+?)\]\]/,
      render: (m) => <span key={key++} className="tts-phoneme" title={`Фонемы: ${m[1]}`}>🔤{m[1]}</span>,
    },
    {
      // **слово** — логическое ударение (Яндекс TTS-разметка, API v3)
      re: /\*\*([^*]+)\*\*/,
      render: (m) => <strong key={key++} className="tts-logic-accent" title={`Логическое ударение: «${m[1]}»`}>{m[1]}</strong>,
    },
    {
      // + перед гласной (фонетическое ударение) — нативная Яндекс разметка
      re: /\+([аеёиоуыэюяАЕЁИОУЫЭЮЯaeiouAEIOU])/,
      render: (m) => <span key={key++} className="tts-stress">+{m[1]}</span>,
    },
  ];

  while (remaining.length > 0) {
    let earliest: { index: number; length: number; node: React.ReactNode } | null = null;

    for (const p of patterns) {
      const m = p.re.exec(remaining);
      if (m && (earliest === null || m.index < earliest.index)) {
        earliest = { index: m.index, length: m[0].length, node: p.render(m) };
      }
    }

    if (!earliest) {
      nodes.push(<span key={key++}>{remaining}</span>);
      break;
    }

    if (earliest.index > 0) {
      nodes.push(<span key={key++}>{remaining.slice(0, earliest.index)}</span>);
    }
    nodes.push(earliest.node);
    remaining = remaining.slice(earliest.index + earliest.length);
  }

  return nodes;
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

  /** Логическое ударение **word**: оборачивает слово под курсором в **...** */
  const doLogicAccent = () => {
    const { start, end } = sel.current;
    let wS = start, wE = end;
    if (start === end) [wS, wE] = wordBounds(currentText, start);

    if (wS === wE) {
      // Нет слова — вставляем ****  и ставим курсор внутрь
      const ins = '****';
      onChange(insertAt(currentText, start, ins));
      refocus(start + 2);
      return;
    }

    const before = currentText.slice(0, wS);
    const word   = currentText.slice(wS, wE);
    const after  = currentText.slice(wE);
    onChange(before + '**' + word + '**' + after);
    refocus(wS + 2 + word.length + 2);
  };

  /** Фонетическое ударение +: ставит + перед первой гласной в слове под курсором.
   * Яндекс TTS разметка: б+олван, пр+иятно.
   */
  const doAccent = () => {
    const { start, end } = sel.current;
    let wS = start, wE = end;
    if (start === end) [wS, wE] = wordBounds(currentText, start);

    // Нет слова — просто вставляем + в позицию курсора
    if (wS === wE) {
      onChange(insertAt(currentText, start, '+'));
      refocus(start + 1);
      return;
    }

    // Слово найдено — ставим + перед первой гласной
    const VOWELS = 'аеёиоуыэюяАЕЁИОУЫЭЮЯaeiouAEIOU';
    const word = currentText.slice(wS, wE);
    const vowelIdx = word.split('').findIndex(ch => VOWELS.includes(ch));
    if (vowelIdx === -1) {
      // Нет гласных (аббревиатура, число) — + в начало
      onChange(insertAt(currentText, wS, '+'));
      refocus(wS + 1);
    } else {
      const insertPos = wS + vowelIdx;
      onChange(insertAt(currentText, insertPos, '+'));
      refocus(insertPos + 1 + (wE - wS)); // после слова
    }
  };

  /** Фонемы [[...]] — определяет слово под курсором автоматически */
  const doPhoneme = () => {
    const { start, end } = sel.current;
    let wS = start, wE = end;
    if (start === end) [wS, wE] = wordBounds(currentText, start);

    const selected = wS < wE ? currentText.slice(wS, wE) : '';
    const ph = window.prompt('Введите фонемы через пробел (например: v a sʲ ʌ):', selected);
    if (!ph) return;

    const newVal = currentText.slice(0, wS < wE ? wS : start)
      + '[[' + ph + ']]'
      + currentText.slice(wS < wE ? wE : start);

    onChange(newVal);
    refocus((wS < wE ? wS : start) + 2 + ph.length + 2);
  };

  /**
   * Прослушать — ВАЖНО: читаем getTextarea().value (живое значение),
   * не проп currentText (может не отражать последние правки).
   */
  const doPreview = async () => {
    if (previewing) return;
    // Живое значение из textarea — самое актуальное
    const liveText = (getTextarea()?.value ?? currentText).trim();
    if (!liveText) return;
    setPreviewErr('');
    setPreviewing(true);
    try {
      await onPreview(liveText);
    } catch (e) {
      showErr(e instanceof Error ? e.message.slice(0, 60) : 'Ошибка синтеза');
    } finally {
      setPreviewing(false);
    }
  };

  // ── JSX ──────────────────────────────────────────────────────────────────
  return (
    <div className="ssml-toolbar" role="toolbar" aria-label="TTS-разметка произношения">


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

      {/* Акцент: + перед гласной */}
      <button
        className="ssml-btn ssml-btn--accent"
        title={"Ударение на слове: ставит + перед первой гласной\nПример: болван → б+олван, вода → в+ода\nПоставьте курсор внутри слова или выделите его"}
        onMouseDown={saveSel}
        onClick={doAccent}
        type="button"
      >
        +á
      </button>

      <div className="ssml-divider" />

      {/* Логическое ударение **word** */}
      <button
        className="ssml-btn ssml-btn--logic-accent"
        title={"Логическое ударение **слово**\nПример: **Кот** пошёл в лес? — акцент на 'Кот'\nПоставьте курсор внутри слова или выделите его"}
        onMouseDown={saveSel}
        onClick={doLogicAccent}
        type="button"
      >
        **B**
      </button>

      <div className="ssml-divider" />

      {/* Фонемы [[...]] */}
      <button
        className="ssml-btn ssml-btn--phoneme"
        title={"Фонетическое произношение\nПоставьте курсор внутри слова\nПример: [[v a sʲ ʌ]] → «Вася»"}
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
        title="Синтезировать и прослушать этот фрагмент (читает текущее содержимое textarea)"
        onClick={doPreview}
        disabled={previewing}
        type="button"
      >
        {previewing ? '⏳' : '▶'} Прослушать
      </button>

      {hasOverride && (
        <span className="ssml-override-badge" title="Активна ручная TTS-разметка">✎ TTS</span>
      )}

      {previewErr && (
        <span className="ssml-preview-err" title={previewErr}>⚠ {previewErr}</span>
      )}
    </div>
  );
};
