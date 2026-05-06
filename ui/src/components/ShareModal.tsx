import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';

interface ShareModalProps {
  projectId: string;
  onClose: () => void;
}

/**
 * ShareModal — модальное окно для управления публичной ссылкой (R9-И3)
 *
 * Позволяет:
 * - Создать share-ссылку (токен 7 дней)
 * - Скопировать ссылку в clipboard
 * - Отозвать ссылку
 */
export function ShareModal({ projectId, onClose }: ShareModalProps) {
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Загружаем существующую ссылку
  useEffect(() => {
    const load = async () => {
      try {
        const { getShareLink } = await import('../api/client');
        const data = await getShareLink(projectId);
        setShareUrl(data.share_url);
        setExpiresAt(data.expires_at);
      } catch {
        // Нет ссылки — нормально
      }
    };
    load();
  }, [projectId]);

  const handleCreate = async () => {
    setLoading(true);
    setError(null);
    try {
      const { createShareLink } = await import('../api/client');
      const data = await createShareLink(projectId);
      setShareUrl(data.share_url);
      setExpiresAt(data.expires_at);
    } catch (err) {
      setError('Ошибка создания ссылки');
    } finally {
      setLoading(false);
    }
  };

  const handleRevoke = async () => {
    setLoading(true);
    try {
      const { revokeShareLink } = await import('../api/client');
      await revokeShareLink(projectId);
      setShareUrl(null);
      setExpiresAt(null);
    } catch {
      setError('Ошибка при отзыве ссылки');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setError('Не удалось скопировать');
    }
  };

  const formatExpiry = (iso: string) => {
    try {
      return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
    } catch {
      return iso;
    }
  };

  const modal = (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Поделиться проектом">
      <div className="modal-box share-modal">
        <div className="modal-header">
          <h2>🔗 Поделиться проектом</h2>
          <button className="modal-close" onClick={onClose} aria-label="Закрыть">✕</button>
        </div>

        <div className="modal-body">
          <p className="share-description">
            Публичная ссылка позволяет просматривать перевод без авторизации (только чтение).
            Срок действия: <strong>7 дней</strong>.
          </p>

          {error && <div className="share-error">⚠️ {error}</div>}

          {shareUrl ? (
            <div className="share-url-block">
              <div className="share-url-row">
                <input
                  className="share-url-input"
                  type="text"
                  readOnly
                  value={shareUrl}
                  onClick={(e) => (e.target as HTMLInputElement).select()}
                />
                <button
                  className={`btn-secondary ${copied ? 'btn--success' : ''}`}
                  onClick={handleCopy}
                  title="Скопировать ссылку"
                >
                  {copied ? '✅ Скопировано' : '📋 Копировать'}
                </button>
              </div>
              {expiresAt && (
                <p className="share-expiry">
                  Действует до: <strong>{formatExpiry(expiresAt)}</strong>
                </p>
              )}
              <button
                className="btn-danger share-revoke"
                onClick={handleRevoke}
                disabled={loading}
              >
                🗑 Отозвать ссылку
              </button>
            </div>
          ) : (
            <div className="share-create-block">
              <p className="share-empty">Публичная ссылка ещё не создана.</p>
              <button
                className="btn-primary"
                onClick={handleCreate}
                disabled={loading}
              >
                {loading ? '⏳ Создание...' : '🔗 Создать ссылку'}
              </button>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>Закрыть</button>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
