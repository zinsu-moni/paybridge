from __future__ import annotations

from typing import Any, Dict, Optional

from .idempotency_store import (
    FileIdempotencyStore,
    IdempotencyStore,
    InMemoryIdempotencyStore,
)


class IdempotencyTracker:
    """Compatibility wrapper over the storage-backed idempotency store."""

    def __init__(
        self,
        ttl_seconds: int = 3600,
        storage: Optional[IdempotencyStore] = None,
        storage_path: Optional[str] = None,
    ):
        self.ttl_seconds = ttl_seconds
        if storage is not None:
            self._store = storage
        elif storage_path:
            self._store = FileIdempotencyStore(storage_path, ttl_seconds=ttl_seconds)
        else:
            self._store = InMemoryIdempotencyStore(ttl_seconds=ttl_seconds)

    def generate_key(self) -> str:
        return self._store.generate_key()

    def start_request(self, key: str, provider_name: str, endpoint: str) -> bool:
        return self._store.start_request(key, provider_name, endpoint)

    def record_response(self, key: str, response: Any):
        self._store.record_response(key, response)

    def record_error(self, key: str, error: Exception):
        self._store.record_error(key, error)

    def get_cached_response(self, key: str) -> Optional[Any]:
        return self._store.get_cached_response(key)

    def _cleanup_expired(self):
        self._store.cleanup_expired()

    def get_stats(self) -> Dict[str, Any]:
        return self._store.get_stats()