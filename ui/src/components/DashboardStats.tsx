/**
 * DashboardStats — сводная статистика проектов (NM2-05, D5)
 *
 * Показывает: всего / завершено / в процессе / с ошибкой
 * D5: + слова переведено + среднее время
 */
import React from 'react';
import type { VideoProject } from '../types/schemas';
import { CheckCircle2, Loader2, AlertTriangle, Film, BookOpen, Clock } from 'lucide-react';

interface Props {
  projects: VideoProject[];
}

export const DashboardStats: React.FC<Props> = ({ projects }) => {
  if (!projects.length) return null;

  const total = projects.length;
  const completed = projects.filter((p) => p.status === 'completed').length;
  const running = projects.filter((p) => p.status === 'running').length;
  const failed = projects.filter((p) => p.status === 'failed').length;

  // D5: Подсчёт слов переведённых сегментов по всем завершённым проектам
  const totalWords = projects.reduce((acc, p) => {
    if (!Array.isArray(p.segments)) return acc;
    return acc + p.segments.reduce((wAcc: number, seg: {translated_text?: string}) => {
      return wAcc + (seg.translated_text?.split(/\s+/).filter(Boolean).length ?? 0);
    }, 0);
  }, 0);

  // D5: Среднее время выполнения (из started_at → completed)
  const completedWithTime = projects.filter(p =>
    p.status === 'completed' && p.started_at
  );
  const avgMinutes = completedWithTime.length > 0
    ? Math.round(completedWithTime.reduce((acc, p) => {
        // Грубая оценка: если нет ended_at — используем stage_runs
        const stageRuns = Array.isArray(p.stage_runs) ? p.stage_runs : [];
        const lastRun = stageRuns[stageRuns.length - 1];
        if (!lastRun?.finished_at || !p.started_at) return acc;
        const diff = (new Date(lastRun.finished_at).getTime() - new Date(p.started_at).getTime()) / 60000;
        return acc + Math.max(0, diff);
      }, 0) / completedWithTime.length)
    : null;

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
      {/* D5: Слова и время */}
      {totalWords > 0 && (
        <div className="stat-card stat-words" title="Слов переведено по всем проектам">
          <div className="stat-icon"><BookOpen size={16} /></div>
          <div className="stat-value">
            {totalWords >= 1000 ? `${(totalWords / 1000).toFixed(1)}k` : totalWords}
          </div>
          <div className="stat-label">слов</div>
        </div>
      )}
      {avgMinutes !== null && (
        <div className="stat-card stat-time" title="Среднее время перевода">
          <div className="stat-icon"><Clock size={16} /></div>
          <div className="stat-value">{avgMinutes}м</div>
          <div className="stat-label">ср. время</div>
        </div>
      )}
    </div>
  );
};
