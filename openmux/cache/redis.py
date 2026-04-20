"""Redis-backed cache implementation (optional dependency).

If redis.asyncio is not available or connecting fails, instantiation should
raise so callers can fall back to another backend.
"""
from __future__ import annotations

from typing import Optional
from .base import BaseCache


class RedisCache(BaseCache):
    def __init__(self, url: str = "redis://localhost:6379"):
        try:
            import redis.asyncio as redis_async
        except Exception as e:
            raise RuntimeError("redis.asyncio is required for RedisCache") from e

        self._client = redis_async.from_url(url)

    async def get(self, key: str) -> Optional[str]:
        val = await self._client.get(key)
        if val is None:
            return None
        if isinstance(val, bytes):
            return val.decode("utf-8")
        return str(val)

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        if ttl and ttl > 0:
            await self._client.set(key, value, ex=ttl)
        else:
            await self._client.set(key, value)

    async def invalidate(self, key: str) -> None:
        await self._client.delete(key)
