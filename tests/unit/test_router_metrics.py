import asyncio
import time

from unittest.mock import MagicMock

from openmux.core.router import Router
from openmux.utils.metrics import metrics


async def _mk(name, delay):
    async def _gen(prompt, **kwargs):
        await asyncio.sleep(delay)
        return f"resp-{name}"

    p = MagicMock()
    p.name = name
    p.generate = _gen
    return p


def test_nth_fastest_metrics_recorded():
    # Run an async scenario synchronously for test simplicity
    async def _run():
        # Snapshot before
        before_count = metrics.get("multi.nth_fastest_count")
        before_latency = metrics.get("multi.nth_fastest_latency_ms")

        router = Router(max_concurrency=10, timeout=1.0, max_retries=1)

        p1 = await _mk("fast", 0.01)
        p2 = await _mk("slow", 0.05)

        responses = await router.route_multiple([p1, p2], "q", return_first_n=1)

        assert len(responses) == 1

        after_count = metrics.get("multi.nth_fastest_count")
        after_latency = metrics.get("multi.nth_fastest_latency_ms")

        assert after_count == before_count + 1
        assert after_latency >= before_latency + 1

    asyncio.get_event_loop().run_until_complete(_run())
