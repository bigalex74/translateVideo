import { useState } from 'react';
import { Dashboard } from './components/Dashboard';
import { Workspace } from './components/Workspace';
import { NewProject } from './components/NewProject';
import './App.css';

function App() {
  const [currentView, setCurrentView] = useState<'dashboard' | 'new_project' | 'workspace'>('dashboard');
  const [activeProject, setActiveProject] = useState<string | null>(null);

  const openWorkspace = (id: string) => {
    setActiveProject(id);
    setCurrentView('workspace');
  };

  return (
    <div className="app-container">
      <aside className="sidebar">
        <h1>Video Translator</h1>
        <nav>
          <ul>
            <li className={currentView === 'dashboard' ? "active" : ""} onClick={() => setCurrentView('dashboard')}>
              Dashboard
            </li>
            <li className={currentView === 'new_project' ? "active" : ""} onClick={() => setCurrentView('new_project')}>
              New Project
            </li>
            <li>Settings</li>
          </ul>
        </nav>
      </aside>
      <div className="main-content">
        {currentView === 'dashboard' && <Dashboard onOpenProject={openWorkspace} />}
        {currentView === 'new_project' && <NewProject onProjectCreated={openWorkspace} />}
        {currentView === 'workspace' && activeProject && (
          <Workspace projectId={activeProject} onBack={() => setCurrentView('dashboard')} />
        )}
      </div>
    </div>
  );
}

export default App;
