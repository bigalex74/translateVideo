import { useState, useEffect } from 'react';
import { Dashboard } from './components/Dashboard';
import { Workspace } from './components/Workspace';
import { NewProject } from './components/NewProject';
import { Settings as SettingsPage } from './components/Settings';
import { OnboardingTour } from './components/OnboardingTour';
import { t } from './i18n';
import {
  applyLocale,
  applyTheme,
  applyFontLevel,
  getPersistedLargeText,
  getPersistedLocale,
  getPersistedTheme,
  getPersistedFontLevel,
  getPersistedCompactMode,
  persistLocale,
  type AppLocale,
} from './store/settings';
import { LayoutList, PlusCircle, Settings, Video, Sun, Moon } from 'lucide-react';
import './App.css';

function App() {
  const [currentView, setCurrentView] = useState<'dashboard' | 'new_project' | 'workspace' | 'settings'>('dashboard');
  const [activeProject, setActiveProject] = useState<string | null>(null);
  const [theme, setTheme] = useState(getPersistedTheme);
  const [locale, setLocale] = useState<AppLocale>(getPersistedLocale);
  const [sidebarOpen, setSidebarOpen] = useState(false);  // R1-R5: мобильный sidebar
  const largeText = getPersistedLargeText();
  const fontLevel = getPersistedFontLevel();
  const compactMode = getPersistedCompactMode();

  // Применяем тему при монтировании и при изменении
  useEffect(() => {
    applyTheme(theme, largeText);
    applyFontLevel(fontLevel, compactMode);
  }, [theme, largeText, fontLevel, compactMode]);

  useEffect(() => {
    applyLocale(locale);
  }, [locale]);

  // Миграция: если пользователь ранее сохранил 'fake' как провайдер — переключаем на 'legacy'
  useEffect(() => {
    if (localStorage.getItem('tv_default_provider') === 'fake') {
      localStorage.setItem('tv_default_provider', 'legacy');
    }
  }, []);

  const openWorkspace = (id: string) => {
    setActiveProject(id);
    setCurrentView('workspace');
    setSidebarOpen(false);  // закрываем sidebar при переходе
  };

  const navigateTo = (view: typeof currentView) => {
    setCurrentView(view);
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
    <>
    {/* R1-R5: Hamburger кнопка на мобиле */}
    <button
      className="sidebar-toggle"
      onClick={() => setSidebarOpen(true)}
      aria-label="Открыть меню"
      title="Открыть меню"
    >☰</button>

    {/* Backdrop overlay */}
    <div
      className={`sidebar-overlay${sidebarOpen ? ' open' : ''}`}
      onClick={() => setSidebarOpen(false)}
      aria-hidden="true"
    />

    <div className="app-container">
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
          {/* R1-R5: Кнопка закрыть sidebar на мобиле */}
          <button className="sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="Закрыть меню">✕</button>
        </div>
        <nav>
          <ul>
            <li
              id="nav-my-translations"
              className={currentView === 'dashboard' ? 'active' : ''}
              onClick={() => navigateTo('dashboard')}
            >
              <LayoutList size={18} />
              {t('nav.dashboard', locale)}
            </li>
            <li
              id="nav-new-project"
              className={currentView === 'new_project' ? 'active' : ''}
              onClick={() => navigateTo('new_project')}
            >
              <PlusCircle size={18} />
              {t('nav.newProject', locale)}
            </li>
            <li
              id="nav-settings"
              className={currentView === 'settings' ? 'active' : ''}
              style={{ marginTop: 'auto' }}
              onClick={() => navigateTo('settings')}
            >
              <Settings size={18} />
              {t('nav.settings', locale)}
            </li>
          </ul>
        </nav>
      </aside>
      <div className="main-content">
        {currentView === 'dashboard'    && <Dashboard onOpenProject={openWorkspace} locale={locale} />}
        {currentView === 'new_project'  && <NewProject onProjectCreated={openWorkspace} locale={locale} />}
        {currentView === 'settings'     && <SettingsPage locale={locale} onLocaleChange={handleLocaleChange} />}
        {currentView === 'workspace' && activeProject && (
          <Workspace projectId={activeProject} onBack={() => setCurrentView('dashboard')} locale={locale} />
        )}
      </div>
    </div>
    <OnboardingTour />
    </>
  );
}

export default App;
