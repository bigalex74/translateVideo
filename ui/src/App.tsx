import { useState } from 'react';
import { Dashboard } from './components/Dashboard';
import { Workspace } from './components/Workspace';
import { NewProject } from './components/NewProject';
import { LayoutDashboard, PlusCircle, Settings, Video } from 'lucide-react';
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
        <div className="sidebar-header">
            <Video className="text-accent" size={24} />
            <h1>AI Translator</h1>
        </div>
        <nav>
          <ul>
            <li className={currentView === 'dashboard' ? "active" : ""} onClick={() => setCurrentView('dashboard')}>
              <LayoutDashboard size={18} />
              Dashboard
            </li>
            <li className={currentView === 'new_project' ? "active" : ""} onClick={() => setCurrentView('new_project')}>
              <PlusCircle size={18} />
              New Translation
            </li>
            <li className="mt-auto opacity-50" style={{marginTop: 'auto', opacity: 0.5}}>
              <Settings size={18} />
              Settings
            </li>
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