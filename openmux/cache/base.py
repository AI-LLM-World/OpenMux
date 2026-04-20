"""Cache base interface and a simple in-memory cache implementation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict
import asyncio
import json
import hashlib


def make_key(payload: Any) -> str:
    try:
        js = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        js = repr(payload)
    return hashlib.sha256(js.encode("utf-8")).hexdigest()


class BaseCache(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def invalidate(self, key: str) -> None:
        raise NotImplementedError


class MemoryCache(BaseCache):
    def __init__(self):
        self._store: Dict[str, tuple[float, str]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expiry, value = item
            if expiry != 0 and __import__("time").time() > expiry:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        expiry = 0
        if ttl and ttl > 0:
            expiry = __import__("time").time() + int(ttl)
        async with self._lock:
            self._store[key] = (expiry, value)

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            if key in self._store:
                del self._store[key]
