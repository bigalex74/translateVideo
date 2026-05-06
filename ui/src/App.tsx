import { useState, useEffect } from 'react';
import { Dashboard } from './components/Dashboard';
import { Workspace } from './components/Workspace';
import { NewProject } from './components/NewProject';
import { Settings as SettingsPage } from './components/Settings';
import { t } from './i18n';
import {
  applyLocale,
  applyTheme,
  getPersistedLargeText,
  getPersistedLocale,
  getPersistedTheme,
  persistLocale,
  type AppLocale,
} from './store/settings';
import { LayoutList, PlusCircle, Settings, Video, Sun, Moon, Menu } from 'lucide-react';
import './App.css';

function App() {
  const [currentView, setCurrentView] = useState<'dashboard' | 'new_project' | 'workspace' | 'settings'>('dashboard');
  const [activeProject, setActiveProject] = useState<string | null>(null);
  const [theme, setTheme] = useState(getPersistedTheme);
  const [locale, setLocale] = useState<AppLocale>(getPersistedLocale);
  const [sidebarOpen, setSidebarOpen] = useState(false); // мобильный drawer
  const largeText = getPersistedLargeText();

  // Применяем тему при монтировании и при изменении
  useEffect(() => {
    applyTheme(theme, largeText);
  }, [theme, largeText]);

  useEffect(() => {
    applyLocale(locale);
  }, [locale]);

  // Миграция: если пользователь ранее сохранил 'fake' как провайдер — переключаем на 'legacy'
  useEffect(() => {
    if (localStorage.getItem('tv_default_provider') === 'fake') {
      localStorage.setItem('tv_default_provider', 'legacy');
    }
  }, []);

  const navigate = (view: typeof currentView) => {
    setCurrentView(view);
    setSidebarOpen(false); // закрываем sidebar при навигации (мобильный)
  };

  const openWorkspace = (id: string) => {
    setActiveProject(id);
    setCurrentView('workspace');
    setSidebarOpen(false);
  };

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('tv_theme', next);
  };

  const handleLocaleChange = (next: AppLocale) => {
    persistLocale(next);
    setLocale(next);
  };

  return (
    <div className="app-container">
      {/* Мобильная кнопка-гамбургер — видна только ≤768px */}
      <button
        className="sidebar-toggle"
        onClick={() => setSidebarOpen(v => !v)}
        aria-label="Открыть меню"
        aria-expanded={sidebarOpen}
      >
        <Menu size={20} />
      </button>

      {/* Overlay для закрытия sidebar по клику вне */}
      <div
        className={`sidebar-overlay${sidebarOpen ? ' open' : ''}`}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      <aside className={`sidebar${sidebarOpen ? ' open' : ''}`}>
        <div className="sidebar-header">
          <Video className="text-accent" size={24} />
          <h1>{t('app.title', locale)}</h1>
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={theme === 'dark' ? t('app.themeLight', locale) : t('app.themeDark', locale)}
            aria-label={t('app.themeToggle', locale)}
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
        <nav>
          <ul>
            <li
              id="nav-my-translations"
              className={currentView === 'dashboard' ? 'active' : ''}
              onClick={() => navigate('dashboard')}
            >
              <LayoutList size={18} />
              {t('nav.dashboard', locale)}
            </li>
            <li
              id="nav-new-project"
              className={currentView === 'new_project' ? 'active' : ''}
              onClick={() => navigate('new_project')}
            >
              <PlusCircle size={18} />
              {t('nav.newProject', locale)}
            </li>
            <li
              id="nav-settings"
              className={currentView === 'settings' ? 'active' : ''}
              style={{ marginTop: 'auto' }}
              onClick={() => navigate('settings')}
            >
              <Settings size={18} />
              {t('nav.settings', locale)}
            </li>
          </ul>
        </nav>
      </aside>

      <div className="main-content">
        {currentView === 'dashboard'   && <Dashboard onOpenProject={openWorkspace} locale={locale} />}
        {currentView === 'new_project' && <NewProject onProjectCreated={openWorkspace} locale={locale} />}
        {currentView === 'settings'    && <SettingsPage locale={locale} onLocaleChange={handleLocaleChange} />}
        {currentView === 'workspace' && activeProject && (
          <Workspace projectId={activeProject} onBack={() => navigate('dashboard')} locale={locale} />
        )}
      </div>
    </div>
  );
}

export default App;
