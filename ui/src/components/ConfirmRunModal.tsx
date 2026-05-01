import React from 'react';
import { AlertTriangle, Info, Play, RefreshCw, X } from 'lucide-react';
import { PROVIDER_WARNINGS, needsReviewCount } from '../i18n';
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
  const providerNote = PROVIDER_WARNINGS[provider];

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-run-title">
      <div className="modal-box">
        <div className="modal-header">
          <AlertTriangle size={22} className="text-warning" />
          <h3 id="confirm-run-title">
            {isForce ? 'Запустить заново?' : 'Запустить перевод?'}
          </h3>
          <button className="btn-icon" onClick={onCancel} aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div className="modal-project-id">
            Проект: <strong>{projectId}</strong>
          </div>

          {/* Информация о провайдере — только если есть что сказать пользователю */}
          {providerNote && (
            <div className="modal-warning modal-warning--info">
              <Info size={14} />
              <span>{providerNote}</span>
            </div>
          )}

          {/* Предупреждение о принудительном перезапуске */}
          {isForce && (
            <div className="modal-warning modal-warning--danger">
              <AlertTriangle size={14} />
              <span>
                Все этапы обработки будут запущены заново, включая уже завершённые.
                Готовые файлы будут перезаписаны.
              </span>
            </div>
          )}

          {/* QA: непереведённые сегменты */}
          {reviewCount > 0 && segments.length > 0 && (
            <div className="modal-warning modal-warning--warn">
              <AlertTriangle size={14} />
              <span>
                <strong>{reviewCount} из {segments.length} сегментов</strong> не переведены.
                Рекомендуем заполнить их в редакторе перед запуском озвучки.
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
              ? <><RefreshCw size={16} /> Запустить заново</>
              : <><Play size={16} /> Запустить</>
            }
          </button>
        </div>
      </div>
    </div>
  );
};
