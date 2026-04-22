import asyncio
import time
from unittest.mock import MagicMock

from openmux.core.router import Router


async def make_provider(name, delay_before_start=0.01, work_time=0.05):
    async def _gen(prompt, **kwargs):
        # mark start
        starts.append((name, time.time()))
        await asyncio.sleep(work_time)
        return f"resp-{name}"

    p = MagicMock()
    p.name = name
    p.generate = _gen
    return p


async def main():
    global starts
    starts = []

    # Create router limited to 1 concurrent call
    router = Router(max_concurrency=1, timeout=1.0, max_retries=1)

    p1 = await make_provider("p1")
    p2 = await make_provider("p2")

    # Run route_multiple to request both; with concurrency=1 they should start serially
    responses = await router.route_multiple([p1, p2], "q", return_first_n=2)
    print("responses:", responses)
    print("starts:", starts)


if __name__ == '__main__':
    asyncio.run(main())
