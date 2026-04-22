"""Adapter wrapper for concrete cache backends.

This module keeps the ResponseCache API used by the rest of the codebase
but delegates to implementations in the `openmux.cache` package.
"""
from __future__ import annotations

from typing import Optional, Any
from ..cache.base import MemoryCache, make_key
from ..cache.disk import DiskCache
from ..cache.redis import RedisCache
from ..utils.metrics import metrics
from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class ResponseCache:
    """Selects a concrete cache implementation and exposes async get/set.

    Args:
        ttl: default TTL in seconds
        backend: 'memory'|'disk'|'redis'
        path: optional path or redis URL
    """

    def __init__(self, ttl: int = 3600, backend: str = "memory", path: Optional[str] = None):
        self.ttl = int(ttl or 0)
        self.backend_name = backend or "memory"

        try:
            if self.backend_name == "memory":
                self._impl = MemoryCache()
            elif self.backend_name == "disk":
                self._impl = DiskCache(path)
            elif self.backend_name == "redis":
                # For redis we prefer to surface errors to the caller so the
                # orchestrator can choose to disable caching rather than
                # silently falling back. RedisCache will raise if redis.asyncio
                # is not available.
                self._impl = RedisCache(path or "redis://localhost:6379")
            else:
                logger.warning(f"Unknown cache backend '{self.backend_name}', falling back to memory")
                self._impl = MemoryCache()
        except Exception as e:
            # If the user explicitly requested redis and initialization
            # failed, surface the error so higher layers can react (and log).
            if self.backend_name == "redis":
                logger.error(f"Failed to initialize redis cache backend: {e}")
                raise

            # For other backends, log and fall back to memory
            logger.warning(f"Cache backend '{self.backend_name}' init failed, falling back to memory: {e}")
            self._impl = MemoryCache()
            self.backend_name = "memory"

    @staticmethod
    def make_key(payload: Any) -> str:
        return make_key(payload)

    async def get(self, key: str) -> Optional[str]:
        try:
            val = await self._impl.get(key)
            if val is None:
                metrics.incr("cache_miss")
            else:
                metrics.incr("cache_hit")
            return val
        except Exception:
            metrics.incr("cache_error")
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        ttl = int(ttl) if ttl is not None else self.ttl
        try:
            await self._impl.set(key, value, ttl)
            metrics.incr("cache_set")
        except Exception:
            metrics.incr("cache_error")

    async def clear(self) -> None:
        # Best-effort clear: attempt memory/disk/redis clears where possible.
        try:
            impl = self._impl
            # MemoryCache exposes _store
            if hasattr(impl, "_store"):
                impl._store.clear()
                return
            if hasattr(impl, "base"):
                for p in impl.base.iterdir():
                    try:
                        p.unlink()
                    except Exception:
                        pass
                return
            # Redis client attribute may be named _client or _redis
            client = getattr(impl, "_client", None) or getattr(impl, "_redis", None)
            if client is not None:
                try:
                    await client.flushdb()
                except Exception:
                    pass
        except Exception:
            pass
