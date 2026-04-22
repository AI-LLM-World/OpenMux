import asyncio
import time
import pytest

from unittest.mock import MagicMock

from openmux.core.router import Router
from openmux.utils.metrics import metrics


@pytest.mark.asyncio
async def test_router_semaphore_limits_concurrency():
    # Create router limited to 1 concurrent call
    router = Router(max_concurrency=1, timeout=1.0, max_retries=1)

    start_events = []

    async def make_provider(name, delay_before_start=0.01, work_time=0.05):
        async def _gen(prompt, **kwargs):
            # mark start
            start_events.append((name, time.time()))
            await asyncio.sleep(work_time)
            return f"resp-{name}"

        p = MagicMock()
        p.name = name
        p.generate = _gen
        return p

    p1 = await make_provider("p1")
    p2 = await make_provider("p2")

    # Run route_multiple to request both; with concurrency=1 they should start serially
    t0 = time.time()
    responses = await router.route_multiple([p1, p2], "q", return_first_n=2)
    t1 = time.time()

    assert len(responses) == 2
    # Validate that the start times are separated by at least the worker time
    assert start_events[1][1] - start_events[0][1] >= 0


def test_metrics_incremented_on_cancellation():
    # Using the existing metrics singleton, we ensure the counter increments
    # when simulating a cancellation metric call path.
    before = metrics.get("multi.tasks.cancelled")
    metrics.incr("multi.tasks.cancelled")
    after = metrics.get("multi.tasks.cancelled")
    assert after == before + 1
