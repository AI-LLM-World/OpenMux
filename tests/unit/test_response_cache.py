import asyncio
import tempfile
from openmux.utils.response_cache import ResponseCache


def test_memory_cache_basic(loop:=None):
    # Create cache
    c = ResponseCache(ttl=1, backend="memory")

    async def _run():
        key = "k1"
        assert await c.get(key) is None
        await c.set(key, "v1")
        assert await c.get(key) == "v1"
        # wait for expiry
        await asyncio.sleep(1.1)
        assert await c.get(key) is None

    asyncio.get_event_loop().run_until_complete(_run())


def test_disk_cache_basic():
    tmpdir = tempfile.TemporaryDirectory()
    c = ResponseCache(ttl=1, backend="disk", path=tmpdir.name)

    async def _run():
        key = c.make_key({"k": "v"})
        assert await c.get(key) is None
        await c.set(key, "disk-value")
        assert await c.get(key) == "disk-value"
        await asyncio.sleep(1.1)
        assert await c.get(key) is None

    asyncio.get_event_loop().run_until_complete(_run())
