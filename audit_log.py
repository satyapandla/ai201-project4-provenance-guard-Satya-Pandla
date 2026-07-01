"""
Structured audit log for Provenance Guard.
Uses a JSON file as the store — simple, inspectable, no extra setup.
Switch to SQLite later if you want queryability; not needed for this project's scale.
"""

import json
import os
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "audit_log.json")


def _read_all() -> list:
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _write_all(entries: list) -> None:
    with open(LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2)


def append_log(entry: dict) -> None:
    """Adds a timestamped entry to the audit log."""
    entry = dict(entry)  # don't mutate caller's dict
    entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    entries = _read_all()
    entries.append(entry)
    _write_all(entries)


def get_log(limit: int = 50) -> list:
    """Returns the most recent `limit` entries, newest first."""
    entries = _read_all()
    return list(reversed(entries))[:limit]


def find_by_content_id(content_id: str) -> dict | None:
    """Finds the most recent entry matching a content_id (used by /appeal in M5)."""
    for entry in reversed(_read_all()):
        if entry.get("content_id") == content_id:
            return entry
    return None