import asyncio
import sys

sys.path.append('')

from openmux.core.orchestrator import Orchestrator
from openmux.providers.base import BaseProvider
from openmux.classifier.task_types import TaskType


class DummyProvider(BaseProvider):
    def __init__(self):
        super().__init__('dummy')

    def is_available(self):
        return True

    def supports_task(self, t):
        return True

    async def generate(self, prompt, **kwargs):
        return 'ok'

    async def generate_stream(self, prompt, **kwargs):
        # yield a few chunks
        for p in ['chunk1', 'chunk2', 'chunk3']:
            yield p


class DummySelector:
    def __init__(self, provider):
        self._p = provider

    def select_single(self, task_type):
        return self._p


async def main():
    orc = Orchestrator()
    provider = DummyProvider()
    orc.selector = DummySelector(provider)

    collected = []
    async for ch in orc.process_stream('hello world', task_type=TaskType.CHAT):
        collected.append(ch)

    print('collected =', collected)
    print('last provider =', getattr(orc, '_last_stream_provider', None))


if __name__ == '__main__':
    asyncio.run(main())
