import asyncio
import pytest

from openmux.cache.redis import RedisCache


@pytest.mark.asyncio
async def test_redis_cache_basic():
    """Basic get/set/invalidate behaviour for RedisCache.

    This test will be skipped if the redis.asyncio package is not
    available or if a Redis server is not reachable at the default
    URL (redis://localhost:6379). The test is best-effort and will
    not fail the suite when Redis isn't present.
    """
    # Skip if redis.asyncio isn't installed
    pytest.importorskip("redis.asyncio")

    url = "redis://localhost:6379"
    rc = None
    key = "test_redis_cache_basic:key"

    try:
        # Instantiation will raise if redis.asyncio isn't importable; we
        # already guarded for that above, but connection may still fail.
        rc = RedisCache(url)

        # Ensure Redis is reachable; skip test if ping fails.
        try:
            await rc._client.ping()
        except Exception:
            pytest.skip(f"Redis server not available at {url}")

        # Clean slate
        try:
            await rc._client.flushdb()
        except Exception:
            pass

        assert await rc.get(key) is None
        await rc.set(key, "v1", ttl=1)
        assert await rc.get(key) == "v1"

        # allow expiry
        await asyncio.sleep(1.1)
        assert await rc.get(key) is None

    finally:
        # Best-effort cleanup
        if rc is not None:
            try:
                await rc.invalidate(key)
            except Exception:
                pass
