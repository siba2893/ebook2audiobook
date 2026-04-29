"""
Disk-backed session metadata store.

Each session gets a small JSON file at:
  <repo_root>/run/__sessions/<session_id>/session_meta.json

This allows the backend to survive restarts and offer resume.
It is intentionally separate from lib/core.py's blocks_current.json.
"""

import json
import os
from typing import Any

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SESSIONS_DIR = os.path.join(_ROOT, "run", "__sessions")

# Keys from ConversionSettings saved into metadata
_SETTINGS_KEYS = (
    "language", "voice_path", "tts_engine", "device",
    "output_format", "xtts_speed", "xtts_temperature",
)


def _meta_path(session_id: str) -> str:
    return os.path.join(_SESSIONS_DIR, session_id, "session_meta.json")


def save(session_id: str, data: dict[str, Any]) -> None:
    """Write (or overwrite) session metadata to disk."""
    path = _meta_path(session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[session_store] save() error for {session_id}: {e}")


def load(session_id: str) -> dict[str, Any] | None:
    """Load session metadata from disk. Returns None if not found."""
    path = _meta_path(session_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[session_store] load() error for {session_id}: {e}")
        return None


def all_sessions() -> list[dict[str, Any]]:
    """Return metadata for all persisted sessions, sorted newest-first."""
    if not os.path.isdir(_SESSIONS_DIR):
        return []
    results = []
    for entry in os.scandir(_SESSIONS_DIR):
        if not entry.is_dir():
            continue
        meta_file = os.path.join(entry.path, "session_meta.json")
        if not os.path.exists(meta_file):
            continue
        try:
            with open(meta_file, encoding="utf-8") as f:
                data = json.load(f)
            results.append(data)
        except Exception:
            continue
    # Sort newest first by mtime of the meta file
    results.sort(
        key=lambda d: os.path.getmtime(
            os.path.join(_SESSIONS_DIR, d["session_id"], "session_meta.json")
        ),
        reverse=True,
    )
    return results
