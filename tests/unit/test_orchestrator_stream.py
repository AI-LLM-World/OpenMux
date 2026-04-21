"""Unit tests for Orchestrator streaming behaviour."""
import asyncio

from openmux.core.orchestrator import Orchestrator
from openmux.classifier.task_types import TaskType


class DummyProvider:
    def __init__(self):
        self.name = "dummy"

    async def generate_stream(self, prompt, task_type=None, **kwargs):
        # simple async generator
        yield "one"
        yield "two"


class DummySelector:
    def __init__(self, provider):
        self._p = provider

    def select_single(self, task_type):
        return self._p


def test_process_stream_yields_chunks_and_sets_provider():
    orch = Orchestrator()

    # Inject dummy selector/provider
    provider = DummyProvider()
    orch.selector = DummySelector(provider)

    async def collect():
        collected = []
        async for chunk in orch.process_stream("hello", task_type=TaskType.CHAT):
            collected.append(chunk)
        return collected

    chunks = asyncio.run(collect())

    assert chunks == ["one", "two"]
    # provider name should be recorded for attribution
    assert getattr(orch, "_last_stream_provider", None) == "dummy"
