import React, { useState, useEffect } from 'react';
import { getProjectStatus } from '../api/client';
import type { VideoProject, Segment } from '../types/schemas';
import { ArrowLeft, Settings, Save, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
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

    if (!project) return (
        <div className="workspace-loading">
            <Loader2 className="animate-spin text-accent" size={32} />
            <p>Loading Workspace...</p>
        </div>
    );

    const segments = Array.isArray(project.segments) ? project.segments : [];

    const handleTextChange = (segId: string, newText: string) => {
        setProject(prev => {
            if (!prev) return prev;
            const newSegments = (prev.segments as Segment[]).map(s => 
                s.id === segId ? { ...s, translated_text: newText } : s
            );
            return { ...prev, segments: newSegments };
        });
    };

    const getVideoUrl = () => {
        const base = `/runs/${projectId}`;
        if (activeTab === 'translated' && project.artifacts['output_video']) {
            return `${base}/${project.artifacts['output_video']}`;
        }
        return `${base}/input.mp4`; 
    };

    const getStatusIcon = (status: string) => {
        switch(status) {
            case 'completed': return <CheckCircle2 size={16} className="text-success" />;
            case 'failed': return <AlertCircle size={16} className="text-danger" />;
            case 'running': return <Loader2 size={16} className="text-warning animate-spin" />;
            default: return <div className="timeline-marker"></div>;
        }
    };

    return (
        <div className="workspace fade-in">
            <header className="workspace-header">
                <div className="header-left">
                    <button onClick={onBack} className="btn-icon">
                        <ArrowLeft size={20} />
                    </button>
                    <h2>{projectId}</h2>
                    <span className={`badge ${project.status}`}>{project.status}</span>
                </div>
                <div className="header-right">
                    <button className="btn-secondary"><Settings size={16} /> Config</button>
                    <button className="btn-primary"><Save size={16} /> Save Edits</button>
                </div>
            </header>

            <div className="workspace-grid">
                {/* Left: Player */}
                <div className="panel video-panel glass-panel">
                    <div className="panel-tabs">
                        <button className={activeTab === 'source' ? 'active' : ''} onClick={() => setActiveTab('source')}>Original Video</button>
                        <button className={activeTab === 'translated' ? 'active' : ''} onClick={() => setActiveTab('translated')}>AI Voiceover</button>
                        <button className={activeTab === 'subtitles' ? 'active' : ''} onClick={() => setActiveTab('subtitles')}>Subtitles Only</button>
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

                {/* Center: Editor */}
                <div className="panel segments-panel glass-panel">
                    <div className="panel-header">
                        <h3>Interactive Transcript</h3>
                        <span className="text-sm text-muted">{segments.length} segments</span>
                    </div>
                    <div className="segments-list">
                        {segments.map((seg) => (
                            <div key={seg.id} className={`segment-item ${seg.status}`}>
                                <div className="seg-header">
                                    <span className="seg-timing">{seg.start.toFixed(1)}s — {seg.end.toFixed(1)}s</span>
                                    <span className="seg-status">{seg.status}</span>
                                </div>
                                <div className="seg-source">{seg.source_text}</div>
                                <textarea 
                                    className="seg-translated text-input"
                                    value={seg.translated_text}
                                    onChange={(e) => handleTextChange(seg.id, e.target.value)}
                                    placeholder="Translation..."
                                />
                            </div>
                        ))}
                        {segments.length === 0 && (
                            <div className="empty-text">
                                <p>No transcript available yet.</p>
                                <small>Wait for the transcription stage to finish.</small>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right: Progress */}
                <div className="panel progress-panel glass-panel">
                    <div className="panel-header">
                        <h3>Pipeline Status</h3>
                    </div>
                    <div className="timeline-container">
                        <ul className="timeline">
                            {project.stage_runs?.map(run => (
                                <li key={run.id} className={`timeline-item ${run.status}`}>
                                    <div className="timeline-icon">
                                        {getStatusIcon(run.status)}
                                    </div>
                                    <div className="timeline-content">
                                        <strong>{run.stage.replace('_', ' ')}</strong>
                                        <span className="status-text">{run.status}</span>
                                        {run.error && <div className="error-text text-sm">{run.error}</div>}
                                    </div>
                                </li>
                            ))}
                            {(!project.stage_runs || project.stage_runs.length === 0) && (
                                <p className="empty-text">Pipeline has not started.</p>
                            )}
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    );
};
