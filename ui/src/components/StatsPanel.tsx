import React, { useEffect, useState, useCallback } from 'react';
import { RefreshCw, Clock, FileText, Star, Mic, AlertTriangle, ChevronDown, ChevronUp, DollarSign } from 'lucide-react';
import './StatsPanel.css';

interface StatsData {
  timing: {
    total_elapsed_s: number | null;
    stage_times: Record<string, number>;
    slowest_stage: string | null;
    translate_per_segment_avg_s: number | null;
  };
  segments: {
    count: number;
    source_words: number;
    target_words: number;
    source_chars: number;
    target_chars: number;
    compression_ratio: number | null;
    avg_duration_s: number | null;
    total_audio_duration_s: number | null;
    segments_rewritten: number;
    empty_translations: number;
  };
  quality: {
    qa_flags_distribution: Record<string, number>;
    segments_with_issues: number;
    avg_confidence: number | null;
    provider_usage: Record<string, number>;
    google_fallback_count: number;
    llm_translation_count: number;
  };
  tts: {
    segments_with_audio: number;
    total_duration_s: number | null;
    overflow_count: number;
    overflow_rate: number | null;
  };
  summary: {
    project_id: string;
    project_status: string;
    stages_done: number;
    stages_failed: number;
    failed_stages: string[];
    translation_quality: string;
    source_language: string;
    target_language: string;
    dev_mode: boolean;
  };
  billing: {
    dominant_translation_provider: string;
    rewrite_provider: string | null;
    estimated_input_tokens: number;
    estimated_output_tokens: number;
    estimated_cost_usd: number;
    estimated_cost_translate_usd: number;
    estimated_cost_rewrite_usd: number;
    price_per_1m_in_usd: number;
    price_per_1m_out_usd: number;
    note: string;
  } | null;
}

const STAGE_LABELS: Record<string, string> = {
  extract_audio: 'Аудио',
  transcribe: 'Распознавание',
  regroup: 'Группировка',
  translate: 'Перевод',
  timing_fit: 'Тайминг',
  tts: 'Озвучка',
  render: 'Рендер',
};

const STAGE_COLORS: Record<string, string> = {
  extract_audio: '#6366f1',
  transcribe: '#8b5cf6',
  regroup: '#a78bfa',
  translate: '#ec4899',
  timing_fit: '#f59e0b',
  tts: '#10b981',
  render: '#3b82f6',
};

const FLAG_LABELS: Record<string, string> = {
  translation_llm: 'LLM-перевод',
  translation_google_fallback: 'Google Fallback',
  translation_empty: 'Пустой перевод',
  translation_fallback_source: 'Копия оригинала',
  tts_overflow: 'Переполнение TTS',
  timing_overflow: 'Переполнение таймингa',
};

function fmt(n: number | null | undefined, decimals = 1): string {
  if (n == null) return '—';
  return n.toFixed(decimals);
}

function fmtTime(s: number | null): string {
  if (s == null) return '—';
  if (s < 60) return `${s.toFixed(1)}с`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}м ${rem.toFixed(0)}с`;
}

interface Props {
  projectId: string;
}

export const StatsPanel: React.FC<Props> = ({ projectId }) => {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedFlags, setExpandedFlags] = useState(false);
  const [expandedProviders, setExpandedProviders] = useState(false);

  const loadStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/stats`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setStats(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadStats(); }, [loadStats]);

  if (loading && !stats) {
    return (
      <div className="stats-loading">
        <div className="stats-spinner" />
        <span>Загрузка статистики…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="stats-error">
        <AlertTriangle size={16} />
        <span>{error}</span>
        <button className="stats-refresh-btn" onClick={loadStats}>Повторить</button>
      </div>
    );
  }

  if (!stats) return null;

  const { timing, segments, quality, tts, summary, billing } = stats;

  // Timing bar data
  const totalTime = Object.values(timing.stage_times).reduce((a, b) => a + b, 0);
  const stageEntries = Object.entries(timing.stage_times).sort((a, b) => b[1] - a[1]);

  // Provider distribution
  const totalTranslations = Object.values(quality.provider_usage).reduce((a, b) => a + b, 0) || 1;

  // Top QA flags (excluding technical)
  const technicalPrefixes = ['translation_provider_', 'translation_llm'];
  const problemFlags = Object.entries(quality.qa_flags_distribution)
    .filter(([k]) => !technicalPrefixes.some(p => k.startsWith(p)))
    .sort((a, b) => b[1] - a[1]);

  return (
    <div className="stats-panel">
      {/* Header */}
      <div className="stats-header">
        <span className="stats-title">📊 Статистика перевода</span>
        <button
          className="stats-refresh-btn"
          onClick={loadStats}
          disabled={loading}
          title="Обновить"
        >
          <RefreshCw size={13} className={loading ? 'spin' : ''} />
        </button>
      </div>

      {/* Status row */}
      <div className="stats-status-row">
        <span className={`stats-badge stats-badge--${summary.project_status}`}>
          {summary.project_status}
        </span>
        <span className="stats-lang">
          {summary.source_language} → {summary.target_language}
        </span>
        <span className={`stats-quality-badge ${summary.translation_quality}`}>
          {summary.translation_quality === 'professional' ? '⭐ Pro' : '🆓 Amateur'}
        </span>
      </div>

      {/* ── Время по этапам ── */}
      <div className="stats-section">
        <div className="stats-section-title">
          <Clock size={13} />
          Время выполнения
        </div>
        <div className="stats-time-total">
          Всего: <strong>{fmtTime(timing.total_elapsed_s)}</strong>
          {timing.slowest_stage && (
            <span className="stats-slowest">
              Узкое место: {STAGE_LABELS[timing.slowest_stage] || timing.slowest_stage}
            </span>
          )}
        </div>

        {/* Stacked bar */}
        {totalTime > 0 && (
          <div className="stats-time-bar-wrap">
            <div className="stats-time-bar">
              {stageEntries.map(([stage, t]) => (
                <div
                  key={stage}
                  className="stats-time-bar-seg"
                  style={{
                    width: `${(t / totalTime) * 100}%`,
                    background: STAGE_COLORS[stage] || '#6b7280',
                  }}
                  title={`${STAGE_LABELS[stage] || stage}: ${fmtTime(t)}`}
                />
              ))}
            </div>
            <div className="stats-time-legend">
              {stageEntries.map(([stage, t]) => (
                <div key={stage} className="stats-time-legend-item">
                  <span
                    className="stats-legend-dot"
                    style={{ background: STAGE_COLORS[stage] || '#6b7280' }}
                  />
                  <span>{STAGE_LABELS[stage] || stage}</span>
                  <strong>{fmtTime(t)}</strong>
                </div>
              ))}
            </div>
          </div>
        )}

        {timing.translate_per_segment_avg_s != null && (
          <div className="stats-kv">
            <span>Среднее на сегмент</span>
            <strong>{fmt(timing.translate_per_segment_avg_s, 2)}с</strong>
          </div>
        )}
      </div>

      {/* ── Сегменты ── */}
      <div className="stats-section">
        <div className="stats-section-title">
          <FileText size={13} />
          Сегменты и текст
        </div>
        <div className="stats-cards">
          <div className="stats-card">
            <span className="stats-card-val">{segments.count}</span>
            <span className="stats-card-label">сегментов</span>
          </div>
          <div className="stats-card">
            <span className="stats-card-val">{segments.source_words.toLocaleString()}</span>
            <span className="stats-card-label">слов (оригинал)</span>
          </div>
          <div className="stats-card">
            <span className="stats-card-val">{segments.target_words.toLocaleString()}</span>
            <span className="stats-card-label">слов (перевод)</span>
          </div>
          <div className="stats-card">
            <span className="stats-card-val">
              {segments.compression_ratio != null
                ? `${(segments.compression_ratio * 100).toFixed(0)}%`
                : '—'}
            </span>
            <span className="stats-card-label">сжатие текста</span>
          </div>
        </div>
        <div className="stats-kv-group">
          <div className="stats-kv">
            <span>Средняя длина сегмента</span>
            <strong>{fmt(segments.avg_duration_s, 1)}с</strong>
          </div>
          <div className="stats-kv">
            <span>Сокращений (rewrite)</span>
            <strong>{segments.segments_rewritten}</strong>
          </div>
          {segments.empty_translations > 0 && (
            <div className="stats-kv stats-kv--warn">
              <span>⚠️ Пустых переводов</span>
              <strong>{segments.empty_translations}</strong>
            </div>
          )}
        </div>
      </div>

      {/* ── Качество ── */}
      <div className="stats-section">
        <div className="stats-section-title">
          <Star size={13} />
          Качество перевода
        </div>
        <div className="stats-kv-group">
          {quality.avg_confidence != null && (
            <div className="stats-kv">
              <span>Уверенность Whisper</span>
              <strong>{(quality.avg_confidence * 100).toFixed(1)}%</strong>
            </div>
          )}
          <div className="stats-kv">
            <span>LLM-перевод</span>
            <strong>{quality.llm_translation_count} сегм.</strong>
          </div>
          <div className="stats-kv">
            <span>Google fallback</span>
            <strong className={quality.google_fallback_count > 0 ? 'text-warn' : ''}>
              {quality.google_fallback_count}
            </strong>
          </div>
        </div>

        {/* Провайдеры */}
        {Object.keys(quality.provider_usage).length > 0 && (
          <div className="stats-providers">
            <button
              className="stats-expand-btn"
              onClick={() => setExpandedProviders(v => !v)}
            >
              Провайдеры {expandedProviders ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {expandedProviders && (
              <div className="stats-provider-list">
                {Object.entries(quality.provider_usage).map(([name, count]) => (
                  <div key={name} className="stats-provider-row">
                    <div
                      className="stats-provider-bar"
                      style={{ width: `${(count / totalTranslations) * 100}%` }}
                    />
                    <span className="stats-provider-name">{name}</span>
                    <span className="stats-provider-count">{count} ({Math.round(count / totalTranslations * 100)}%)</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* QA флаги */}
        {problemFlags.length > 0 && (
          <div className="stats-flags">
            <button
              className="stats-expand-btn"
              onClick={() => setExpandedFlags(v => !v)}
            >
              QA флаги ({quality.segments_with_issues} сегм.)
              {expandedFlags ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
            {expandedFlags && (
              <div className="stats-flag-list">
                {problemFlags.map(([flag, count]) => (
                  <div key={flag} className="stats-flag-item">
                    <span className="stats-flag-name">
                      {FLAG_LABELS[flag] || flag.replace(/_/g, ' ')}
                    </span>
                    <span className="stats-flag-count">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── TTS ── */}
      {tts.segments_with_audio > 0 && (
        <div className="stats-section">
          <div className="stats-section-title">
            <Mic size={13} />
            Озвучка (TTS)
          </div>
          <div className="stats-kv-group">
            <div className="stats-kv">
              <span>Сегментов с аудио</span>
              <strong>{tts.segments_with_audio}</strong>
            </div>
            {tts.total_duration_s != null && (
              <div className="stats-kv">
                <span>Общая длительность</span>
                <strong>{fmtTime(tts.total_duration_s)}</strong>
              </div>
            )}
            <div className="stats-kv">
              <span>Переполнений</span>
              <strong className={tts.overflow_count > 0 ? 'text-warn' : ''}>
                {tts.overflow_count}
                {tts.overflow_rate != null && ` (${(tts.overflow_rate * 100).toFixed(1)}%)`}
              </strong>
            </div>
          </div>
        </div>
      )}

      {/* ── Биллинг ── */}
      {billing && (
        <div className="stats-section">
          <div className="stats-section-title">
            <DollarSign size={13} />
            Стоимость перевода
          </div>
          <div className="stats-billing-total">
            <span className="stats-billing-amount">
              ${billing.estimated_cost_usd.toFixed(4)}
            </span>
            <span className="stats-billing-approx">≈ оценка</span>
          </div>
          <div className="stats-kv-group">
            <div className="stats-kv">
              <span>Провайдер перевода</span>
              <strong className="stats-billing-provider">{billing.dominant_translation_provider}</strong>
            </div>
            {billing.rewrite_provider && (
              <div className="stats-kv">
                <span>Провайдер rewrite</span>
                <strong className="stats-billing-provider">{billing.rewrite_provider}</strong>
              </div>
            )}
            <div className="stats-kv">
              <span>Токены (вход / выход)</span>
              <strong>
                {billing.estimated_input_tokens.toLocaleString()} / {billing.estimated_output_tokens.toLocaleString()}
              </strong>
            </div>
          </div>
          {/* Разбивка по статьям */}
          <div className="stats-billing-breakdown">
            <div className="stats-billing-row">
              <span>Перевод</span>
              <span className="stats-billing-val">${billing.estimated_cost_translate_usd.toFixed(4)}</span>
            </div>
            {billing.estimated_cost_rewrite_usd > 0 && (
              <div className="stats-billing-row">
                <span>Timing rewrite</span>
                <span className="stats-billing-val">${billing.estimated_cost_rewrite_usd.toFixed(4)}</span>
              </div>
            )}
            <div className="stats-billing-row stats-billing-price-row">
              <span>Цена (1M tok in/out)</span>
              <span className="stats-billing-val">
                ${billing.price_per_1m_in_usd.toFixed(2)} / ${billing.price_per_1m_out_usd.toFixed(2)}
              </span>
            </div>
          </div>
          <div className="stats-billing-note">{billing.note}</div>
        </div>
      )}

      {/* Failed stages */}
      {summary.failed_stages.length > 0 && (
        <div className="stats-failed-stages">
          <AlertTriangle size={13} />
          Ошибки в этапах: {summary.failed_stages.map(s => STAGE_LABELS[s] || s).join(', ')}
        </div>
      )}
    </div>
  );
};
