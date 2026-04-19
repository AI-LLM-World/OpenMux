import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from openmux.core.router import Router


@pytest.mark.asyncio
async def test_route_multiple_return_first_n_returns_first_n_successes():
    router = Router(timeout=1.0, max_retries=1)

    async def gen1(prompt, **kwargs):
        await asyncio.sleep(0.01)
        return "r1"

    async def gen2(prompt, **kwargs):
        await asyncio.sleep(0.02)
        return "r2"

    async def gen3(prompt, **kwargs):
        # slower provider
        await asyncio.sleep(0.05)
        return "r3"

    p1 = MagicMock()
    p1.name = "p1"
    p1.generate = AsyncMock(side_effect=gen1)

    p2 = MagicMock()
    p2.name = "p2"
    p2.generate = AsyncMock(side_effect=gen2)

    p3 = MagicMock()
    p3.name = "p3"
    p3.generate = AsyncMock(side_effect=gen3)

    responses = await router.route_multiple([p1, p2, p3], "query", return_first_n=2)

    assert len(responses) == 2
    assert "r1" in responses and "r2" in responses


@pytest.mark.asyncio
async def test_route_multiple_handles_exceptions_and_returns_successes():
    router = Router(timeout=1.0, max_retries=1)

    async def gen_err(prompt, **kwargs):
        await asyncio.sleep(0.01)
        raise Exception("fail")

    async def gen_ok(prompt, **kwargs):
        await asyncio.sleep(0.01)
        return "ok"

    p1 = MagicMock()
    p1.name = "p1"
    p1.generate = AsyncMock(side_effect=gen_err)

    p2 = MagicMock()
    p2.name = "p2"
    p2.generate = AsyncMock(side_effect=gen_ok)

    responses = await router.route_multiple([p1, p2], "query", return_first_n=1)

    assert responses == ["ok"]
