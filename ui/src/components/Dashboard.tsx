import React, { useEffect, useState } from 'react';
import { getProjectStatus, runPipeline } from '../api/client';
import type { VideoProject } from '../types/schemas';
import { Play, Clock, FolderOpen } from 'lucide-react';
import './Dashboard.css';

interface DashboardProps {
    onOpenProject: (id: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onOpenProject }) => {
    const [project, setProject] = useState<VideoProject | null>(null);
    const [projectId, setProjectId] = useState('demo');

    const loadStatus = async () => {
        try {
            const data = await getProjectStatus(projectId);
            setProject(data);
        } catch (e) {
            console.error(e);
        }
    };

    const handleRun = async () => {
        try {
            await runPipeline(projectId, false, 'fake');
            loadStatus();
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        loadStatus();
        const interval = setInterval(loadStatus, 2000);
        return () => clearInterval(interval);
    }, [projectId]);

    return (
        <div className="dashboard">
            <header>
                <h2>Dashboard</h2>
                <div className="actions">
                    <input 
                        value={projectId} 
                        onChange={e => setProjectId(e.target.value)}
                        placeholder="Project ID"
                    />
                    <button onClick={loadStatus}><Clock size={16}/> Refresh</button>
                    <button onClick={handleRun} className="primary"><Play size={16}/> Run Pipeline</button>
                </div>
            </header>
            
            <main>
                {project ? (
                    <div className="project-card">
                        <div className="card-header">
                            <h3>{project.project_id}</h3>
                            <button onClick={() => onOpenProject(project.project_id)} className="open-btn">
                                <FolderOpen size={16}/> Open Workspace
                            </button>
                        </div>
                        <span className={`status badge ${project.status}`}>{project.status}</span>
                        <p>Work Dir: {project.work_dir}</p>
                        
                        <div className="stages">
                            <h4>Pipeline Stages</h4>
                            <ul>
                                {project.stage_runs?.map(run => (
                                    <li key={run.id} className={run.status}>
                                        <strong>{run.stage}</strong>: {run.status} 
                                        {run.error && <span className="error-text"> ({run.error})</span>}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                ) : (
                    <p>No project found. Make sure backend is running and project ID is correct.</p>
                )}
            </main>
        </div>
    );
};
