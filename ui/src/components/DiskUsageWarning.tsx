/**
 * DiskUsageWarning — предупреждение когда disk_usage_mb > порога (NC4-03)
 *
 * Получает данные из /api/health и показывает баннер при переполнении.
 * Порог по умолчанию: 500 MB (настраивается через VITE_DISK_WARN_MB).
 */
import React, { useEffect, useState } from 'react';
import { HardDrive, X } from 'lucide-react';

const WARN_MB = Number(import.meta.env?.VITE_DISK_WARN_MB ?? 500);
const CHECK_INTERVAL_MS = 60_000; // раз в минуту

interface HealthData {
  disk_usage_mb?: number;
  disk_work_root?: string;
}

export const DiskUsageWarning: React.FC = () => {
  const [diskMb, setDiskMb] = useState<number | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch('/api/health');
        const data: HealthData = await r.json();
        if (data.disk_usage_mb != null) setDiskMb(data.disk_usage_mb);
      } catch {
        // Нет подключения — игнорируем
      }
    };
    check();
    const timer = setInterval(check, CHECK_INTERVAL_MS);
    return () => clearInterval(timer);
  }, []);

  if (dismissed || diskMb === null || diskMb < WARN_MB) return null;

  const pct = Math.min(100, Math.round((diskMb / (WARN_MB * 2)) * 100));

  return (
    <div className="disk-warning-banner" role="alert" aria-live="assertive">
      <HardDrive size={18} className="disk-warning-icon" />
      <div className="disk-warning-text">
        <strong>Предупреждение: диск заполнен</strong>
        <span>
          Занято {diskMb.toFixed(0)} MB ({pct}% от рекомендуемого лимита).
          Освободите место, удалив старые проекты.
        </span>
      </div>
      <button
        className="disk-warning-dismiss"
        onClick={() => setDismissed(true)}
        aria-label="Закрыть"
      >
        <X size={14} />
      </button>
    </div>
  );
};
