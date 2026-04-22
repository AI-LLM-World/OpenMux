"""Benchmarks for different cache backends: memory, disk, and redis.

These benchmarks are lightweight and aimed at comparing basic get/set
latency for the three provided cache implementations. Redis benchmarks
will be skipped if redis.asyncio is not installed or a server isn't
reachable at the configured URL.
"""
import os
import tempfile
import asyncio
import pytest

from openmux.cache.base import MemoryCache, make_key
from openmux.cache.disk import DiskCache


def _run_sync(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def benchmark_cache_set_get(benchmark, cache_impl_factory):
    """Helper to benchmark a simple set/get cycle for a cache impl factory."""

    async def _bench():
        cache = cache_impl_factory()
        key = make_key({"k": "v"})
        await cache.set(key, "value", ttl=5)
        return await cache.get(key)

    result = benchmark(lambda: _run_sync(_bench()))
    assert result is not None


def test_memory_cache_benchmark(benchmark):
    benchmark_cache_set_get(benchmark, lambda: MemoryCache())


def test_disk_cache_benchmark(benchmark):
    tmp = tempfile.TemporaryDirectory()
    benchmark_cache_set_get(benchmark, lambda: DiskCache(tmp.name))


def test_redis_cache_benchmark(benchmark):
    # Skip if redis.asyncio not installed
    pytest.importorskip("redis.asyncio")

    from openmux.cache.redis import RedisCache

    url = os.getenv("OPENMUX_TEST_REDIS_URL", "redis://localhost:6379")

    async def _bench():
        cache = RedisCache(url)
        # ensure server reachable
        try:
            await cache._client.ping()
        except Exception:
            pytest.skip(f"Redis server not available at {url}")

        key = make_key({"k": "v"})
        await cache.set(key, "value", ttl=5)
        return await cache.get(key)

    result = benchmark(lambda: asyncio.get_event_loop().run_until_complete(_bench()))
    assert result is not None
