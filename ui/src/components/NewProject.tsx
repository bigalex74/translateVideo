import React, { useState, useRef } from 'react';
import { createProject, uploadProject } from '../api/client';
import { Play, UploadCloud, Link as LinkIcon, FileVideo, Loader2 } from 'lucide-react';
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
            setError('Пожалуйста, выберите или перетащите видеофайл.');
            return;
        }
        if (inputType === 'url' && !videoUrl) {
            setError('Пожалуйста, введите корректный URL или локальный путь к файлу.');
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
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Ошибка при создании проекта');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="new-project page-container fade-in">
            <header className="page-header">
                <h2>Создание нового перевода</h2>
                <p className="subtitle">Загрузите видео или укажите ссылку для старта конвейера ИИ-перевода.</p>
            </header>

            <form onSubmit={handleSubmit} className="glass-panel wizard-form">
                <div className="input-type-toggle">
                    <button 
                        type="button" 
                        className={inputType === 'upload' ? 'active' : ''} 
                        onClick={() => setInputType('upload')}
                    >
                        <UploadCloud size={16} /> Загрузить файл
                    </button>
                    <button 
                        type="button" 
                        className={inputType === 'url' ? 'active' : ''} 
                        onClick={() => setInputType('url')}
                    >
                        <LinkIcon size={16} /> URL / Путь на сервере
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
                                <span className="file-size">{(file.size / (1024 * 1024)).toFixed(2)} МБ</span>
                                <span className="change-file">Кликните или перетащите другой файл для замены</span>
                            </div>
                        ) : (
                            <div className="drop-prompt">
                                <UploadCloud size={48} className="text-muted" />
                                <span>Перетащите ваше видео сюда</span>
                                <span className="text-muted text-sm">или кликните для выбора файла</span>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="form-group">
                        <label>URL видео или путь на сервере</label>
                        <input 
                            className="text-input"
                            value={videoUrl}
                            onChange={e => setVideoUrl(e.target.value)}
                            placeholder="https://example.com/video.mp4 или /app/data/video.mp4"
                        />
                    </div>
                )}

                <div className="form-group">
                    <label>Имя проекта (ID)</label>
                    <input 
                        className="text-input"
                        value={projectId}
                        onChange={e => setProjectId(e.target.value)}
                        placeholder="Оставьте пустым для автогенерации из имени файла"
                    />
                    <small className="help-text">Используется для названия папки проекта и формирования URL.</small>
                </div>

                <div className="form-row">
                    <div className="form-group">
                        <label>Исходный язык</label>
                        <select className="select-input" value={sourceLang} onChange={e => setSourceLang(e.target.value)}>
                            <option value="auto">Автоопределение</option>
                            <option value="en">Английский (en)</option>
                            <option value="ko">Корейский (ko)</option>
                            <option value="ja">Японский (ja)</option>
                            <option value="zh">Китайский (zh)</option>
                            <option value="ru">Русский (ru)</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Язык перевода</label>
                        <select className="select-input" value={targetLang} onChange={e => setTargetLang(e.target.value)}>
                            <option value="ru">Русский (ru)</option>
                            <option value="en">Английский (en)</option>
                            <option value="es">Испанский (es)</option>
                        </select>
                    </div>
                </div>

                <div className="form-group">
                    <label>Режим перевода</label>
                    <select className="select-input" value={mode} onChange={e => setMode(e.target.value)}>
                        <option value="voiceover">Закадровый голос (оригинал приглушен)</option>
                        <option value="dub">Дубляж (полная замена оригинала)</option>
                        <option value="subtitles">Только субтитры</option>
                    </select>
                </div>

                {error && <div className="error-banner">{error}</div>}

                <div className="form-actions">
                    <button type="submit" disabled={loading || (inputType === 'upload' && !file)} className="btn-primary w-full" style={{justifyContent: 'center'}}>
                        {loading ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
                        {loading ? ' Загрузка и инициализация...' : ' Создать проект'}
                    </button>
                </div>
            </form>
        </div>
    );
};
