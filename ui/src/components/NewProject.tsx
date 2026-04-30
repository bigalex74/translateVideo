import React, { useState } from 'react';
import { createProject } from '../api/client';
import { Play } from 'lucide-react';
import './NewProject.css';

interface NewProjectProps {
    onProjectCreated: (id: string) => void;
}

export const NewProject: React.FC<NewProjectProps> = ({ onProjectCreated }) => {
    const [videoUrl, setVideoUrl] = useState('');
    const [projectId, setProjectId] = useState('');
    const [sourceLang, setSourceLang] = useState('auto');
    const [targetLang, setTargetLang] = useState('ru');
    const [mode, setMode] = useState('voiceover');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        
        try {
            const project = await createProject(
                videoUrl, 
                projectId || undefined, 
                {
                    source_language: sourceLang,
                    target_language: targetLang,
                    translation_mode: mode
                }
            );
            onProjectCreated(project.project_id);
        } catch (err: any) {
            setError(err.message || 'Failed to create project');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="new-project">
            <h2>Create New Project</h2>
            <form onSubmit={handleSubmit} className="wizard-form">
                <div className="form-group">
                    <label>Input Video (Local Path or URL)</label>
                    <input 
                        required
                        value={videoUrl}
                        onChange={e => setVideoUrl(e.target.value)}
                        placeholder="/path/to/video.mp4 or https://..."
                    />
                </div>

                <div className="form-group">
                    <label>Project ID (Optional)</label>
                    <input 
                        value={projectId}
                        onChange={e => setProjectId(e.target.value)}
                        placeholder="Leave empty to auto-generate"
                    />
                </div>

                <div className="form-row">
                    <div className="form-group">
                        <label>Source Language</label>
                        <select value={sourceLang} onChange={e => setSourceLang(e.target.value)}>
                            <option value="auto">Auto Detect</option>
                            <option value="en">English (en)</option>
                            <option value="ko">Korean (ko)</option>
                            <option value="ja">Japanese (ja)</option>
                            <option value="zh">Chinese (zh)</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Target Language</label>
                        <select value={targetLang} onChange={e => setTargetLang(e.target.value)}>
                            <option value="ru">Russian (ru)</option>
                            <option value="en">English (en)</option>
                            <option value="es">Spanish (es)</option>
                        </select>
                    </div>
                </div>

                <div className="form-group">
                    <label>Translation Mode</label>
                    <select value={mode} onChange={e => setMode(e.target.value)}>
                        <option value="voiceover">Voiceover (Original muted)</option>
                        <option value="dub">Dub (Replace original)</option>
                        <option value="subtitles">Subtitles Only</option>
                    </select>
                </div>

                {error && <div className="error-message">{error}</div>}

                <button type="submit" disabled={loading} className="primary submit-btn">
                    <Play size={16} /> 
                    {loading ? 'Creating...' : 'Create & Proceed'}
                </button>
            </form>
        </div>
    );
};
