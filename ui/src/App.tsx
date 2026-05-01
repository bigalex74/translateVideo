import { useState } from 'react';
import { Dashboard } from './components/Dashboard';
import { Workspace } from './components/Workspace';
import { NewProject } from './components/NewProject';
import { Settings as SettingsPage } from './components/Settings';
import { LayoutList, PlusCircle, Settings, Video } from 'lucide-react';
import './App.css';

function App() {
  const [currentView, setCurrentView] = useState<'dashboard' | 'new_project' | 'workspace' | 'settings'>('dashboard');
  const [activeProject, setActiveProject] = useState<string | null>(null);

  const openWorkspace = (id: string) => {
    setActiveProject(id);
    setCurrentView('workspace');
  };

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <Video className="text-accent" size={24} />
          <h1>ИИ Переводчик</h1>
        </div>
        <nav>
          <ul>
            <li
              id="nav-my-translations"
              className={currentView === 'dashboard' ? 'active' : ''}
              onClick={() => setCurrentView('dashboard')}
            >
              <LayoutList size={18} />
              Мои переводы
            </li>
            <li
              id="nav-new-project"
              className={currentView === 'new_project' ? 'active' : ''}
              onClick={() => setCurrentView('new_project')}
            >
              <PlusCircle size={18} />
              Новый перевод
            </li>
            <li
              id="nav-settings"
              className={currentView === 'settings' ? 'active' : ''}
              style={{ marginTop: 'auto' }}
              onClick={() => setCurrentView('settings')}
            >
              <Settings size={18} />
              Настройки
            </li>
          </ul>
        </nav>
      </aside>
      <div className="main-content">
        {currentView === 'dashboard'    && <Dashboard onOpenProject={openWorkspace} />}
        {currentView === 'new_project'  && <NewProject onProjectCreated={openWorkspace} />}
        {currentView === 'settings'     && <SettingsPage />}
        {currentView === 'workspace' && activeProject && (
          <Workspace projectId={activeProject} onBack={() => setCurrentView('dashboard')} />
        )}
      </div>
    </div>
  );
}

export default App;
