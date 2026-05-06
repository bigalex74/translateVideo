#!/usr/bin/env python3
"""
css_guard.py — Статический анализатор CSS (Designer Agent, Уровень 1).

Проверяет что критические CSS-классы содержат ВСЕ обязательные свойства.
Ловит баги типа R8-И2: добавление только `animation` к `.modal-overlay`
без `position`, `background`, `z-index`.

Использование:
  python3 scripts/css_guard.py ui/src/index.css [ui/src/components/*.css]
  python3 scripts/css_guard.py --summary ui/src/index.css

Exit codes:
  0 — OK
  1 — BLOCKER (отсутствуют обязательные свойства)
  2 — WARNING (частичные нарушения)
"""

import re
import sys
import argparse
from pathlib import Path

# ─── Правила: класс → обязательные свойства ─────────────────────────────────
# Если класс определён — он ДОЛЖЕН содержать эти свойства.
# Если класс не определён вообще — OK (возможно он в другом файле).

REQUIRED_PROPS: dict[str, list[str]] = {
    # Модальные overlays — D-AP-01 (R8-ИЮН-2 bug)
    '.modal-overlay': ['position', 'background', 'z-index', 'display'],
    '.modal-box':     ['background', 'border-radius'],

    # Toast/уведомления — должны быть позиционированы
    '.completion-toast': ['position', 'z-index'],

    # Dashboard overlay — drag-and-drop
    '.dashboard-dnd-overlay': ['position', 'z-index'],
}

# Классы, которые ЗАПРЕЩЕНЫ к добавлению только с animation/transition
# без layout-свойств (антипаттерн D-AP-02)
ANIMATION_ONLY_FORBIDDEN: list[str] = [
    '.modal-overlay',
    '.dashboard-dnd-overlay',
    '.completion-toast',
    '.running-overlay',
]

# Допустимый диапазон z-index по слоям
Z_INDEX_LAYERS = {
    'content':  (0, 99),
    'sticky':   (100, 199),
    'dropdown': (200, 999),
    'modal':    (1000, 1099),
    'toast':    (1100, 1999),
    'debug':    (9000, 9999),  # ЗАПРЕЩЕНО в prod
}

LAYOUT_PROPS = {'position', 'display', 'flex', 'grid', 'float', 'width', 'height', 'inset', 'top', 'left', 'right', 'bottom'}


def parse_css_blocks(content: str) -> dict[str, dict[str, str]]:
    """Парсит CSS и возвращает {selector: {prop: value}}."""
    # Убираем комментарии
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Убираем @keyframes, @media и другие at-rules (упрощённо)
    content = re.sub(r'@[\w-]+[^{]*\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', '', content, flags=re.DOTALL)

    blocks: dict[str, dict[str, str]] = {}

    for m in re.finditer(r'([^{};@]+)\{([^}]*)\}', content):
        selectors_raw = m.group(1).strip()
        props_raw = m.group(2)

        # Парсим свойства
        props: dict[str, str] = {}
        for decl in props_raw.split(';'):
            decl = decl.strip()
            if ':' in decl:
                prop, _, val = decl.partition(':')
                props[prop.strip().lstrip('-')] = val.strip()
            elif decl:
                props[decl] = ''

        # Разбиваем составные селекторы
        for selector in selectors_raw.split(','):
            selector = selector.strip()
            if selector:
                if selector not in blocks:
                    blocks[selector] = {}
                blocks[selector].update(props)

    return blocks


def check_required_props(
    all_blocks: dict[str, dict[str, str]]
) -> tuple[list[str], list[str]]:
    """Проверяет обязательные свойства. Возвращает (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    for selector, required in REQUIRED_PROPS.items():
        # Ищем все блоки, содержащие этот selector (точное совпадение или с медиа-суффиксом)
        matching = {k: v for k, v in all_blocks.items()
                    if k == selector or k.endswith(' ' + selector)}

        if not matching:
            # Класс не определён в этих файлах — не ошибка
            continue

        # Объединяем все свойства из всех блоков с этим селектором
        merged: dict[str, str] = {}
        for props in matching.values():
            merged.update(props)

        missing = [p for p in required if p not in merged]
        if missing:
            errors.append(
                f"BLOCKER [{selector}]: отсутствуют обязательные свойства: "
                f"{', '.join(missing)}"
            )

    return errors, warnings


def check_animation_only(
    all_blocks: dict[str, dict[str, str]]
) -> list[str]:
    """Ищет классы где есть animation/transition, но нет layout-свойств."""
    warnings: list[str] = []

    for selector in ANIMATION_ONLY_FORBIDDEN:
        matching = {k: v for k, v in all_blocks.items() if k == selector}
        for sel, props in matching.items():
            has_anim = any(p in props for p in ('animation', 'transition'))
            has_layout = any(p in props for p in LAYOUT_PROPS)
            if has_anim and not has_layout:
                warnings.append(
                    f"WARN [{selector}]: содержит animation/transition но НЕТ layout-свойств "
                    f"({', '.join(LAYOUT_PROPS & set(props.keys()) or {'?'})}). "
                    f"D-AP-02: это может ломать позиционирование."
                )

    return warnings


def check_z_index(all_blocks: dict[str, dict[str, str]]) -> list[str]:
    """Проверяет что z-index укладывается в допустимые слои."""
    warnings: list[str] = []
    # Известные исключения: PWA splash использует z-index:9999 намеренно
    KNOWN_HIGH_Z: set[str] = {'#pwa-splash', '#pwa-splash.hidden'}
    for selector, props in all_blocks.items():
        if 'z-index' in props and selector not in KNOWN_HIGH_Z:
            try:
                z = int(props['z-index'])
                if z >= 9000:
                    warnings.append(
                        f"WARN [{selector}]: z-index={z} в зоне DEBUG/9000+ — "
                        f"допустимо только в dev-инструментах"
                    )
            except ValueError:
                pass  # auto, inherit и т.д. — OK
    return warnings


def check_files(files: list[Path]) -> tuple[list[str], list[str]]:
    """Запускает все проверки по всем файлам."""
    all_blocks: dict[str, dict[str, str]] = {}

    for path in files:
        try:
            content = path.read_text(encoding='utf-8')
            blocks = parse_css_blocks(content)
            for sel, props in blocks.items():
                if sel not in all_blocks:
                    all_blocks[sel] = {}
                all_blocks[sel].update(props)
        except Exception as e:
            print(f"⚠️  Не удалось прочитать {path}: {e}", file=sys.stderr)

    errors: list[str] = []
    warnings: list[str] = []

    e, w = check_required_props(all_blocks)
    errors.extend(e)
    warnings.extend(w)

    warnings.extend(check_animation_only(all_blocks))
    warnings.extend(check_z_index(all_blocks))

    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description='CSS Guard — static CSS analyzer')
    parser.add_argument('files', nargs='+', help='CSS files to analyze')
    parser.add_argument('--summary', action='store_true', help='One-line summary output')
    parser.add_argument('--strict', action='store_true', help='Treat warnings as errors')
    args = parser.parse_args()

    paths = []
    for pattern in args.files:
        p = Path(pattern)
        if p.is_file():
            paths.append(p)
        else:
            # glob support
            parent = p.parent if p.parent != Path('.') else Path('.')
            paths.extend(parent.glob(p.name))

    if not paths:
        print("❌ Файлы не найдены", file=sys.stderr)
        sys.exit(1)

    errors, warnings = check_files(paths)

    if args.summary:
        status = '✅ OK' if not errors else '❌ FAIL'
        print(f"{status} | {len(paths)} файлов | {len(errors)} BLOCKER | {len(warnings)} WARN")
        sys.exit(1 if errors else (2 if warnings and args.strict else 0))

    print(f"🛡  CSS Guard — проверка {len(paths)} файл(ов)")
    print(f"   Классов проверено: {len(REQUIRED_PROPS)}")
    print()

    if errors:
        print("🚨 BLOCKER:")
        for e in errors:
            print(f"  {e}")
        print()

    if warnings:
        print("⚠️  WARNING:")
        for w in warnings:
            print(f"  {w}")
        print()

    if not errors and not warnings:
        print("✅ CSS в порядке — все обязательные свойства присутствуют")
    elif not errors:
        print("⚠️  Предупреждения есть, BLOCKER-ошибок нет")

    sys.exit(1 if errors else (2 if warnings and args.strict else 0))


if __name__ == '__main__':
    main()
