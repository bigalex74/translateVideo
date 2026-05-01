#!/usr/bin/env python3
"""Живое тестирование всех облачных rewriter-провайдеров.

Запуск:
  GEMINI_API_KEY=... OPENROUTER_API_KEY=... python3 scripts/test_cloud_providers.py

Или через .env:
  # Заполни .env и запусти:
  python3 scripts/test_cloud_providers.py
"""

import sys
import os
import time

# Загружаем .env если есть
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from translate_video.core.env import load_env_file
load_env_file()

from translate_video.timing.cloud import (
    GeminiRewriteProvider,
    OpenAICompatibleRewriteProvider,
)
from translate_video.timing.natural import RuleBasedTimingRewriter

# ── Тестовый текст ──────────────────────────────────────────────────────────
# Оригинальный: "The era of manual coding is coming to an end."
SOURCE_TEXT = "The era of manual coding is coming to an end."
TRANSLATED  = "Эпоха ручного программирования подходит к концу."
MAX_CHARS   = 25   # жёсткое ограничение → нужно реальное сжатие

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def test_provider(name: str, provider, label: str) -> bool:
    key_env = {
        "Gemini":    "GEMINI_API_KEY",
        "OpenRouter": "OPENROUTER_API_KEY",
        "AIHubMix":  "AIHUBMIX_API_KEY",
        "Polza":     "POLZA_API_KEY",
    }.get(name, "")

    if key_env and not os.getenv(key_env):
        print(f"  {YELLOW}⚠  {name}: ключ {key_env} не задан — пропуск{RESET}")
        return None  # skip

    model = getattr(provider, "model", "N/A")
    print(f"\n{BOLD}── {name}{RESET} [{label}]")
    print(f"   Модель: {model}")
    print(f"   Текст:  «{TRANSLATED}» ({len(TRANSLATED)} симв.) → цель ≤{MAX_CHARS} симв.")

    t0 = time.time()
    try:
        result = provider.rewrite(
            TRANSLATED,
            source_text=SOURCE_TEXT,
            max_chars=MAX_CHARS,
            attempt=1,
        )
        elapsed = time.time() - t0
        ok = len(result) <= MAX_CHARS + 5  # +5 небольшой допуск
        color = GREEN if ok else YELLOW
        mark = "✅" if ok else "⚠ "
        print(f"   {color}{mark} Результат: «{result}» ({len(result)} симв.) — {elapsed:.1f}с{RESET}")
        return ok
    except Exception as e:
        elapsed = time.time() - t0
        print(f"   {RED}❌ Ошибка ({elapsed:.1f}с): {e}{RESET}")
        return False


def main():
    print(f"\n{BOLD}╔══════════════════════════════════════════════════╗")
    print(f"║   Тест облачных rewriter-провайдеров              ║")
    print(f"╚══════════════════════════════════════════════════╝{RESET}")
    print(f"Исходный EN: «{SOURCE_TEXT}»")
    print(f"Перевод RU:  «{TRANSLATED}» ({len(TRANSLATED)} симв.)")
    print(f"Ограничение: ≤{MAX_CHARS} симв. (нужно реальное сжатие)")

    results = {}

    # 1. Gemini
    if os.getenv("GEMINI_API_KEY"):
        p = GeminiRewriteProvider.from_env()
        results["Gemini"] = test_provider("Gemini", p, p.model)

    # 2. OpenRouter
    if os.getenv("OPENROUTER_API_KEY"):
        p = OpenAICompatibleRewriteProvider.openrouter_from_env()
        results["OpenRouter"] = test_provider("OpenRouter", p, p.model)
    else:
        print(f"\n  {YELLOW}⚠  OpenRouter: OPENROUTER_API_KEY не задан — пропуск{RESET}")
        results["OpenRouter"] = None

    # 3. AIHubMix
    if os.getenv("AIHUBMIX_API_KEY"):
        p = OpenAICompatibleRewriteProvider.aihubmix_from_env()
        results["AIHubMix"] = test_provider("AIHubMix", p, p.model)
    else:
        print(f"\n  {YELLOW}⚠  AIHubMix: AIHUBMIX_API_KEY не задан — пропуск{RESET}")
        results["AIHubMix"] = None

    # 4. Polza
    if os.getenv("POLZA_API_KEY"):
        p = OpenAICompatibleRewriteProvider.polza_from_env()
        results["Polza"] = test_provider("Polza", p, p.model)
    else:
        print(f"\n  {YELLOW}⚠  Polza: POLZA_API_KEY не задан — пропуск{RESET}")
        results["Polza"] = None

    # 5. RuleBased (всегда)
    p = RuleBasedTimingRewriter()
    print(f"\n{BOLD}── RuleBased{RESET} [fallback, без API]")
    print(f"   Текст:  «{TRANSLATED}» ({len(TRANSLATED)} симв.) → цель ≤{MAX_CHARS} симв.")
    result = p.rewrite(TRANSLATED, source_text=SOURCE_TEXT, max_chars=MAX_CHARS, attempt=1)
    ok = result != TRANSLATED
    print(f"   {'✅' if ok else '⚠ '} Результат: «{result}» ({len(result)} симв.)")
    results["RuleBased"] = ok

    # ── Итог ─────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}══ ИТОГ ══════════════════════════════════════════{RESET}")
    # RuleBased — это всегда-доступный fallback, он не LLM.
    # Провалить агрессивный лимит 25 симв. — нормально. Не учитываем в ошибках.
    cloud_results = {k: v for k, v in results.items() if k != "RuleBased"}
    tested   = {k: v for k, v in cloud_results.items() if v is not None}
    skipped  = [k for k, v in cloud_results.items() if v is None]
    passed   = [k for k, v in tested.items() if v]
    failed   = [k for k, v in tested.items() if not v]

    for p_name in passed:
        print(f"  {GREEN}✅ {p_name}{RESET}")
    for f_name in failed:
        print(f"  {RED}❌ {f_name}{RESET}")
    for s_name in skipped:
        print(f"  {YELLOW}⚠  {s_name} (нет ключа){RESET}")

    # RuleBased — только информационно
    rb = results.get("RuleBased")
    if rb:
        print(f"  {GREEN}✅ RuleBased (смог сократить){RESET}")
    else:
        print(f"  {YELLOW}ℹ  RuleBased: не смог сократить до {MAX_CHARS} симв. (ожидаемо при жёстком лимите){RESET}")

    if failed:
        print(f"\n{RED}Есть ошибки в облачных провайдерах!{RESET}")
        sys.exit(1)
    elif not tested:
        print(f"\n{YELLOW}Нет ключей для тестирования облачных провайдеров.{RESET}")
        print("Добавь ключи в .env или экспортируй переменные окружения.")
    else:
        print(f"\n{GREEN}Все проверенные облачные провайдеры работают!{RESET}")


if __name__ == "__main__":
    main()
