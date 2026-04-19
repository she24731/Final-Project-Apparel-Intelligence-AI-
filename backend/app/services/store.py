from __future__ import annotations

import threading
from collections.abc import Iterable

from app.schemas.wardrobe import GarmentRecord


class InMemoryWardrobeStore:
    """Process-local store for demo reliability."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, GarmentRecord] = {}

    def upsert(self, garment: GarmentRecord) -> None:
        with self._lock:
            self._items[garment.id] = garment

    def get(self, garment_id: str) -> GarmentRecord | None:
        with self._lock:
            return self._items.get(garment_id)

    def get_many(self, ids: Iterable[str]) -> list[GarmentRecord]:
        out: list[GarmentRecord] = []
        with self._lock:
            for gid in ids:
                g = self._items.get(gid)
                if g:
                    out.append(g)
        return out

    def delete(self, garment_id: str) -> GarmentRecord | None:
        with self._lock:
            return self._items.pop(garment_id, None)

    def all(self) -> list[GarmentRecord]:
        with self._lock:
            return list(self._items.values())


_store = InMemoryWardrobeStore()


def get_store() -> InMemoryWardrobeStore:
    return _store
