/**
 * OnboardingTour — Guided tour при первом визите (C-01).
 * Показывается автоматически если localStorage не содержит 'tv_onboarded'.
 */
import React, { useState, useEffect } from 'react';
import { X, ArrowRight, ArrowLeft, CheckCircle2 } from 'lucide-react';
import './OnboardingTour.css';

const STEPS = [
  {
    icon: '🎬',
    title: 'Добро пожаловать в AI Video Translator',
    body: 'Это приложение переводит видео с одного языка на другой: транскрибирует речь, переводит текст и создаёт озвученную версию. Всё автоматически.',
    hint: null,
  },
  {
    icon: '📁',
    title: 'Шаг 1 — Загрузите видео',
    body: 'Нажмите «+ Новый проект», загрузите файл (или укажите путь к нему) и дайте ему название. Поддерживаются форматы MP4, MKV, WebM, MP3, WAV.',
    hint: 'Максимальный размер файла: 2 ГБ',
  },
  {
    icon: '⚙️',
    title: 'Шаг 2 — Выберите настройки',
    body: 'Укажите исходный язык видео и язык перевода. Выберите пресет под ваш сценарий: Shorts, Лекция, Интервью или Вебинар.',
    hint: 'Не знаете что выбрать? Используйте «Без пресета» — настройки по умолчанию работают хорошо.',
  },
  {
    icon: '🚀',
    title: 'Шаг 3 — Запустите перевод',
    body: 'Нажмите «▶ Запустить» в карточке проекта. Процесс занимает от нескольких минут до получаса — зависит от длины видео. Прогресс отображается в реальном времени.',
    hint: 'Вы можете закрыть вкладку и вернуться позже — работа продолжается на сервере.',
  },
  {
    icon: '💾',
    title: 'Шаг 4 — Скачайте результат',
    body: 'После завершения откройте проект и перейдите на вкладку «Артефакты». Там вы найдёте переведённое видео, файлы субтитров (.srt, .vtt) и аудиодорожку.',
    hint: 'Можно отредактировать субтитры прямо в приложении перед скачиванием.',
  },
  {
    icon: '❓',
    title: 'Частые вопросы',
    body: (
      <>
        <b>Что такое «Провайдер»?</b> — сервис, который озвучивает перевод (OpenAI, Яндекс).<br />
        <b>Что такое «TTS»?</b> — Text-to-Speech, синтез речи.<br />
        <b>Что такое «Пайплайн»?</b> — последовательность шагов обработки видео.<br />
        <b>Нужны ли мне API-ключи?</b> — если приложение развёрнуто администратором, ключи уже настроены. Иначе — см. раздел «Настройки».
      </>
    ),
    hint: null,
  },
];

const LS_KEY = 'tv_onboarded';

export const OnboardingTour: React.FC<{ onDone?: () => void }> = ({ onDone }) => {
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!localStorage.getItem(LS_KEY)) {
      setVisible(true);
    }
  }, []);

  if (!visible) return null;

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  const finish = () => {
    localStorage.setItem(LS_KEY, '1');
    setVisible(false);
    onDone?.();
  };

  return (
    <div className="onboarding-overlay" role="dialog" aria-modal="true" aria-label="Добро пожаловать">
      <div className="onboarding-modal">
        <button
          className="onboarding-close"
          onClick={finish}
          aria-label="Закрыть онбординг"
          title="Закрыть"
        >
          <X size={18} />
        </button>

        {/* Progress dots */}
        <div className="onboarding-dots">
          {STEPS.map((_, i) => (
            <button
              key={i}
              className={`onboarding-dot ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`}
              onClick={() => setStep(i)}
              aria-label={`Шаг ${i + 1}`}
            />
          ))}
        </div>

        <div className="onboarding-icon">{current.icon}</div>
        <h2 className="onboarding-title">{current.title}</h2>
        <div className="onboarding-body">{current.body}</div>
        {current.hint && (
          <div className="onboarding-hint">💡 {current.hint}</div>
        )}

        <div className="onboarding-nav">
          {step > 0 && (
            <button
              className="onboarding-btn-secondary"
              onClick={() => setStep(s => s - 1)}
            >
              <ArrowLeft size={15} /> Назад
            </button>
          )}
          <div style={{ flex: 1 }} />
          {!isLast ? (
            <button
              className="onboarding-btn-primary"
              onClick={() => setStep(s => s + 1)}
            >
              Далее <ArrowRight size={15} />
            </button>
          ) : (
            <button
              className="onboarding-btn-primary onboarding-btn-finish"
              onClick={finish}
            >
              <CheckCircle2 size={15} /> Начать работу
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

/** Кнопка для повторного запуска тура (из Settings) */
export function resetOnboarding() {
  localStorage.removeItem(LS_KEY);
}
