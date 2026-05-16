from __future__ import annotations

import json
import os
from typing import Any, Dict


class ContextStore:
    """Simple JSON-backed context store using the OpenClaw workspace directory."""

    def __init__(self, workspace_root: str | None = None) -> None:
        self._workspace_root = workspace_root or os.getenv("OPENCLAW_WORKSPACE", "/tmp/openclaw")
        self._path = os.path.join(self._workspace_root, "context_store.json")
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                self._data = json.load(handle)
        except Exception:
            self._data = {}

    def _save(self) -> None:
        os.makedirs(self._workspace_root, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2, sort_keys=True)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def append(self, key: str, value: Any) -> None:
        items = self._data.get(key, [])
        if not isinstance(items, list):
            items = [items]
        items.append(value)
        self._data[key] = items
        self._save()
