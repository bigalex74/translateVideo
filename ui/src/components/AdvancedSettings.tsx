import React from 'react';
import type { PipelineConfig } from '../types/schemas';
import './AdvancedSettings.css';

// ─── Словари меток для всех полей конфигурации ────────────────────────────

export const STYLE_LABELS: Record<string, string> = {
  neutral:       'Нейтральный',
  business:      'Деловой',
  casual:        'Разговорный',
  humorous:      'Юмористический',
  educational:   'Образовательный',
  cinematic:     'Кинематографический',
  child_friendly:'Для детей',
};

export const ADAPTATION_LABELS: Record<string, string> = {
  literal:             'Дословно (точный перевод)',
  natural:             'Естественно (рекомендуется)',
  localized:           'Локализовано (культурная адаптация)',
  shortened_for_timing:'Укорочено (под тайминг)',
};

export const VOICE_LABELS: Record<string, string> = {
  single:      'Один голос',
  by_gender:   'По полу (муж./жен.)',
  two_voices:  'Два голоса',
  per_speaker: 'Каждому спикеру свой',
};

export const PROFANITY_LABELS: Record<string, string> = {
  keep:    'Сохранить',
  soften:  'Смягчить',
  remove:  'Удалить',
};

// ─── Дефолтные значения ───────────────────────────────────────────────────

export const DEFAULT_CONFIG: Partial<PipelineConfig> = {
  translation_style: 'neutral',
  adaptation_level: 'natural',
  voice_strategy: 'single',
  do_not_translate: [],
  profanity_policy: 'keep',
  preserve_names: true,
};

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

  return (
    <div className="adv-settings">
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
    </div>
  );
};
