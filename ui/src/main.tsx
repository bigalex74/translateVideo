import { StrictMode, Component, type ReactNode, type ErrorInfo } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// ── Вспомогательная функция: скрыть PWA splash ──────────────────────────
// Функция определена в index.html как window.__hideSplash
// Здесь обёртка с type-safe проверкой
function hideSplash() {
  if (typeof (window as unknown as Record<string, unknown>).__hideSplash === 'function') {
    (window as unknown as Record<string, () => void>).__hideSplash();
  } else {
    // Fallback если index.html не добавил функцию (например в тестах)
    const splash = document.getElementById('pwa-splash');
    if (splash) splash.classList.add('hidden');
  }
}

// ── ErrorBoundary: перехватывает ошибки рендера и скрывает splash ───────
interface EBState { hasError: boolean; error: Error | null }

class AppErrorBoundary extends Component<{ children: ReactNode }, EBState> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): EBState {
    return { hasError: true, error };
  }

  componentDidMount() {
    // React смонтировался успешно — скрываем splash немедленно
    hideSplash();
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[App] Критическая ошибка рендера:', error, info);
    // Скрываем splash даже при ошибке — показываем fallback UI
    hideSplash();
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          background: '#0f0f1a',
          color: '#e8e8f0',
          fontFamily: 'Inter, sans-serif',
          gap: '16px',
          padding: '24px',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '48px' }}>⚠️</div>
          <h1 style={{ fontSize: '20px', margin: 0, color: '#ef4444' }}>
            Произошла ошибка приложения
          </h1>
          <p style={{ color: '#9898b5', margin: 0, maxWidth: '400px' }}>
            {this.state.error?.message || 'Неизвестная ошибка'}
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: '#6366f1',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '10px 24px',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            🔄 Перезагрузить страницу
          </button>
          <details style={{ color: '#5a5a7a', fontSize: '12px', maxWidth: '500px' }}>
            <summary style={{ cursor: 'pointer' }}>Детали ошибки</summary>
            <pre style={{ textAlign: 'left', marginTop: '8px', overflow: 'auto' }}>
              {this.state.error?.stack}
            </pre>
          </details>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Монтирование приложения ──────────────────────────────────────────────
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppErrorBoundary>
      <App />
    </AppErrorBoundary>
  </StrictMode>,
)
