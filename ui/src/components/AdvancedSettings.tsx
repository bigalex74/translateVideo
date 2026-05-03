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

// Список голосов-фолбэк (показывается пока API не ответил)
const TTS_VOICES_FALLBACK = [
  { id: 'alloy',   name: 'Alloy',   gender: 'neutral', tone: 'Нейтральный' },
  { id: 'echo',    name: 'Echo',    gender: 'male',    tone: 'Чёткий' },
  { id: 'fable',   name: 'Fable',   gender: 'male',    tone: 'Выразительный' },
  { id: 'onyx',    name: 'Onyx',    gender: 'male',    tone: 'Глубокий' },
  { id: 'nova',    name: 'Nova',    gender: 'female',  tone: 'Живой' },
  { id: 'shimmer', name: 'Shimmer', gender: 'female',  tone: 'Мягкий' },
];

// ElevenLabs голоса-фолбэк (21 голос, актуальный список из Polza API)
const ELEVENLABS_VOICES_FALLBACK = [
  { id: 'Rachel',    name: 'Rachel',    gender: 'female',  tone: 'Спокойный, профессиональный' },
  { id: 'Aria',      name: 'Aria',      gender: 'female',  tone: 'Выразительный, живой' },
  { id: 'Roger',     name: 'Roger',     gender: 'male',    tone: 'Уверенный, авторитетный' },
  { id: 'Sarah',     name: 'Sarah',     gender: 'female',  tone: 'Мягкий, дружелюбный' },
  { id: 'Laura',     name: 'Laura',     gender: 'female',  tone: 'Чёткий, информационный' },
  { id: 'Charlie',   name: 'Charlie',   gender: 'male',    tone: 'Разговорный, непринуждённый' },
  { id: 'George',    name: 'George',    gender: 'male',    tone: 'Зрелый, солидный' },
  { id: 'Callum',    name: 'Callum',    gender: 'male',    tone: 'Молодой, динамичный' },
  { id: 'River',     name: 'River',     gender: 'neutral', tone: 'Нейтральный, спокойный' },
  { id: 'Liam',      name: 'Liam',      gender: 'male',    tone: 'Живой, энергичный' },
  { id: 'Charlotte', name: 'Charlotte', gender: 'female',  tone: 'Тёплый, эмоциональный' },
  { id: 'Alice',     name: 'Alice',     gender: 'female',  tone: 'Чёткий, профессиональный' },
  { id: 'Matilda',   name: 'Matilda',   gender: 'female',  tone: 'Мягкий, дружелюбный' },
  { id: 'Will',      name: 'Will',      gender: 'male',    tone: 'Непринуждённый, разговорный' },
  { id: 'Jessica',   name: 'Jessica',   gender: 'female',  tone: 'Живой, выразительный' },
  { id: 'Eric',      name: 'Eric',      gender: 'male',    tone: 'Глубокий, авторитетный' },
  { id: 'Chris',     name: 'Chris',     gender: 'male',    tone: 'Разговорный, естественный' },
  { id: 'Brian',     name: 'Brian',     gender: 'male',    tone: 'Уверенный, профессиональный' },
  { id: 'Daniel',    name: 'Daniel',    gender: 'male',    tone: 'Чёткий, дикторский' },
  { id: 'Lily',      name: 'Lily',      gender: 'female',  tone: 'Молодой, яркий' },
  { id: 'Bill',      name: 'Bill',      gender: 'male',    tone: 'Зрелый, спокойный' },
];

// Yandex SpeechKit голоса-фолбэк
const SPEECHKIT_VOICES_FALLBACK = [
  { id: 'alena',   name: 'Алёна',   gender: 'female', tone: 'Тёплая, дружелюбная',       roles: ['neutral', 'good'] },
  { id: 'jane',    name: 'Джейн',   gender: 'female', tone: 'Эмоциональная, живая',       roles: ['neutral', 'good', 'evil'] },
  { id: 'omazh',   name: 'Омаж',    gender: 'female', tone: 'Нейтральная, офисная',       roles: ['neutral', 'evil'] },
  { id: 'madirus', name: 'Мадирус', gender: 'male',   tone: 'Молодой, энергичный',        roles: [] },
  { id: 'zahar',   name: 'Захар',   gender: 'male',   tone: 'Авторитетный, солидный',     roles: ['neutral', 'good'] },
  { id: 'ermil',   name: 'Ермил',   gender: 'male',   tone: 'Дикторский, чёткий',         roles: ['neutral', 'good'] },
  { id: 'filipp',  name: 'Филипп',  gender: 'male',   tone: 'Деловой, уверенный',         roles: [] },
  { id: 'amira',   name: 'Амира',   gender: 'female', tone: 'Мягкая, приятная',           roles: [] },
  { id: 'john',    name: 'Джон',    gender: 'male',   tone: 'Нейтральный, универсальный', roles: [] },
];

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
  const isSubtitlesOnly = c.translation_mode === 'subtitles';

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

  // ── Профессиональный TTS ─────────────────────────────────────────────
  const [ttsVoices, setTtsVoices] = React.useState<{id:string;name:string;gender:string;tone:string;roles?:string[]}[]>([]);
  const [ttsModels, setTtsModels] = React.useState<{id:string;name:string;note:string}[]>([]);
  const lastLoadedProvider = React.useRef('');

  const ttsProvider   = c.professional_tts_provider ?? '';
  const ttsModel      = c.professional_tts_model    ?? 'tts-1';
  const ttsVoice1     = c.professional_tts_voice    ?? (ttsProvider === 'yandex' ? 'alena' : 'nova');
  const ttsVoice2     = c.professional_tts_voice_2  ?? (ttsProvider === 'yandex' ? 'filipp' : 'onyx');
  const ttsRole1      = c.professional_tts_role     ?? 'neutral';
  const ttsRole2      = c.professional_tts_role_2   ?? 'neutral';
  const ttsSpeed1     = c.professional_tts_speed    ?? 1.0;
  const ttsSpeed2     = c.professional_tts_speed_2  ?? 1.0;
  const ttsPitch1     = c.professional_tts_pitch    ?? 0;
  const ttsPitch2     = c.professional_tts_pitch_2  ?? 0;
  const voiceStrategy = c.voice_strategy ?? 'single';
  const needVoice2    = voiceStrategy === 'two_voices' || voiceStrategy === 'per_speaker';
  const isYandex      = ttsProvider === 'yandex';
  const isElevenLabs  = ttsProvider === 'polza' && ttsModel.startsWith('elevenlabs/');
  const elStability   = c.el_stability      ?? 0.5;
  const elSimilarity  = c.el_similarity_boost ?? 0.75;
  const elStyle       = c.el_style           ?? 0.0;
  const elSpeed       = c.el_speed           ?? 1.0;

  React.useEffect(() => {
    if (!professional || !ttsProvider) return;
    const prov = isYandex ? 'yandex' : ttsProvider === 'polza' ? 'polza' : 'openai';
    const key = `${prov}:${ttsModel}`;
    if (lastLoadedProvider.current === key) return;
    lastLoadedProvider.current = key;
    const modelParam = prov === 'polza' ? `&model=${encodeURIComponent(ttsModel)}` : '';
    fetch(`/api/v1/tts/voices?provider=${prov}${modelParam}`).then(r => r.json()).then(d => setTtsVoices(d.voices ?? []));
    fetch(`/api/v1/tts/models?provider=${prov}`).then(r => r.json()).then(d => setTtsModels(d.models ?? []));
  }, [professional, ttsProvider, isYandex, ttsModel]);

  // Роли доступные для выбранного голоса (Yandex)
  const voice1Meta = ttsVoices.find(v => v.id === ttsVoice1);
  const voice2Meta = ttsVoices.find(v => v.id === ttsVoice2);
  const roles1 = voice1Meta?.roles ?? ['neutral'];
  const roles2 = voice2Meta?.roles ?? ['neutral'];

  const ROLE_LABELS: Record<string, string> = {
    neutral: 'Нейтральный',
    good:    'Добродушный',
    evil:    'Суровый / злодей',
    strict:  'Строгий',
    whisper: 'Шёпот',
  };

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

      {/* Режим «только субтитры» — TTS/Render недоступны */}
      {isSubtitlesOnly && (
        <div className="adv-section adv-section--info">
          <span style={{ fontSize: '1.5rem' }}>💬</span>
          <div>
            <strong>Режим «Только субтитры»</strong><br />
            <span className="adv-hint">
              В этом режиме TTS, тайминги и рендер не запускаются —
              пайплайн остановится после экспорта SRT/VTT.
              Настройки озвучки ниже неактивны.
            </span>
          </div>
        </div>
      )}

      {/* Дополнительные настройки — только в профессиональном режиме */}
      {professional && !isSubtitlesOnly && (
        <div className="adv-section">
          <div className="adv-section-title">Дополнительные настройки</div>

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
          {/* Профессиональная озвучка */}
          <div className="adv-field">
            <label className="adv-label">Профессиональная озвучка</label>
            <div className="adv-tts-block">

              {/* Провайдер TTS */}
              <div className="adv-tts-row">
                <div className="adv-field">
                  <label className="adv-label" htmlFor="adv-tts-provider">Провайдер TTS</label>
                  <select
                    id="adv-tts-provider"
                    className="adv-select"
                    value={ttsProvider}
                    onChange={e => {
                      const p = e.target.value;
                      // Сбрасываем голос на дефолт нового провайдера
                      onChange({
                        professional_tts_provider: p,
                        professional_tts_voice:   p === 'yandex' ? 'alena'  : p === 'polza' ? 'Rachel' : 'nova',
                        professional_tts_voice_2: p === 'yandex' ? 'filipp' : p === 'polza' ? 'Adam'   : 'onyx',
                        professional_tts_role:    'neutral',
                        professional_tts_role_2:  'neutral',
                        professional_tts_model:   p === 'polza' ? 'openai/gpt-4o-mini-tts' : 'tts-1',
                      });
                    }}
                    disabled={disabled}
                  >
                    <option value="">Edge TTS (бесплатный)</option>
                    <option value="neuroapi">NeuroAPI</option>
                    <option value="polza">Polza</option>
                    <option value="yandex">Yandex SpeechKit</option>
                  </select>
                </div>

                {/* Модель TTS — только для OpenAI-совместимых провайдеров */}
                {ttsProvider && !isYandex && (
                  <div className="adv-field">
                    <label className="adv-label" htmlFor="adv-tts-model">Модель</label>
                    <select
                      id="adv-tts-model"
                      className="adv-select"
                      value={ttsModel}
                      onChange={e => onChange({ professional_tts_model: e.target.value })}
                      disabled={disabled}
                    >
                      {(ttsModels.length ? ttsModels : [
                        {id:'tts-1',name:'TTS-1',note:'Стандартное'},
                        {id:'tts-1-hd',name:'TTS-1 HD',note:'HD'},
                        {id:'gpt-4o-mini-tts',name:'GPT-4o Mini TTS',note:'Высокое'},
                        ...(ttsProvider === 'polza' ? [
                          {id:'openai/gpt-4o-mini-tts',name:'GPT-4o Mini TTS',note:'быстрый'},
                          {id:'openai/tts-1-hd',name:'TTS-1 HD',note:'HD'},
                          {id:'openai/tts-1',name:'TTS-1',note:'стандарт'},
                          {id:'elevenlabs/text-to-speech-turbo-2-5',name:'ElevenLabs Turbo 2.5',note:'эмоции'},
                          {id:'elevenlabs/text-to-speech-multilingual-v2',name:'ElevenLabs Multilingual v2',note:'многоязычный'},
                        ] : []),
                      ]).map(m => (
                        <option key={m.id} value={m.id}>{m.name} — {m.note}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {/* Голос(а) — только для платного провайдера */}
              {ttsProvider && (
                <>
                  <div className="adv-tts-voices-label">
                    Голос{needVoice2 ? ' 1 (чётные сегменты)' : ''}
                  </div>
                  <div className="adv-tts-voices-grid">
                    {(ttsVoices.length
                      ? ttsVoices
                      : isYandex ? SPEECHKIT_VOICES_FALLBACK
                      : isElevenLabs ? ELEVENLABS_VOICES_FALLBACK
                      : TTS_VOICES_FALLBACK
                    ).map(v => (
                      <button
                        key={v.id}
                        type="button"
                        className={`adv-tts-voice-card ${ttsVoice1 === v.id ? 'adv-tts-voice-card--selected' : ''}`}
                        onClick={() => !disabled && onChange({
                          professional_tts_voice: v.id,
                          professional_tts_role: 'neutral',
                        })}
                        disabled={disabled}
                        title={v.tone}
                      >
                        <span className="adv-tts-voice-gender">
                          {v.gender === 'female' ? '👩' : v.gender === 'male' ? '👨' : '🧑'}
                        </span>
                        <span className="adv-tts-voice-name">{v.name}</span>
                        <span className="adv-tts-voice-tone">{v.tone}</span>
                      </button>
                    ))}
                  </div>

                  {/* Амплуа голоса 1 (только Yandex) */}
                  {isYandex && roles1.length > 1 && (
                    <div className="adv-tts-roles">
                      {roles1.map(role => (
                        <button
                          key={role}
                          type="button"
                          className={`adv-tts-role-btn ${ttsRole1 === role ? 'adv-tts-role-btn--active' : ''}`}
                          onClick={() => !disabled && onChange({ professional_tts_role: role })}
                          disabled={disabled}
                        >
                          {ROLE_LABELS[role] ?? role}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Скорость и высота голоса 1 (только Yandex) */}
                  {isYandex && (
                    <div className="adv-tts-sliders">
                      <div className="adv-tts-slider-row">
                        <label className="adv-tts-slider-label">
                          🎚 Скорость: <strong>{ttsSpeed1.toFixed(2)}×</strong>
                        </label>
                        <input
                          id="adv-tts-speed-1"
                          type="range"
                          className="adv-tts-slider"
                          min={0.5} max={2.0} step={0.05}
                          value={ttsSpeed1}
                          onChange={e => onChange({ professional_tts_speed: parseFloat(e.target.value) })}
                          disabled={disabled}
                        />
                        <div className="adv-tts-slider-ticks">
                          <span>0.5×</span><span>1.0×</span><span>1.5×</span><span>2.0×</span>
                        </div>
                      </div>
                      <div className="adv-tts-slider-row">
                        <label className="adv-tts-slider-label">
                          🎵 Высота: <strong>{ttsPitch1 > 0 ? `+${ttsPitch1}` : ttsPitch1}</strong>
                        </label>
                        <input
                          id="adv-tts-pitch-1"
                          type="range"
                          className="adv-tts-slider"
                          min={-500} max={500} step={25}
                          value={ttsPitch1}
                          onChange={e => onChange({ professional_tts_pitch: parseInt(e.target.value) })}
                          disabled={disabled}
                        />
                        <div className="adv-tts-slider-ticks">
                          <span>-500</span><span>0</span><span>+500</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* ElevenLabs: стабильность, схожесть, стиль, скорость */}
                  {isElevenLabs && (
                    <div className="adv-tts-sliders">
                      <div className="adv-tts-slider-row">
                        <label className="adv-tts-slider-label">
                          🎭 Стабильность голоса: <strong>{elStability.toFixed(2)}</strong>
                          <span className="adv-tts-slider-hint">0 = живой, 1 = стабильный</span>
                        </label>
                        <input
                          id="adv-el-stability"
                          type="range" className="adv-tts-slider"
                          min={0} max={1} step={0.05}
                          value={elStability}
                          onChange={e => onChange({ el_stability: parseFloat(e.target.value) })}
                          disabled={disabled}
                        />
                        <div className="adv-tts-slider-ticks">
                          <span>Живой</span><span>0.5</span><span>Стабильный</span>
                        </div>
                      </div>
                      <div className="adv-tts-slider-row">
                        <label className="adv-tts-slider-label">
                          🎤 Схожесть: <strong>{elSimilarity.toFixed(2)}</strong>
                          <span className="adv-tts-slider-hint">насколько точно копируется тембр</span>
                        </label>
                        <input
                          id="adv-el-similarity"
                          type="range" className="adv-tts-slider"
                          min={0} max={1} step={0.05}
                          value={elSimilarity}
                          onChange={e => onChange({ el_similarity_boost: parseFloat(e.target.value) })}
                          disabled={disabled}
                        />
                        <div className="adv-tts-slider-ticks">
                          <span>Низкая</span><span>0.5</span><span>Высокая</span>
                        </div>
                      </div>
                      <div className="adv-tts-slider-row">
                        <label className="adv-tts-slider-label">
                          ✨ Стиль / экспрессия: <strong>{elStyle.toFixed(2)}</strong>
                          <span className="adv-tts-slider-hint">0 = нейтрально, 1 = максимум</span>
                        </label>
                        <input
                          id="adv-el-style"
                          type="range" className="adv-tts-slider"
                          min={0} max={1} step={0.05}
                          value={elStyle}
                          onChange={e => onChange({ el_style: parseFloat(e.target.value) })}
                          disabled={disabled}
                        />
                        <div className="adv-tts-slider-ticks">
                          <span>Нейтрально</span><span>0.5</span><span>Ярко</span>
                        </div>
                      </div>
                      <div className="adv-tts-slider-row">
                        <label className="adv-tts-slider-label">
                          🎚 Скорость: <strong>{elSpeed.toFixed(2)}×</strong>
                        </label>
                        <input
                          id="adv-el-speed"
                          type="range" className="adv-tts-slider"
                          min={0.7} max={1.2} step={0.05}
                          value={elSpeed}
                          onChange={e => onChange({ el_speed: parseFloat(e.target.value) })}
                          disabled={disabled}
                        />
                        <div className="adv-tts-slider-ticks">
                          <span>0.7×</span><span>1.0×</span><span>1.2×</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {needVoice2 && (
                    <>
                      <div className="adv-tts-voices-label">Голос 2 (нечётные / другие спикеры)</div>
                      <div className="adv-tts-voices-grid">
                        {(ttsVoices.length
                          ? ttsVoices
                          : isYandex ? SPEECHKIT_VOICES_FALLBACK
                          : isElevenLabs ? ELEVENLABS_VOICES_FALLBACK
                          : TTS_VOICES_FALLBACK
                        ).map(v => (
                          <button
                            key={v.id}
                            type="button"
                            className={`adv-tts-voice-card ${ttsVoice2 === v.id ? 'adv-tts-voice-card--selected' : ''}`}
                            onClick={() => !disabled && onChange({
                              professional_tts_voice_2: v.id,
                              professional_tts_role_2: 'neutral',
                            })}
                            disabled={disabled}
                            title={v.tone}
                          >
                            <span className="adv-tts-voice-gender">
                              {v.gender === 'female' ? '👩' : v.gender === 'male' ? '👨' : '🧑'}
                            </span>
                            <span className="adv-tts-voice-name">{v.name}</span>
                            <span className="adv-tts-voice-tone">{v.tone}</span>
                          </button>
                        ))}
                      </div>

                      {/* Амплуа голоса 2 (только Yandex) */}
                      {isYandex && roles2.length > 1 && (
                        <div className="adv-tts-roles">
                          {roles2.map(role => (
                            <button
                              key={role}
                              type="button"
                              className={`adv-tts-role-btn ${ttsRole2 === role ? 'adv-tts-role-btn--active' : ''}`}
                              onClick={() => !disabled && onChange({ professional_tts_role_2: role })}
                              disabled={disabled}
                            >
                              {ROLE_LABELS[role] ?? role}
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Скорость и высота голоса 2 (только Yandex) */}
                      {isYandex && (
                        <div className="adv-tts-sliders">
                          <div className="adv-tts-slider-row">
                            <label className="adv-tts-slider-label">
                              🎚 Скорость: <strong>{ttsSpeed2.toFixed(2)}×</strong>
                            </label>
                            <input
                              id="adv-tts-speed-2"
                              type="range"
                              className="adv-tts-slider"
                              min={0.5} max={2.0} step={0.05}
                              value={ttsSpeed2}
                              onChange={e => onChange({ professional_tts_speed_2: parseFloat(e.target.value) })}
                              disabled={disabled}
                            />
                            <div className="adv-tts-slider-ticks">
                              <span>0.5×</span><span>1.0×</span><span>1.5×</span><span>2.0×</span>
                            </div>
                          </div>
                          <div className="adv-tts-slider-row">
                            <label className="adv-tts-slider-label">
                              🎵 Высота: <strong>{ttsPitch2 > 0 ? `+${ttsPitch2}` : ttsPitch2}</strong>
                            </label>
                            <input
                              id="adv-tts-pitch-2"
                              type="range"
                              className="adv-tts-slider"
                              min={-500} max={500} step={25}
                              value={ttsPitch2}
                              onChange={e => onChange({ professional_tts_pitch_2: parseInt(e.target.value) })}
                              disabled={disabled}
                            />
                            <div className="adv-tts-slider-ticks">
                              <span>-500</span><span>0</span><span>+500</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </>
              )}
            </div>
          </div>

          {/* 🎭 Уровень эмоций SSML (только Yandex) */}
          {isYandex && (
            <div className="adv-field">
              <label className="adv-label">
                🎭 Эмоциональность SSML
              </label>
              <div className="adv-emotion-note">
                Автоматически добавляет паузы, просодию и акценты в речь через SSML-разметку.
                Требует повторной озвучки.
              </div>
              <div className="adv-role-btns">
                {([
                  { val: 0, label: '🔇 Выкл' },
                  { val: 1, label: '🌿 Мягко' },
                  { val: 2, label: '🔥 Средне' },
                  { val: 3, label: '⚡ Экспресс' },
                ] as { val: number; label: string }[]).map(({ val, label }) => (
                  <button
                    key={val}
                    id={`adv-emotion-${val}`}
                    className={`adv-tts-role-btn${(c.professional_tts_emotion ?? 0) === val ? ' adv-tts-role-btn--active' : ''}`}
                    onClick={() => onChange({ professional_tts_emotion: val })}
                    disabled={disabled}
                    title={[
                      'SSML отключён — обычный текст',
                      'Паузы на знаках препинания',
                      'Паузы + просодия по типу предложений',
                      'Полная экспрессия: просодия + ударения + паузы',
                    ][val]}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

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

          {/* Режим разработчика */}
          <div className="adv-field adv-field--devmode">
            <div className="adv-devmode-row">
              <div className="adv-devmode-info">
                <label className="adv-label adv-label--devmode" htmlFor="adv-devmode">
                  🔧 Режим разработчика
                </label>
                <span className="adv-hint">
                  Записывает все промты, ответы моделей и I/O этапов в devlog.jsonl.
                  Позволяет анализировать качество перевода через вкладку Dev.
                </span>
              </div>
              <button
                id="adv-devmode"
                type="button"
                className={`adv-toggle ${c.dev_mode ? 'adv-toggle--on' : ''}`}
                onClick={() => onChange({ dev_mode: !c.dev_mode })}
                disabled={disabled}
                aria-pressed={c.dev_mode}
              >
                {c.dev_mode ? 'Вкл' : 'Выкл'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ Субтитры ══════════════════════════════════════════════════════════ */}
      <div className="adv-section">
        <div className="adv-section-title">Субтитры в видео</div>

        <div className="adv-field">
          <label className="adv-label" htmlFor="adv-subtitle-mode">Режим встраивания</label>
          <select
            id="adv-subtitle-mode"
            className="adv-select"
            value={c.subtitle_embed_mode ?? 'none'}
            onChange={e => onChange({ subtitle_embed_mode: e.target.value })}
            disabled={disabled}
          >
            <option value="none">Не встраивать (только SRT/VTT файлы)</option>
            <option value="soft">Мягкие (трек в MP4, включается в плеере)</option>
            <option value="burn">Жёсткие (вжечь в видео, всегда видны)</option>
          </select>
        </div>

        {(c.subtitle_embed_mode ?? 'none') !== 'none' && (
          <div className="adv-hint">
            {c.subtitle_embed_mode === 'soft'
              ? '💬 Субтитры будут встроены как отдельный трек. Их можно включить/выключить в VLC, браузере или медиаплеере.'
              : '🔥 Субтитры будут вжжены в видеопоток (hardcode). Всегда видны, независимо от плеера.'}
          </div>
        )}
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
