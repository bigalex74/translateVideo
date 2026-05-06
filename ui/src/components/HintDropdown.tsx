import { useState } from 'react';

interface HintDropdownProps {
  projectId: string;
  segmentId: string;
  contextSegments?: Array<{
    source_text?: string;
    translated_text?: string;
    start?: number;
    end?: number;
  }>;
  onSelect: (text: string) => void;
}

/**
 * HintDropdown — выпадающий список AI-подсказок перевода (R9-И2)
 *
 * Показывает 3 альтернативных варианта перевода от LLM.
 * При клике на вариант — вставляет его в поле translated_text.
 */
export function HintDropdown({ projectId, segmentId, contextSegments = [], onSelect }: HintDropdownProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [hints, setHints] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleToggle = async () => {
    if (open) {
      setOpen(false);
      return;
    }

    if (hints.length > 0) {
      setOpen(true);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const { fetchTranslationHint } = await import('../api/client');
      const result = await fetchTranslationHint(projectId, segmentId, contextSegments);
      setHints(result.suggestions || []);
      setOpen(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg.includes('503') ? 'LLM не настроен' : 'Ошибка подсказки');
      setOpen(true);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (text: string) => {
    onSelect(text);
    setOpen(false);
    setHints([]); // сбрасываем для следующего запроса
  };

  return (
    <div className="hint-dropdown-wrapper" style={{ position: 'relative', display: 'inline-block' }}>
      <button
        className="btn-xs hint-trigger"
        onClick={handleToggle}
        title="AI-подсказки перевода"
        aria-label="Получить AI-подсказки перевода"
        disabled={loading}
        style={{ padding: '2px 6px', fontSize: '0.75rem' }}
      >
        {loading ? '⏳' : '💡'}
      </button>

      {open && (
        <div className="hint-dropdown" role="listbox" aria-label="Варианты перевода">
          {error ? (
            <div className="hint-item hint-item--error">{error}</div>
          ) : hints.length > 0 ? (
            hints.map((hint, i) => (
              <button
                key={i}
                className="hint-item"
                role="option"
                onClick={() => handleSelect(hint)}
                title={`Использовать: ${hint}`}
              >
                {hint}
              </button>
            ))
          ) : (
            <div className="hint-item hint-item--empty">Нет вариантов</div>
          )}
          <button
            className="hint-item hint-item--close"
            onClick={() => setOpen(false)}
            aria-label="Закрыть подсказки"
          >
            ✕ Закрыть
          </button>
        </div>
      )}
    </div>
  );
}
