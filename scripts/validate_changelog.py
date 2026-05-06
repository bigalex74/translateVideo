#!/usr/bin/env python3
"""
validate_changelog.py — Валидатор журнала изменений (change.log).

Правила:
  - Каждая версия должна начинаться с "## X.Y.Z - YYYY-MM-DD - TYPE - TVIDEO-XXX"
  - TYPE для записей >= 1.24.0: FEAT | FIX | REFACTOR | CHORE | TEST | DOCS | HOTFIX | RELEASE
  - TYPE для legacy записей < 1.24.0: дополнительно допускаются MINOR | PATCH | MAJOR | SEMVER
  - Версии должны идти в убывающем порядке
  - Нет дублирующихся версий
  - Нет пропущенных minor/patch-версий (например 1.62→1.73 = пропуск 1.63..1.72)
  - Каждая запись должна иметь хотя бы 1 строку описания

Использование:
  python3 scripts/validate_changelog.py [--fix]  # --fix применяет автоисправления

Exit codes:
  0 — OK
  1 — найдены ошибки (BLOCKER)
  2 — только предупреждения (WARNING)
"""

import re
import sys
import argparse
from datetime import datetime

# ─── Паттерны ───────────────────────────────────────────────────────────────

HEADER_RE = re.compile(
    r'^## (\d+\.\d+\.\d+) - (\d{4}-\d{2}-\d{2}) - ([A-Z]+) - (TVIDEO-[\w-]+)$',
    re.MULTILINE
)

# Актуальные типы (с версии 1.24.0+)
MODERN_TYPES = {'FEAT', 'FIX', 'REFACTOR', 'CHORE', 'TEST', 'DOCS', 'HOTFIX', 'RELEASE'}

# Legacy типы (до введения Conventional Commits, версии < 1.24.0)
LEGACY_TYPES = {'MINOR', 'PATCH', 'MAJOR', 'SEMVER'}

# Версия, с которой введены modern types
MODERN_TYPES_SINCE = (1, 24, 0)


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split('.'))


def is_legacy(version: str) -> bool:
    """Версия до введения современных типов."""
    return parse_version(version) < MODERN_TYPES_SINCE


def check_gaps(versions: list[str]) -> list[str]:
    """Ищет пропущенные minor и patch версии.

    Логика:
      - Берём все версии в порядке убывания (как они идут в файле)
      - Для каждой пары соседних версий проверяем: если major одинаков,
        то между minor должна быть разница ровно в 1 (иначе пропуск).
      - Patch версии (X.Y.1, X.Y.2...) могут идти внутри одного minor —
        если между ними пропуск, тоже предупреждаем.
      - Прыжок major (1.x -> 2.x) считается нормальным.
    """
    gaps: list[str] = []
    # Сортируем по убыванию версии (как и в файле)
    parsed = [(v, parse_version(v)) for v in versions]

    for i in range(len(parsed) - 1):
        v_curr, (maj_c, min_c, pat_c) = parsed[i]
        v_next, (maj_n, min_n, pat_n) = parsed[i + 1]

        # Прыжок major — ок
        if maj_c != maj_n:
            continue

        if min_c == min_n:
            # Тот же minor — проверяем patch
            if pat_c - pat_n > 1:
                missing = [f"{maj_c}.{min_c}.{p}" for p in range(pat_n + 1, pat_c)]
                gaps.append(
                    f"WARN: Пропущены patch-версии между {v_next} и {v_curr}: "
                    f"{', '.join(missing)}"
                )
        else:
            # Разные minor — должна быть разница 1
            if min_c - min_n > 1:
                missing_minors = []
                for m in range(min_n + 1, min_c):
                    missing_minors.append(f"{maj_c}.{m}.0")
                gaps.append(
                    f"WARN: Пропущены версии между {v_next} и {v_curr}: "
                    f"{', '.join(missing_minors)}"
                )
            # Если minor увеличился на 1, но patch у curr > 0 — предыдущие patch тоже ок

    return gaps


def validate(content: str, strict: bool = False) -> tuple[list[str], list[str]]:
    """
    Возвращает (errors, warnings).
    errors   — BLOCKER, требуют исправления
    warnings — информационные
    """
    errors: list[str] = []
    warnings: list[str] = []

    headers = list(HEADER_RE.finditer(content))

    if not headers:
        errors.append("BLOCKER: В файле нет ни одной записи формата '## X.Y.Z - YYYY-MM-DD - TYPE - TVIDEO-XXX'")
        return errors, warnings

    seen_versions: dict[str, int] = {}
    versions_ordered: list[str] = []

    for i, m in enumerate(headers):
        version = m.group(1)
        date_str = m.group(2)
        typ = m.group(3)
        ticket = m.group(4)
        lineno = content[:m.start()].count('\n') + 1

        # ── Дублирующиеся версии ──────────────────────────────────────────
        if version in seen_versions:
            errors.append(
                f"BLOCKER: Дубль версии {version} "
                f"(строки ~{seen_versions[version]} и ~{lineno})"
            )
        else:
            seen_versions[version] = lineno

        versions_ordered.append(version)

        # ── Валидность типа ───────────────────────────────────────────────
        if is_legacy(version):
            allowed = MODERN_TYPES | LEGACY_TYPES
        else:
            allowed = MODERN_TYPES

        if typ not in allowed:
            if is_legacy(version):
                errors.append(
                    f"BLOCKER: Невалидный тип '{typ}' в версии {version} (строка ~{lineno}). "
                    f"Допустимо для legacy: {sorted(allowed)}"
                )
            else:
                errors.append(
                    f"BLOCKER: Невалидный тип '{typ}' в версии {version} (строка ~{lineno}). "
                    f"Допустимо: {sorted(MODERN_TYPES)}"
                )

        # ── Формат даты ───────────────────────────────────────────────────
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            errors.append(f"BLOCKER: Неверный формат даты '{date_str}' в версии {version} (строка ~{lineno})")

        # ── Описание после заголовка (хотя бы 1 непустая строка) ─────────
        end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        block = content[m.end():end].strip()
        if not block:
            warnings.append(f"WARN: Версия {version} (строка ~{lineno}) не имеет описания")

    # ── Порядок версий (убывающий) ────────────────────────────────────────
    for i in range(len(versions_ordered) - 1):
        v_curr = versions_ordered[i]
        v_next = versions_ordered[i + 1]
        try:
            if parse_version(v_curr) < parse_version(v_next):
                errors.append(
                    f"BLOCKER: Неверный порядок версий: {v_curr} стоит перед {v_next} "
                    f"(версии должны убывать)"
                )
        except Exception:
            pass

    # ── Пропущенные версии ────────────────────────────────────────────────
    unique_ordered = list(dict.fromkeys(versions_ordered))  # убираем дубли для gap-check
    for gap_warn in check_gaps(unique_ordered):
        warnings.append(gap_warn)

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description='Validate change.log')
    parser.add_argument('file', nargs='?', default='change.log', help='Path to changelog file')
    parser.add_argument('--strict', action='store_true', help='Treat warnings as errors')
    parser.add_argument('--summary', action='store_true', help='Only print summary line')
    parser.add_argument('--gaps-only', action='store_true', help='Only check for missing versions')
    args = parser.parse_args()

    try:
        with open(args.file, encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ Файл не найден: {args.file}", file=sys.stderr)
        sys.exit(1)

    errors, warnings = validate(content, strict=args.strict)

    headers = list(HEADER_RE.finditer(content))
    versions = [m.group(1) for m in headers]

    if args.gaps_only:
        # Только проверка пропущенных версий
        unique = list(dict.fromkeys(versions))
        gaps = check_gaps(unique)
        if gaps:
            print(f"⚠️  Найдено пропущенных диапазонов: {len(gaps)}")
            for g in gaps:
                print(f"  {g}")
            sys.exit(2)
        else:
            print(f"✅ Пропущенных версий нет ({len(versions)} записей)")
            sys.exit(0)

    if args.summary:
        gap_count = len([w for w in (validate(open(args.file, encoding='utf-8').read())[1]) if 'Пропущены' in w])
        status = '✅ OK' if not errors else '❌ FAIL'
        gap_str = f" | ⚠️ пропусков: {gap_count}" if gap_count else ''
        print(f"{status} | {len(headers)} версий | {len(errors)} ошибок | {len(warnings)} предупреждений{gap_str}")
        sys.exit(1 if errors else (2 if warnings else 0))

    print(f"📋 Журнал изменений: {args.file}")
    print(f"   Записей: {len(headers)}")
    if versions:
        print(f"   Диапазон: {versions[-1]} → {versions[0]}")
    print()

    if errors:
        print("🚨 ОШИБКИ (BLOCKER):")
        for e in errors:
            print(f"  {e}")
        print()

    if warnings:
        print("⚠️  ПРЕДУПРЕЖДЕНИЯ:")
        for w in warnings:
            print(f"  {w}")
        print()

    if not errors and not warnings:
        print("✅ Журнал изменений валиден")
    elif not errors:
        print("⚠️  Предупреждения есть, но BLOCKER-ошибок нет")

    sys.exit(1 if errors else (2 if warnings and args.strict else 0))


if __name__ == '__main__':
    main()
