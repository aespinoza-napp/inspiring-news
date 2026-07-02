from pathlib import Path

IGNORE = {
    ".git",
    ".venv",
    "venv",
    ".env",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
}

for path in Path(".").rglob("*"):
    if path.is_file() and not any(part in IGNORE for part in path.parts):
        print(path)