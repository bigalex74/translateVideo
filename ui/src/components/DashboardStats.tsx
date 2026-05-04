/**
 * DashboardStats — сводная статистика проектов (NM2-05)
 *
 * Показывает: всего / завершено / в процессе / с ошибкой
 */
import React from 'react';
import type { VideoProject } from '../types/schemas';
import { CheckCircle2, Loader2, AlertTriangle, Film } from 'lucide-react';

interface Props {
  projects: VideoProject[];
}

export const DashboardStats: React.FC<Props> = ({ projects }) => {
  if (!projects.length) return null;

  const total = projects.length;
  const completed = projects.filter((p) => p.status === 'completed').length;
  const running = projects.filter((p) => p.status === 'running').length;
  const failed = projects.filter((p) => p.status === 'failed').length;

  const stats = [
    { label: 'Всего', value: total, icon: <Film size={16} />, cls: 'stat-total' },
    { label: 'Готово', value: completed, icon: <CheckCircle2 size={16} />, cls: 'stat-ok' },
    { label: 'В работе', value: running, icon: <Loader2 size={16} className="animate-spin" />, cls: 'stat-running' },
    { label: 'Ошибок', value: failed, icon: <AlertTriangle size={16} />, cls: 'stat-fail' },
  ];

  return (
    <div className="dashboard-stats" role="region" aria-label="Статистика проектов">
      {stats.map((s) => (
        <div key={s.label} className={`stat-card ${s.cls}`}>
          <div className="stat-icon">{s.icon}</div>
          <div className="stat-value">{s.value}</div>
          <div className="stat-label">{s.label}</div>
        </div>
      ))}
    </div>
  );
};
