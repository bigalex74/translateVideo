import React, { useState } from 'react';

export const Settings: React.FC = () => {
    const [theme, setTheme] = useState('dark');
    
    return (
        <div className="settings page-container fade-in">
            <header className="page-header">
                <h2>Настройки</h2>
                <p className="subtitle">Управление конфигурацией интерфейса и системными параметрами.</p>
            </header>
            <div className="glass-panel p-6" style={{padding: '24px'}}>
                <h3 style={{marginBottom: '16px'}}>Внешний вид</h3>
                <div className="form-group mt-4">
                    <label>Тема оформления</label>
                    <select className="select-input w-full" value={theme} onChange={e => setTheme(e.target.value)}>
                        <option value="dark">Темная (По умолчанию)</option>
                        <option value="light">Светлая</option>
                        <option value="system">Системная</option>
                    </select>
                </div>

                <h3 style={{marginTop: '32px', marginBottom: '16px'}}>Интеграции</h3>
                <div className="form-group mt-4">
                    <label>Webhook URL (n8n)</label>
                    <input 
                        className="text-input" 
                        placeholder="https://n8n.bigalexn8n.ru/webhook/..."
                    />
                    <small className="help-text">Этот URL будет получать уведомления о завершении пайплайнов.</small>
                </div>
                
                <div className="form-actions" style={{marginTop: '32px'}}>
                    <button className="btn-primary">Сохранить настройки</button>
                </div>
            </div>
        </div>
    );
};
