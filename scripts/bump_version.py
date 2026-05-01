#!/usr/bin/env python3
"""Автоматическое обновление версии проекта.

Использование:
    python3 bump_version.py patch     # 1.2.3 -> 1.2.4
    python3 bump_version.py minor     # 1.2.3 -> 1.3.0
    python3 bump_version.py major     # 1.2.3 -> 2.0.0
    python3 bump_version.py 2.0.0     # явная версия

SemVer-правило: при bump major -> minor и patch сбрасываются в 0,
при bump minor -> patch сбрасывается в 0.
"""

import re
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).parent.parent


def _read_current_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _compute_new_version(current: str, bump: str) -> str:
    """Вычислить новую версию согласно SemVer."""
    if bump not in ("major", "minor", "patch"):
        # Явная версия — валидируем формат
        if not re.fullmatch(r"\d+\.\d+\.\d+", bump):
            raise ValueError(f"Некорректная версия: '{bump}'. Ожидается X.Y.Z или major/minor/patch.")
        return bump

    parts = current.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Текущая версия '{current}' не соответствует X.Y.Z")

    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    # patch
    return f"{major}.{minor}.{patch + 1}"


def bump_version(bump_arg: str) -> str:
    current = _read_current_version()
    new_version = _compute_new_version(current, bump_arg)

    if new_version == current:
        print(f"Версия уже {current}, ничего не изменилось.")
        return current

    # 1. VERSION
    version_file = ROOT / "VERSION"
    version_file.write_text(new_version + "\n", encoding="utf-8")
    print(f"Updated VERSION: {current} -> {new_version}")

    # 2. pyproject.toml
    pyproject_file = ROOT / "pyproject.toml"
    content = pyproject_file.read_text(encoding="utf-8")
    content = re.sub(r'version\s*=\s*"[^"]+"', f'version = "{new_version}"', content, count=1)
    pyproject_file.write_text(content, encoding="utf-8")
    print(f"Updated pyproject.toml: {new_version}")

    # 3. src/translate_video/__init__.py
    init_file = ROOT / "src" / "translate_video" / "__init__.py"
    content = init_file.read_text(encoding="utf-8")
    content = re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{new_version}"', content, count=1)
    init_file.write_text(content, encoding="utf-8")
    print(f"Updated __init__.py: {new_version}")

    # 4. change.log: добавить заготовку в начало после заголовка
    today = datetime.now().strftime("%Y-%m-%d")
    changelog_file = ROOT / "change.log"
    changelog = changelog_file.read_text(encoding="utf-8")
    # Проверяем: не добавлять дубликат если уже есть запись для этой версии
    if f"## {new_version}" in changelog:
        print(f"change.log: запись для {new_version} уже существует, пропускаем.")
    else:
        bump_type = {"major": "MAJOR", "minor": "MINOR", "patch": "PATCH"}.get(bump_arg, "RELEASE")
        new_entry = (
            f"## {new_version} - {today} - {bump_type}\n\n"
            f"- TODO: заполнить перед мержем в master.\n\n\n"
        )
        changelog = changelog.replace("# Журнал Изменений\n", f"# Журнал Изменений\n\n{new_entry}", 1)
        changelog_file.write_text(changelog, encoding="utf-8")
        print(f"Added changelog entry for {new_version}")

    return new_version


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python3 bump_version.py <major|minor|patch|X.Y.Z>")
        sys.exit(1)

    result = bump_version(sys.argv[1])
    print(f"\n✓ Версия: {result}")
