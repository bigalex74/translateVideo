import sys
import re
from pathlib import Path

def bump_version(new_version):
    """Обновляет версию во всех нужных файлах."""
    
    root = Path(__file__).parent.parent
    
    # 1. VERSION
    version_file = root / "VERSION"
    version_file.write_text(new_version + "\n", encoding="utf-8")
    print(f"Updated VERSION to {new_version}")

    # 2. pyproject.toml
    pyproject_file = root / "pyproject.toml"
    content = pyproject_file.read_text(encoding="utf-8")
    content = re.sub(r'version\s*=\s*"[^"]+"', f'version = "{new_version}"', content, count=1)
    pyproject_file.write_text(content, encoding="utf-8")
    print(f"Updated pyproject.toml to {new_version}")

    # 3. src/translate_video/__init__.py
    init_file = root / "src" / "translate_video" / "__init__.py"
    content = init_file.read_text(encoding="utf-8")
    content = re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{new_version}"', content, count=1)
    init_file.write_text(content, encoding="utf-8")
    print(f"Updated __init__.py to {new_version}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 bump_version.py <new_version>")
        sys.exit(1)
        
    bump_version(sys.argv[1])
