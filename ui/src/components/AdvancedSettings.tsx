import React from 'react';
import { fetchProviderBalance, fetchProviderModels } from '../api/client';
import type { PipelineConfig, ProviderBalance } from '../types/schemas';
import {
  ADAPTATION_LABELS,
  DEFAULT_CONFIG,
  MODEL_PROVIDER_LABELS,
  PROFANITY_LABELS,
  PROFESSIONAL_MODEL_OPTIONS,
  QUALITY_LABELS,
  STYLE_LABELS,
  VOICE_LABELS,
} from './advancedSettingsConfig';
import './AdvancedSettings.css';

// ─── Компонент ────────────────────────────────────────────────────────────

interface AdvancedSettingsProps {
  config: Partial<PipelineConfig>;
  onChange: (patch: Partial<PipelineConfig>) => void;
  disabled?: boolean;
}

export const AdvancedSettings: React.FC<AdvancedSettingsProps> = ({
  config,
  onChange,
  disabled = false,
}) => {
  const c = { ...DEFAULT_CONFIG, ...config };
  const professional = c.translation_quality === 'professional';

  // Управление тегами do_not_translate
  const [tagInput, setTagInput] = React.useState('');
  const tags = c.do_not_translate ?? [];

  const addTag = () => {
    const word = tagInput.trim();
    if (!word || tags.includes(word)) { setTagInput(''); return; }
    onChange({ do_not_translate: [...tags, word] });
    setTagInput('');
  };

  const removeTag = (word: string) => {
    onChange({ do_not_translate: tags.filter(t => t !== word) });
  };

  const translationProvider = c.professional_translation_provider ?? 'neuroapi';
  const rewriteProvider = c.professional_rewrite_provider ?? 'neuroapi';
  const [modelsByProvider, setModelsByProvider] = React.useState<Record<string, string[]>>({});
  const [modelErrors, setModelErrors] = React.useState<Record<string, string>>({});
  const [loadingModels, setLoadingModels] = React.useState<Set<string>>(new Set());
  const [balances, setBalances] = React.useState<Record<string, ProviderBalance>>({});
  const [balanceErrors, setBalanceErrors] = React.useState<Record<string, string>>({});
  const [loadingBalances, setLoadingBalances] = React.useState<Set<string>>(new Set());
  const requestedModels = React.useRef(new Set<string>());
  const requestedBalances = React.useRef(new Set<string>());

  React.useEffect(() => {
    if (!professional) return;
    const providers = Array.from(new Set([translationProvider, rewriteProvider]));
    for (const provider of providers) {
      if (!provider || modelsByProvider[provider] || requestedModels.current.has(provider)) continue;
      requestedModels.current.add(provider);
      setLoadingModels(prev => new Set(prev).add(provider));
      fetchProviderModels(provider)
        .then(models => {
          setModelsByProvider(prev => ({
            ...prev,
            [provider]: models.map(model => model.id),
          }));
          setModelErrors(prev => {
            const next = { ...prev };
            delete next[provider];
            return next;
          });
        })
        .catch(error => {
          setModelErrors(prev => ({
            ...prev,
            [provider]: error instanceof Error ? error.message : String(error),
          }));
        })
        .finally(() => {
          setLoadingModels(prev => {
            const next = new Set(prev);
            next.delete(provider);
            return next;
          });
        });
    }
  }, [professional, translationProvider, rewriteProvider, modelsByProvider]);

  const loadBalance = React.useCallback((provider: string) => {
    setLoadingBalances(prev => new Set(prev).add(provider));
    fetchProviderBalance(provider)
      .then(balance => {
        setBalances(prev => ({ ...prev, [provider]: balance }));
        setBalanceErrors(prev => { const next = { ...prev }; delete next[provider]; return next; });
      })
      .catch(error => {
        setBalanceErrors(prev => ({
          ...prev,
          [provider]: error instanceof Error ? error.message : String(error),
        }));
      })
      .finally(() => {
        setLoadingBalances(prev => { const next = new Set(prev); next.delete(provider); return next; });
      });
  }, []);

  // Автозагрузка балансов при включении professional-режима
  React.useEffect(() => {
    if (!professional) return;
    for (const provider of ['neuroapi', 'polza']) {
      if (balances[provider] || requestedBalances.current.has(provider)) continue;
      requestedBalances.current.add(provider);
      loadBalance(provider);
    }
  }, [professional, balances, loadBalance]);

  const translationModels = withCurrentModel(
    modelsByProvider[translationProvider] ?? PROFESSIONAL_MODEL_OPTIONS[translationProvider] ?? [],
    c.professional_translation_model,
  );
  const rewriteModels = withCurrentModel(
    modelsByProvider[rewriteProvider] ?? PROFESSIONAL_MODEL_OPTIONS[rewriteProvider] ?? [],
    c.professional_rewrite_model,
  );

  return (
    <div className="adv-settings">
      {/* Профиль качества */}
      <div className="adv-section">
        <div className="adv-section-title">Уровень перевода</div>
        <div className="adv-field">
          <label className="adv-label" htmlFor="adv-quality">Профиль качества</label>
          <select
            id="adv-quality"
            className="adv-select"
            value={c.translation_quality ?? 'amateur'}
            onChange={e => onChange({ translation_quality: e.target.value })}
            disabled={disabled}
          >
            {Object.entries(QUALITY_LABELS).map(([val, label]) => (
              <option key={val} value={val}>{label}</option>
            ))}
          </select>
          <span className="adv-hint">
            Любительский режим берёт бесплатные модели по рейтингу. Профессиональный использует
            только выбранную платную модель отдельно для перевода и сокращения.
          </span>
        </div>

        {professional && (
          <>
            {/* Блок балансов */}
            <div className="adv-balance-row">
              {(['neuroapi', 'polza'] as const).map(provider => (
                <BalanceCard
                  key={provider}
                  provider={provider}
                  balance={balances[provider]}
                  error={balanceErrors[provider]}
                  loading={loadingBalances.has(provider)}
                  onRefresh={() => {
                    // сбрасываем кэш чтобы разрешить повторный запрос
                    requestedBalances.current.delete(provider);
                    setBalances(prev => { const next = { ...prev }; delete next[provider]; return next; });
                    loadBalance(provider);
                  }}
                />
              ))}
            </div>

            {/* Настройки провайдеров */}
            <div className="adv-professional-grid">
              <div className="adv-field">
                <label className="adv-label" htmlFor="adv-pro-trans-provider">Провайдер перевода</label>
                <select
                  id="adv-pro-trans-provider"
                  className="adv-select"
                  value={translationProvider}
                  onChange={e => {
                    const provider = e.target.value;
                    const firstModel =
                      modelsByProvider[provider]?.[0] ??
                      PROFESSIONAL_MODEL_OPTIONS[provider]?.[0] ??
                      '';
                    onChange({
                      professional_translation_provider: provider,
                      professional_translation_model: firstModel,
                    });
                  }}
                  disabled={disabled}
                >
                  {Object.entries(MODEL_PROVIDER_LABELS).map(([val, label]) => (
                    <option key={val} value={val}>{label}</option>
                  ))}
                </select>
              </div>
              <div className="adv-field">
                <label className="adv-label" htmlFor="adv-pro-trans-model">Модель перевода</label>
                <select
                  id="adv-pro-trans-model"
                  className="adv-select"
                  value={c.professional_translation_model ?? translationModels[0] ?? ''}
                  onChange={e => onChange({ professional_translation_model: e.target.value })}
                  disabled={disabled || loadingModels.has(translationProvider)}
                >
                  {loadingModels.has(translationProvider) ? (
                    <option value="">Загрузка моделей…</option>
                  ) : (
                    translationModels.map(model => (
                      <option key={model} value={model}>{model}</option>
                    ))
                  )}
                </select>
                {modelErrors[translationProvider] && (
                  <span className="adv-hint adv-hint--error">{modelErrors[translationProvider]}</span>
                )}
              </div>
              <div className="adv-field">
                <label className="adv-label" htmlFor="adv-pro-rewrite-provider">Провайдер постредактуры</label>
                <select
                  id="adv-pro-rewrite-provider"
                  className="adv-select"
                  value={rewriteProvider}
                  onChange={e => {
                    const provider = e.target.value;
                    const firstModel =
                      modelsByProvider[provider]?.[0] ??
                      PROFESSIONAL_MODEL_OPTIONS[provider]?.[0] ??
                      '';
                    onChange({
                      professional_rewrite_provider: provider,
                      professional_rewrite_model: firstModel,
                    });
                  }}
                  disabled={disabled}
                >
                  {Object.entries(MODEL_PROVIDER_LABELS).map(([val, label]) => (
                    <option key={val} value={val}>{label}</option>
                  ))}
                </select>
              </div>
              <div className="adv-field">
                <label className="adv-label" htmlFor="adv-pro-rewrite-model">Модель постредактуры</label>
                <select
                  id="adv-pro-rewrite-model"
                  className="adv-select"
                  value={c.professional_rewrite_model ?? rewriteModels[0] ?? ''}
                  onChange={e => onChange({ professional_rewrite_model: e.target.value })}
                  disabled={disabled || loadingModels.has(rewriteProvider)}
                >
                  {loadingModels.has(rewriteProvider) ? (
                    <option value="">Загрузка моделей…</option>
                  ) : (
                    rewriteModels.map(model => (
                      <option key={model} value={model}>{model}</option>
                    ))
                  )}
                </select>
                {modelErrors[rewriteProvider] && (
                  <span className="adv-hint adv-hint--error">{modelErrors[rewriteProvider]}</span>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Стиль перевода */}
      <div className="adv-field">
        <label className="adv-label" htmlFor="adv-style">Стиль перевода</label>
        <select
          id="adv-style"
          className="adv-select"
          value={c.translation_style ?? 'neutral'}
          onChange={e => onChange({ translation_style: e.target.value })}
          disabled={disabled}
        >
          {Object.entries(STYLE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
      </div>

      {/* Степень адаптации */}
      <div className="adv-field">
        <label className="adv-label" htmlFor="adv-adaptation">Адаптация</label>
        <select
          id="adv-adaptation"
          className="adv-select"
          value={c.adaptation_level ?? 'natural'}
          onChange={e => onChange({ adaptation_level: e.target.value })}
          disabled={disabled}
        >
          {Object.entries(ADAPTATION_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
      </div>

      {/* Стратегия голосов */}
      <div className="adv-field">
        <label className="adv-label" htmlFor="adv-voice">Голоса</label>
        <select
          id="adv-voice"
          className="adv-select"
          value={c.voice_strategy ?? 'single'}
          onChange={e => onChange({ voice_strategy: e.target.value })}
          disabled={disabled}
        >
          {Object.entries(VOICE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
      </div>

      {/* Обсценная лексика */}
      <div className="adv-field">
        <label className="adv-label" htmlFor="adv-profanity">Ненормативная лексика</label>
        <select
          id="adv-profanity"
          className="adv-select"
          value={c.profanity_policy ?? 'keep'}
          onChange={e => onChange({ profanity_policy: e.target.value })}
          disabled={disabled}
        >
          {Object.entries(PROFANITY_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
      </div>

      {/* Сохранять имена */}
      <div className="adv-field adv-field--toggle">
        <label className="adv-label" htmlFor="adv-names">Сохранять имена собственные</label>
        <button
          id="adv-names"
          type="button"
          className={`adv-toggle ${c.preserve_names ? 'adv-toggle--on' : ''}`}
          onClick={() => onChange({ preserve_names: !c.preserve_names })}
          disabled={disabled}
          aria-pressed={c.preserve_names}
        >
          {c.preserve_names ? 'Вкл' : 'Выкл'}
        </button>
      </div>

      {/* Не переводить */}
      <div className="adv-field">
        <label className="adv-label">Не переводить (слова/термины)</label>
        <div className="adv-tags">
          {tags.map(word => (
            <span key={word} className="adv-tag">
              {word}
              <button
                type="button"
                className="adv-tag-remove"
                onClick={() => removeTag(word)}
                disabled={disabled}
                aria-label={`Удалить ${word}`}
              >×</button>
            </span>
          ))}
          <input
            id="adv-tag-input"
            className="adv-tag-input"
            type="text"
            value={tagInput}
            placeholder="Слово или бренд..."
            onChange={e => setTagInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(); } }}
            disabled={disabled}
          />
          <button
            type="button"
            className="adv-tag-add"
            onClick={addTag}
            disabled={disabled || !tagInput.trim()}
          >+</button>
        </div>
        <span className="adv-hint">Нажмите Enter или «+» для добавления</span>
      </div>

      <div className="adv-section adv-section--muted">
        <div className="adv-section-title">Озвучка: следующий этап</div>
        <span className="adv-hint">
          Для TTS будет такая же структура: любительский режим на бесплатных/дешёвых голосах
          и профессиональный режим с выбором платной модели, провайдера и голоса.
        </span>
      </div>
    </div>
  );
};

const PROVIDER_DISPLAY: Record<string, { label: string; url: string }> = {
  neuroapi: { label: 'NeuroAPI', url: 'https://neuroapi.host' },
  polza: { label: 'Polza.ai', url: 'https://polza.ai' },
};

function BalanceCard({
  provider,
  balance,
  error,
  loading,
  onRefresh,
}: {
  provider: string;
  balance?: ProviderBalance;
  error?: string;
  loading: boolean;
  onRefresh: () => void;
}) {
  const meta = PROVIDER_DISPLAY[provider] ?? { label: provider, url: '#' };

  return (
    <div className={`adv-balance-card ${!balance?.configured ? 'adv-balance-card--unconfigured' : ''}`}>
      <div className="adv-balance-card__header">
        <a
          className="adv-balance-card__name"
          href={meta.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {meta.label}
        </a>
        <button
          type="button"
          className={`adv-balance-card__refresh ${loading ? 'adv-balance-card__refresh--spinning' : ''}`}
          onClick={onRefresh}
          disabled={loading}
          title="Обновить баланс"
          aria-label="Обновить баланс"
        >
          ↻
        </button>
      </div>

      {loading && !balance && (
        <div className="adv-balance-card__loading">Загрузка…</div>
      )}

      {error && (
        <div className="adv-balance-card__error" title={error}>⚠ {error.slice(0, 60)}</div>
      )}

      {balance && !error && (
        <div className="adv-balance-card__body">
          {typeof balance.balance === 'number' ? (
            <div className="adv-balance-card__main">
              <span className="adv-balance-card__value">{formatMoney(balance.balance, balance.currency)}</span>
              <span className="adv-balance-card__sublabel">остаток</span>
            </div>
          ) : !balance.configured ? (
            <div className="adv-balance-card__error">Ключ не настроен</div>
          ) : null}

          {typeof balance.used === 'number' && (
            <div className="adv-balance-card__secondary">
              потрачено: <strong>{formatMoney(balance.used, balance.currency)}</strong>
            </div>
          )}

          {balance.message && (
            <div className="adv-balance-card__hint">{balance.message}</div>
          )}
        </div>
      )}
    </div>
  );
}

function withCurrentModel(options: string[], current?: string): string[] {
  const value = current?.trim();
  if (!value || options.includes(value)) return options;
  return [value, ...options];
}

function formatMoney(value: number, currency?: string | null): string {
  const suffix = currency ? ` ${currency}` : '';
  return `${value.toFixed(2)}${suffix}`;
}
