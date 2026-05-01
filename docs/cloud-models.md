# Облачные Модели

## Назначение

Облачные модели используются в `timing_fit`, чтобы переформулировать перевод
короче под естественную озвучку. Локальные LLM не используются, потому что они
конфликтуют по ресурсам с FFmpeg и медиа-обработкой.

## Рейтинг Rewriter-Провайдеров

Порядок по умолчанию:

1. `gemini` — основной бесплатный/условно бесплатный провайдер качества.
2. `openrouter` — агрегатор бесплатных моделей, первый fallback.
   Дефолтная модель: `gpt-oss-120b`.
3. `aihubmix` — резервный OpenAI-compatible агрегатор.
   Дефолтная модель: `gemini-3-flash-preview-free`.
4. `polza` — последний fallback, потому что провайдер платный.
   Дефолтная модель: `google/gemini-2.5-flash-lite-preview-09-2025`.
5. `rule_based` — локальный безопасный fallback без сети.

## Переменные Окружения

Создайте локальный `.env` на основе `.env.example` или экспортируйте переменные
на сервере:

```bash
GEMINI_API_KEY=...
GEMINI_REWRITE_MODEL=gemini-2.5-flash-lite

OPENROUTER_API_KEY=...
OPENROUTER_REWRITE_MODEL=gpt-oss-120b
OPENROUTER_SITE_URL=http://localhost:8002
OPENROUTER_APP_NAME=translateVideo

AIHUBMIX_API_KEY=...
AIHUBMIX_BASE_URL=https://aihubmix.com/v1
AIHUBMIX_REWRITE_MODEL=gemini-3-flash-preview-free

POLZA_API_KEY=...
POLZA_BASE_URL=https://api.polza.ai/api/v1
POLZA_REWRITE_MODEL=google/gemini-2.5-flash-lite-preview-09-2025
```

Реальный `.env` игнорируется Git. Не добавляйте ключи в код, тесты,
документацию или issue.

## Поведение Fallback

Если провайдер вернул ошибку, пустой ответ, слишком длинный ответ или ответ без
сокращения, роутер переходит к следующему провайдеру. Если все облачные модели
недоступны, используется `RuleBasedTimingRewriter`.

QA-флаги:

- `rewrite_provider_used`: использован облачный провайдер.
- `rewrite_fallback_used`: был переход на fallback.
- `rewrite_provider_failed`: один из провайдеров не дал полезный ответ.
- `rewrite_provider_gemini`: сработал Gemini.
- `rewrite_provider_openrouter`: сработал OpenRouter.
- `rewrite_provider_aihubmix`: сработал AIHubMix.
- `rewrite_provider_polza`: сработал Polza.ai.
- `rewrite_provider_rule_based`: сработал локальный fallback.
