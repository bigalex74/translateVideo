/**
 * URLDownloadStatus — индикатор прогресса скачивания по URL (NC-01)
 *
 * Показывается когда проект создан из URL и имеет статус "initializing"
 * (yt-dlp скачивает файл в фоне).
 */
import React, { useEffect, useState } from 'react';
import { Download } from 'lucide-react';

interface Props {
  isVisible: boolean;
  url?: string;
}

const STEPS = [
  'Подключаемся к источнику…',
  'Анализируем URL…',
  'Скачиваем видео…',
  'Обрабатываем файл…',
  'Почти готово…',
];

export const URLDownloadStatus: React.FC<Props> = ({ isVisible, url }) => {
  const [step, setStep] = useState(0);
  const [dots, setDots] = useState('');

  useEffect(() => {
    if (!isVisible) { setStep(0); return; }

    const stepTimer = setInterval(() => {
      setStep((s) => Math.min(s + 1, STEPS.length - 1));
    }, 4000);

    const dotsTimer = setInterval(() => {
      setDots((d) => d.length >= 3 ? '' : d + '.');
    }, 500);

    return () => {
      clearInterval(stepTimer);
      clearInterval(dotsTimer);
    };
  }, [isVisible]);

  if (!isVisible) return null;

  const host = (() => {
    try { return new URL(url || '').hostname; } catch { return url?.slice(0, 40); }
  })();

  return (
    <div className="url-download-status" role="status" aria-live="polite">
      <div className="url-download-icon">
        <Download size={20} className="url-dl-spin" />
      </div>
      <div className="url-download-text">
        <div className="url-download-title">
          Скачивание видео{dots}
        </div>
        <div className="url-download-source">
          Источник: <b>{host}</b>
        </div>
        <div className="url-download-step">
          {STEPS[step]}
        </div>
        <div className="url-download-bar">
          <div className="url-download-bar-inner url-download-bar-animated" />
        </div>
        <div className="url-download-hint">
          Это может занять 1–5 мин для длинного видео
        </div>
      </div>
    </div>
  );
};
