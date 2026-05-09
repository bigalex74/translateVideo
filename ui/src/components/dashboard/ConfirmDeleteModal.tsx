import React from 'react';
import { createPortal } from 'react-dom';
import { Trash2 } from 'lucide-react';

interface ConfirmDeleteModalProps {
  projectId: string;
  onConfirm: (id: string) => void;
  onCancel: () => void;
}

export const ConfirmDeleteModal: React.FC<ConfirmDeleteModalProps> = ({
  projectId,
  onConfirm,
  onCancel,
}) => {
  return createPortal(
    <div className="modal-overlay" onClick={onCancel}>
      <div className="delete-modal" onClick={e => e.stopPropagation()}>
        <div className="delete-modal-icon">
          <Trash2 size={28} />
        </div>
        <h3 className="delete-modal-title">Удалить проект?</h3>
        <p className="delete-modal-desc">
          Проект <strong>{projectId}</strong> и все его файлы будут удалены без возможности восстановления.
        </p>
        <div className="delete-modal-actions">
          <button className="delete-modal-cancel" onClick={onCancel}>
            Отмена
          </button>
          <button className="delete-modal-confirm" onClick={() => onConfirm(projectId)}>
            <Trash2 size={15} /> Удалить навсегда
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};
