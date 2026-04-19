"""Simple pluggable response caching layer.

Supports in-memory and on-disk backends. Redis support is attempted
if the optional `redis` dependency is available, but it's not required.

This cache is intentionally small and dependency-free for MVP. It
provides async `get`/`set` used by the orchestrator's async flows.
"""
from __future__ import annotations

import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Any, Dict
import asyncio
from ..utils.metrics import metrics


def _now() -> float:
    return time.time()


class ResponseCache:
    """A tiny async cache with memory and disk backends.

    Args:
        ttl: default time-to-live in seconds
        backend: one of 'memory'|'disk'|'redis' (redis optional)
        path: base path for disk cache (Path or str)
    """

    def __init__(self, ttl: int = 3600, backend: str = "memory", path: Optional[str] = None):
        self.ttl = int(ttl or 0)
        self.backend = backend or "memory"
        self._lock = asyncio.Lock()

        if self.backend == "memory":
            # key -> (expiry_timestamp, value)
            self._store: Dict[str, tuple[float, str]] = {}

        elif self.backend == "disk":
            base = Path(path) if path else (Path.home() / ".openmux" / "cache")
            base.mkdir(parents=True, exist_ok=True)
            self.base = base

        elif self.backend == "redis":
            # Use redis.asyncio if available. If not available, fall back to memory.
            try:
                import redis.asyncio as redis_async

                self._redis = redis_async.from_url(path or "redis://localhost:6379")
            except Exception:
                # Keep behavior predictable: fallback to memory
                self.backend = "memory"
                self._store = {}

        else:
            # Unknown backend -> fallback to memory
            self.backend = "memory"
            self._store = {}

    # --- Key helpers ---
    @staticmethod
    def make_key(payload: Any) -> str:
        """Create a stable sha256 hex key from a JSON-serializable payload."""
        try:
            js = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        except TypeError:
            # Last resort: stringify and hash
            js = repr(payload)

        return hashlib.sha256(js.encode("utf-8")).hexdigest()

    # --- Async API ---
    async def get(self, key: str) -> Optional[str]:
        """Get cached value for `key` or None if miss/expired."""
        if self.backend == "memory":
            async with self._lock:
                item = self._store.get(key)
                if not item:
                    metrics.incr("cache_miss")
                    return None
                expiry, value = item
                if expiry != 0 and _now() > expiry:
                    # expired
                    del self._store[key]
                    metrics.incr("cache_miss")
                    return None
                metrics.incr("cache_hit")
                return value

        if self.backend == "disk":
            path = self.base / key
            if not path.exists():
                return None
            try:
                with path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                expiry = data.get("expiry", 0)
                if expiry != 0 and _now() > expiry:
                    try:
                        path.unlink()
                    except Exception:
                        pass
                    metrics.incr("cache_miss")
                    return None
                metrics.incr("cache_hit")
                return data.get("value")
            except Exception:
                # On corruption or read error, treat as miss
                try:
                    path.unlink()
                except Exception:
                    pass
                metrics.incr("cache_error")
                return None

        if self.backend == "redis":
            try:
                val = await self._redis.get(key)
                if val is None:
                    metrics.incr("cache_miss")
                    return None
                # redis stores bytes
                if isinstance(val, bytes):
                    metrics.incr("cache_hit")
                    return val.decode("utf-8")
                metrics.incr("cache_hit")
                return str(val)
            except Exception:
                metrics.incr("cache_error")
                return None

        return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """Set cache `key` to `value` with optional TTL (seconds)."""
        expiry = 0
        ttl = int(ttl) if ttl is not None else self.ttl
        if ttl and ttl > 0:
            expiry = _now() + ttl

        if self.backend == "memory":
            async with self._lock:
                self._store[key] = (expiry, value)
            metrics.incr("cache_set")
            return

        if self.backend == "disk":
            path = self.base / key
            tmp = path.with_suffix(".tmp")
            try:
                with tmp.open("w", encoding="utf-8") as fh:
                    json.dump({"expiry": expiry, "value": value}, fh)
                tmp.replace(path)
                metrics.incr("cache_set")
            except Exception:
                try:
                    if tmp.exists():
                        tmp.unlink()
                except Exception:
                    pass
            return

        if self.backend == "redis":
            try:
                if ttl and ttl > 0:
                    await self._redis.set(key, value, ex=ttl)
                else:
                    await self._redis.set(key, value)
                metrics.incr("cache_set")
            except Exception:
                metrics.incr("cache_error")
                # Best-effort
                return

    # testing helper
    async def clear(self) -> None:
        if self.backend == "memory":
            async with self._lock:
                self._store.clear()
            return
        if self.backend == "disk":
            for p in self.base.iterdir():
                try:
                    p.unlink()
                except Exception:
                    pass
            return
        if self.backend == "redis":
            try:
                await self._redis.flushdb()
            except Exception:
                pass
