#!/usr/bin/env python3
"""
Skill Modernizer — реальный тюнинг AGENT.md всех агентов после каждой итерации.

Принцип: каждый агент после раунда должен стать лучшей версией себя.
Скрипт:
1. Читает что изменилось в коде (git diff последнего коммита)
2. Определяет новые паттерны/уроки по категориям
3. Дописывает секцию уроков в AGENT.md КАЖДОГО агента
4. Обновляет порог тестов в continuous-improvement/SKILL.md
5. Обновляет собственный AGENT.md (рефлексия)
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

# ── Пути ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
AGENTS_DIR = ROOT / ".agents"
SKILL_MD = Path("/home/user/.gemini/skills/continuous-improvement/SKILL.md")
SM_LOG = AGENTS_DIR / "skill-modernizer" / "modernizer-log.md"
SM_AGENT = AGENTS_DIR / "skill-modernizer" / "AGENT.md"
LESSONS_MD = AGENTS_DIR / "LESSONS.md"  # Канал 3: session-start читает этот файл
KI_ARTIFACT = Path("/home/user/.gemini/antigravity/knowledge/translateVideo/artifacts/project_overview.md")
KI_METADATA = Path("/home/user/.gemini/antigravity/knowledge/translateVideo/metadata.json")

TODAY = date.today().isoformat()


def run(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=ROOT)
    return result.stdout.strip()


# ── Сбор данных о раунде ──────────────────────────────────────────────

def get_version() -> str:
    return (ROOT / "VERSION").read_text().strip()


def get_test_count() -> int:
    """Запускаем тесты и считаем."""
    out = run("PYTHONPATH=src python3 -m unittest discover -s tests -q 2>&1 | grep 'Ran '")
    for part in out.split():
        if part.isdigit():
            return int(part)
    return 0


def get_last_commit_info() -> dict:
    """Информация о последнем коммите."""
    msg = run("git log -1 --pretty=format:'%s'")
    diff_stat = run("git log -1 --stat --pretty=format:'' | tail -1")
    files_changed = run("git diff HEAD~1 HEAD --name-only 2>/dev/null || git show --name-only --pretty=format:'' HEAD")
    return {"message": msg, "stat": diff_stat, "files": files_changed}


def grep_antipatterns() -> dict:
    """Grep антипаттернов в коде."""
    return {
        "utcnow": run("grep -rn 'utcnow' src/ --include='*.py' 2>/dev/null | grep -v test | wc -l"),
        "shell_true": run("grep -rn 'shell=True' src/ --include='*.py' 2>/dev/null | grep -v test | wc -l"),
        "bare_except": run("grep -rn 'except:$' src/ --include='*.py' 2>/dev/null | grep -v test | wc -l"),
        "hardcoded_secrets": run(
            "grep -rn 'password\\s*=\\|secret\\s*=' src/ --include='*.py' 2>/dev/null "
            "| grep -v 'os\\.getenv\\|test_\\|#' | wc -l"
        ),
        "ws_auth_missing": run(
            "grep -n '@router.websocket' src/translate_video/api/routes/projects.py 2>/dev/null | wc -l"
        ),
        "js_bundle_kb": run(
            "gzip -c ui/dist/assets/*.js 2>/dev/null | wc -c | awk '{printf \"%.1f\", $1/1024}'"
        ) or "N/A",
        "css_bundle_kb": run(
            "gzip -c ui/dist/assets/*.css 2>/dev/null | wc -c | awk '{printf \"%.1f\", $1/1024}'"
        ) or "N/A",
        "health_ms": run(
            "curl -s -o /dev/null -w '%{time_total}' http://localhost:8002/api/health 2>/dev/null"
        ) or "ERR",
    }


def get_round_lessons(commit: dict, ap: dict, version: str) -> dict[str, list[str]]:
    """
    Определяем уроки раунда по категориям агентов.
    Возвращает dict: agent_name → [список строк урока].
    """
    msg = commit["message"]
    files = commit["files"]

    lessons: dict[str, list[str]] = {name: [] for name in ALL_AGENTS}

    # ── Backend ────────────────────────────────────────────────────────
    if any(k in files for k in ["routes/", "middleware/", "core/"]):
        if "rate_limit" in files:
            lessons["backend"].append(
                f"[{version}] RateLimitMiddleware: lazy import в try/except избегает circular import "
                f"(`from ...metrics import fn` внутри if-блока)"
            )
        if "middleware" in files:
            lessons["backend"].append(
                f"[{version}] Middleware: проверяй что `await call_next(request)` вызывается "
                f"во ВСЕХ путях — иначе 500 без traceback"
            )
    if int(ap["bare_except"] or 0) > 0:
        lessons["backend"].append(
            f"[{version}] AP: найдено {ap['bare_except']} голых `except:` — заменить на `except Exception:`"
        )
    if int(ap["utcnow"] or 0) > 0:
        lessons["backend"].append(
            f"[{version}] AP: datetime.utcnow() устарел → использовать datetime.now(UTC)"
        )

    # ── Frontend ───────────────────────────────────────────────────────
    if any(k in files for k in [".tsx", ".css", "hooks/"]):
        if "WebSocket" in files or "useProjectWebSocket" in files:
            lessons["frontend"].append(
                f"[{version}] WS hook: intentionalCloseRef — отличает намеренный close от ошибки сети. "
                f"code 1000 = сервер завершил нормально → onDone(), нет реконнекта"
            )
            lessons["frontend"].append(
                f"[{version}] WS hook: visibilitychange → немедленный реконнект при возврате вкладки"
            )
        if "drag" in msg.lower() or "drop" in msg.lower() or "Safari" in msg:
            lessons["frontend"].append(
                f"[{version}] Safari drag-and-drop: onDragEnter + e.stopPropagation() ОБЯЗАТЕЛЕН "
                f"(Safari игнорирует drop без preventDefault в DragEnter)"
            )
        if "scroll" in msg.lower() or "mobile" in msg.lower():
            lessons["frontend"].append(
                f"[{version}] Mobile scroll: scrollIntoView только при `'ontouchstart' in window` — "
                f"не мешаем desktop UX"
            )
        if "gap" in msg.lower() or "iOS" in msg or "safari" in msg.lower():
            lessons["frontend"].append(
                f"[{version}] iOS Safari gap fallback: `> * + * {{ margin-left }}` + "
                f"`@supports(gap:10px)` убирает margin на современных"
            )

    # ── Security ───────────────────────────────────────────────────────
    if int(ap["hardcoded_secrets"] or 0) > 0:
        lessons["security"].append(
            f"[{version}] ⚠️ Найдено {ap['hardcoded_secrets']} потенциальных хардкодов секретов → проверить вручную"
        )
    if int(ap["shell_true"] or 0) > 0:
        lessons["security"].append(
            f"[{version}] AP: shell=True в {ap['shell_true']} местах → command injection риск"
        )
    if "auth" in msg.lower() or "rate_limit" in files:
        lessons["security"].append(
            f"[{version}] Rate limit: exemptировать 127.0.0.1/testclient НЕМЕДЛЕННО при создании — "
            f"иначе тесты падают после N-го запроса"
        )

    # ── QA Monitor ─────────────────────────────────────────────────────
    test_count = int(ap.get("test_count", 0))
    if test_count > 0:
        lessons["qa-monitor"].append(
            f"[{version}] Порог тестов: {test_count}. Любой PR не должен снижать этот счётчик"
        )
    if "router" in files or "routes/" in files:
        lessons["qa-monitor"].append(
            f"[{version}] Правило #11: новый routes/X.py → минимум 5 тестов В ТОЙ ЖЕ итерации. "
            f"Не в финальной gate-итерации"
        )
    lessons["qa-monitor"].append(
        f"[{version}] Smoke test новых endpoints после каждого деплоя: "
        f"curl -s http://localhost:8002/api/health + все новые пути"
    )

    # ── Performance ────────────────────────────────────────────────────
    js = ap["js_bundle_kb"]
    css = ap["css_bundle_kb"]
    lessons["performance"].append(
        f"[{version}] Bundle: JS={js} KB gzip, CSS={css} KB gzip. "
        f"Порог: JS < 200 KB. /health: {ap['health_ms']}s"
    )
    if float(js.replace(",", ".")) > 150 if js != "N/A" else False:
        lessons["performance"].append(
            f"[{version}] ⚠️ JS bundle {js} KB — растёт к 200 KB порогу. Рассмотреть code splitting"
        )

    # ── Designer ───────────────────────────────────────────────────────
    if "btn-success" in files or "download" in msg.lower():
        lessons["designer"].append(
            f"[{version}] btn-success: green gradient #16a34a + pulse animation (1 раз). "
            f"Используй для primary CTA (скачать, создать)"
        )
    if "drag-active" in files or "drag" in msg.lower():
        lessons["designer"].append(
            f"[{version}] drag-active: border-color accent + scale(1.01) + box-shadow glow. "
            f"transform: scale нельзя без will-change — добавить will-change: transform"
        )
    if "mobile" in msg.lower() or "480" in msg:
        lessons["designer"].append(
            f"[{version}] Mobile 480px: touch target минимум 44px. "
            f"Проверяй: grep -n 'min-height\\|touch' ui/src/components/*.css"
        )

    # ── UX Designer ───────────────────────────────────────────────────
    if "cta" in msg.lower() or "download" in msg.lower():
        lessons["ux-designer"].append(
            f"[{version}] CTA видимость: completed статус → Download кнопка должна быть "
            f"ЗЕЛЁНОЙ и в области первого экрана (above the fold)"
        )
    if "mobile" in msg.lower():
        lessons["ux-designer"].append(
            f"[{version}] Mobile flow: после выбора файла → форма ДОЛЖНА скроллиться к CTA. "
            f"Иначе пользователь не знает что делать дальше (FBA: Никита)"
        )

    # ── DevOps ────────────────────────────────────────────────────────
    if "metrics" in msg.lower() or "prometheus" in msg.lower():
        lessons["devops"].append(
            f"[{version}] /metrics: доступен на localhost без auth (METRICS_ALLOW_LOCALHOST=1). "
            f"Prometheus scrape: добавь job 'translatevideo' target localhost:8002"
        )
        lessons["devops"].append(
            f"[{version}] /api/metrics alias добавлен для backward compat. "
            f"Оба URL работают, используй /metrics в prometheus.yml"
        )
    lessons["devops"].append(
        f"[{version}] D-RULE-02: после make deploy → "
        f"docker exec --user root video-translator chown -R appuser:appuser /app/runs/"
    )

    # ── System Analyst ────────────────────────────────────────────────
    if "adr" in msg.lower() or "router" in msg.lower():
        lessons["system-analyst"].append(
            f"[{version}] ADR-001: декомпозиция больших роутеров (>1500 строк). "
            f"Фаза 1: export.py | Фаза 2: pipeline | Фаза 3: analytics"
        )

    # ── Tech Writer ───────────────────────────────────────────────────
    lessons["tech-writer"].append(
        f"[{version}] После деплоя: версия в VERSION = версия в RELEASE_NOTES.md = "
        f"версия в продакшн /api/health. Расхождение блокирует round-close"
    )
    if "alias" in msg.lower() or "metrics" in msg.lower():
        lessons["tech-writer"].append(
            f"[{version}] Новый alias endpoint → задокументировать ОБА URL в README/docs"
        )

    # ── CEO ───────────────────────────────────────────────────────────
    lessons["ceo"].append(
        f"[{version}] FBA правило: каждый раунд минимум 5 персон → инсайты → P1 бэклог. "
        f"Без survey round-close блокируется"
    )

    # ── CTO ───────────────────────────────────────────────────────────
    if "reconnect" in msg.lower() or "ws" in msg.lower():
        lessons["cto"].append(
            f"[{version}] WS reliability: exponential backoff [1s..30s], макс 10 попыток. "
            f"visibilitychange → immediate reconnect"
        )
    lessons["cto"].append(
        f"[{version}] Архитектурный принцип: новый роутер = новый файл = ADR запись. "
        f"Монолитный projects.py (>1500 строк) — красный флаг"
    )

    # ── ML Engineer ───────────────────────────────────────────────────
    # ML engineer получает уроки про quality/reliability translation pipeline
    if "segment" in msg.lower() or "translation" in msg.lower():
        lessons["ml-engineer"].append(
            f"[{version}] Segment editor: source_text должен быть виден при редактировании. "
            f"Label 'Оригинал:' помогает переводчику"
        )

    # ── Project Manager ───────────────────────────────────────────────
    lessons["project-manager"].append(
        f"[{version}] Итерация = деплой в прод + 4 агента. "
        f"Раунд = 5 итераций + round-close (8 стратег. агентов) + git push"
    )

    # ── Business Analyst ──────────────────────────────────────────────
    lessons["business-analyst"].append(
        f"[{version}] FBA формат: персона + контекст + тест-сессия + инсайты → P1/P2. "
        f"Минимум 5 персон. Без R{{N}}-survey.md round-close падает"
    )

    # QA Engineer
    lessons["qa-engineer"].append(
        f"[{version}] Правило: тесты пишутся В ТОЙ ЖЕ итерации что и код. "
        f"Отложить на gate-итерацию = нарушение правила #11"
    )

    return lessons


# ── Запись в AGENT.md ──────────────────────────────────────────────────

def append_lessons_to_agent(agent_name: str, version: str, lessons: list[str]) -> bool:
    """Дописывает секцию уроков в конец AGENT.md агента. Возвращает True если что-то добавлено."""
    if not lessons:
        return False

    agent_md = AGENTS_DIR / agent_name / "AGENT.md"
    if not agent_md.exists():
        print(f"  ⚠️  {agent_name}/AGENT.md не найден — пропускаем")
        return False

    content = agent_md.read_text()

    # Проверяем — не добавляли ли уже эту версию
    marker = f"[SM-{version}]"
    if marker in content:
        print(f"  ⏭  {agent_name}: уже обновлён для {version}")
        return False

    section = f"\n## {marker} Уроки раунда | {TODAY}\n\n"
    for lesson in lessons:
        section += f"- {lesson}\n"
    section += f"\n> Обновлено Skill Modernizer | {TODAY} v{version}\n"

    agent_md.write_text(content + section)
    print(f"  ✅ {agent_name}/AGENT.md: +{len(lessons)} урок(а)")
    return True


def update_skill_md(test_count: int, version: str) -> None:
    """Обновляет порог тестов в continuous-improvement/SKILL.md."""
    if not SKILL_MD.exists():
        print(f"  ⚠️  SKILL.md не найден: {SKILL_MD}")
        return

    content = SKILL_MD.read_text()
    import re

    # Паттерн: "**NNN тестов — текущая планка.**" или "**NNN тестов — ..."
    pattern = r'\*\*(\d+) тестов[^*]*\*\*'
    match = re.search(pattern, content)
    if match:
        old_count = int(match.group(1))
        if test_count > old_count:
            old_str = match.group(0)
            new_str = f"**{test_count} тестов — текущая планка.** *({old_count} до v{version})*"
            content = content.replace(old_str, new_str, 1)
            SKILL_MD.write_text(content)
            print(f"  ✅ SKILL.md: тест-порог {old_count} → {test_count}")
        else:
            print(f"  ⏭  SKILL.md: тест-порог уже {old_count}, новый {test_count} — не снижаем")
    else:
        print("  ⚠️  SKILL.md: не найден паттерн порога тестов")


def update_sm_agent_md(version: str, ap: dict, changed_agents: list[str]) -> None:
    """Skill Modernizer обновляет свой собственный AGENT.md — рефлексия."""
    content = SM_AGENT.read_text()
    marker = f"[SM-SELF-{version}]"
    if marker in content:
        print(f"  ⏭  skill-modernizer/AGENT.md: уже обновлён для {version}")
        return

    reflection = f"""
## {marker} Саморефлексия | {TODAY}

### Что я сделал в этом раунде:
- Обновлены AGENT.md: {', '.join(changed_agents) if changed_agents else 'нет изменений'}
- Антипаттерны: utcnow={ap['utcnow']}, shell_true={ap['shell_true']}, bare_except={ap['bare_except']}
- JS bundle: {ap['js_bundle_kb']} KB gzip | /health: {ap['health_ms']}s

### Что улучшить в следующий раз:
- Добавлять более специфичные уроки (не шаблоны) на основе реального git diff
- Проверять что уроки прошлого раунда были реально применены

> Обновлено Skill Modernizer (саморефлексия) | {TODAY} v{version}
"""
    SM_AGENT.write_text(content + reflection)
    print(f"  ✅ skill-modernizer/AGENT.md: саморефлексия добавлена")


def update_modernizer_log(version: str, ap: dict, changed_agents: list[str], test_count: int) -> None:
    """Финальный лог в modernizer-log.md."""
    entry = f"""
## SM — {TODAY} v{version}
```
utcnow: {ap['utcnow']} | shell=True: {ap['shell_true']} | bare_except: {ap['bare_except']}
hardcoded_secrets: {ap['hardcoded_secrets']} | ws_auth: {ap['ws_auth_missing']}
JS gzip: {ap['js_bundle_kb']} KB | CSS gzip: {ap['css_bundle_kb']} KB | /health: {ap['health_ms']}s
tests: {test_count}
Обновлены AGENT.md ({len(changed_agents)}): {', '.join(changed_agents) or 'нет'}
```
### Подпись: Skill Modernizer АПРУV | {TODAY} v{version}
"""
    with open(SM_LOG, "a") as f:
        f.write(entry)
    print(f"  ✅ modernizer-log.md обновлён")


def update_lessons_md(all_lessons: dict, version: str, test_count: int, ap: dict) -> None:
    """
    Канал 3: .agents/LESSONS.md — дистиллированный файл топ-уроков.
    Читается make session-start → попадает в контекст каждой сессии.
    Формат: короткий, по ролям, только самое важное.
    """
    lines = [f"# 🧠 LESSONS — Дистиллированные уроки агентов\n"]
    lines.append(f"> Обновлено Skill Modernizer | {TODAY} v{version} | Тестов: {test_count}\n")
    lines.append(f"> JS={ap['js_bundle_kb']} KB | /health={ap['health_ms']}s | "
                 f"utcnow={ap['utcnow']} shell=True={ap['shell_true']}\n")
    lines.append("")
    lines.append("## Критические правила (читать ВСЕГДА)\n")
    lines.append(f"- **Тестов:** {test_count} — не снижать никогда")
    lines.append("- **D-RULE-02:** после `make deploy` → chown -R appuser:appuser /app/runs/")
    lines.append("- **Правило #11:** новый роутер = тесты В ТОЙ ЖЕ итерации")
    lines.append("- **FBA:** каждый раунд минимум 5 персон → R{N}-survey.md → блокирует round-close")
    lines.append("- **ИДЕМПОТЕНТНОСТЬ:** проверяй EXISTS перед INSERT везде")
    lines.append("")

    # Уроки по ролям — только непустые
    role_labels = {
        "backend": "🔧 Backend", "frontend": "⚛️ Frontend", "security": "🔒 Security",
        "qa-monitor": "🔍 QA", "designer": "🎨 Designer", "ux-designer": "👤 UX",
        "devops": "🚀 DevOps", "cto": "🏗️ CTO/Arch", "performance": "⚡ Performance",
    }
    for agent, label in role_labels.items():
        lessons = all_lessons.get(agent, [])
        if lessons:
            lines.append(f"## {label}")
            for lesson in lessons[:3]:  # топ-3 на роль чтобы не раздувать
                lines.append(f"- {lesson}")
            lines.append("")

    LESSONS_MD.write_text("\n".join(lines))
    print(f"  ✅ .agents/LESSONS.md обновлён ({len([l for l in lines if l.startswith('-')])} правил)")


def update_ki_artifact(version: str, test_count: int, all_lessons: dict, ap: dict) -> None:
    """
    Канал 1: KI (Knowledge Item) — загружается автоматически при КАЖДОМ разговоре.
    Обновляем project_overview.md: версия, тест-порог, топ-уроки раунда.
    """
    import re, json
    if not KI_ARTIFACT.exists():
        print(f"  ⚠️  KI artifact не найден: {KI_ARTIFACT}")
        return

    content = KI_ARTIFACT.read_text()

    # Обновляем шапку версии
    content = re.sub(
        r'> ⚠️ \*\*KI обновлён: [^*]+\*\*',
        f'> ⚠️ **KI обновлён: {TODAY} | v{version} | {test_count} тестов Python**',
        content
    )

    # Собираем топ-уроки для KI (короткий блок)
    top_lessons = []
    for agent in ["backend", "frontend", "security", "qa-monitor", "devops", "cto"]:
        for lesson in all_lessons.get(agent, [])[:1]:  # по 1 на агента
            top_lessons.append(f"- [{agent}] {lesson}")

    # Заменяем или добавляем секцию SM уроков
    sm_section = f"""\n## 🎓 Уроки последнего раунда (SM {TODAY} v{version})

{chr(10).join(top_lessons) if top_lessons else '- Нет новых уроков'}

> Метрики: JS={ap['js_bundle_kb']} KB gzip | tests={test_count} | /health={ap['health_ms']}s
"""
    # Удаляем старую секцию если есть
    content = re.sub(r'\n## 🎓 Уроки последнего раунда.*?(?=\n## |\Z)', '', content, flags=re.DOTALL)
    content = content.rstrip() + "\n" + sm_section

    KI_ARTIFACT.write_text(content)

    # Обновляем metadata.json (summary + updated_at)
    if KI_METADATA.exists():
        try:
            meta = json.loads(KI_METADATA.read_text())
            old_summary = meta.get("summary", "")
            # Обновляем версию и тест-счётчик в summary
            new_summary = re.sub(r'Версия: [\d.]+', f'Версия: {version}', old_summary)
            new_summary = re.sub(r'\d+ unit-тестов', f'{test_count} unit-тестов', new_summary)
            meta["summary"] = new_summary
            meta["updated_at"] = f"{TODAY}T12:00:00+03:00"
            KI_METADATA.write_text(json.dumps(meta, ensure_ascii=False, indent=4))
        except Exception as e:
            print(f"  ⚠️  metadata.json не обновлён: {e}")

    print(f"  ✅ KI artifact обновлён: v{version}, {test_count} тестов, {len(top_lessons)} уроков")


def update_skill_md_lessons(all_lessons: dict, version: str, test_count: int) -> None:
    """
    Канал 2: добавляет секцию 'Уроки раундов' в SKILL.md.
    Читается при триггерах 'сделай N итераций'.
    """
    import re
    if not SKILL_MD.exists():
        return
    content = SKILL_MD.read_text()
    marker = f"SM-SKILL-{version}"
    if marker in content:
        print(f"  ⏭  SKILL.md: уроки для {version} уже добавлены")
        return

    # Собираем только критические уроки для разработки
    dev_lessons = []
    for agent in ["backend", "frontend", "security", "qa-monitor"]:
        for lesson in all_lessons.get(agent, [])[:2]:
            dev_lessons.append(f"- [{agent}] {lesson}")

    if not dev_lessons:
        print(f"  ⏭  SKILL.md: нет уроков для добавления")
        return

    section = f"\n\n<!-- {marker} -->\n## Уроки раунда v{version} ({TODAY})\n\n"
    section += "\n".join(dev_lessons)
    section += f"\n\n> Tests: {test_count} | SM автоматически | {TODAY}\n"

    # Ищем раздел антипаттернов и добавляем перед ним, или в конец
    insert_before = "## Round "
    idx = content.rfind(insert_before)
    if idx > 0:
        content = content[:idx] + section + "\n" + content[idx:]
    else:
        content = content.rstrip() + section

    SKILL_MD.write_text(content)
    print(f"  ✅ SKILL.md: {len(dev_lessons)} уроков добавлено (канал 2)")


# ── Список всех агентов ────────────────────────────────────────────────

ALL_AGENTS = [
    "backend", "frontend", "security", "qa-monitor", "qa-engineer",
    "designer", "ux-designer", "devops", "system-analyst", "tech-writer",
    "ceo", "cto", "ml-engineer", "project-manager", "business-analyst",
    "performance",
]


# ── Точка входа ────────────────────────────────────────────────────────

def main() -> None:
    print("🧠 Skill Modernizer — реальный тюнинг всех агентов")
    print(f"   Дата: {TODAY}")

    version = get_version()
    print(f"   Версия: {version}")

    # Сбор данных
    commit = get_last_commit_info()
    print(f"   Коммит: {commit['message'][:60]}")

    ap = grep_antipatterns()

    # Тест-счётчик (пробуем из лога если тесты долго)
    test_count = 0
    sm_log_content = SM_LOG.read_text() if SM_LOG.exists() else ""
    import re
    m = re.search(r'tests: (\d+)', sm_log_content)
    if m:
        test_count = int(m.group(1))
    # Более свежий из последнего запуска discover
    last_ran = run("PYTHONPATH=src python3 -m unittest discover -s tests -q 2>&1 | grep 'Ran '")
    for part in last_ran.split():
        if part.isdigit():
            test_count = int(part)
            break
    ap["test_count"] = test_count
    print(f"   Тестов: {test_count}")

    # Определяем уроки
    all_lessons = get_round_lessons(commit, ap, version)

    # Обновляем каждый AGENT.md
    print("\n📝 Обновление AGENT.md агентов:")
    changed_agents = []
    for agent_name in ALL_AGENTS:
        lessons = all_lessons.get(agent_name, [])
        if append_lessons_to_agent(agent_name, version, lessons):
            changed_agents.append(agent_name)

    # Обновляем SKILL.md (тест-порог)
    print("\n📊 Канал 2 — SKILL.md (читается при итерациях):")
    if test_count > 0:
        update_skill_md(test_count, version)
    update_skill_md_lessons(all_lessons, version, test_count)

    # Канал 1: KI artifact (читается при КАЖДОМ разговоре)
    print("\n🌐 Канал 1 — KI artifact (авто-загрузка при старте разговора):")
    update_ki_artifact(version, test_count, all_lessons, ap)

    # Канал 3: LESSONS.md (читается session-start)
    print("\n📖 Канал 3 — .agents/LESSONS.md (читается session-start):")
    update_lessons_md(all_lessons, version, test_count, ap)

    # Саморефлексия SM
    print("\n🔄 Саморефлексия Skill Modernizer:")
    update_sm_agent_md(version, ap, changed_agents)

    # Лог
    print("\n📋 Обновление лога:")
    update_modernizer_log(version, ap, changed_agents, test_count)

    print(f"\n✅ Skill Modernizer завершён: {len(changed_agents)}/{len(ALL_AGENTS)} агентов обновлены")
    if changed_agents:
        print(f"   Обновлены: {', '.join(changed_agents)}")
    print(f"\n📡 Каналы доставки уроков:")
    print(f"   KI artifact  → авто при старте разговора (/antigravity/knowledge/)")
    print(f"   SKILL.md     → при триггерах 'сделай N итераций'")
    print(f"   LESSONS.md   → make session-start (начало каждой сессии)")
    print(f"   AGENT.md ×{len(ALL_AGENTS)}  → справочник по ролям (явный просмотр)")


if __name__ == "__main__":
    main()
