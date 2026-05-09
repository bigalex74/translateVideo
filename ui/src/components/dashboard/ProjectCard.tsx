import React, { useState, useRef } from 'react';
import { Clock, ArrowRight, Download, FolderOpen, Trash2, Pencil, Check, X } from 'lucide-react';
import type { VideoProject } from '../../types/schemas';
import { STATUS_EMOJI, statusLabel, t } from '../../i18n';
import type { AppLocale } from '../../store/settings';

interface ProjectCardProps {
  project: VideoProject;
  locale: AppLocale;
  onOpenProject: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, newName: string) => Promise<void>;
}

export const ProjectCard: React.FC<ProjectCardProps> = ({
  project,
  locale,
  onOpenProject,
  onDelete,
  onRename,
}) => {
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef<HTMLInputElement>(null);

  const displayName = (project as VideoProject & { display_name?: string }).display_name || project.project_id;
  const segmentsCount = Array.isArray(project.segments) ? project.segments.length : (project.segments || 0);

  const handleRenameStart = () => {
    setIsRenaming(true);
    setRenameValue(displayName);
    setTimeout(() => renameInputRef.current?.focus(), 50);
  };

  const handleRenameSubmit = async () => {
    if (!renameValue.trim()) {
      setIsRenaming(false);
      return;
    }
    try {
      await onRename(project.project_id, renameValue.trim());
    } finally {
      setIsRenaming(false);
    }
  };

  return (
    <article className="project-mini-card">
      <div className="mini-card-title">
        {/* О1: Переименование проекта */}
        {isRenaming ? (
          <div style={{ display: 'flex', gap: '4px', flex: 1, minWidth: 0 }}>
            <input
              ref={renameInputRef}
              className="select-input"
              style={{ flex: 1, padding: '2px 6px', fontSize: '0.85rem' }}
              value={renameValue}
              onChange={e => setRenameValue(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') handleRenameSubmit();
                if (e.key === 'Escape') setIsRenaming(false);
              }}
              placeholder="Название проекта…"
              maxLength={120}
            />
            <button onClick={handleRenameSubmit} title="Сохранить" style={{ padding: '2px 6px', cursor: 'pointer' }}><Check size={13} /></button>
            <button onClick={() => setIsRenaming(false)} title="Отмена" style={{ padding: '2px 6px', cursor: 'pointer' }}><X size={13} /></button>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flex: 1, minWidth: 0, overflow: 'hidden' }}>
            <strong style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
              title={project.project_id}>
              {displayName}
            </strong>
            <button
              onClick={handleRenameStart}
              title="Переименовать проект (О1)"
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', color: 'var(--text-muted)', flexShrink: 0 }}
            ><Pencil size={11} /></button>
          </div>
        )}
        <span
          className={`badge ${project.status}`}
          title={
            project.status === 'created'   ? '⏳ Проект создан — нажмите «▶ Запустить перевод» чтобы начать' :
            project.status === 'running'   ? '🔄 Перевод выполняется прямо сейчас — можно закрыть вкладку' :
            project.status === 'completed' ? '✅ Перевод готов — откройте редактор и скачайте результат' :
            project.status === 'failed'    ? '❌ Произошла ошибка — откройте проект и нажмите «Попробовать снова»' :
            project.status === 'cancelled' ? '🚫 Перевод был остановлен вручную — можно запустить снова' :
            project.status
          }
        >
          {STATUS_EMOJI[project.status as keyof typeof STATUS_EMOJI] ?? ''} {statusLabel(project.status, locale)}
        </span>
      </div>
      <div className="mini-card-meta">
        <span>{project.config?.source_language ?? 'auto'}</span>
        <ArrowRight size={12} />
        <span>{project.config?.target_language ?? 'ru'}</span>
        <Clock size={12} />
        <span>{segmentsCount} {t('dashboard.segmentShort', locale)}</span>
      </div>
      <div className="mini-card-actions">
        {/* R14-И3: CTA скачать для completed */}
        {project.status === 'completed' && (
          <a
            href={`/api/v1/projects/${project.project_id}/export/zip`}
            className="btn-card-download"
            download
            id={`btn-download-zip-${project.project_id}`}
            title="Скачать результат перевода (ZIP)"
            aria-label={`Скачать проект ${project.project_id}`}
          >
            <Download size={14} /> Скачать
          </a>
        )}
        <button
          className="btn-card-open"
          onClick={() => onOpenProject(project.project_id)}
          aria-label={`${t('dashboard.openEditor', locale)} ${project.project_id}`}
        >
          <FolderOpen size={14} /> {t('dashboard.editor', locale)}
        </button>
        {/* Удаление проекта */}
        {project.status !== 'running' && (
          <button
            className="btn-card-delete"
            onClick={() => onDelete(project.project_id)}
            title="Удалить проект"
            aria-label={`Удалить проект ${project.project_id}`}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </article>
  );
};
