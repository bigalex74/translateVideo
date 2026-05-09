import { useState, useEffect } from 'react';
import { fetchAnalytics } from '../api/client'; // QA-001: static import (no dynamic import needed)

interface AnalyticsSummary {
  total_projects: number;
  total_segments: number;
  total_words_translated: number;
  avg_translation_quality: string;
  cost_usd_total: number;
  most_used_provider: string;
  projects_per_day: Array<{ date: string; count: number }>;
  status_distribution: Record<string, number>;
  provider_distribution: Record<string, number>;
}

/**
 * AnalyticsDashboard — страница аналитики использования (R9-И4)
 *
 * Показывает:
 * - 4 stat-карточки: проекты / слова / оценка / стоимость
 * - Недельный CSS bar chart
 * - Таблица провайдеров
 * - Распределение статусов
 */
export function AnalyticsDashboard() {
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const summary = await fetchAnalytics();
        setData(summary);
      } catch {
        setError('Не удалось загрузить аналитику');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="analytics-page">
        <h1 className="analytics-title">📊 Аналитика</h1>
        <div className="analytics-loading">⏳ Загрузка данных...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="analytics-page">
        <h1 className="analytics-title">📊 Аналитика</h1>
        <div className="analytics-error">⚠️ {error || 'Нет данных'}</div>
      </div>
    );
  }

  const maxDay = Math.max(...data.projects_per_day.map((d) => d.count), 1);

  const statusLabels: Record<string, string> = {
    completed: '✅ Завершено',
    running: '🔄 В работе',
    failed: '❌ Ошибка',
    pending: '⏳ Ожидание',
    cancelled: '🚫 Отменено',
    draft: '📝 Черновик',
  };

  return (
    <div className="analytics-page">
      <h1 className="analytics-title">📊 Аналитика</h1>

      {/* Stat cards */}
      <div className="analytics-stats">
        <div className="analytics-stat-card">
          <div className="analytics-stat-icon">📁</div>
          <div className="analytics-stat-value">{data.total_projects}</div>
          <div className="analytics-stat-label">Всего проектов</div>
        </div>
        <div className="analytics-stat-card">
          <div className="analytics-stat-icon">📝</div>
          <div className="analytics-stat-value">{data.total_words_translated.toLocaleString()}</div>
          <div className="analytics-stat-label">Слов переведено</div>
        </div>
        <div className="analytics-stat-card">
          <div className="analytics-stat-icon">⭐</div>
          <div className="analytics-stat-value">{data.avg_translation_quality}</div>
          <div className="analytics-stat-label">Средняя оценка</div>
        </div>
        <div className="analytics-stat-card">
          <div className="analytics-stat-icon">💰</div>
          <div className="analytics-stat-value">${data.cost_usd_total.toFixed(4)}</div>
          <div className="analytics-stat-label">Стоимость</div>
        </div>
      </div>

      <div className="analytics-grid">
        {/* Weekly chart */}
        <div className="analytics-card">
          <h2 className="analytics-card-title">📅 Проекты за неделю</h2>
          <div className="analytics-chart" aria-label="Гистограмма проектов за 7 дней">
            {data.projects_per_day.map((d) => (
              <div key={d.date} className="analytics-bar-col">
                <div
                  className="analytics-bar"
                  style={{ height: `${Math.round((d.count / maxDay) * 100)}%` }}
                  title={`${d.date}: ${d.count} проект(ов)`}
                />
                <div className="analytics-bar-label">
                  {d.date.slice(5)} {/* MM-DD */}
                </div>
                {d.count > 0 && (
                  <div className="analytics-bar-count">{d.count}</div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Status distribution */}
        <div className="analytics-card">
          <h2 className="analytics-card-title">📊 Статусы проектов</h2>
          <div className="analytics-status-list">
            {Object.entries(data.status_distribution).length > 0 ? (
              Object.entries(data.status_distribution)
                .sort((a, b) => b[1] - a[1])
                .map(([status, count]) => (
                  <div key={status} className="analytics-status-row">
                    <span className="analytics-status-label">
                      {statusLabels[status] || status}
                    </span>
                    <span className="analytics-status-count">{count}</span>
                  </div>
                ))
            ) : (
              <div className="analytics-empty">Нет данных</div>
            )}
          </div>
        </div>

        {/* Provider distribution */}
        <div className="analytics-card">
          <h2 className="analytics-card-title">🤖 Провайдеры</h2>
          {Object.keys(data.provider_distribution).length > 0 ? (
            <table className="analytics-table">
              <thead>
                <tr>
                  <th>Провайдер</th>
                  <th>Использование</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.provider_distribution).map(([prov, pct]) => (
                  <tr key={prov}>
                    <td>{prov}</td>
                    <td>
                      <div className="analytics-pct-bar">
                        <div
                          className="analytics-pct-fill"
                          style={{ width: `${pct}%` }}
                        />
                        <span>{pct}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="analytics-empty">
              Нет данных о провайдерах
              <br />
              <small>Запустите хотя бы один перевод</small>
            </div>
          )}
        </div>

        {/* Most used */}
        <div className="analytics-card analytics-card--highlight">
          <h2 className="analytics-card-title">🏆 Топ провайдер</h2>
          <div className="analytics-top-provider">
            <div className="analytics-top-icon">🤖</div>
            <div className="analytics-top-name">{data.most_used_provider}</div>
            <div className="analytics-top-sub">Основной LLM провайдер</div>
          </div>
        </div>
      </div>
    </div>
  );
}
