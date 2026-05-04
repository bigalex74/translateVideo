/**
 * Shared Tooltip component (CI iter 2 — предложение Frontend агента).
 * Переиспользуется в NewProject, Workspace и онбординге.
 */
import React, { useState } from 'react';
import { HelpCircle } from 'lucide-react';
import './Tooltip.css';

export const TERM_GLOSSARY: Record<string, string> = {
  'TTS': 'Text-to-Speech — синтез речи. Превращает текст перевода в голосовую озвучку.',
  'Провайдер': 'Сервис озвучки (OpenAI, Яндекс, ElevenLabs). У каждого свои голоса и стоимость.',
  'Движок обработки': 'AI-сервис для синтеза речи. OpenAI — высокое качество, Яндекс — оптимально для русского.',
  'Дубляж': 'Оригинальная речь заменяется озвученным переводом.',
  'Preflight': 'Предварительная проверка файла: формат, длина, наличие звука.',
  'Пресет': 'Готовый набор настроек для Shorts, Лекций, Интервью и т.д.',
  'Сегмент': 'Один фрагмент речи с временными метками. Перевод редактируется по сегментам.',
  'Пайплайн': 'Последовательность этапов обработки: транскрипция → перевод → озвучка → рендер.',
  'Артефакт': 'Файл-результат работы: переведённое видео, субтитры (.srt/.vtt), аудио.',
};

interface TooltipProps {
  term: string;
  children: React.ReactNode;
  position?: 'top' | 'bottom';
}

export const Tooltip: React.FC<TooltipProps> = ({ term, children, position = 'top' }) => {
  const [show, setShow] = useState(false);
  const tip = TERM_GLOSSARY[term];
  if (!tip) return <>{children}</>;
  return (
    <span className="tooltip-wrap">
      {children}
      <button
        type="button"
        className="tooltip-help-btn"
        aria-label={`Что такое ${term}?`}
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onFocus={() => setShow(true)}
        onBlur={() => setShow(false)}
      >
        <HelpCircle size={13} />
      </button>
      {show && (
        <div className={`tooltip-popup tooltip-popup--${position}`} role="tooltip">
          {tip}
        </div>
      )}
    </span>
  );
};
