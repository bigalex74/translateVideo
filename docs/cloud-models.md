# Облачные Модели

## Назначение

Облачные модели используются в двух местах:

- `translate` — первичный LLM-перевод сегментов с контекстом и fallback на
  Google Translate.
- `timing_fit` — переформулирование уже переведённого текста короче под
  естественную озвучку.

Локальные LLM не используются, потому что они конфликтуют по ресурсам с FFmpeg
и медиа-обработкой.

## Рейтинг Translation-Провайдеров

Порядок по умолчанию:

1. `gemini` — основной бесплатный/условно бесплатный переводчик.
   Дефолтная модель: `gemini-2.5-flash-lite`.
2. `aihubmix` — резервный OpenAI-compatible агрегатор.
   Дефолтная модель: `gemini-3-flash-preview-free`.
3. `openrouter` — резервный агрегатор бесплатных моделей.
   Дефолтная модель: `openai/gpt-oss-20b:free`.
4. `polza` — последний fallback, потому что провайдер платный.
   Дефолтная модель: `google/gemini-2.5-flash-lite-preview-09-2025`.
   По умолчанию не включается даже при наличии ключа; нужен явный флаг
   `TRANSLATION_ALLOW_PAID_FALLBACK=true`.
5. `google` — legacy Google Translate через `deep-translator`.

LLM-переводчик получает 2 предыдущих и 2 следующих сегмента, стиль перевода,
уровень адаптации, аудиторию, предметную область, глоссарий и список
`do_not_translate`.

## Профили Качества

`translation_quality = amateur` — режим по умолчанию. Он использует бесплатные
и условно бесплатные модели по рейтингу. Платные агрегаторы `polza` и
`neuroapi` подключаются только если явно включён соответствующий
`*_ALLOW_PAID_FALLBACK`.

`translation_quality = professional` — профессиональный режим. Для перевода и
для сокращения текста используются только выбранные провайдеры и модели:

```json
{
  "translation_quality": "professional",
  "professional_translation_provider": "neuroapi",
  "professional_translation_model": "gpt-5-mini",
  "professional_rewrite_provider": "neuroapi",
  "professional_rewrite_model": "gpt-5-mini"
}
```

Профессиональный режим нужен для дорогих топовых моделей: он не ходит по
цепочке бесплатных fallback-моделей и не подменяет результат Google/rule-based.
Если ключ, провайдер или модель недоступны, этап падает явно.

## Рейтинг Rewriter-Провайдеров

Порядок по умолчанию:

1. `gemini` — основной бесплатный/условно бесплатный провайдер качества.
2. `aihubmix` — быстрый резервный OpenAI-compatible агрегатор.
   Дефолтная модель: `gpt-4.1-nano-free`.
3. `openrouter` — агрегатор бесплатных моделей, второй fallback.
   Дефолтная модель: `openai/gpt-oss-20b:free`.
4. `polza` — последний fallback, потому что провайдер платный.
   Дефолтная модель: `google/gemini-2.5-flash-lite-preview-09-2025`.
   По умолчанию не включается даже при наличии ключа; нужен явный флаг
   `REWRITE_ALLOW_PAID_FALLBACK=true`.
5. `rule_based` — локальный безопасный fallback без сети.

## Переменные Окружения

Создайте локальный `.env` на основе `.env.example` или экспортируйте переменные
на сервере:

```bash
GEMINI_API_KEY=...
GEMINI_TRANSLATION_MODEL=gemini-2.5-flash-lite
GEMINI_REWRITE_MODEL=gemini-2.5-flash-lite

OPENROUTER_API_KEY=...
OPENROUTER_TRANSLATION_MODEL=openai/gpt-oss-20b:free
OPENROUTER_REWRITE_MODEL=openai/gpt-oss-20b:free
OPENROUTER_SITE_URL=http://localhost:8002
OPENROUTER_APP_NAME=translateVideo

AIHUBMIX_API_KEY=...
AIHUBMIX_BASE_URL=https://aihubmix.com/v1
AIHUBMIX_TRANSLATION_MODEL=gemini-3-flash-preview-free
AIHUBMIX_REWRITE_MODEL=gpt-4.1-nano-free

POLZA_API_KEY=...
POLZA_BASE_URL=https://api.polza.ai/api/v1
POLZA_TRANSLATION_MODEL=google/gemini-2.5-flash-lite-preview-09-2025
POLZA_REWRITE_MODEL=google/gemini-2.5-flash-lite-preview-09-2025

NEUROAPI_API_KEY=...
NEUROAPI_BASE_URL=https://neuroapi.host/v1
NEUROAPI_TRANSLATION_MODEL=gpt-5-mini
NEUROAPI_REWRITE_MODEL=gpt-5-mini

TRANSLATION_ALLOW_PAID_FALLBACK=false
REWRITE_ALLOW_PAID_FALLBACK=false

TRANSLATION_PROVIDER_TIMEOUT=15
REWRITE_PROVIDER_TIMEOUT=8
```

Реальный `.env` игнорируется Git. Не добавляйте ключи в код, тесты,
документацию или issue.

## Поведение Fallback

Если провайдер вернул ошибку, пустой ответ, слишком длинный ответ или ответ без
сокращения, роутер переходит к следующему провайдеру. Ошибки `429`, `503` и
`timeout` считаются признаком исчерпанного лимита или перегрузки: такой
провайдер временно уходит в cooldown, а не отключается навсегда. После cooldown
он снова может использоваться в том же запуске.

Для бесплатных моделей включён консервативный RPM-лимит: по умолчанию `5`
запросов в минуту для `gemini`, `openrouter` и `aihubmix`. Это медленнее, но
сильно снижает вероятность `429`. Настройки хранятся в `project.json`.

Настройки перевода:

```json
{
  "translation_provider_rpm": {
    "gemini": 5.0,
    "openrouter": 5.0,
    "aihubmix": 5.0,
    "polza": 30.0
  },
  "translation_provider_cooldown_seconds": 75.0,
  "translation_provider_wait_for_rate_limit": true,
  "translation_allow_paid_fallback": false
}
```

Настройки `timing_fit`:

```json
{
  "rewrite_provider_rpm": {
    "gemini": 5.0,
    "openrouter": 5.0,
    "aihubmix": 5.0,
    "polza": 30.0
  },
  "rewrite_provider_cooldown_seconds": 75.0,
  "rewrite_provider_wait_for_rate_limit": true,
  "rewrite_allow_paid_fallback": false
}
```

Если все бесплатные облачные модели недоступны, а платный fallback не разрешён,
для перевода используется Google Translate, а для `timing_fit` используется
`RuleBasedTimingRewriter`.

QA-флаги перевода:

- `translation_llm`: сегмент переведён LLM-провайдером.
- `translation_provider_used`: использован облачный провайдер.
- `translation_provider_gemini`: сработал Gemini.
- `translation_provider_openrouter`: сработал OpenRouter.
- `translation_provider_aihubmix`: сработал AIHubMix.
- `translation_provider_polza`: сработал Polza.ai.
- `translation_provider_neuroapi`: сработал NeuroAPI.
- `translation_google_fallback`: сегмент переведён резервным Google Translate.

QA-флаги `timing_fit`:

- `rewrite_provider_used`: использован облачный провайдер.
- `rewrite_fallback_used`: был переход на fallback.
- `rewrite_provider_failed`: один из провайдеров не дал полезный ответ.
- `rewrite_provider_quota_limited`: провайдер получил 429/503/timeout.
- `rewrite_provider_cooldown`: провайдер временно пропущен из-за cooldown.
- `rewrite_provider_rate_limited`: роутер сделал паузу перед запросом по RPM.
- `rewrite_provider_skipped`: провайдер временно пропущен.
- `rewrite_provider_gemini`: сработал Gemini.
- `rewrite_provider_openrouter`: сработал OpenRouter.
- `rewrite_provider_aihubmix`: сработал AIHubMix.
- `rewrite_provider_polza`: сработал Polza.ai.
- `rewrite_provider_neuroapi`: сработал NeuroAPI.
- `rewrite_provider_rule_based`: сработал локальный fallback.
