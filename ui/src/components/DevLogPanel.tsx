import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  RefreshCw, Download, Copy, Search, ChevronDown, ChevronRight,
  Zap, AlertTriangle, GitBranch, MessageSquare, BarChart2, Loader2, X,
} from 'lucide-react';
import './DevLogPanel.css';

interface DevEvent {
  ts: string;
  event: string;
  stage?: string;
  elapsed_s?: number;
  provider?: string;
  model?: string;
  segment_id?: string;
  segment_index?: number;
  source_text?: string;
  prompt?: string;
  response?: string;
  original_text?: string;
  result_chars?: number;
  max_chars?: number;
  fits?: boolean;
  attempt?: number;
  error?: string;
  [key: string]: unknown;
}

interface DevLogData {
  project_id: string;
  dev_mode: boolean;
  size_bytes: number;
  event_count: number;
  events: DevEvent[];
}

interface AnalysisResult {
  mode: string;
  events_analyzed: number;
  model_used: string;
  analysis: string;
}

const EVENT_ICONS: Record<string, string> = {
  'translate.prompt':   '💬',
  'translate.fallback': '⚠️',
  'rewrite.attempt':    '✂️',
  'stage.start':        '▶️',
  'stage.end':          '✅',
  'stage.io':           '📤',
  'transcribe.result':  '🎙️',
  'tts.segment':        '🔊',
  'error':              '🔴',
  'devlog.start':       '📋',
};

const ANALYSIS_MODES = [
  { id: 'errors',       label: '🔴 Ошибки',        desc: 'Найти все сбои и ошибки провайдеров' },
  { id: 'quality',      label: '⭐ Качество',       desc: 'Оценить качество переводов' },
  { id: 'performance',  label: '⚡ Производит.',    desc: 'Узкие места и медленные этапы' },
  { id: 'improvements', label: '💡 Улучшения',      desc: 'Рекомендации по промтам и настройкам' },
  { id: 'anomalies',    label: '🔍 Аномалии',       desc: 'Необычные паттерны в логе' },
  { id: 'full',         label: '📈 Полный отчёт',   desc: 'Комплексный анализ' },
];

const STAGE_FILTER_OPTIONS = ['all', 'translate', 'timing_fit', 'transcribe', 'tts', 'render', 'extract_audio'];
const TYPE_FILTER_OPTIONS  = ['all', 'translate', 'rewrite', 'stage', 'transcribe', 'tts', 'error'];

function fmtBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(2)} MB`;
}

function getEventClass(event: string): string {
  if (event.startsWith('translate.')) return 'evt-translate';
  if (event.startsWith('rewrite.'))   return 'evt-rewrite';
  if (event.startsWith('stage.'))     return 'evt-stage';
  if (event.startsWith('tts.'))       return 'evt-tts';
  if (event === 'error')              return 'evt-error';
  if (event.startsWith('transcribe')) return 'evt-transcribe';
  return 'evt-default';
}

function EventRow({ evt }: { evt: DevEvent }) {
  const [expanded, setExpanded] = useState(false);

  const icon = EVENT_ICONS[evt.event] || '📄';
  const cls  = getEventClass(evt.event);

  // Build short summary
  let summary = '';
  if (evt.event === 'translate.prompt') {
    summary = `${evt.provider || ''} / ${evt.model || ''} — сегм. ${(evt.segment_index ?? 0) + 1} (${evt.elapsed_s?.toFixed(2)}с)`;
  } else if (evt.event === 'rewrite.attempt') {
    const fits = evt.fits ? '✅' : '❌';
    summary = `${evt.provider} / попытка ${evt.attempt} — ${evt.result_chars}/${evt.max_chars} симв. ${fits}`;
  } else if (evt.event === 'stage.end') {
    summary = `${evt.stage} — ${evt.elapsed_s?.toFixed(2)}с`;
  } else if (evt.event === 'transcribe.result') {
    summary = `${evt.segments_count} сегм. lang=${evt.language} conf=${Number(evt.avg_confidence ?? 0).toFixed(2)}`;
  } else if (evt.event === 'error') {
    summary = String(evt.error || '').slice(0, 100);
  } else {
    const extras = Object.entries(evt)
      .filter(([k]) => !['ts', 'event', 'stage', 'prompt', 'response', 'source_text'].includes(k))
      .slice(0, 4)
      .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
      .join(' ');
    summary = extras;
  }

  // Build expanded content
  const renderField = (label: string, value: string | undefined, mono = false) => {
    if (!value) return null;
    return (
      <div key={label} className="devlog-field">
        <span className="devlog-field-label">{label}</span>
        <pre className={`devlog-field-val${mono ? ' devlog-mono' : ''}`}>{value}</pre>
      </div>
    );
  };

  return (
    <div className={`devlog-evt ${cls} ${expanded ? 'expanded' : ''}`}>
      <div className="devlog-evt-header" onClick={() => setExpanded(v => !v)}>
        <span className="devlog-evt-icon">{icon}</span>
        <span className="devlog-evt-time">{evt.ts?.slice(11, 19)}</span>
        <span className="devlog-evt-name">{evt.event}</span>
        <span className="devlog-evt-summary">{summary}</span>
        <span className="devlog-evt-toggle">
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </div>

      {expanded && (
        <div className="devlog-evt-body">
          {/* Raw fields (not prompt/response/source) */}
          {Object.entries(evt)
            .filter(([k]) => !['prompt', 'response', 'source_text', 'original_text', 'ts', 'event'].includes(k))
            .map(([k, v]) => (
              <div key={k} className="devlog-field devlog-field--inline">
                <span className="devlog-field-label">{k}</span>
                <code className="devlog-field-code">{JSON.stringify(v)}</code>
              </div>
            ))
          }
          {evt.source_text    && renderField('Оригинал',      evt.source_text,   false)}
          {evt.original_text  && renderField('Перевод до',    evt.original_text, false)}
          {evt.prompt         && renderField('ПРОМТ',         evt.prompt,        true)}
          {evt.response       && renderField('ОТВЕТ МОДЕЛИ',  evt.response,      true)}
        </div>
      )}
    </div>
  );
}

interface Props {
  projectId: string;
  devMode: boolean;
}

export const DevLogPanel: React.FC<Props> = ({ projectId, devMode }) => {
  const [data, setData]           = useState<DevLogData | null>(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [stageFilter, setStage]   = useState('all');
  const [typeFilter, setType]     = useState('all');
  const [search, setSearch]       = useState('');
  const [showAnalysis, setShowAI] = useState(false);
  const [aiMode, setAiMode]       = useState('errors');
  const [analysis, setAnalysis]   = useState<AnalysisResult | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError]     = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const loadLog = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: '500' });
      if (stageFilter !== 'all') params.set('stage', stageFilter);
      if (typeFilter  !== 'all') params.set('event_type', typeFilter);
      const res = await fetch(`/api/v1/projects/${projectId}/devlog?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [projectId, stageFilter, typeFilter]);

  useEffect(() => { loadLog(); }, [loadLog]);

  const filteredEvents = (data?.events || []).filter(evt => {
    if (!search) return true;
    const hay = JSON.stringify(evt).toLowerCase();
    return hay.includes(search.toLowerCase());
  });

  const copyAll = () => {
    const text = filteredEvents.map(e => JSON.stringify(e)).join('\n');
    navigator.clipboard.writeText(text).catch(() => {});
  };

  const downloadLog = () => {
    if (!data) return;
    const text = data.events.map(e => JSON.stringify(e)).join('\n');
    const blob = new Blob([text], { type: 'application/jsonl' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `devlog-${projectId}.jsonl`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const runAnalysis = async () => {
    setAiLoading(true);
    setAiError(null);
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/analyze-log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: aiMode }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      setAnalysis(await res.json());
    } catch (e) {
      setAiError(e instanceof Error ? e.message : String(e));
    } finally {
      setAiLoading(false);
    }
  };

  if (!devMode && !data?.event_count) {
    return (
      <div className="devlog-disabled">
        <GitBranch size={28} className="devlog-disabled-icon" />
        <strong>Режим разработчика выключен</strong>
        <p>Включите «🔧 Режим разработчика» в расширенных настройках проекта и запустите перевод заново.</p>
      </div>
    );
  }

  return (
    <div className="devlog-panel">
      {/* Toolbar */}
      <div className="devlog-toolbar">
        <div className="devlog-toolbar-row">
          {/* Stage filter */}
          <select
            className="devlog-select"
            value={stageFilter}
            onChange={e => setStage(e.target.value)}
            title="Фильтр по этапу"
          >
            {STAGE_FILTER_OPTIONS.map(s => (
              <option key={s} value={s}>{s === 'all' ? '🎬 Все этапы' : s}</option>
            ))}
          </select>

          {/* Type filter */}
          <select
            className="devlog-select"
            value={typeFilter}
            onChange={e => setType(e.target.value)}
            title="Фильтр по типу"
          >
            {TYPE_FILTER_OPTIONS.map(t => (
              <option key={t} value={t}>{t === 'all' ? '📂 Все типы' : t}</option>
            ))}
          </select>

          {/* Actions */}
          <button className="devlog-icon-btn" onClick={loadLog}    title="Обновить">
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
          </button>
          <button className="devlog-icon-btn" onClick={copyAll}    title="Копировать">
            <Copy size={13} />
          </button>
          <button className="devlog-icon-btn" onClick={downloadLog} title="Скачать .jsonl">
            <Download size={13} />
          </button>
          <button
            className={`devlog-icon-btn devlog-ai-btn ${showAnalysis ? 'active' : ''}`}
            onClick={() => setShowAI(v => !v)}
            title="AI-анализ"
          >
            <Zap size={13} /> <span>ИИ</span>
          </button>
        </div>

        {/* Search */}
        <div className="devlog-search-row">
          <Search size={12} className="devlog-search-icon" />
          <input
            ref={searchRef}
            className="devlog-search"
            placeholder="Поиск по тексту…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button className="devlog-search-clear" onClick={() => setSearch('')}>
              <X size={11} />
            </button>
          )}
        </div>

        {/* Meta row */}
        <div className="devlog-meta-row">
          {data && (
            <>
              <span className="devlog-meta-item">
                <MessageSquare size={10} />
                {filteredEvents.length} / {data.event_count} событий
              </span>
              <span className="devlog-meta-item">
                <BarChart2 size={10} />
                {fmtBytes(data.size_bytes)}
              </span>
              {!devMode && (
                <span className="devlog-meta-item devlog-meta-warn">
                  ⚠️ dev_mode выключен
                </span>
              )}
            </>
          )}
        </div>
      </div>

      {/* AI Analysis Panel */}
      {showAnalysis && (
        <div className="devlog-ai-panel">
          <div className="devlog-ai-header">
            <Zap size={13} />
            <strong>AI-анализ лога</strong>
          </div>
          <div className="devlog-ai-modes">
            {ANALYSIS_MODES.map(m => (
              <button
                key={m.id}
                className={`devlog-ai-mode-btn ${aiMode === m.id ? 'active' : ''}`}
                onClick={() => setAiMode(m.id)}
                title={m.desc}
              >
                {m.label}
              </button>
            ))}
          </div>
          <button
            className="devlog-ai-run-btn"
            onClick={runAnalysis}
            disabled={aiLoading}
          >
            {aiLoading
              ? <><Loader2 size={13} className="spin" /> Анализирую…</>
              : <><Zap size={13} /> Запустить анализ</>
            }
          </button>
          {aiError && (
            <div className="devlog-ai-error">
              <AlertTriangle size={12} /> {aiError}
            </div>
          )}
          {analysis && !aiLoading && (
            <div className="devlog-ai-result">
              <div className="devlog-ai-result-meta">
                Модель: <code>{analysis.model_used}</code> | 
                Событий: {analysis.events_analyzed} |
                Режим: {analysis.mode}
              </div>
              <div className="devlog-ai-result-text">
                {analysis.analysis.split('\n').map((line, i) => {
                  if (line.startsWith('##')) return <h4 key={i}>{line.replace(/^#+\s*/, '')}</h4>;
                  if (line.startsWith('#'))  return <h3 key={i}>{line.replace(/^#+\s*/, '')}</h3>;
                  if (line.startsWith('- ') || line.startsWith('• '))
                    return <li key={i}>{line.replace(/^[-•]\s*/, '')}</li>;
                  if (line.trim() === '') return <br key={i} />;
                  return <p key={i}>{line}</p>;
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="devlog-error">
          <AlertTriangle size={13} /> {error}
        </div>
      )}

      {/* Events list */}
      <div className="devlog-events">
        {filteredEvents.length === 0 ? (
          <div className="devlog-empty">
            {loading ? 'Загрузка…' : search ? 'Ничего не найдено' : 'Лог пуст. Запустите перевод с включённым dev_mode.'}
          </div>
        ) : (
          filteredEvents.map((evt, i) => <EventRow key={i} evt={evt} />)
        )}
      </div>
    </div>
  );
};
