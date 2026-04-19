import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from openmux.core.router import Router
from openmux.utils.exceptions import APIError


@pytest.mark.asyncio
async def test_router_respects_parsed_retry_after(monkeypatch):
    router = Router(timeout=5.0, max_retries=3)

    # Create a provider that raises APIError with parsed_retry_after=5 on first call,
    # then returns success on the second call.
    provider = MagicMock()
    provider.name = "TestProvider"

    api_err = APIError("TestProvider", status_code=429, response_text="Rate limit", parsed_retry_after=5)
    provider.generate = AsyncMock(side_effect=[api_err, "Success"])

    # Replace asyncio.sleep with a recorder so we don't actually sleep
    sleeps = []

    async def fake_sleep(duration):
        sleeps.append(duration)
        # do not actually sleep
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    result = await router.route_single(provider, "query")

    assert result == "Success"
    # Expect one recorded sleep that is at least the parsed_retry_after value
    assert len(sleeps) >= 1
    assert sleeps[0] == 5
