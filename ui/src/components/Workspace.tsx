import React, { useState, useEffect } from 'react';
import { getProjectStatus } from '../api/client';
import type { VideoProject, Segment } from '../types/schemas';
import './Workspace.css';

interface WorkspaceProps {
    projectId: string;
    onBack: () => void;
}

export const Workspace: React.FC<WorkspaceProps> = ({ projectId, onBack }) => {
    const [project, setProject] = useState<VideoProject | null>(null);
    const [activeTab, setActiveTab] = useState<'source' | 'translated' | 'subtitles'>('source');

    const loadProject = async () => {
        try {
            const data = await getProjectStatus(projectId);
            setProject(data);
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        loadProject();
        const interval = setInterval(loadProject, 5000);
        return () => clearInterval(interval);
    }, [projectId]);

    if (!project) return <div className="workspace-loading">Loading project {projectId}...</div>;

    const segments = Array.isArray(project.segments) ? project.segments : [];

    const handleTextChange = (segId: string, newText: string) => {
        // Здесь мы будем обновлять локальный стейт, 
        // в будущем можно добавить API вызов для сохранения
        setProject(prev => {
            if (!prev) return prev;
            const newSegments = (prev.segments as Segment[]).map(s => 
                s.id === segId ? { ...s, translated_text: newText } : s
            );
            return { ...prev, segments: newSegments };
        });
    };

    // Определяем URL видео в зависимости от вкладки
    const getVideoUrl = () => {
        // Если проект на сервере, путь к артефактам /runs/{project_id}/...
        const base = `/runs/${projectId}`;
        if (activeTab === 'translated' && project.artifacts['output_video']) {
            return `${base}/${project.artifacts['output_video']}`;
        }
        return `${base}/input.mp4`; // При условии, что мы скопировали input туда, или используем исходник
    };

    return (
        <div className="workspace">
            <header className="workspace-header">
                <button onClick={onBack} className="back-btn">← Back to Dashboard</button>
                <h2>Workspace: {projectId}</h2>
                <span className={`status badge ${project.status}`}>{project.status}</span>
            </header>

            <div className="workspace-grid">
                {/* Левая панель: Видеоплеер */}
                <div className="panel video-panel">
                    <div className="video-tabs">
                        <button className={activeTab === 'source' ? 'active' : ''} onClick={() => setActiveTab('source')}>Original</button>
                        <button className={activeTab === 'translated' ? 'active' : ''} onClick={() => setActiveTab('translated')}>Voiceover</button>
                        <button className={activeTab === 'subtitles' ? 'active' : ''} onClick={() => setActiveTab('subtitles')}>Subtitles</button>
                    </div>
                    <div className="video-container">
                        <video controls src={getVideoUrl()} key={getVideoUrl()}>
                            {activeTab === 'subtitles' && project.artifacts['subtitles'] && (
                                <track 
                                    kind="subtitles" 
                                    src={`/runs/${projectId}/${project.artifacts['subtitles']}`} 
                                    srcLang="ru" 
                                    label="Russian" 
                                    default 
                                />
                            )}
                            Your browser does not support the video tag.
                        </video>
                    </div>
                </div>

                {/* Центральная панель: Интерактивные субтитры */}
                <div className="panel segments-panel">
                    <h3>Segments</h3>
                    <div className="segments-list">
                        {segments.map((seg) => (
                            <div key={seg.id} className={`segment-item ${seg.status}`}>
                                <div className="seg-timing">
                                    {seg.start.toFixed(1)}s - {seg.end.toFixed(1)}s
                                </div>
                                <div className="seg-source">{seg.source_text}</div>
                                <textarea 
                                    className="seg-translated"
                                    value={seg.translated_text}
                                    onChange={(e) => handleTextChange(seg.id, e.target.value)}
                                    placeholder="Translation..."
                                />
                            </div>
                        ))}
                        {segments.length === 0 && <p className="empty-text">No segments yet. Wait for the transcription stage to complete.</p>}
                    </div>
                </div>

                {/* Правая панель: Прогресс */}
                <div className="panel progress-panel">
                    <h3>Pipeline Progress</h3>
                    <ul className="timeline">
                        {project.stage_runs?.map(run => (
                            <li key={run.id} className={`timeline-item ${run.status}`}>
                                <div className="timeline-marker"></div>
                                <div className="timeline-content">
                                    <strong>{run.stage}</strong>
                                    <span className="status-text">{run.status}</span>
                                    {run.error && <div className="error-text">{run.error}</div>}
                                </div>
                            </li>
                        ))}
                        {(!project.stage_runs || project.stage_runs.length === 0) && (
                            <p className="empty-text">No pipeline runs recorded.</p>
                        )}
                    </ul>
                </div>
            </div>
        </div>
    );
};
