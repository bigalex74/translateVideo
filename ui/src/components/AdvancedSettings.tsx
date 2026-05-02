import React from 'react';
import type { PipelineConfig } from '../types/schemas';
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
  const translationModels = withCurrentModel(
    PROFESSIONAL_MODEL_OPTIONS[translationProvider] ?? [],
    c.professional_translation_model,
  );
  const rewriteModels = withCurrentModel(
    PROFESSIONAL_MODEL_OPTIONS[rewriteProvider] ?? [],
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
          <div className="adv-professional-grid">
            <div className="adv-field">
              <label className="adv-label" htmlFor="adv-pro-trans-provider">Провайдер перевода</label>
              <select
                id="adv-pro-trans-provider"
                className="adv-select"
                value={translationProvider}
                onChange={e => {
                  const provider = e.target.value;
                  onChange({
                    professional_translation_provider: provider,
                    professional_translation_model: PROFESSIONAL_MODEL_OPTIONS[provider]?.[0] ?? '',
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
                disabled={disabled}
              >
                {translationModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
            <div className="adv-field">
              <label className="adv-label" htmlFor="adv-pro-rewrite-provider">Провайдер сокращения</label>
              <select
                id="adv-pro-rewrite-provider"
                className="adv-select"
                value={rewriteProvider}
                onChange={e => {
                  const provider = e.target.value;
                  onChange({
                    professional_rewrite_provider: provider,
                    professional_rewrite_model: PROFESSIONAL_MODEL_OPTIONS[provider]?.[0] ?? '',
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
              <label className="adv-label" htmlFor="adv-pro-rewrite-model">Модель сокращения</label>
              <select
                id="adv-pro-rewrite-model"
                className="adv-select"
                value={c.professional_rewrite_model ?? rewriteModels[0] ?? ''}
                onChange={e => onChange({ professional_rewrite_model: e.target.value })}
                disabled={disabled}
              >
                {rewriteModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </div>
          </div>
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

function withCurrentModel(options: string[], current?: string): string[] {
  const value = current?.trim();
  if (!value || options.includes(value)) return options;
  return [value, ...options];
}
