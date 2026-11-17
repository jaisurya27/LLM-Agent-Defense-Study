"""Small helpers shared by task selection and the runner."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "preliminary.json"
TASKS_PATH = ROOT / "config" / "tasks.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_env_file(path: Path = ROOT / ".env") -> None:
    """Read KEY=value lines from .env without overriding the real environment."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if value.strip():
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def config_hash() -> str:
    """Fingerprint of everything that defines the experiment."""
    digest = hashlib.sha256()
    for path in (CONFIG_PATH, TASKS_PATH, ROOT / "prompts" / "warning.txt", ROOT / "src" / "defenses.py", ROOT / "src" / "pipeline.py"):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def code_revision() -> str | None:
    """Git commit of the code, with '-dirty' if there are uncommitted changes."""
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "config", "prompts"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        return f"{rev}-dirty" if dirty else rev
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
