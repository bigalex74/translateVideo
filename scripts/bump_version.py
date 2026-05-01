#!/usr/bin/env python3
"""Обновление версии проекта по правилам SemVer.

Использование:
    python3 scripts/bump_version.py patch     # X.Y.Z -> X.Y.(Z+1)
    python3 scripts/bump_version.py minor     # X.Y.Z -> X.(Y+1).0
    python3 scripts/bump_version.py major     # X.Y.Z -> (X+1).0.0
    python3 scripts/bump_version.py 1.2.3     # явная версия

Правила SemVer при bump:
  major -> minor и patch сбрасываются в 0
  minor -> patch сбрасывается в 0
"""

import re
import sys
from datetime import datetime
from pathlib import Path

KEYWORDS = ("major", "minor", "patch")
ROOT = Path(__file__).resolve().parent.parent
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _read_current_version() -> str:
    raw = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if any(m in raw for m in ("<<<<<<", "=======", ">>>>>>")):
        raise SystemExit(
            "ОШИБКА: VERSION содержит конфликт-маркеры git.\n"
            "Разрешите конфликт вручную: echo 'X.Y.Z' > VERSION"
        )
    if raw in KEYWORDS:
        raise SystemExit(
            f"ОШИБКА: VERSION содержит '{raw}' вместо X.Y.Z.\n"
            "Восстановите версию вручную: echo 'X.Y.Z' > VERSION"
        )
    if not SEMVER_RE.match(raw):
        raise SystemExit(
            f"ОШИБКА: VERSION содержит некорректное значение: '{raw}'.\n"
            "Ожидается формат X.Y.Z."
        )
    return raw


def _compute_new_version(current: str, bump: str) -> str:
    """Вычислить следующую SemVer-версию."""
    if bump not in KEYWORDS:
        if not SEMVER_RE.match(bump):
            raise SystemExit(
                f"ОШИБКА: '{bump}' — недопустимое значение.\n"
                "Используйте: major | minor | patch | X.Y.Z"
            )
        return bump

    major, minor, patch = map(int, current.split("."))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def bump_version(bump_arg: str) -> str:
    current = _read_current_version()
    new_version = _compute_new_version(current, bump_arg)

    if new_version == current:
        print(f"Версия уже {current}, ничего не изменено.")
        return current

    # 1. VERSION
    (ROOT / "VERSION").write_text(new_version + "\n", encoding="utf-8")
    print(f"  VERSION:       {current} -> {new_version}")

    # 2. pyproject.toml
    f = ROOT / "pyproject.toml"
    f.write_text(
        re.sub(r'version\s*=\s*"[^"]+"', f'version = "{new_version}"',
               f.read_text(encoding="utf-8"), count=1),
        encoding="utf-8",
    )
    print(f"  pyproject.toml: {new_version}")

    # 3. src/translate_video/__init__.py
    f = ROOT / "src" / "translate_video" / "__init__.py"
    f.write_text(
        re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{new_version}"',
               f.read_text(encoding="utf-8"), count=1),
        encoding="utf-8",
    )
    print(f"  __init__.py:    {new_version}")

    # 4. change.log — добавить заготовку ТОЛЬКО если записи ещё нет
    changelog = ROOT / "change.log"
    content = changelog.read_text(encoding="utf-8")
    if f"## {new_version}" in content:
        print(f"  change.log:     запись для {new_version} уже существует, пропускаем.")
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        bump_label = {"major": "MAJOR", "minor": "MINOR", "patch": "PATCH"}.get(bump_arg, "RELEASE")
        entry = (
            f"## {new_version} - {today} - {bump_label}\n\n"
            f"- TODO: заполнить описание перед мержем в master.\n\n\n"
        )
        changelog.write_text(
            content.replace("# Журнал Изменений\n", f"# Журнал Изменений\n\n{entry}", 1),
            encoding="utf-8",
        )
        print(f"  change.log:     добавлена заготовка для {new_version} — ЗАПОЛНИТЕ ДО МЕРЖА!")

    return new_version


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    result = bump_version(sys.argv[1])
    print(f"\n✓ Версия: {result}")
