import React, { useState, useEffect } from 'react';
import { getProjectStatus, listProjects, runPipeline } from '../api/client';
import type { VideoProject } from '../types/schemas';
import { Play, Clock, FolderOpen, AlertCircle, CheckCircle2, Loader2, ArrowRight, RefreshCw } from 'lucide-react';
import './Dashboard.css';

interface DashboardProps {
    onOpenProject: (id: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onOpenProject }) => {
    const [project, setProject] = useState<VideoProject | null>(null);
    const [projects, setProjects] = useState<VideoProject[]>([]);
    const [projectId, setProjectId] = useState('');
    const [searchInput, setSearchInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const loadStatus = async (id: string) => {
        if (!id) return;
        setLoading(true);
        setError('');
        try {
            const data = await getProjectStatus(id);
            setProject(data);
            await refreshProjects();
        } catch (e) {
            console.error(e);
            setProject(null);
            setError(e instanceof Error ? e.message : 'Не удалось загрузить проект');
        } finally {
            setLoading(false);
        }
    };

    const refreshProjects = async () => {
        const data = await listProjects();
        setProjects(data);
    };

    const handleRun = async (id: string, force = false) => {
        try {
            await runPipeline(id, force, 'fake');
            await loadStatus(id);
        } catch (e) {
            console.error(e);
            setError(e instanceof Error ? e.message : 'Не удалось запустить пайплайн');
        }
    };

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        setProjectId(searchInput);
        loadStatus(searchInput);
    };

    useEffect(() => {
        refreshProjects().catch(e => {
            console.error(e);
            setError(e instanceof Error ? e.message : 'Не удалось загрузить список проектов');
        });
    }, []);

    useEffect(() => {
        if (!projectId) return;
        const refreshOpenProject = async () => {
            try {
                const data = await getProjectStatus(projectId);
                setProject(data);
            } catch (e) {
                console.error(e);
            }
        };
        const interval = setInterval(refreshOpenProject, 3000);
        return () => clearInterval(interval);
    }, [projectId]);

    const getStatusIcon = (status: string) => {
        switch(status) {
            case 'completed': return <CheckCircle2 size={16} className="text-success" />;
            case 'failed': return <AlertCircle size={16} className="text-danger" />;
            case 'running': return <Loader2 size={16} className="text-warning animate-spin" />;
            default: return null;
        }
    };

    return (
        <div className="dashboard page-container fade-in">
            <header className="page-header">
                <h2>Дашборд</h2>
                <p className="subtitle">Управление и мониторинг запущенных проектов перевода.</p>
            </header>

            <form onSubmit={handleSearch} className="search-bar glass-panel">
                <input 
                    className="text-input"
                    value={searchInput} 
                    onChange={e => setSearchInput(e.target.value)}
                    placeholder="Введите ID проекта (например: demo) для загрузки..."
                />
                <button type="submit" className="btn-secondary" disabled={loading}>
                    {loading ? <Loader2 className="animate-spin" size={16} /> : <Clock size={16}/>}
                    Загрузить проект
                </button>
                <button type="button" className="btn-secondary" onClick={() => refreshProjects()} title="Обновить список проектов">
                    <RefreshCw size={16} />
                </button>
            </form>
            {error && <div className="error-banner">{error}</div>}
            
            <main className="dashboard-content">
                {project ? (
                    <div className="project-card glass-panel" data-testid="project-card">
                        <div className="card-header">
                            <div className="card-title">
                                <h3>{project.project_id}</h3>
                                <span className={`badge ${project.status}`}>
                                    {getStatusIcon(project.status)}
                                    {project.status}
                                </span>
                            </div>
                            <div className="card-actions">
                                {project.status !== 'running' && (
                                    <button onClick={() => handleRun(project.project_id)} className="btn-secondary">
                                        <Play size={16}/> Запустить пайплайн
                                    </button>
                                )}
                                {project.status !== 'running' && (
                                    <button onClick={() => handleRun(project.project_id, true)} className="btn-secondary">
                                        <RefreshCw size={16}/> Перезапустить
                                    </button>
                                )}
                                <button onClick={() => onOpenProject(project.project_id)} className="btn-primary">
                                    <FolderOpen size={16}/> Открыть Воркспейс
                                </button>
                            </div>
                        </div>

                        <div className="card-body">
                            <div className="meta-info">
                                <div className="meta-item">
                                    <span className="meta-label">Путь (Рабочая папка)</span>
                                    <span className="meta-value">{project.work_dir}</span>
                                </div>
                                <div className="meta-item">
                                    <span className="meta-label">Направление перевода</span>
                                    <span className="meta-value">
                                        {project.config?.source_language || 'Auto'} 
                                        <ArrowRight size={14} className="inline-icon" /> 
                                        {project.config?.target_language || 'RU'}
                                    </span>
                                </div>
                            </div>
                            
                            <div className="stages">
                                <h4>Прогресс обработки</h4>
                                <div className="stages-grid">
                                    {project.stage_runs?.map(run => (
                                        <div key={run.id} className={`stage-pill ${run.status}`}>
                                            <div className="stage-header">
                                                <strong>{run.stage.replace('_', ' ')}</strong>
                                                {getStatusIcon(run.status)}
                                            </div>
                                            {run.error && <div className="stage-error">{run.error}</div>}
                                        </div>
                                    ))}
                                    {(!project.stage_runs || project.stage_runs.length === 0) && (
                                        <p className="text-muted">Пайплайн еще не запускался.</p>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="empty-state glass-panel">
                        <FolderOpen size={48} className="text-muted mb-4" />
                        <h3>Проект не выбран</h3>
                        <p className="text-muted">Введите ID проекта в поиск выше или создайте новый проект в боковом меню.</p>
                    </div>
                )}

                <section className="projects-section glass-panel">
                    <div className="section-header">
                        <div>
                            <h3>Последние проекты</h3>
                            <p className="text-muted">Карточки берутся из рабочего каталога backend.</p>
                        </div>
                        <span className="text-sm text-muted">Всего: {projects.length}</span>
                    </div>
                    <div className="projects-grid" data-testid="project-list">
                        {projects.map(item => (
                            <article key={item.project_id} className="project-mini-card">
                                <div className="mini-card-title">
                                    <strong>{item.project_id}</strong>
                                    <span className={`badge ${item.status}`}>{item.status}</span>
                                </div>
                                <div className="mini-card-meta">
                                    <span>{item.config?.source_language || 'auto'}</span>
                                    <ArrowRight size={12} />
                                    <span>{item.config?.target_language || 'ru'}</span>
                                    <span>Сегментов: {Array.isArray(item.segments) ? item.segments.length : item.segments}</span>
                                </div>
                                <div className="mini-card-actions">
                                    <button className="btn-secondary" onClick={() => loadStatus(item.project_id)}>
                                        <Clock size={14}/> Статус
                                    </button>
                                    <button className="btn-primary" onClick={() => onOpenProject(item.project_id)}>
                                        <FolderOpen size={14}/> Открыть
                                    </button>
                                </div>
                            </article>
                        ))}
                        {projects.length === 0 && (
                            <p className="empty-text">Проекты пока не найдены.</p>
                        )}
                    </div>
                </section>
            </main>
        </div>
    );
};
