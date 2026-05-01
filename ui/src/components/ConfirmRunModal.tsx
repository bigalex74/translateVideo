import React from 'react';
import { AlertTriangle, Play, RefreshCw, X } from 'lucide-react';
import { PROVIDER_LABELS, PROVIDER_WARNINGS, needsReviewCount } from '../i18n';
import type { Segment } from '../types/schemas';
import './ConfirmRunModal.css';

interface ConfirmRunModalProps {
  projectId: string;
  provider: string;
  isForce: boolean;
  segments: Segment[];
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmRunModal: React.FC<ConfirmRunModalProps> = ({
  projectId,
  provider,
  isForce,
  segments,
  onConfirm,
  onCancel,
}) => {
  const reviewCount = needsReviewCount(segments);
  const providerWarning = PROVIDER_WARNINGS[provider];

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-run-title">
      <div className="modal-box">
        <div className="modal-header">
          <AlertTriangle size={22} className="text-warning" />
          <h3 id="confirm-run-title">
            {isForce ? 'Принудительный перезапуск' : 'Запустить перевод?'}
          </h3>
          <button className="btn-icon" onClick={onCancel} aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div className="modal-project-id">
            Проект: <strong>{projectId}</strong>
          </div>

          <div className="modal-provider">
            <span className="modal-label">Режим обработки:</span>
            <span>{PROVIDER_LABELS[provider] ?? provider}</span>
          </div>

          {providerWarning && (
            <div className="modal-warning">
              <AlertTriangle size={14} />
              {providerWarning}
            </div>
          )}

          {isForce && (
            <div className="modal-warning modal-warning--danger">
              <AlertTriangle size={14} />
              <span>
                <strong>Принудительный перезапуск</strong> пересчитает все этапы заново,
                включая уже завершённые. Все ранее сгенерированные артефакты будут перезаписаны.
              </span>
            </div>
          )}

          {reviewCount > 0 && segments.length > 0 && (
            <div className="modal-warning modal-warning--info">
              <span>
                ⚠️ В транскрипте <strong>{reviewCount} из {segments.length} сегментов</strong> требуют
                ручной проверки — перевод не применён или совпадает с оригиналом. Рекомендуем
                отредактировать их перед запуском TTS.
              </span>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onCancel}>
            Отмена
          </button>
          <button className="btn-primary" onClick={onConfirm} autoFocus>
            {isForce
              ? <><RefreshCw size={16} /> Перезапустить</>
              : <><Play size={16} /> Запустить</>
            }
          </button>
        </div>
      </div>
    </div>
  );
};
