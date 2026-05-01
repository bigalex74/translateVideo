import React from 'react';
import { AlertTriangle, Info, Play, RefreshCw, X } from 'lucide-react';
import { needsReviewCount, providerWarning, t } from '../i18n';
import type { AppLocale } from '../store/settings';
import type { Segment } from '../types/schemas';
import './ConfirmRunModal.css';

interface ConfirmRunModalProps {
  projectId: string;
  provider: string;
  isForce: boolean;
  segments: Segment[];
  locale: AppLocale;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmRunModal: React.FC<ConfirmRunModalProps> = ({
  projectId,
  provider,
  isForce,
  segments,
  locale,
  onConfirm,
  onCancel,
}) => {
  const reviewCount = needsReviewCount(segments);
  const providerNote = providerWarning(provider, locale);

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-run-title">
      <div className="modal-box">
        <div className="modal-header">
          <AlertTriangle size={22} className="text-warning" />
          <h3 id="confirm-run-title">
            {isForce ? t('modal.runAgain', locale) : t('modal.continueTranslation', locale)}
          </h3>
          <button className="btn-icon" onClick={onCancel} aria-label={t('modal.close', locale)}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div className="modal-project-id">
            {t('modal.project', locale)}: <strong>{projectId}</strong>
          </div>

          {/* Информация о провайдере — только если есть что сказать пользователю */}
          {providerNote && (
            <div className="modal-warning modal-warning--info">
              <Info size={14} />
              <span>{providerNote}</span>
            </div>
          )}

          {/* Пояснение для resume */}
          {!isForce && (
            <div className="modal-warning modal-warning--info">
              <Info size={14} />
              <span>{t('modal.resumeNote', locale)}</span>
            </div>
          )}

          {/* Предупреждение о принудительном перезапуске */}
          {isForce && (
            <div className="modal-warning modal-warning--danger">
              <AlertTriangle size={14} />
              <span>{t('modal.forceNote', locale)}</span>
            </div>
          )}

          {/* QA: непереведённые сегменты */}
          {reviewCount > 0 && segments.length > 0 && (
            <div className="modal-warning modal-warning--warn">
              <AlertTriangle size={14} />
              <span>
                <strong>{reviewCount} / {segments.length}</strong> {t('modal.reviewPrefix', locale)}
              </span>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onCancel}>
            {t('modal.cancel', locale)}
          </button>
          <button className="btn-primary" onClick={onConfirm} autoFocus>
            {isForce
              ? <><RefreshCw size={16} /> {t('modal.runAgainButton', locale)}</>
              : <><Play size={16} /> {t('modal.continueButton', locale)}</>
            }
          </button>
        </div>
      </div>
    </div>
  );
};
