import React, { useEffect, useState } from 'react';
import { getProjectStatus, runPipeline } from '../api/client';
import type { VideoProject } from '../types/schemas';
import { Play, Clock, FolderOpen, AlertCircle, CheckCircle2, Loader2, ArrowRight } from 'lucide-react';
import './Dashboard.css';

interface DashboardProps {
    onOpenProject: (id: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onOpenProject }) => {
    const [project, setProject] = useState<VideoProject | null>(null);
    const [projectId, setProjectId] = useState('');
    const [searchInput, setSearchInput] = useState('');

    const loadStatus = async (id: string) => {
        if (!id) return;
        try {
            const data = await getProjectStatus(id);
            setProject(data);
        } catch (e) {
            console.error(e);
            setProject(null);
        }
    };

    const handleRun = async () => {
        if (!project) return;
        try {
            await runPipeline(project.project_id, false, 'fake');
            loadStatus(project.project_id);
        } catch (e) {
            console.error(e);
        }
    };

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        setProjectId(searchInput);
        loadStatus(searchInput);
    };

    useEffect(() => {
        if (!projectId) return;
        loadStatus(projectId);
        const interval = setInterval(() => loadStatus(projectId), 2000);
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
                <h2>Dashboard</h2>
                <p className="subtitle">Monitor and manage your translation projects.</p>
            </header>

            <form onSubmit={handleSearch} className="search-bar glass-panel">
                <input 
                    className="text-input"
                    value={searchInput} 
                    onChange={e => setSearchInput(e.target.value)}
                    placeholder="Enter Project ID to load..."
                />
                <button type="submit" className="btn-secondary"><Clock size={16}/> Load Project</button>
            </form>
            
            <main className="dashboard-content">
                {project ? (
                    <div className="project-card glass-panel">
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
                                    <button onClick={handleRun} className="btn-secondary">
                                        <Play size={16}/> Run
                                    </button>
                                )}
                                <button onClick={() => onOpenProject(project.project_id)} className="btn-primary">
                                    <FolderOpen size={16}/> Open Workspace
                                </button>
                            </div>
                        </div>

                        <div className="card-body">
                            <div className="meta-info">
                                <div className="meta-item">
                                    <span className="meta-label">Path</span>
                                    <span className="meta-value">{project.work_dir}</span>
                                </div>
                                <div className="meta-item">
                                    <span className="meta-label">Translation</span>
                                    <span className="meta-value">
                                        {project.config?.source_language || 'Auto'} 
                                        <ArrowRight size={14} className="inline-icon" /> 
                                        {project.config?.target_language || 'RU'}
                                    </span>
                                </div>
                            </div>
                            
                            <div className="stages">
                                <h4>Pipeline Progress</h4>
                                <div className="stages-grid">
                                    {project.stage_runs?.map(run => (
                                        <div key={run.id} className={`stage-pill ${run.status}`}>
                                            <div className="stage-header">
                                                <strong>{run.stage}</strong>
                                                {getStatusIcon(run.status)}
                                            </div>
                                            {run.error && <div className="stage-error">{run.error}</div>}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="empty-state glass-panel">
                        <FolderOpen size={48} className="text-muted mb-4" />
                        <h3>No project selected</h3>
                        <p className="text-muted">Enter a project ID above to view its status, or create a new one from the sidebar.</p>
                    </div>
                )}
            </main>
        </div>
    );
};
