"""Quick local CI-like checks for cache-related functionality.

Run this script with the repository virtualenv activated (dev extras installed)
to sanity-check the cache implementations and the orchestrator cache path.

This is not a replacement for CI but helps reproduce failing tests locally
when pytest is not available.
"""
import asyncio
import tempfile
import sys


async def _memory_cache_check():
    from openmux.utils.response_cache import ResponseCache

    print("[check] memory cache basic ...", end=" ")
    c = ResponseCache(ttl=1, backend="memory")
    key = "k1"
    assert await c.get(key) is None
    await c.set(key, "v1")
    v = await c.get(key)
    assert v == "v1"
    await asyncio.sleep(1.1)
    assert await c.get(key) is None
    print("OK")


async def _disk_cache_check():
    from openmux.utils.response_cache import ResponseCache

    print("[check] disk cache basic ...", end=" ")
    tmp = tempfile.TemporaryDirectory()
    c = ResponseCache(ttl=1, backend="disk", path=tmp.name)
    key = c.make_key({"k": "v"})
    assert await c.get(key) is None
    await c.set(key, "disk-value")
    assert await c.get(key) == "disk-value"
    await asyncio.sleep(1.1)
    assert await c.get(key) is None
    tmp.cleanup()
    print("OK")


def _orchestrator_cache_check():
    print("[check] orchestrator cache integration ...", end=" ")
    from openmux.core.orchestrator import Orchestrator
    from openmux.utils.response_cache import ResponseCache

    orch = Orchestrator()
    # avoid touching providers
    orch._initialize_selector = lambda: None
    orch._initialize_fallback = lambda: None

    orch.response_cache = ResponseCache(ttl=60, backend="memory")

    cfg = orch.config.load()
    defaults = cfg.get("defaults", {})

    key_payload = {
        "q": "hello",
        "task": "None",
        "temperature": defaults.get("temperature"),
        "top_p": defaults.get("top_p"),
        "max_tokens": defaults.get("max_tokens"),
        "provider_preference": None,
        "system_prompt": None,
        "session_id": None,
    }

    key = orch.response_cache.make_key(key_payload)
    asyncio.get_event_loop().run_until_complete(orch.response_cache.set(key, "cached-response"))

    # If the cache hit works, process should return the cached response and not
    # attempt provider calls.
    result = orch.process("hello")
    assert result == "cached-response"
    print("OK")


def main():
    try:
        asyncio.run(_memory_cache_check())
        asyncio.run(_disk_cache_check())
        _orchestrator_cache_check()
    except AssertionError as e:
        print("FAILED", e)
        sys.exit(2)
    except Exception as e:
        print("ERROR", e)
        sys.exit(3)

    print("All quick checks passed.")


if __name__ == "__main__":
    main()
