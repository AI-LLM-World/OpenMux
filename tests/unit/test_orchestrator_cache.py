import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from openmux.core.orchestrator import Orchestrator
from openmux.utils.response_cache import ResponseCache


def test_orchestrator_uses_cache(monkeypatch):
    orch = Orchestrator()

    # enable in-memory cache on orchestrator
    orch.response_cache = ResponseCache(ttl=60, backend="memory")

    # Pre-populate cache with the same payload the orchestrator uses for keys
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

    # Patch router so that if called it would raise - proving it shouldn't be called
    orch.router.route_with_failover = AsyncMock(side_effect=Exception("should not be called"))

    result = orch.process("hello")
    assert result == "cached-response"
