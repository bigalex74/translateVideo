import React from 'react';

export interface BatchItem {
  name: string;
  status: 'pending' | 'uploading' | 'done' | 'error';
  projectId?: string;
  error?: string;
}

interface BatchQueueProps {
  queue: BatchItem[];
  active: boolean;
  onHide: () => void;
  onOpenProject: (id: string) => void;
}

export const BatchQueue: React.FC<BatchQueueProps> = ({ queue, active, onHide, onOpenProject }) => {
  if (queue.length === 0) return null;

  return (
    <div className="batch-queue glass-panel" role="status" aria-live="polite">
      <div className="batch-queue-header">
        <span>📦 Батч-загрузка: {queue.filter(i => i.status === 'done').length}/{queue.length}</span>
        {!active && (
          <button className="btn-secondary btn-xs" onClick={onHide}>× Скрыть</button>
        )}
      </div>
      {queue.map((item, idx) => (
        <div key={idx} className={`batch-queue-item batch-queue-item--${item.status}`}>
          <span className="batch-queue-status">
            {item.status === 'pending'   ? '⏳' :
             item.status === 'uploading' ? '🔄' :
             item.status === 'done'      ? '✅' : '❌'}
          </span>
          <span className="batch-queue-name">{item.name}</span>
          {item.projectId && (
            <button className="btn-secondary btn-xs" onClick={() => onOpenProject(item.projectId!)}>Открыть</button>
          )}
          {item.error && <span className="batch-queue-error">{item.error.slice(0, 60)}</span>}
        </div>
      ))}
    </div>
  );
};
