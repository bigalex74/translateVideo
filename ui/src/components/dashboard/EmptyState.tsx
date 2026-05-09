import React from 'react';
import { BookOpen } from 'lucide-react';
import { t } from '../../i18n';
import type { AppLocale } from '../../store/settings';

interface EmptyStateProps {
  locale: AppLocale;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ locale }) => {
  return (
    <div className="empty-state glass-panel">
      <div className="onboarding-hero">
        <div className="onboarding-icon">🎬</div>
        <h3>{t('dashboard.noProjectTitle', locale)}</h3>
        <p className="text-muted">{t('dashboard.noProjectText', locale)}</p>
      </div>
      <div className="onboarding-steps">
        <div className="onboarding-step">
          <div className="step-num">1</div>
          <div>
            <strong>Создайте проект</strong>
            <p>Нажмите «+ Новый проект», загрузите видео или вставьте ссылку</p>
          </div>
        </div>
        <div className="onboarding-step">
          <div className="step-num">2</div>
          <div>
            <strong>Выберите язык и провайдера</strong>
            <p>Настройте параметры перевода и озвучки в мастере</p>
          </div>
        </div>
        <div className="onboarding-step">
          <div className="step-num">3</div>
          <div>
            <strong>Запустите перевод</strong>
            <p>Нажмите «Запустить» — всё остальное сделает ИИ автоматически</p>
          </div>
        </div>
        <div className="onboarding-step">
          <div className="step-num">4</div>
          <div>
            <strong>Скачайте результат</strong>
            <p>Готовое видео с переводом появится в редакторе</p>
          </div>
        </div>
      </div>
      <div className="onboarding-actions">
        <a href="/docs" target="_blank" className="btn-secondary onboarding-docs-link">
          <BookOpen size={15} /> API документация
        </a>
      </div>
    </div>
  );
};