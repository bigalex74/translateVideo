import React from 'react';
import { Search } from 'lucide-react';
import { STATUS_EMOJI, statusLabel } from '../../i18n';
import type { AppLocale } from '../../store/settings';

interface DashboardFiltersProps {
  locale: AppLocale;
  projectSearch: string;
  setProjectSearch: (v: string) => void;
  sortBy: 'created_at' | 'name' | 'status';
  sortDir: 'asc' | 'desc';
  handleSortBy: (v: 'created_at' | 'name' | 'status') => void;
  handleSortDir: (v: 'asc' | 'desc') => void;
  statusFilter: string;
  setStatusFilter: (v: string) => void;
}

export const DashboardFilters: React.FC<DashboardFiltersProps> = ({
  locale,
  projectSearch,
  setProjectSearch,
  sortBy,
  sortDir,
  handleSortBy,
  handleSortDir,
  statusFilter,
  setStatusFilter,
}) => {
  return (
    <>
      <div className="section-header-controls">
        <div className="project-list-search">
          <Search size={14} />
          <input
            id="project-list-search-input"
            className="text-input search-input-compact"
            value={projectSearch}
            onChange={e => setProjectSearch(e.target.value)}
            placeholder="Поиск…"
          />
        </div>
        <select
          id="project-sort-select"
          className="select-input select-compact"
          value={`${sortBy}_${sortDir}`}
          onChange={e => {
            const [by, dir] = e.target.value.split('_');
            handleSortBy(by as 'created_at' | 'name' | 'status');
            handleSortDir(dir as 'asc' | 'desc');
          }}
          title="Сортировка запоминается между сессиями (А9)"
        >
          <option value="created_at_desc">🕐 Новые</option>
          <option value="created_at_asc">🕐 Старые</option>
          <option value="name_asc">🔤 А→Я</option>
          <option value="name_desc">🔤 Я→А</option>
          <option value="status_asc">📊 Статус</option>
        </select>
      </div>
      {/* Фильтр по статусу */}
      <div className="status-filter-row" style={{ gridColumn: '1 / -1' }}>
        {['all', 'created', 'running', 'completed', 'failed', 'cancelled'].map(s => (
          <button
            key={s}
            className={`filter-pill ${statusFilter === s ? 'active' : ''}`}
            onClick={() => setStatusFilter(s)}
          >
            {s === 'all' ? (locale === 'ru' ? 'Все' : 'All') : `${STATUS_EMOJI[s as keyof typeof STATUS_EMOJI] ?? ''} ${statusLabel(s, locale)}`}
          </button>
        ))}
      </div>
    </>
  );
};
