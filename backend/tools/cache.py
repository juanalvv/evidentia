import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Optional


class AsyncCache:
    """A small async-safe in-memory cache for academic wrapper results."""

    def __init__(self):
        self._store: Dict[str, tuple[float, Any, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value, ttl = item
            if expires_at and expires_at < time.time():
                self._store.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: Any, ttl: Optional[float] = 3600) -> None:
        expires_at = time.time() + ttl if ttl is not None else 0
        async with self._lock:
            self._store[key] = (expires_at, value, ttl)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    async def memoize(
        self,
        key: str,
        fetcher: Callable[[], Awaitable[Any]],
        ttl: Optional[float] = 3600,
        cache_errors: bool = False,
    ) -> Any:
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await fetcher()
        if cache_errors or (isinstance(value, dict) and value.get("success") is True):
            await self.set(key, value, ttl)
        return value


def make_cache_key(*parts: Optional[str]) -> str:
    normalized_parts = [part.strip().replace(" ", "_") for part in parts if part]
    return ":".join(normalized_parts)


cache = AsyncCache()
