/**
 * InstallPWABanner — кнопка установки PWA (NM2-07)
 *
 * Использует beforeinstallprompt API.
 * Показывается только если браузер поддерживает и пользователь не отклонял.
 */
import React, { useEffect, useState } from 'react';
import { Download, X } from 'lucide-react';

const DISMISSED_KEY = 'pwa_install_dismissed';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export const InstallPWABanner: React.FC = () => {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    // Уже отклонено пользователем?
    if (localStorage.getItem(DISMISSED_KEY)) return;

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setVisible(true);
    };

    window.addEventListener('beforeinstallprompt', handler);

    // Уже установлено
    window.addEventListener('appinstalled', () => {
      setVisible(false);
      setInstalled(true);
    });

    return () => {
      window.removeEventListener('beforeinstallprompt', handler);
    };
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setVisible(false);
      setInstalled(true);
    }
    setDeferredPrompt(null);
  };

  const handleDismiss = () => {
    setVisible(false);
    localStorage.setItem(DISMISSED_KEY, '1');
  };

  if (!visible || installed) return null;

  return (
    <div className="pwa-install-banner" role="complementary" aria-label="Установить приложение">
      <div className="pwa-install-icon">📱</div>
      <div className="pwa-install-text">
        <strong>Установить как приложение</strong>
        <span>Работает офлайн, быстрее, удобнее</span>
      </div>
      <button
        className="pwa-install-btn"
        onClick={handleInstall}
        id="pwa-install-btn"
        aria-label="Установить приложение"
      >
        <Download size={14} />
        Установить
      </button>
      <button
        className="pwa-dismiss-btn"
        onClick={handleDismiss}
        aria-label="Закрыть баннер"
      >
        <X size={14} />
      </button>
    </div>
  );
};
