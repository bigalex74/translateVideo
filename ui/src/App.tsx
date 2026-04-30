import { Dashboard } from './components/Dashboard';
import './App.css';

function App() {
  return (
    <div className="app-container">
      <aside className="sidebar">
        <h1>Video Translator</h1>
        <nav>
          <ul>
            <li className="active">Dashboard</li>
            <li>New Project</li>
            <li>Settings</li>
          </ul>
        </nav>
      </aside>
      <div className="main-content">
        <Dashboard />
      </div>
    </div>
  );
}

export default App;
