"""Durable cursor + incident dedupe (FR-W4, FR-L3).

Two tiny pieces of state survive poller restarts. Firestore by default to avoid
standing up a database; a local-file backend keeps tests/dev offline.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import get_settings

_LOCAL_PATH = Path(".cursor_state.json")


class StateStore:
    def get_cursor(self) -> datetime | None: ...
    def set_cursor(self, ts: datetime) -> None: ...
    def seen(self, span_id: str) -> bool: ...
    def mark_seen(self, span_id: str) -> None: ...


class LocalState(StateStore):
    def __init__(self, path: Path = _LOCAL_PATH) -> None:
        self.path = path
        self._data = json.loads(path.read_text()) if path.exists() else {"seen": []}

    def _flush(self) -> None:
        self.path.write_text(json.dumps(self._data))

    def get_cursor(self) -> datetime | None:
        c = self._data.get("cursor")
        return datetime.fromisoformat(c) if c else None

    def set_cursor(self, ts: datetime) -> None:
        self._data["cursor"] = ts.isoformat()
        self._flush()

    def seen(self, span_id: str) -> bool:
        return span_id in self._data["seen"]

    def mark_seen(self, span_id: str) -> None:
        self._data["seen"] = ([*self._data["seen"], span_id])[-500:]
        self._flush()


class FirestoreState(StateStore):
    def __init__(self, collection: str, doc_id: str = "watcher") -> None:
        from google.cloud import firestore  # imported lazily; not needed for tests

        self._doc = firestore.Client().collection(collection).document(doc_id)

    def _get(self) -> dict:
        snap = self._doc.get()
        return snap.to_dict() or {} if snap.exists else {}

    def get_cursor(self) -> datetime | None:
        c = self._get().get("cursor")
        return datetime.fromisoformat(c) if c else None

    def set_cursor(self, ts: datetime) -> None:
        self._doc.set({"cursor": ts.isoformat()}, merge=True)

    def seen(self, span_id: str) -> bool:
        return span_id in self._get().get("seen", [])

    def mark_seen(self, span_id: str) -> None:
        seen = ([*self._get().get("seen", []), span_id])[-500:]
        self._doc.set({"seen": seen}, merge=True)


_STATE_STORE: StateStore | None = None

def get_state() -> StateStore:
    global _STATE_STORE
    if _STATE_STORE is not None:
        return _STATE_STORE
    s = get_settings()
    if s.state_backend == "firestore":
        _STATE_STORE = FirestoreState(s.firestore_collection)
    else:
        _STATE_STORE = LocalState()
    return _STATE_STORE
