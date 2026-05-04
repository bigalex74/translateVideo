/**
 * CompletionToast — уведомление когда пользователь вернулся на вкладку
 * и проект завершён (C-20).
 */
import React, { useEffect, useState } from 'react';
import { CheckCircle2, X } from 'lucide-react';

interface Props {
  projectId: string | null;
  status: string | undefined;
}

const LS_NOTIFIED = 'tv_notified_';

export const CompletionToast: React.FC<Props> = ({ projectId, status }) => {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!projectId || status !== 'completed') return;
    const key = LS_NOTIFIED + projectId;
    if (localStorage.getItem(key)) return; // уже показывали

    const handler = () => {
      if (!document.hidden) {
        // Пользователь вернулся на вкладку — показываем toast
        setShow(true);
        localStorage.setItem(key, '1');
        setTimeout(() => setShow(false), 6000);
      }
    };

    document.addEventListener('visibilitychange', handler);
    // Также показываем сразу если уже на вкладке при завершении
    if (!document.hidden) {
      handler();
    }
    return () => document.removeEventListener('visibilitychange', handler);
  }, [projectId, status]);

  if (!show) return null;

  return (
    <div className="toast-notification" role="status" aria-live="polite">
      <CheckCircle2 size={20} style={{ color: '#22c55e', flexShrink: 0 }} />
      <span>
        <b>Перевод завершён!</b><br />
        <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>
          Откройте проект, чтобы скачать результат.
        </span>
      </span>
      <button onClick={() => setShow(false)} aria-label="Закрыть уведомление">
        <X size={16} />
      </button>
    </div>
  );
};
