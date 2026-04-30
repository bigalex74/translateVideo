import React, { useState, useRef } from 'react';
import { createProject, uploadProject } from '../api/client';
import { Play, UploadCloud, Link as LinkIcon, FileVideo } from 'lucide-react';
import './NewProject.css';

interface NewProjectProps {
    onProjectCreated: (id: string) => void;
}

export const NewProject: React.FC<NewProjectProps> = ({ onProjectCreated }) => {
    const [inputType, setInputType] = useState<'upload' | 'url'>('upload');
    const [file, setFile] = useState<File | null>(null);
    const [videoUrl, setVideoUrl] = useState('');
    const [projectId, setProjectId] = useState('');
    const [sourceLang, setSourceLang] = useState('auto');
    const [targetLang, setTargetLang] = useState('ru');
    const [mode, setMode] = useState('voiceover');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const droppedFile = e.dataTransfer.files[0];
            setFile(droppedFile);
            if (!projectId) {
                // Automatically set project ID from filename without extension
                const name = droppedFile.name.replace(/\.[^/.]+$/, "");
                setProjectId(name);
            }
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const selectedFile = e.target.files[0];
            setFile(selectedFile);
            if (!projectId) {
                const name = selectedFile.name.replace(/\.[^/.]+$/, "");
                setProjectId(name);
            }
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (inputType === 'upload' && !file) {
            setError('Please select or drop a video file.');
            return;
        }
        if (inputType === 'url' && !videoUrl) {
            setError('Please enter a valid URL or local path.');
            return;
        }

        setLoading(true);
        setError('');
        
        try {
            const config = {
                source_language: sourceLang,
                target_language: targetLang,
                translation_mode: mode
            };

            let project;
            if (inputType === 'upload' && file) {
                project = await uploadProject(file, projectId || undefined, config);
            } else {
                project = await createProject(videoUrl, projectId || undefined, config);
            }
            
            onProjectCreated(project.project_id);
        } catch (err: any) {
            setError(err.message || 'Failed to create project');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="new-project page-container fade-in">
            <header className="page-header">
                <h2>Create New Translation</h2>
                <p className="subtitle">Upload a video or provide a link to start the AI translation pipeline.</p>
            </header>

            <form onSubmit={handleSubmit} className="glass-panel wizard-form">
                <div className="input-type-toggle">
                    <button 
                        type="button" 
                        className={inputType === 'upload' ? 'active' : ''} 
                        onClick={() => setInputType('upload')}
                    >
                        <UploadCloud size={16} /> Upload File
                    </button>
                    <button 
                        type="button" 
                        className={inputType === 'url' ? 'active' : ''} 
                        onClick={() => setInputType('url')}
                    >
                        <LinkIcon size={16} /> URL / Local Path
                    </button>
                </div>

                {inputType === 'upload' ? (
                    <div 
                        className={`drop-zone ${file ? 'has-file' : ''}`}
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <input 
                            type="file" 
                            accept="video/*,audio/*" 
                            ref={fileInputRef} 
                            onChange={handleFileSelect} 
                            style={{ display: 'none' }} 
                        />
                        {file ? (
                            <div className="file-info">
                                <FileVideo size={48} className="text-accent" />
                                <span className="file-name">{file.name}</span>
                                <span className="file-size">{(file.size / (1024 * 1024)).toFixed(2)} MB</span>
                                <span className="change-file">Click or drop to change</span>
                            </div>
                        ) : (
                            <div className="drop-prompt">
                                <UploadCloud size={48} className="text-muted" />
                                <span>Drag and drop your video file here</span>
                                <span className="text-muted text-sm">or click to browse</span>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="form-group">
                        <label>Input Video URL or Server Path</label>
                        <input 
                            className="text-input"
                            value={videoUrl}
                            onChange={e => setVideoUrl(e.target.value)}
                            placeholder="https://example.com/video.mp4 or /app/data/video.mp4"
                        />
                    </div>
                )}

                <div className="form-group">
                    <label>Project Name (ID)</label>
                    <input 
                        className="text-input"
                        value={projectId}
                        onChange={e => setProjectId(e.target.value)}
                        placeholder="Leave empty to auto-generate"
                    />
                    <small className="help-text">Used for folder naming and URL routes.</small>
                </div>

                <div className="form-row">
                    <div className="form-group">
                        <label>Source Language</label>
                        <select className="select-input" value={sourceLang} onChange={e => setSourceLang(e.target.value)}>
                            <option value="auto">Auto Detect</option>
                            <option value="en">English (en)</option>
                            <option value="ko">Korean (ko)</option>
                            <option value="ja">Japanese (ja)</option>
                            <option value="zh">Chinese (zh)</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Target Language</label>
                        <select className="select-input" value={targetLang} onChange={e => setTargetLang(e.target.value)}>
                            <option value="ru">Russian (ru)</option>
                            <option value="en">English (en)</option>
                            <option value="es">Spanish (es)</option>
                        </select>
                    </div>
                </div>

                <div className="form-group">
                    <label>Translation Mode</label>
                    <select className="select-input" value={mode} onChange={e => setMode(e.target.value)}>
                        <option value="voiceover">Voiceover (Original muted)</option>
                        <option value="dub">Dub (Replace original)</option>
                        <option value="subtitles">Subtitles Only</option>
                    </select>
                </div>

                {error && <div className="error-banner">{error}</div>}

                <div className="form-actions">
                    <button type="submit" disabled={loading || (inputType === 'upload' && !file)} className="btn-primary w-full">
                        <Play size={18} /> 
                        {loading ? 'Uploading & Creating...' : 'Initialize Project'}
                    </button>
                </div>
            </form>
        </div>
    );
};
