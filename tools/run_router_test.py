import asyncio
from openmux.core.router import Router
from unittest.mock import MagicMock, AsyncMock


async def gen1(prompt, **kwargs):
    await asyncio.sleep(0.01)
    return "r1"


async def gen2(prompt, **kwargs):
    await asyncio.sleep(0.02)
    return "r2"


async def gen3(prompt, **kwargs):
    await asyncio.sleep(0.05)
    return "r3"


async def main():
    router = Router(timeout=1.0, max_retries=1)

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
    print(responses)


if __name__ == '__main__':
    asyncio.run(main())
